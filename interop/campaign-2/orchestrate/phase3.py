"""Phase 3 — live two-direction HTTP/CBOR state exchange (v0.9.2-r2).

Direction R: the frozen Rust participant's production `relay serve`
binary serves the relay profile over real loopback HTTP; the frozen
Motoko participant acts as client/producer/receiver through its own
production `RelayClient`/ingress modules behind its own loopback shim
(byte transport only, driven by the coordinator bridge).

Direction M: the frozen Motoko participant serves the complete relay
HTTP profile through its own production `RelayHttp`/`RelayServe`
modules behind its own loopback shim; the frozen Rust participant acts
as client/producer/receiver through its production CLI surfaces
(`relay publish`, `relay resolve`, `relay changes`, `relay sync`,
`resolve`).

Hostile-peer material (published Appendix B.11 bytes and the
constructed `info-missing-version` / `info-missing-suite` /
`directory-duplicate-index` responses) is served by a coordinator
fixture server to each side's production client paths — mandatorily,
per ACCEPTANCE.md step 6.

Comparisons follow NONDETERMINISM.md: relay-chosen opaque values are
never byte-compared and never normalized away; pinned protocol bytes
are compared exactly; the publish status-1 reason-code choice is
compared against the enumerated conforming set and reported as
permitted diagnostic variation. Every raw exchange is preserved.
"""

from __future__ import annotations

import http.server
import json
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interop_common as ic
from gates import (
    ALICE,
    NOW_ADMISSIBLE,
    MotokoBridge,
    RustRelay,
    build_clockshim,
    cbor,
    changes_request,
    contains_bytes,
    find_cursor,
    fresh_db,
    http_request,
    load_transcript,
    materialize_gate_driver,
)

BOB = "did:flw:zQmdGJbJu6pBbiyZX9gJHBTFxnUCtBgRa7mZRcKKs1TcFEy"
MALFORMED_DID = "did:flw:not-a-multibase"

# The sealed challenge inputs carry timestamps around 1790000000000 —
# in the future of both the wall clock and the published B.11.5
# recipient clock — so the challenge-crossing scenario runs the serving
# relay and the verifying clients at the challenge file's own
# `verifyNowMs` (the clock the challenge protocol itself prescribes).
CHALLENGE_NOW = int(
    json.loads(
        (
            Path(__file__).resolve().parent.parent.parent
            / "v0.9.2" / "authoring" / "vectors" / "challenge" / "challenge-records.json"
        ).read_text()
    )["verifyNowMs"]
)

CHECKS: list[dict] = []
EXCHANGES: list[dict] = []


def check(section: str, label: str, condition: bool, detail=None) -> None:
    entry = {"section": section, "label": label, "ok": bool(condition)}
    if detail is not None and not condition:
        entry["detail"] = detail
    CHECKS.append(entry)


def record(direction: str, operation: str, scenario: str, **kw) -> None:
    EXCHANGES.append({"direction": direction, "operation": operation, "scenario": scenario, **kw})


class FixtureServer:
    """Serves coordinator-configured bytes (published hostile-peer
    material and scenario responses) to a production client under test.
    Transport only; routes are (method, path) -> (status, contentType,
    bytes)."""

    def __init__(self):
        fixture = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _serve(self):
                length = int(self.headers.get("content-length") or 0)
                request_body = self.rfile.read(length) if length else b""
                fixture.hits.append(
                    {"method": self.command, "path": self.path, "requestHex": request_body.hex()}
                )
                route = fixture.routes.get((self.command, self.path))
                if route is None:
                    self.send_response(404)
                    self.send_header("content-length", "0")
                    self.end_headers()
                    return
                status, ctype, body = route
                self.send_response(status)
                if ctype:
                    self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = _serve
            do_POST = _serve

            def log_message(self, *args):
                pass

        self.routes: dict = {}
        self.hits: list = []
        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_port
        self.base = f"http://127.0.0.1:{self.port}/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def rust_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(ic.RUST_BIN), *args], capture_output=True, text=True, timeout=300
    )


def motoko_publish(bridge: MotokoBridge, port: int, envelope_hex: str) -> dict:
    return bridge.cmd(
        {
            "op": "client",
            "port": port,
            "statement": f'RelayNode.buildPublish(node, __ID__, "{envelope_hex}");',
        }
    )


def motoko_resolve(bridge: MotokoBridge, port: int, dids: list[str]) -> dict:
    csv = ",".join(dids)
    return bridge.cmd(
        {
            "op": "client",
            "port": port,
            "statement": f'RelayNode.buildResolve(node, __ID__, "{csv}");',
        }
    )


def motoko_changes(bridge: MotokoBridge, port: int, item_limit=100, byte_limit=1048576) -> dict:
    return bridge.cmd(
        {
            "op": "client",
            "port": port,
            "statement": f"RelayNode.buildChanges(node, __ID__, {item_limit}, {byte_limit});",
        }
    )


def motoko_cursor(bridge: MotokoBridge) -> str:
    probe = bridge.cmd({"op": "probe"})["probe"]
    return probe.split("peerCursor=")[1].strip()


