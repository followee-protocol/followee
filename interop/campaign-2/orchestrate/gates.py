"""Pre-Phase-3 gates G1, G2, G3 (ACCEPTANCE.md), executed live in both
directions after Phases 1 and 2. A failure of any gate aborts the
campaign before general Phase 3 execution.

Direction R: the frozen Rust participant serves through its production
`relay serve` binary over real loopback HTTP. The Gate G1 scenario pins
the *relay's* clock, so the serving process runs under the coordinator
scenario-clock shim (`clockshim/`), which configures the process
environment's realtime clock — participant code is unchanged and makes
every protocol decision.

Direction M: the frozen Motoko participant serves through its
production `RelayHttp.handle` / `RelayServe` modules behind the
coordinator gate driver (`motoko-driver/GateNode.mo`) and the byte-only
bridge — the same production handler and framing the participant's own
loopback shim uses, with the scenario clock and the opaque instance
identifiers as explicit configuration (`RelayHttp.handle` takes the
clock as a production parameter; generations are relay-chosen opaque
values per NONDETERMINISM.md).

Cursor probes follow the ACCEPTANCE G3 rules exactly: only null
cursors, exact previously returned cursors, one relay-relative
malformed probe (a truncation of a genuinely returned cursor — a byte
string each participant's declared wrong-length rule classifies as
malformed), and a foreign-generation cursor genuinely returned by a
second instance of the same participant are ever presented. No cursor
is forged, no state is seeded through a test-only surface, and no
never-issued position is probed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interop_common as ic

sys.path.insert(0, str(ic.bundle_verify_dir()))
from interopkit import cbor  # type: ignore

NOW_ADMISSIBLE = 1785589201123  # the published B.11.5 recipient clock
NOW_PREMATURE = 1785588900122  # the changes/resolve-premature-retained relay clock

ALICE = "did:flw:zQmPcGstBa7wW9hoYQbS6JZ4UxwZmoKr7YVf9y7qxiyD3Cm"

# Participant-declared pre-parse publish transport caps, recorded at
# freeze (Gate G2 evidence source is the participant-owned declaration):
# - Rust: interop/v0.9.2/README.md "Recorded participant facts" —
#   65,536-byte HTTP publish request-entity cap.
# - Motoko: docs/MAINTENANCE-RECORD-v0.9.2.md section 7 item 2 —
#   publish entities over 64 KiB (65,536 bytes) rejected 413 pre-parse.
DECLARED_CAPS = {"rust": 65536, "motoko": 65536}

# Participant-owned regression evidence for the two G1 behaviours
# (test identifiers from the frozen revisions' own suites; recorded as
# a supplement to — never a substitute for — the live gate).
G1_REGRESSION_EVIDENCE = {
    "rust": [
        "relay_core::sec_12_3_locally_premature_current_record_is_error_not_absent",
        "tests/REQUIREMENTS.md section 12.6/5.4 rows (premature retained tuple emission and receiver-side classification)",
        "sync_receiver::sec_13_3_premature_and_invalid_candidates_advance_the_cursor_without_stalling",
    ],
    "motoko": [
        "test/relayserve.test.mo — premature serving rows (stored ordering timestamp; premature under the present clock served in changes, Error(premature) in resolve)",
    ],
}


def load_transcript(name: str) -> dict:
    return json.loads(
        (ic.BUNDLE_DIR / "coordinator" / "transcripts" / (name + ".json")).read_text()
    )


def http_request(base: str, method: str, path: str, body: bytes | None, ctype: str):
    request = urllib.request.Request(base + path, data=body, method=method)
    if body is not None:
        request.add_header("content-type", ctype)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, response.headers.get("content-type"), response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("content-type"), error.read()


def contains_bytes(value, needle: bytes) -> bool:
    if isinstance(value, bytes):
        return value == needle
    if isinstance(value, list):
        return any(contains_bytes(v, needle) for v in value)
    if isinstance(value, dict):
        return any(contains_bytes(v, needle) for v in value.values())
    return False


def find_cursor(changes_response: bytes) -> bytes:
    """The `nextCursor` member (Section 12.6 label 3) of a successful
    changes response. Opaque: never interpreted, only presented back
    exactly."""
    decoded = cbor.decode_strict(changes_response)
    cursor = decoded[3]
    assert isinstance(cursor, bytes) and cursor, f"no nextCursor: {decoded!r}"
    return cursor


def fresh_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        sibling = path.with_name(path.name + suffix)
        if sibling.exists():
            sibling.unlink()
    return path


class RustRelay:
    def __init__(self, database: Path, scenario_now_ms: int | None = None):
        env = dict(os.environ)
        if scenario_now_ms is not None:
            env["LD_PRELOAD"] = str(ic.WORK_DIR / "clockshim.so")
            env["FOLLOWEE_SCENARIO_NOW_MS"] = str(scenario_now_ms)
        self.proc = subprocess.Popen(
            [
                str(ic.RUST_BIN),
                "relay",
                "serve",
                "--database",
                str(database),
                "--listen",
                "127.0.0.1:0",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        self.startup = json.loads(self.proc.stdout.readline())
        assert "listen" in self.startup, f"relay startup failed: {self.startup}"
        self.base_uri = f"http://{self.startup['listen']}/"

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=30)


class MotokoBridge:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["node", str(Path(__file__).resolve().parent / "motoko_bridge.js")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=dict(os.environ),
        )

    def cmd(self, obj: dict) -> dict:
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()
        result = json.loads(self.proc.stdout.readline())
        assert result.get("ok"), f"bridge command failed: {obj} -> {result}"
        return result

    def stop(self):
        try:
            self.cmd({"op": "stop"})
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()
            self.proc.wait(timeout=30)


def materialize_gate_driver() -> None:
    """Copies the coordinator gate driver into the participant
    checkout's gitignored runner/generated/ directory (the same place
    the participant's own runner writes embeddings), keeping the frozen
    tree clean for the pin checks."""
    generated = ic.MOTOKO_REPO / "runner" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        Path(__file__).resolve().parent / "motoko-driver" / "GateNode.mo",
        generated / "GateNode.mo",
    )


def build_clockshim() -> None:
    ic.WORK_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "gcc",
            "-shared",
            "-fPIC",
            "-O2",
            "-o",
            str(ic.WORK_DIR / "clockshim.so"),
            str(Path(__file__).resolve().parent / "clockshim" / "clockshim.c"),
            "-ldl",
        ],
        check=True,
    )


CHANGES_CTYPE = "application/cbor"


def changes_request(cursor: bytes | None, item_limit: int = 100, byte_limit: int = 1048576) -> bytes:
    return cbor.encode(
        {0: 1, 1: cursor if cursor is not None else None, 2: item_limit, 3: byte_limit}
    )


def run_gate_g1(vectors: ic.ExpectedVectors, bridge: MotokoBridge, checks: list) -> dict:
    b4_hex = vectors.by_case["records"]["b4-root"]["expected"]["envelopeHex"]
    b4 = bytes.fromhex(b4_hex)
    changes_transcript = load_transcript("changes-premature-retained")
    resolve_transcript = load_transcript("resolve-premature-retained")
    changes_body = bytes.fromhex(changes_transcript["request"]["bodyHex"])
    resolve_body = bytes.fromhex(resolve_transcript["request"]["bodyHex"])
    exchanges = []

    def check(label, condition, detail=None):
        checks.append({"gate": "G1", "label": label, "ok": bool(condition), **({"detail": detail} if detail and not condition else {})})

    # --- Direction R: Rust serves under the pinned scenario clock. ---
    db = fresh_db(ic.WORK_DIR / "gates" / "g1-rust.sqlite")
    relay = RustRelay(db)
    status, _, body = http_request(relay.base_uri, "POST", "v1/publish", b4, "application/cose")
    check("R: B.4 admitted before the premature clock", status == 200 and body.hex() == "a200010100", body.hex())
    relay.stop()

    relay = RustRelay(db, scenario_now_ms=NOW_PREMATURE)
    status, ctype, body = http_request(relay.base_uri, "POST", "v1/changes", changes_body, CHANGES_CTYPE)
    decoded = cbor.decode_strict(body)
    entries = next(v for v in decoded.values() if isinstance(v, list))
    check(
        "R: null-cursor changes returns the retained premature Full tuple with exact B.4 bytes",
        status == 200 and len(entries) == 1 and contains_bytes(entries, b4)
        and any(ALICE in str(e) for e in entries),
        body.hex()[:120],
    )
    exchanges.append({"direction": "rust-serves", "operation": "v1/changes", "scenario": "premature-retained", "requestHex": changes_body.hex(), "status": status, "contentType": ctype, "responseHex": body.hex()})

    status, ctype, body = http_request(relay.base_uri, "POST", "v1/resolve", resolve_body, CHANGES_CTYPE)
    decoded = cbor.decode_strict(body)
    items = next(v for v in decoded.values() if isinstance(v, list))
    check(
        "R: resolve returns the aligned per-DID Error(premature) {0:3,2:10}",
        status == 200 and items == [{0: 3, 2: 10}],
        body.hex(),
    )
    exchanges.append({"direction": "rust-serves", "operation": "v1/resolve", "scenario": "premature-retained", "requestHex": resolve_body.hex(), "status": status, "contentType": ctype, "responseHex": body.hex()})

    # Receiving half of the contrast: the Motoko production receiver
    # classifies the served tuple under its own clock (1785589201123)
    # and admits it.
    result = bridge.cmd(
        {
            "op": "client",
            "port": int(relay.base_uri.rsplit(":", 1)[1].rstrip("/")),
            "statement": "RelayNode.buildChanges(node, __ID__, 100, 1048576);",
        }
    )
    check(
        "R: Motoko receiver admits the premature-served tuple under its own clock",
        result["outcome"].startswith("changes processed admitted:"),
        result["outcome"],
    )
    exchanges.append({"direction": "rust-serves", "operation": "v1/changes", "scenario": "receiver-own-clock-admission", "clientOutcome": result["outcome"], "status": result["raw"]["status"], "responseHex": result["raw"]["bodyHex"]})
    relay.stop()

    # --- Direction M: Motoko serves through the production handler. ---
    g1_port = 42921
    bridge.cmd({"op": "gateInit", "name": "gateG1", "genStart": 0x30})
    bridge.cmd({"op": "gateServe", "name": "gateG1", "port": g1_port, "nowMs": NOW_ADMISSIBLE})
    base = f"http://127.0.0.1:{g1_port}/"
    status, _, body = http_request(base, "POST", "v1/publish", b4, "application/cose")
    check("M: B.4 admitted before the premature clock", status == 200 and body.hex() == "a200010100", body.hex())

    bridge.cmd({"op": "gateClock", "name": "gateG1", "nowMs": NOW_PREMATURE})
    status, ctype, body = http_request(base, "POST", "v1/changes", changes_body, CHANGES_CTYPE)
    decoded = cbor.decode_strict(body)
    entries = next(v for v in decoded.values() if isinstance(v, list))
    check(
        "M: null-cursor changes returns the retained premature Full tuple with exact B.4 bytes",
        status == 200 and len(entries) == 1 and contains_bytes(entries, b4)
        and any(ALICE in str(e) for e in entries),
        body.hex()[:120],
    )
    exchanges.append({"direction": "motoko-serves", "operation": "v1/changes", "scenario": "premature-retained", "requestHex": changes_body.hex(), "status": status, "contentType": ctype, "responseHex": body.hex()})

    status, ctype, body = http_request(base, "POST", "v1/resolve", resolve_body, CHANGES_CTYPE)
    decoded = cbor.decode_strict(body)
    items = next(v for v in decoded.values() if isinstance(v, list))
    check(
        "M: resolve returns the aligned per-DID Error(premature) {0:3,2:10}",
        status == 200 and items == [{0: 3, 2: 10}],
        body.hex(),
    )
    exchanges.append({"direction": "motoko-serves", "operation": "v1/resolve", "scenario": "premature-retained", "requestHex": resolve_body.hex(), "status": status, "contentType": ctype, "responseHex": body.hex()})

    # Receiving half: the Rust production receiver synchronizes from the
    # premature-serving relay under its own explicit clock and admits.
    sync_db = fresh_db(ic.WORK_DIR / "gates" / "g1-rust-receiver.sqlite")
    sync = subprocess.run(
        [
            str(ic.RUST_BIN), "relay", "sync",
            "--database", str(sync_db),
            "--peer", base,
            "--policy", "development",
            "--now-ms", str(NOW_ADMISSIBLE),
            "--max-pages", "10",
        ],
        capture_output=True, text=True, timeout=300,
    )
    sync_out = json.loads(sync.stdout) if sync.returncode == 0 else {}
    check(
        "M: Rust receiver admits the premature-served tuple under its own clock",
        sync.returncode == 0
        and [a["did"] for a in sync_out.get("admitted", [])] == [ALICE]
        and sync_out.get("rejected") == [],
        sync.stdout[:300] or sync.stderr[:300],
    )
    exchanges.append({"direction": "motoko-serves", "operation": "v1/changes", "scenario": "receiver-own-clock-admission", "clientOutcome": sync.stdout.strip()})

    return {"exchanges": exchanges, "regressionEvidence": G1_REGRESSION_EVIDENCE}


def run_gate_g2(vectors: ic.ExpectedVectors, bridge: MotokoBridge, checks: list) -> dict:
    transcript = load_transcript("publish-record-too-large")
    oversized = bytes.fromhex(transcript["request"]["bodyHex"])
    expected_response = transcript["response"]["bodyHex"]
    assert len(oversized) == 16385
    exchanges = []

    def check(label, condition, detail=None):
        checks.append({"gate": "G2", "label": label, "ok": bool(condition), **({"detail": detail} if detail and not condition else {})})

    check(
        "declared caps admit the 16385-byte case",
        16385 <= min(DECLARED_CAPS.values()),
        DECLARED_CAPS,
    )

    # Direction R.
    db = fresh_db(ic.WORK_DIR / "gates" / "g2-rust.sqlite")
    relay = RustRelay(db)
    status, ctype, body = http_request(relay.base_uri, "POST", "v1/publish", oversized, "application/cose")
    check(
        "R: 16385-byte record is HTTP 200 status-2 recordTooLarge",
        status == 200 and body.hex() == expected_response,
        (status, body.hex()),
    )
    exchanges.append({"direction": "rust-serves", "operation": "v1/publish", "scenario": "record-too-large-16385", "requestLength": len(oversized), "status": status, "contentType": ctype, "responseHex": body.hex()})

    # ... and through the Motoko production client, which must classify
    # the protocol rejection.
    oversized_hex = oversized.hex()
    result = bridge.cmd(
        {
            "op": "client",
            "port": int(relay.base_uri.rsplit(":", 1)[1].rstrip("/")),
            "statement": f'RelayNode.buildPublish(node, __ID__, "{oversized_hex}");',
        }
    )
    # The Motoko production client enforces the Section 15.1 record
    # bound on its own side: it refuses to construct a publish request
    # for the over-limit record (`build-refused`, no request emitted).
    # That is a conforming client-side outcome, recorded visibly; the
    # serving-side comparison above is the normative Gate G2 check.
    check(
        "R: Motoko client classifies the over-limit record on its own side",
        result["outcome"] in ("publish rejected recordTooLarge", "build-refused"),
        result["outcome"],
    )
    exchanges.append({"direction": "rust-serves", "operation": "v1/publish", "scenario": "record-too-large-16385-motoko-client", "clientOutcome": result["outcome"], "note": "client-side Section 15.1 bound: request construction refused; no wire exchange occurred"})
    relay.stop()

    # Direction M.
    g2_port = 42922
    bridge.cmd({"op": "gateInit", "name": "gateG2", "genStart": 0x50})
    bridge.cmd({"op": "gateServe", "name": "gateG2", "port": g2_port, "nowMs": NOW_ADMISSIBLE})
    base = f"http://127.0.0.1:{g2_port}/"
    status, ctype, body = http_request(base, "POST", "v1/publish", oversized, "application/cose")
    check(
        "M: 16385-byte record is HTTP 200 status-2 recordTooLarge",
        status == 200 and body.hex() == expected_response,
        (status, body.hex()),
    )
    exchanges.append({"direction": "motoko-serves", "operation": "v1/publish", "scenario": "record-too-large-16385", "requestLength": len(oversized), "status": status, "contentType": ctype, "responseHex": body.hex()})

    record_file = ic.WORK_DIR / "gates" / "record-16385.cose"
    record_file.write_bytes(oversized)
    publish = subprocess.run(
        [
            str(ic.RUST_BIN), "relay", "publish",
            "--relay", base,
            "--record", str(record_file),
            "--policy", "development",
        ],
        capture_output=True, text=True, timeout=120,
    )
    rust_client_out = (publish.stdout + publish.stderr).strip()
    check(
        "M: Rust client classifies the over-limit record",
        publish.returncode != 0
        and ("recordTooLarge" in rust_client_out or "TooLarge" in rust_client_out or "large" in rust_client_out),
        rust_client_out[:300],
    )
    exchanges.append({"direction": "motoko-serves", "operation": "v1/publish", "scenario": "record-too-large-16385-rust-client", "clientOutcome": rust_client_out[:400]})
    return {"declaredCaps": DECLARED_CAPS, "exchanges": exchanges}


def run_gate_g3(vectors: ic.ExpectedVectors, bridge: MotokoBridge, checks: list) -> dict:
    b4 = bytes.fromhex(vectors.by_case["records"]["b4-root"]["expected"]["envelopeHex"])
    reset_expected = load_transcript("changes-reset-required")["response"]["bodyHex"]
    # Section 12.6 status-2 changes response: {0:1, 1:2, 6:errorCode},
    # errorCode 18 = invalidCursor (Section 15.3).
    invalid_cursor_expected = cbor.encode({0: 1, 1: 2, 6: 18}).hex()
    exchanges = []

    def check(label, condition, detail=None):
        checks.append({"gate": "G3", "label": label, "ok": bool(condition), **({"detail": detail} if detail and not condition else {})})

    def probe_side(name: str, base_a: str, base_b: str):
        # Natural cursor from instance A.
        http_request(base_a, "POST", "v1/publish", b4, "application/cose")
        status, _, body = http_request(base_a, "POST", "v1/changes", changes_request(None), CHANGES_CTYPE)
        cursor_a = find_cursor(body)
        # (a) Malformed probe: a truncation of the genuinely returned
        # cursor (wrong length under both participants' declared
        # bounded encodings; relay-relative, production path only).
        malformed = cursor_a[:1]
        status, _, body = http_request(base_a, "POST", "v1/changes", changes_request(malformed), CHANGES_CTYPE)
        check(
            f"{name}: malformed cursor probe is status-2 invalidCursor",
            status == 200 and body.hex() == invalid_cursor_expected,
            body.hex(),
        )
        exchanges.append({"direction": name, "operation": "v1/changes", "scenario": "malformed-cursor-probe", "probe": "1-byte truncation of a returned cursor", "status": status, "responseHex": body.hex()})
        # (b) Foreign-generation probe: a cursor genuinely returned by
        # the second instance of the same participant.
        http_request(base_b, "POST", "v1/publish", b4, "application/cose")
        status, _, body = http_request(base_b, "POST", "v1/changes", changes_request(None), CHANGES_CTYPE)
        cursor_b = find_cursor(body)
        check(
            f"{name}: second-instance cursor differs (independent generation)",
            cursor_a != cursor_b and cursor_a[:16] != cursor_b[:16],
        )
        status, _, body = http_request(base_a, "POST", "v1/changes", changes_request(cursor_b), CHANGES_CTYPE)
        check(
            f"{name}: foreign-generation cursor is the exact two-field ResetRequired",
            status == 200 and body.hex() == reset_expected,
            body.hex(),
        )
        exchanges.append({"direction": name, "operation": "v1/changes", "scenario": "foreign-generation-cursor", "probe": "cursor genuinely returned by a second instance", "status": status, "responseHex": body.hex()})

    # Direction R: two independent Rust relay instances (fresh databases
    # generate fresh, independently chosen cursor generations).
    db_a = fresh_db(ic.WORK_DIR / "gates" / "g3-rust-a.sqlite")
    db_b = fresh_db(ic.WORK_DIR / "gates" / "g3-rust-b.sqlite")
    relay_a = RustRelay(db_a)
    relay_b = RustRelay(db_b)
    probe_side("rust-serves", relay_a.base_uri, relay_b.base_uri)
    relay_a.stop()
    relay_b.stop()

    # Direction M: two gate nodes with independently configured opaque
    # generations, both served by the production handler.
    port_a, port_b = 42923, 42924
    bridge.cmd({"op": "gateInit", "name": "gateG3A", "genStart": 0x60})
    bridge.cmd({"op": "gateInit", "name": "gateG3B", "genStart": 0x70})
    bridge.cmd({"op": "gateServe", "name": "gateG3A", "port": port_a, "nowMs": NOW_ADMISSIBLE})
    bridge.cmd({"op": "gateServe", "name": "gateG3B", "port": port_b, "nowMs": NOW_ADMISSIBLE})
    probe_side("motoko-serves", f"http://127.0.0.1:{port_a}/", f"http://127.0.0.1:{port_b}/")

    return {
        "probePolicy": {
            "malformed": (
                "1-byte truncation of a cursor genuinely returned by the probed "
                "relay; malformed under both participants' declared bounded "
                "(generation, position) encodings (Rust: relay cursor tests; "
                "Motoko: declared 16+8-byte form, wrong length malformed)"
            ),
            "foreignGeneration": (
                "cursor genuinely returned by a second instance of the same "
                "participant; no forging, injection, seeding, or test-only "
                "surface used"
            ),
            "neverIssuedPositions": "excluded from every input (permitted variation)",
        },
        "exchanges": exchanges,
    }


def run() -> dict:
    pins = ic.verify_pins()
    ic.run_bundle_verifier()
    vectors = ic.ExpectedVectors()
    build_clockshim()
    materialize_gate_driver()
    ic.build_rust()

    checks: list[dict] = []
    bridge = MotokoBridge()
    try:
        g1 = run_gate_g1(vectors, bridge, checks)
        g2 = run_gate_g2(vectors, bridge, checks)
        g3 = run_gate_g3(vectors, bridge, checks)
    finally:
        bridge.stop()

    failed = [c for c in checks if not c["ok"]]
    report = {
        "gates": {"G1": g1, "G2": g2, "G3": g3},
        "checks": checks,
        "pins": pins,
        "verdict": "pass" if not failed else "ABORT",
        "failedChecks": failed,
    }
    return report


if __name__ == "__main__":
    report = run()
    ic.write_result(ic.WORK_DIR / "gates" / "gates-report.json", report)
    for check in report["checks"]:
        print(("ok  " if check["ok"] else "FAIL"), check["gate"], check["label"])
    print("gates verdict:", report["verdict"])
    if report["verdict"] != "pass":
        sys.exit(1)