def load_material(vectors: ic.ExpectedVectors) -> dict:
    records = vectors.by_case["records"]
    m = {
        "b4": records["b4-root"]["expected"]["envelopeHex"],
        "b5": records["b5-root-revoked"]["expected"]["envelopeHex"],
        "b6a": records["b6-alice-a"]["expected"]["envelopeHex"],
        "b6b": records["b6-alice-b"]["expected"]["envelopeHex"],
        "b9": records["b9-bob-root"]["expected"]["envelopeHex"],
        "b4Digest": records["b4-root"]["expected"]["recordBodyDigestHex"],
        "b5Digest": records["b5-root-revoked"]["expected"]["recordBodyDigestHex"],
        "b9Digest": records["b9-bob-root"]["expected"]["recordBodyDigestHex"],
        "b8": vectors.envelope_hex(
            {"vector": "envelopes-negative", "case": "b8-descriptor-substitution"}
        ),
    }
    transcripts = {
        name: load_transcript(name)
        for name in (
            "publish-admit",
            "publish-no-change",
            "publish-no-change-diagnostic",
            "publish-losing-record",
            "publish-rejected",
            "info-missing-version",
            "info-missing-suite",
            "directory-duplicate-index",
            "info",
        )
    }
    m["publishAdmit"] = transcripts["publish-admit"]["response"]["bodyHex"]
    m["noChangeBare"] = transcripts["publish-no-change"]["response"]["bodyHex"]
    m["noChangeCoded"] = transcripts["publish-no-change-diagnostic"]["response"]["bodyHex"]
    m["losingCoded"] = transcripts["publish-losing-record"]["response"]["bodyHex"]
    m["losingBare"] = m["noChangeBare"]  # enumerated bare member of the losing group
    m["publishRejected"] = transcripts["publish-rejected"]["response"]["bodyHex"]
    m["infoMissingVersion"] = transcripts["info-missing-version"]["response"]["bodyHex"]
    m["infoMissingSuite"] = transcripts["info-missing-suite"]["response"]["bodyHex"]
    m["directoryDuplicateIndex"] = transcripts["directory-duplicate-index"]["response"]["bodyHex"]
    m["infoExample"] = transcripts["info"]["response"]["bodyHex"]

    wire = vectors.by_case["wire-b11"]
    m["b11_1_request"] = wire["b11-1-invalid-outer-request"]["requestBytesHex"]
    m["b11_2_response"] = wire["b11-2-invalid-outer-response"]["responseBytesHex"]
    m["b11_5_response"] = wire["b11-5-changes-isolation-cursor"]["responseBytesHex"]
    m["b11_5_post"] = wire["b11-5-changes-isolation-cursor"]["requiredPostState"]
    m["b11_7_request"] = wire["b11-7-changes-item-limit-overflow"]["requestBytesHex"]
    m["b11_7_response"] = wire["b11-7-changes-item-limit-overflow"]["responseBytesHex"]
    return m


def motoko_challenge_material() -> dict:
    """The Motoko participant's own frozen authored challenge material
    (used for direction R crossing: state authored by Motoko crosses
    the wire to Rust)."""
    lines = [
        json.loads(line)
        for line in (
            ic.MOTOKO_REPO / "outputs" / "v0.9.2-r2" / "challenge-results.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]
    by_id = {r["caseId"]: r for r in lines}
    return by_id


def rust_challenge_material() -> dict:
    by_id = {}
    for group in ("challenge-identities", "challenge-records"):
        for line in (
            ic.RUST_REPO / "interop" / "v0.9.2" / "outputs" / f"{group}.responses.ndjson"
        ).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                by_id[r["caseId"]] = r
    return by_id


CROSSING_CASES = [
    ("challenge-carol-root-full", "carol"),
    ("challenge-dave-continues", "dave"),
    ("challenge-erin-revoked-empty", "erin"),
]


# ---------------------------------------------------------------------------
# Direction R — Rust serves, Motoko is client/producer/receiver
# ---------------------------------------------------------------------------


def direction_r(m: dict, motoko_by_id: dict) -> None:
    S = "R"
    db = fresh_db(ic.WORK_DIR / "phase3" / "r-main.sqlite")
    relay = RustRelay(db)
    port = int(relay.base_uri.rsplit(":", 1)[1].rstrip("/"))
    bridge = MotokoBridge()
    try:
        # 1. info — structure validated by the Motoko production client.
        status, ctype, body = http_request(relay.base_uri, "GET", "v1/info", None, "")
        check(S, "info is 200 application/cbor", status == 200 and ctype == "application/cbor", (status, ctype))
        record("rust-serves", "v1/info", "read", status=status, contentType=ctype, responseHex=body.hex())
        result = bridge.cmd({"op": "client", "port": port, "statement": "RelayNode.buildInfo(node, __ID__);"})
        check(S, "Motoko client accepts Rust info", result["outcome"].startswith("info accepted"), result["outcome"])
        record("rust-serves", "v1/info", "motoko-client-validation", clientOutcome=result["outcome"])

        # 2. directory — validated by the Motoko production client.
        status, ctype, body = http_request(relay.base_uri, "GET", "v1/directory", None, "")
        check(S, "directory is 200 application/cbor", status == 200 and ctype == "application/cbor", (status, ctype))
        record("rust-serves", "v1/directory", "read", status=status, contentType=ctype, responseHex=body.hex())
        result = bridge.cmd({"op": "client", "port": port, "statement": "RelayNode.buildDirectory(node, __ID__);"})
        check(S, "Motoko client accepts Rust directory", result["outcome"].startswith("directory accepted"), result["outcome"])
        record("rust-serves", "v1/directory", "motoko-client-validation", clientOutcome=result["outcome"])

        # 3. publish sequence through the Motoko production client.
        result = motoko_publish(bridge, port, m["b4"])
        check(S, "B.4 admitted (exact publish-admit bytes)", result["outcome"] == "publish admitted" and result["raw"]["bodyHex"] == m["publishAdmit"], result)
        record("rust-serves", "v1/publish", "b4-admit", clientOutcome=result["outcome"], status=result["raw"]["status"], responseHex=result["raw"]["bodyHex"])

        result = motoko_publish(bridge, port, m["b4"])
        check(
            S,
            "B.4 republish: status-1 in the enumerated set, accepted by the Motoko client",
            result["raw"]["bodyHex"] in (m["noChangeBare"], m["noChangeCoded"])
            and result["outcome"] in ("publish noChange bare", "publish noChange duplicate"),
            result,
        )
        record("rust-serves", "v1/publish", "b4-republish-status-1", clientOutcome=result["outcome"], status=result["raw"]["status"], responseHex=result["raw"]["bodyHex"], variation="permitted-diagnostic-variation: Rust emits the bare form")

        result = motoko_publish(bridge, port, m["b8"])
        check(
            S,
            "B.8 rejected identityBindingMismatch under HTTP 200 (exact publish-rejected bytes)",
            result["raw"]["status"] == 200
            and result["raw"]["bodyHex"] == m["publishRejected"]
            and result["outcome"] == "publish rejected identityBindingMismatch",
            result,
        )
        record("rust-serves", "v1/publish", "b8-rejected", clientOutcome=result["outcome"], status=result["raw"]["status"], responseHex=result["raw"]["bodyHex"])

        result = motoko_publish(bridge, port, m["b9"])
        check(S, "B.9 admitted", result["outcome"] == "publish admitted" and result["raw"]["bodyHex"] == m["publishAdmit"], result)
        record("rust-serves", "v1/publish", "b9-admit", clientOutcome=result["outcome"], status=result["raw"]["status"], responseHex=result["raw"]["bodyHex"])

        # Losing record on a dedicated relay (transcript scenario:
        # current = B.6 Alice A; publish the equal-timestamp
        # higher-digest B.6 Alice B).
        db_l = fresh_db(ic.WORK_DIR / "phase3" / "r-losing.sqlite")
        relay_l = RustRelay(db_l)
        port_l = int(relay_l.base_uri.rsplit(":", 1)[1].rstrip("/"))
        result = motoko_publish(bridge, port_l, m["b6a"])
        check(S, "B.6 Alice A admitted on the losing-scenario relay", result["outcome"] == "publish admitted", result["outcome"])
        result = motoko_publish(bridge, port_l, m["b6b"])
        check(
            S,
            "losing record: status-1 in the enumerated losing set, accepted by the Motoko client",
            result["raw"]["bodyHex"] in (m["losingBare"], m["losingCoded"])
            and result["outcome"] in ("publish noChange bare", "publish noChange losingRecord"),
            result,
        )
        record("rust-serves", "v1/publish", "b6b-losing-status-1", clientOutcome=result["outcome"], status=result["raw"]["status"], responseHex=result["raw"]["bodyHex"], variation="permitted-diagnostic-variation: Rust emits the bare form")
        relay_l.stop()

        # 4. resolve — duplicates, malformed DID, full local verification.
        result = motoko_resolve(bridge, port, [ALICE, ALICE, BOB])
        expected_outcome = (
            f"resolve accepted verified:{m['b4Digest']} verified:{m['b4Digest']} verified:{m['b9Digest']}"
        )
        check(S, "resolve [alice,alice,bob]: aligned, every Full candidate verified by Motoko", result["outcome"] == expected_outcome, result["outcome"])
        record("rust-serves", "v1/resolve", "duplicate-dids", clientOutcome=result["outcome"], status=result["raw"]["status"], responseHex=result["raw"]["bodyHex"])

        result = motoko_resolve(bridge, port, [ALICE, MALFORMED_DID, BOB])
        check(
            S,
            "resolve with malformed DID: positionally aligned error 0 (invalidDid)",
            result["outcome"]
            == f"resolve accepted verified:{m['b4Digest']} error:0 verified:{m['b9Digest']}",
            result["outcome"],
        )
        record("rust-serves", "v1/resolve", "malformed-did-in-batch", clientOutcome=result["outcome"], status=result["raw"]["status"], responseHex=result["raw"]["bodyHex"])

        # 5. changes — initial enumeration, revocation propagation,
        # exactly-once visibility, cursor storage.
        result = motoko_changes(bridge, port)
        check(S, "initial null-cursor enumeration admits both records through Motoko ingress", result["outcome"].startswith("changes processed admitted:1 admitted:2 cursor="), result["outcome"])
        record("rust-serves", "v1/changes", "initial-enumeration", clientOutcome=result["outcome"], responseHex=result["raw"]["bodyHex"])
        cursor_1 = result["outcome"].split("cursor=")[1]
        check(S, "returned cursor stored exactly", motoko_cursor(bridge) == cursor_1, motoko_cursor(bridge))

        result = motoko_publish(bridge, port, m["b5"])
        check(S, "B.5 revocation admitted", result["outcome"] == "publish admitted", result["outcome"])
        record("rust-serves", "v1/publish", "b5-revocation-admit", clientOutcome=result["outcome"], responseHex=result["raw"]["bodyHex"])

        result = motoko_changes(bridge, port)
        check(S, "incremental pull sees the revocation exactly once", result["outcome"].startswith("changes processed admitted:3 cursor="), result["outcome"])
        record("rust-serves", "v1/changes", "incremental-revocation", clientOutcome=result["outcome"], responseHex=result["raw"]["bodyHex"])
        cursor_2 = result["outcome"].split("cursor=")[1]
        check(S, "cursor advanced", cursor_2 != cursor_1)

        result = motoko_changes(bridge, port)
        check(S, "second incremental pull is empty (exactly-once visibility)", result["outcome"] == f"changes processed cursor={motoko_cursor(bridge)}", result["outcome"])

        # Final agreement: Motoko re-resolves and verifies the winners.
        result = motoko_resolve(bridge, port, [ALICE, BOB])
        check(
            S,
            "final state agreement: alice=B.5 (rootRevoked), bob=B.9",
            result["outcome"]
            == f"resolve accepted verified:{m['b5Digest']} verified:{m['b9Digest']}",
            result["outcome"],
        )
        record("rust-serves", "v1/resolve", "final-agreement", clientOutcome=result["outcome"], responseHex=result["raw"]["bodyHex"])

        # Pagination with itemLimit 1 through a fresh Motoko receiver.
        bridge2 = MotokoBridge()
        try:
            pages = []
            for _ in range(5):
                result = motoko_changes(bridge2, port, item_limit=1)
                pages.append(result["outcome"])
                if "admitted:" not in result["outcome"]:
                    break
            admissions = [p for p in pages if "admitted:" in p]
            check(
                S,
                "itemLimit-1 pagination walks each record exactly once",
                len(admissions) == 2
                and all(p.count("admitted:") == 1 for p in admissions),
                pages,
            )
            record("rust-serves", "v1/changes", "item-limit-1-pagination", pages=pages)
        finally:
            bridge2.stop()

        # 6. hostile request to the serving side: published B.11.1
        # invalid outer request bytes.
        status, ctype, body = http_request(relay.base_uri, "POST", "v1/resolve", bytes.fromhex(m["b11_1_request"]), "application/cbor")
        check(S, "B.11.1 invalid outer request is HTTP 400 with no per-item body", status == 400 and body == b"", (status, body.hex()))
        record("rust-serves", "v1/resolve", "b11-1-hostile-request", status=status, responseHex=body.hex())

        # 7. challenge records authored by Motoko cross the wire to Rust
        # (admission = Rust production ingress verification at the
        # challenge clock), are served back verbatim, and are verified
        # by the Motoko production interface engine at `verifyNowMs`.
        cross_db = fresh_db(ic.WORK_DIR / "phase3" / "r-crossing.sqlite")
        relay_c = RustRelay(cross_db, scenario_now_ms=CHALLENGE_NOW)
        port_c = int(relay_c.base_uri.rsplit(":", 1)[1].rstrip("/"))
        crossing = []
        for case_id, ref in CROSSING_CASES:
            envelope = motoko_by_id[case_id]["result"]["envelopeHex"]
            did = motoko_by_id[f"challenge-identity-{ref}"]["result"]["did"]
            digest = motoko_by_id[case_id]["result"]["recordBodyDigestHex"]
            crossing.append((case_id, did, digest, envelope))
            result = motoko_publish(bridge, port_c, envelope)
            check(S, f"Motoko-authored {case_id} admitted by Rust ingress", result["outcome"] == "publish admitted", result["outcome"])
            record("rust-serves", "v1/publish", f"crossing-{case_id}", clientOutcome=result["outcome"], responseHex=result["raw"]["bodyHex"])
        resolve_request = cbor.encode({0: 1, 1: [did for _, did, _, _ in crossing]})
        _, _, view = http_request(relay_c.base_uri, "POST", "v1/resolve", resolve_request, "application/cbor")
        items = cbor.decode_strict(view)[2]
        served = [item.get(1) for item in items]
        check(
            S,
            "Rust serves the crossed records back byte-for-byte",
            served == [bytes.fromhex(env) for _, _, _, env in crossing],
            view.hex()[:120],
        )
        record("rust-serves", "v1/resolve", "crossing-served-bytes", responseHex=view.hex())
        lines = [
            ic.request_line(
                f"{case_id}/wire-cross",
                "verifyRecord",
                {"targetDid": did, "envelopeHex": env, "nowMs": str(CHALLENGE_NOW)},
            )
            for case_id, did, _, env in crossing
        ]
        verified = ic.run_motoko(lines)
        check(
            S,
            "crossed challenge records verify through the Motoko production interface",
            all(
                v["status"] == "accepted"
                and v["result"]["recordBodyDigestHex"] == digest
                and v["result"]["premature"] is False
                for v, (_, _, digest, _) in zip(verified, crossing)
            ),
            [v.get("status") for v in verified],
        )
        record("rust-serves", "verifyRecord", "crossing-verification-motoko-interface", outcomes=[v.get("status") for v in verified])
        relay_c.stop()
    finally:
        bridge.stop()
        relay.stop()


# ---------------------------------------------------------------------------
# Direction M — Motoko serves, Rust is client/producer/receiver
# ---------------------------------------------------------------------------


def direction_m(m: dict, rust_by_id: dict) -> None:
    S = "M"
    bridge = MotokoBridge()
    PORT = 42931
    try:
        bridge.cmd({"op": "serve", "port": PORT})
        base = f"http://127.0.0.1:{PORT}/"
        work = ic.WORK_DIR / "phase3"
        work.mkdir(parents=True, exist_ok=True)

        def envelope_file(name: str, envelope_hex: str) -> Path:
            path = work / name
            path.write_bytes(bytes.fromhex(envelope_hex))
            return path

        # 1. info/transport classification (served by the participant's
        # own shim; production handler decides everything).
        status, ctype, body = http_request(base, "GET", "v1/info", None, "")
        check(S, "info is 200 application/cbor", status == 200 and ctype == "application/cbor", (status, ctype))
        record("motoko-serves", "v1/info", "read", status=status, contentType=ctype, responseHex=body.hex())
        status, ctype, body = http_request(base, "GET", "v1/directory", None, "")
        check(S, "directory is 200 application/cbor", status == 200 and ctype == "application/cbor", (status, ctype))
        record("motoko-serves", "v1/directory", "read", status=status, contentType=ctype, responseHex=body.hex())

        # 2. publish sequence through the Rust production client.
        b4_file = envelope_file("b4.cose", m["b4"])
        publish = rust_cli("relay", "publish", "--relay", base, "--record", str(b4_file), "--policy", "development")
        check(S, "B.4 admitted via Rust client", publish.returncode == 0 and json.loads(publish.stdout)["status"] == "admitted", publish.stdout)
        record("motoko-serves", "v1/publish", "b4-admit", clientOutcome=publish.stdout.strip())

        publish = rust_cli("relay", "publish", "--relay", base, "--record", str(b4_file), "--policy", "development")
        out = json.loads(publish.stdout) if publish.returncode == 0 else {}
        check(
            S,
            "B.4 republish: Rust client accepts the coded duplicate form",
            publish.returncode == 0 and out.get("status") == "noChange" and out.get("reason") == "duplicate",
            publish.stdout,
        )
        # Raw byte comparison of the coded form against the enumerated set.
        status, _, body = http_request(base, "POST", "v1/publish", bytes.fromhex(m["b4"]), "application/cose")
        check(S, "republish bytes are the enumerated coded duplicate form", body.hex() == m["noChangeCoded"], body.hex())
        record("motoko-serves", "v1/publish", "b4-republish-status-1", clientOutcome=publish.stdout.strip(), responseHex=body.hex(), variation="permitted-diagnostic-variation: Motoko emits the coded form")

        b8_file = envelope_file("b8.cose", m["b8"])
        publish = rust_cli("relay", "publish", "--relay", base, "--record", str(b8_file), "--policy", "development")
        check(
            S,
            "B.8 rejected identityBindingMismatch via Rust client",
            publish.returncode != 0 and "identityBindingMismatch" in publish.stdout + publish.stderr,
            (publish.stdout + publish.stderr)[:200],
        )
        status, _, body = http_request(base, "POST", "v1/publish", bytes.fromhex(m["b8"]), "application/cose")
        check(S, "B.8 rejection bytes exact under HTTP 200", status == 200 and body.hex() == m["publishRejected"], (status, body.hex()))
        record("motoko-serves", "v1/publish", "b8-rejected", clientOutcome=(publish.stdout + publish.stderr).strip()[:300], status=status, responseHex=body.hex())

        b9_file = envelope_file("b9.cose", m["b9"])
        publish = rust_cli("relay", "publish", "--relay", base, "--record", str(b9_file), "--policy", "development")
        check(S, "B.9 admitted via Rust client", publish.returncode == 0 and json.loads(publish.stdout)["status"] == "admitted", publish.stdout)
        record("motoko-serves", "v1/publish", "b9-admit", clientOutcome=publish.stdout.strip())

        # Losing scenario on a dedicated gate instance of the production
        # handler (transcript: current = B.6 Alice A, publish Alice B).
        bridge.cmd({"op": "gateInit", "name": "gateLose", "genStart": 0x58})
        LOSE_PORT = 42932
        bridge.cmd({"op": "gateServe", "name": "gateLose", "port": LOSE_PORT, "nowMs": NOW_ADMISSIBLE})
        lose_base = f"http://127.0.0.1:{LOSE_PORT}/"
        status, _, body = http_request(lose_base, "POST", "v1/publish", bytes.fromhex(m["b6a"]), "application/cose")
        check(S, "B.6 Alice A admitted on the losing-scenario instance", body.hex() == m["publishAdmit"], body.hex())
        b6b_file = envelope_file("b6b.cose", m["b6b"])
        publish = rust_cli("relay", "publish", "--relay", lose_base, "--record", str(b6b_file), "--policy", "development")
        out = json.loads(publish.stdout) if publish.returncode == 0 else {}
        check(
            S,
            "losing record: Rust client accepts the coded losingRecord form",
            publish.returncode == 0 and out.get("status") == "noChange" and out.get("reason") == "losingRecord",
            publish.stdout,
        )
        status, _, body = http_request(lose_base, "POST", "v1/publish", bytes.fromhex(m["b6b"]), "application/cose")
        check(S, "losing bytes are the enumerated coded losingRecord form", body.hex() == m["losingCoded"], body.hex())
        record("motoko-serves", "v1/publish", "b6b-losing-status-1", clientOutcome=publish.stdout.strip(), responseHex=body.hex(), variation="permitted-diagnostic-variation: Motoko emits the coded form")

        # 3. resolve through the Rust production client.
        resolve = rust_cli("relay", "resolve", "--relay", base, "--did", ALICE, "--did", ALICE, "--did", BOB, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE))
        out = json.loads(resolve.stdout)
        results = out["results"]
        check(
            S,
            "resolve [alice,alice,bob]: aligned, every Full candidate verified by Rust",
            [r["kind"] for r in results] == ["full", "full", "full"]
            and [r["bodyDigest"] for r in results] == [m["b4Digest"], m["b4Digest"], m["b9Digest"]],
            resolve.stdout[:300],
        )
        record("motoko-serves", "v1/resolve", "duplicate-dids", clientOutcome=resolve.stdout.strip()[:2000])

        resolve = rust_cli("relay", "resolve", "--relay", base, "--did", ALICE, "--did", MALFORMED_DID, "--did", BOB, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE))
        out = json.loads(resolve.stdout)
        results = out["results"]
        check(
            S,
            "resolve with malformed DID: positionally aligned invalidDid error",
            len(results) == 3
            and results[0]["kind"] == "full"
            and results[2]["kind"] == "full"
            and results[1]["kind"] == "error"
            and "invalidDid" in json.dumps(results[1]),
            resolve.stdout[:300],
        )
        record("motoko-serves", "v1/resolve", "malformed-did-in-batch", clientOutcome=resolve.stdout.strip()[:2000])

        # 4. changes/sync through the Rust production receiver.
        sync_db = fresh_db(work / "m-sync.sqlite")
        sync = rust_cli("relay", "sync", "--database", str(sync_db), "--peer", base, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "10")
        out = json.loads(sync.stdout)
        check(
            S,
            "initial sync admits both records through Rust ingress and stores the exact cursor",
            sorted(a["did"] for a in out["admitted"]) == sorted([ALICE, BOB])
            and out["rejected"] == []
            and bool(out["finalCursorHex"]),
            sync.stdout[:300],
        )
        record("motoko-serves", "v1/changes", "initial-sync", clientOutcome=sync.stdout.strip())
        cursor_1 = out["finalCursorHex"]

        b5_file = envelope_file("b5.cose", m["b5"])
        publish = rust_cli("relay", "publish", "--relay", base, "--record", str(b5_file), "--policy", "development")
        check(S, "B.5 revocation admitted via Rust client", publish.returncode == 0 and json.loads(publish.stdout)["status"] == "admitted", publish.stdout)

        sync = rust_cli("relay", "sync", "--database", str(sync_db), "--peer", base, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "10")
        out = json.loads(sync.stdout)
        check(
            S,
            "incremental sync sees the revocation exactly once",
            [a["did"] for a in out["admitted"]] == [ALICE] and out["finalCursorHex"] != cursor_1,
            sync.stdout[:300],
        )
        record("motoko-serves", "v1/changes", "incremental-sync-revocation", clientOutcome=sync.stdout.strip())

        sync = rust_cli("relay", "sync", "--database", str(sync_db), "--peer", base, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "10")
        out = json.loads(sync.stdout)
        check(S, "further sync is empty (exactly-once visibility)", out["admitted"] == [] and out["noChange"] == 0, sync.stdout[:300])

        # Pagination with itemLimit 1 into a fresh database.
        page_db = fresh_db(work / "m-sync-pages.sqlite")
        sync = rust_cli("relay", "sync", "--database", str(page_db), "--peer", base, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "10", "--item-limit", "1")
        out = json.loads(sync.stdout)
        check(
            S,
            "itemLimit-1 sync walks each record exactly once across pages",
            out["pages"] > 1 and sorted(a["did"] for a in out["admitted"]) == sorted([ALICE, BOB]),
            sync.stdout[:300],
        )
        record("motoko-serves", "v1/changes", "item-limit-1-pagination", clientOutcome=sync.stdout.strip())

        # Final agreement: the Rust receiver database, served by the
        # Rust relay, agrees with the Motoko-served view on every DID's
        # winning record bytes.
        final_relay = RustRelay(sync_db)
        resolve_request = cbor.encode({0: 1, 1: [ALICE, BOB]})
        _, _, rust_view = http_request(final_relay.base_uri, "POST", "v1/resolve", resolve_request, "application/cbor")
        final_relay.stop()
        _, _, motoko_view = http_request(base, "POST", "v1/resolve", resolve_request, "application/cbor")
        rust_items = cbor.decode_strict(rust_view)[2]
        motoko_items = cbor.decode_strict(motoko_view)[2]
        check(
            S,
            "final state agreement: both sides serve identical winning record bytes for alice and bob",
            rust_items == motoko_items,
            {"rust": rust_view.hex()[:80], "motoko": motoko_view.hex()[:80]},
        )
        record("motoko-serves", "v1/resolve", "final-agreement", rustViewHex=rust_view.hex(), motokoViewHex=motoko_view.hex())

        # 5. hostile request to the serving side.
        status, ctype, body = http_request(base, "POST", "v1/resolve", bytes.fromhex(m["b11_1_request"]), "application/cbor")
        check(S, "B.11.1 invalid outer request is HTTP 400 with no per-item body", status == 400 and body == b"", (status, body.hex()))
        record("motoko-serves", "v1/resolve", "b11-1-hostile-request", status=status, responseHex=body.hex())

        # 6. challenge records authored by Rust cross the wire to Motoko
        # (admission = Motoko production ingress verification at the
        # challenge clock), then are resolved back and locally verified
        # by the Rust production client at `verifyNowMs`.
        bridge.cmd({"op": "gateInit", "name": "gateCross", "genStart": 0x68})
        CROSS_PORT = 42933
        bridge.cmd({"op": "gateServe", "name": "gateCross", "port": CROSS_PORT, "nowMs": CHALLENGE_NOW})
        cross_base = f"http://127.0.0.1:{CROSS_PORT}/"
        crossing = []
        for case_id, ref in CROSSING_CASES:
            envelope = rust_by_id[case_id]["result"]["envelopeHex"]
            did = rust_by_id[f"challenge-identity-{ref}"]["result"]["did"]
            digest = rust_by_id[case_id]["result"]["recordBodyDigestHex"]
            crossing.append((did, digest))
            path = envelope_file(f"cross-{ref}.cose", envelope)
            publish = rust_cli("relay", "publish", "--relay", cross_base, "--record", str(path), "--policy", "development")
            check(S, f"Rust-authored {case_id} admitted by Motoko ingress", publish.returncode == 0 and json.loads(publish.stdout)["status"] == "admitted", (publish.stdout + publish.stderr)[:200])
            record("motoko-serves", "v1/publish", f"crossing-{case_id}", clientOutcome=publish.stdout.strip())
        resolve = rust_cli(
            "relay", "resolve", "--relay", cross_base,
            *[arg for did, _ in crossing for arg in ("--did", did)],
            "--policy", "development", "--now-ms", str(CHALLENGE_NOW),
        )
        out = json.loads(resolve.stdout)
        check(
            S,
            "crossed challenge records resolve and verify (Rust side)",
            [r.get("bodyDigest") for r in out["results"]] == [digest for _, digest in crossing]
            and all(r["kind"] == "full" for r in out["results"]),
            resolve.stdout[:300],
        )
        record("motoko-serves", "v1/resolve", "crossing-verification", clientOutcome=resolve.stdout.strip()[:2000])
    finally:
        bridge.stop()


# ---------------------------------------------------------------------------
# Hostile-peer responses served to both production client paths
# ---------------------------------------------------------------------------


def hostile_clients(m: dict) -> None:
    S = "H"
    fixture = FixtureServer()
    work = ic.WORK_DIR / "phase3"
    try:
        cbor_type = "application/cbor"

        # ----- Motoko production client paths (fresh receiver). -----
        bridge = MotokoBridge()
        try:
            fixture.routes[("GET", "/v1/info")] = (200, cbor_type, bytes.fromhex(m["infoMissingVersion"]))
            result = bridge.cmd({"op": "client", "port": fixture.port, "statement": "RelayNode.buildInfo(node, __ID__);"})
            check(S, "Motoko rejects info without protocol version 1 (schemaViolation)", result["outcome"] == "reject protocol schemaViolation", result["outcome"])
            record("hostile-to-motoko", "v1/info", "info-missing-version", clientOutcome=result["outcome"])

            fixture.routes[("GET", "/v1/info")] = (200, cbor_type, bytes.fromhex(m["infoMissingSuite"]))
            result = bridge.cmd({"op": "client", "port": fixture.port, "statement": "RelayNode.buildInfo(node, __ID__);"})
            check(S, "Motoko rejects info without suite -19 (schemaViolation)", result["outcome"] == "reject protocol schemaViolation", result["outcome"])
            record("hostile-to-motoko", "v1/info", "info-missing-suite", clientOutcome=result["outcome"])

            fixture.routes[("GET", "/v1/directory")] = (200, cbor_type, bytes.fromhex(m["directoryDuplicateIndex"]))
            result = bridge.cmd({"op": "client", "port": fixture.port, "statement": "RelayNode.buildDirectory(node, __ID__);"})
            check(S, "Motoko rejects directory with duplicate indices (schemaViolation)", result["outcome"] == "reject protocol schemaViolation", result["outcome"])
            record("hostile-to-motoko", "v1/directory", "directory-duplicate-index", clientOutcome=result["outcome"])

            fixture.routes[("POST", "/v1/resolve")] = (200, cbor_type, bytes.fromhex(m["b11_2_response"]))
            result = motoko_resolve(bridge, fixture.port, [ALICE, BOB])
            check(S, "Motoko rejects the B.11.2 invalid outer response completely", result["outcome"].startswith("reject protocol"), result["outcome"])
            record("hostile-to-motoko", "v1/resolve", "b11-2-invalid-outer-response", clientOutcome=result["outcome"])

            fixture.routes[("POST", "/v1/publish")] = (200, cbor_type, cbor.encode({0: 1, 1: 1, 2: 0}))
            result = motoko_publish(bridge, fixture.port, m["b4"])
            check(S, "Motoko rejects a malformed publish response completely (status 1 with invalidDid)", result["outcome"] == "reject protocol schemaViolation", result["outcome"])
            record("hostile-to-motoko", "v1/publish", "malformed-publish-response-status1-invalidDid", clientOutcome=result["outcome"])
        finally:
            bridge.stop()

        # B.11.5 and B.11.7 need receiver state: alice current from a
        # helper relay, then the published bytes from the fixture.
        helper_db = fresh_db(work / "h-helper.sqlite")
        helper = RustRelay(helper_db)
        helper_port = int(helper.base_uri.rsplit(":", 1)[1].rstrip("/"))
        http_request(helper.base_uri, "POST", "v1/publish", bytes.fromhex(m["b4"]), "application/cose")

        bridge5 = MotokoBridge()
        try:
            result = motoko_changes(bridge5, helper_port)
            check(S, "B.11.5 setup: Motoko receiver holds alice current", result["outcome"].startswith("changes processed admitted:1"), result["outcome"])
            fixture.routes[("POST", "/v1/changes")] = (200, cbor_type, bytes.fromhex(m["b11_5_response"]))
            result = motoko_changes(bridge5, fixture.port)
            cursor = motoko_cursor(bridge5)
            check(
                S,
                "B.11.5: Motoko admits bob, rejects the B.8 candidate alone, stores the exact cursor",
                "admitted:" in result["outcome"]
                and "rejected:identityBindingMismatch" in result["outcome"]
                and cursor == "7630382d30303032",
                (result["outcome"], cursor),
            )
            record("hostile-to-motoko", "v1/changes", "b11-5-isolation-cursor", clientOutcome=result["outcome"], storedCursor=cursor)

            # B.11.7: over-itemLimit response rejected completely, cursor unchanged.
            b11_7_request = cbor.decode_strict(bytes.fromhex(m["b11_7_request"]))
            item_limit = b11_7_request[2]
            fixture.routes[("POST", "/v1/changes")] = (200, cbor_type, bytes.fromhex(m["b11_7_response"]))
            result = motoko_changes(bridge5, fixture.port, item_limit=item_limit)
            check(
                S,
                "B.11.7: Motoko rejects the over-itemLimit response without using its cursor",
                result["outcome"].startswith("reject protocol") and motoko_cursor(bridge5) == "7630382d30303032",
                (result["outcome"], motoko_cursor(bridge5)),
            )
            record("hostile-to-motoko", "v1/changes", "b11-7-item-limit-overflow", clientOutcome=result["outcome"], storedCursor=motoko_cursor(bridge5))
        finally:
            bridge5.stop()

        # ----- Rust production client paths. -----
        # info: consumed by relay sync before any state change. Rust
        # reports the rejection under its composite client symbol
        # `outerResponseRejected` with the schema-violation layer named
        # in the message (the Campaign 1 client-surface naming note; the
        # rejection decision is identical). No changes request follows:
        # the hostile info yields no usable protocol state.
        for name, hex_key in (("info-missing-version", "infoMissingVersion"), ("info-missing-suite", "infoMissingSuite")):
            fixture.routes[("GET", "/v1/info")] = (200, cbor_type, bytes.fromhex(m[hex_key]))
            fixture.hits.clear()
            db = fresh_db(work / f"h-rust-{name}.sqlite")
            sync = rust_cli("relay", "sync", "--database", str(db), "--peer", fixture.base, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "5")
            out = sync.stdout + sync.stderr
            no_state = all(h["path"] == "/v1/info" for h in fixture.hits)
            check(
                S,
                f"Rust rejects {name} (complete schema rejection, no usable state)",
                sync.returncode != 0
                and ("schemaViolation" in out or ("outerResponseRejected" in out and "schema" in out))
                and no_state,
                (out[:300], [h["path"] for h in fixture.hits]),
            )
            record("hostile-to-rust", "v1/info", name, clientOutcome=out.strip()[:300], fixturePaths=[h["path"] for h in fixture.hits])

        # directory: consumed by the multi-relay resolver on a Ref result.
        fixture.routes[("POST", "/v1/resolve")] = (200, cbor_type, cbor.encode({0: 1, 1: bytes(range(16)), 2: [{0: 1, 1: 0}]}))
        fixture.routes[("GET", "/v1/directory")] = (200, cbor_type, bytes.fromhex(m["directoryDuplicateIndex"]))
        resolve = rust_cli("resolve", "--did", ALICE, "--relay", fixture.base, "--policy", "development", "--deadline-ms", "8000")
        out = resolve.stdout + resolve.stderr
        directory_fetched = any(h["path"] == "/v1/directory" for h in fixture.hits)
        check(
            S,
            "Rust rejects directory with duplicate indices (complete rejection, no reference targets used)",
            resolve.returncode != 0 and directory_fetched and "outerResponseRejected" in out and '"authorityState":"unknown"' in out,
            out[:400],
        )
        record("hostile-to-rust", "v1/directory", "directory-duplicate-index", clientOutcome=out.strip()[:400])

        # B.11.2 invalid outer resolve response.
        fixture.routes[("POST", "/v1/resolve")] = (200, cbor_type, bytes.fromhex(m["b11_2_response"]))
        resolve = rust_cli("relay", "resolve", "--relay", fixture.base, "--did", ALICE, "--did", BOB, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE))
        out = resolve.stdout + resolve.stderr
        check(
            S,
            "Rust rejects the B.11.2 invalid outer response completely",
            resolve.returncode != 0 and "outerResponseRejected" in out,
            out[:300],
        )
        record("hostile-to-rust", "v1/resolve", "b11-2-invalid-outer-response", clientOutcome=out.strip()[:300], note="Rust folds the deterministic-CBOR layer into its composite outerResponseRejected client symbol with the layer named in the message (Campaign 1 note; not a protocol disagreement)")

        # B.11.5 through relay sync (valid info + published changes bytes).
        fixture.routes[("GET", "/v1/info")] = (200, cbor_type, bytes.fromhex(m["infoExample"]))
        fixture.routes[("POST", "/v1/changes")] = (200, cbor_type, bytes.fromhex(m["b11_5_response"]))
        db = fresh_db(work / "h-rust-b11-5.sqlite")
        http_request(helper.base_uri, "GET", "v1/info", None, "")  # helper stays warm
        sync = rust_cli("relay", "sync", "--database", str(db), "--peer", helper.base_uri, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "5")
        out0 = json.loads(sync.stdout)
        check(S, "B.11.5 setup: Rust receiver holds alice current", [a["did"] for a in out0["admitted"]] == [ALICE], sync.stdout[:200])
        sync = rust_cli("relay", "sync", "--database", str(db), "--peer", fixture.base, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "1")
        out = json.loads(sync.stdout) if sync.returncode == 0 else {}
        check(
            S,
            "B.11.5: Rust admits bob, rejects the B.8 candidate alone, stores the exact cursor",
            sync.returncode == 0
            and [a["did"] for a in out.get("admitted", [])] == [BOB]
            and len(out.get("rejected", [])) == 1
            and "identityBindingMismatch" in json.dumps(out.get("rejected"))
            and out.get("finalCursorHex") == "7630382d30303032",
            sync.stdout[:400],
        )
        record("hostile-to-rust", "v1/changes", "b11-5-isolation-cursor", clientOutcome=sync.stdout.strip()[:600])

        # B.11.7 over-itemLimit response: rejected completely (composite
        # schema/limits rejection), cursor kept. Cursor preservation is
        # proven by the next request the production receiver emits: it
        # must still present the exact B.11.5-stored cursor bytes.
        b11_7_request = cbor.decode_strict(bytes.fromhex(m["b11_7_request"]))
        fixture.routes[("POST", "/v1/changes")] = (200, cbor_type, bytes.fromhex(m["b11_7_response"]))
        sync = rust_cli("relay", "sync", "--database", str(db), "--peer", fixture.base, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "1", "--item-limit", str(b11_7_request[2]))
        out = sync.stdout + sync.stderr
        check(
            S,
            "B.11.7: Rust rejects the over-itemLimit response without entry processing",
            sync.returncode != 0
            and ("itemLimit" in out or ("outerResponseRejected" in out and ("limits" in out or "schema" in out))),
            out[:300],
        )
        record("hostile-to-rust", "v1/changes", "b11-7-item-limit-overflow", clientOutcome=out.strip()[:300])
        fixture.hits.clear()
        rust_cli("relay", "sync", "--database", str(db), "--peer", fixture.base, "--policy", "development", "--now-ms", str(NOW_ADMISSIBLE), "--max-pages", "1")
        sent_cursors = [
            cbor.decode_strict(bytes.fromhex(h["requestHex"]))[1]
            for h in fixture.hits
            if h["path"] == "/v1/changes"
        ]
        check(
            S,
            "B.11.7: the receiver's next request still presents the exact stored cursor",
            sent_cursors and sent_cursors[0] == bytes.fromhex("7630382d30303032"),
            [c.hex() if isinstance(c, bytes) else c for c in sent_cursors],
        )
        record("hostile-to-rust", "v1/changes", "b11-7-cursor-preserved", sentCursorHex=[c.hex() if isinstance(c, bytes) else str(c) for c in sent_cursors])

        # Malformed publish response to the Rust publish client.
        fixture.routes[("POST", "/v1/publish")] = (200, cbor_type, cbor.encode({0: 1, 1: 1, 2: 0}))
        b4_file = work / "b4.cose"
        b4_file.write_bytes(bytes.fromhex(m["b4"]))
        publish = rust_cli("relay", "publish", "--relay", fixture.base, "--record", str(b4_file), "--policy", "development")
        out = publish.stdout + publish.stderr
        check(
            S,
            "Rust rejects a malformed publish response completely (status 1 with invalidDid)",
            publish.returncode != 0 and ("schemaViolation" in out or "malformed" in out or "rejected" in out),
            out[:300],
        )
        record("hostile-to-rust", "v1/publish", "malformed-publish-response-status1-invalidDid", clientOutcome=out.strip()[:300])
        helper.stop()
    finally:
        fixture.stop()


def run() -> dict:
    pins = ic.verify_pins()
    ic.run_bundle_verifier()
    vectors = ic.ExpectedVectors()
    build_clockshim()
    materialize_gate_driver()
    ic.build_rust()
    m = load_material(vectors)
    motoko_by_id = motoko_challenge_material()
    rust_by_id = rust_challenge_material()

    direction_r(m, motoko_by_id)
    direction_m(m, rust_by_id)
    hostile_clients(m)

    failed = [c for c in CHECKS if not c["ok"]]
    report = {
        "phase": 3,
        "pins": pins,
        "checks": CHECKS,
        "exchanges": EXCHANGES,
        "verdict": "pass" if not failed else "FAIL",
        "failedChecks": failed,
        "notes": [
            "Opaque relay-chosen values (relay ids, generations, cursors, "
            "lastUpdated numbers) are never byte-compared (NONDETERMINISM.md).",
            "The publish status-1 reason-code choice is permitted diagnostic "
            "variation: Rust emits the bare form, Motoko the coded accurate "
            "form; each side accepted the other's choice; both raws preserved, "
            "never normalized.",
            "HTTP response headers are transport-layer detail outside the "
            "comparison; publish CORS absence is the recorded deliberate "
            "scope decision (PRECLASSIFICATION.md).",
        ],
    }
    return report


if __name__ == "__main__":
    report = run()
    ic.write_result(ic.WORK_DIR / "phase3" / "phase3-report.json", report)
    for c in report["checks"]:
        print(("ok  " if c["ok"] else "FAIL"), f"[{c['section']}]", c["label"])
    print("phase3 verdict:", report["verdict"], f"({len(report['checks'])} checks, {len(report['exchanges'])} exchanges recorded)")
    if report["verdict"] != "pass":
        sys.exit(1)
