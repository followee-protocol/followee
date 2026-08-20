"""Phase 2 — challenge maintenance confirmation (v0.9.2-r2).

Both participants produced and froze their v0.9.2-r2 challenge outputs
before any coordinator material was exposed. This phase:

1. preserves and digest-checks the original pre-exposure Motoko blind
   output (Campaign 1's frozen bytes), the Motoko revision-1 maintained
   output, and both participants' frozen v0.9.2-r2 outputs — none is
   regenerated here;
2. compares the two frozen refrozen output sets value for value under
   the interface result-equality rule, including the complete
   v0.9.2-r2 `record` projection deep and exactly (the Campaign 1 I2
   shape mapping no longer exists);
3. derives an independent coordinator-side result set with the bundle's
   own stdlib tooling (interopkit) and compares both participants
   against it;
4. runs the live cross-verification: each implementation verifies the
   envelopes the other authored, through its own production interface
   engine, at the file-level `verifyNowMs`.

Per CHALLENGES.md, `identityRef` materialization uses each
participant's own derived DIDs and own authored envelopes — never
another participant's or the coordinator's values.

The two participants chose different self-verify case labels
(`<case>-verify` versus `<case>/verify`) and different output file
orderings (grouped by operation versus interleaved). Both are
participant-local labeling outside the interface result-equality rule;
the alignment used here is recorded visibly and maps labels only,
never values.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interop_common as ic


def load_frozen_motoko() -> tuple[str, dict[str, dict], list[str]]:
    """Copies the frozen Motoko v0.9.2-r2 output bytes into the campaign
    work area and verifies the recorded SHA-256 before any comparison."""
    src = ic.MOTOKO_REPO / "outputs" / "v0.9.2-r2" / "challenge-results.jsonl"
    dst = ic.WORK_DIR / "phase2" / "motoko-challenge-frozen-r2.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    digest = ic.sha256_file(dst)
    assert digest == ic.PINS["motokoV092R2ChallengeSha256"]
    order = []
    by_id: dict[str, dict] = {}
    for line in dst.read_text().splitlines():
        if line.strip():
            response = json.loads(line)
            by_id[response["caseId"]] = response
            order.append(response["caseId"])
    assert len(order) == 36, f"expected 36 frozen responses, found {len(order)}"
    return digest, by_id, order


RUST_GROUPS = (
    "challenge-identities",
    "challenge-records",
    "challenge-verify",
    "challenge-selection",
)


def load_frozen_rust() -> tuple[dict[str, str], dict[str, dict], list[str]]:
    """Copies the frozen Rust challenge output bytes into the campaign
    work area; the per-file SHA-256 values were already checked against
    the participant's own frozen MANIFEST.json by the pin verification."""
    digests: dict[str, str] = {}
    by_id: dict[str, dict] = {}
    order: list[str] = []
    out_dir = ic.WORK_DIR / "phase2"
    out_dir.mkdir(parents=True, exist_ok=True)
    for group in RUST_GROUPS:
        name = f"{group}.responses.ndjson"
        src = ic.RUST_REPO / "interop" / "v0.9.2" / "outputs" / name
        dst = out_dir / ("rust-frozen-" + name)
        shutil.copyfile(src, dst)
        digests[name] = ic.sha256_file(dst)
        for line in dst.read_text().splitlines():
            if line.strip():
                response = json.loads(line)
                by_id[response["caseId"]] = response
                order.append(response["caseId"])
    assert len(order) == 36, f"expected 36 frozen responses, found {len(order)}"
    return digests, by_id, order


def label_alignment(challenges: dict) -> dict[str, str]:
    """Motoko caseId -> Rust caseId for the self-verify labels; identity
    on every other case."""
    mapping: dict[str, str] = {}
    for case in challenges["records"]["cases"]:
        mapping[case["id"] + "/verify"] = case["id"] + "-verify"
    return mapping


def compare_pair(case_id: str, rust: dict, motoko: dict) -> dict:
    """Motoko-vs-Rust exact comparison of one frozen challenge response.
    The complete result — including the v0.9.2-r2 `record` projection —
    is compared deep and exactly; no member is mapped or skipped."""
    entry: dict = {"caseId": case_id}
    if rust.get("status") != motoko.get("status"):
        entry["verdict"] = "disagreement"
        entry["category"] = ic.CAT_ACCEPTANCE
        entry["rustStatus"] = rust.get("status")
        entry["motokoStatus"] = motoko.get("status")
        return entry
    if rust["status"] == "rejected":
        same = rust.get("error") == motoko.get("error")
        entry["verdict"] = "match" if same else "disagreement"
        if not same:
            entry["category"] = ic.CAT_SYMBOLIC
            entry["rustError"] = rust.get("error")
            entry["motokoError"] = motoko.get("error")
        return entry

    r = ic.strip_diagnostic(rust["result"])
    m = ic.strip_diagnostic(motoko["result"])
    members = []
    for key in sorted(set(r) | set(m)):
        if key not in r or key not in m:
            members.append({"member": key, "verdict": "notExposed"})
            continue
        same = r[key] == m[key]
        record = {"member": key, "verdict": "match" if same else "mismatch"}
        if not same:
            record["rust"] = r[key]
            record["motoko"] = m[key]
        members.append(record)
    bad = [m2 for m2 in members if m2["verdict"] in ("mismatch", "notExposed")]
    entry["verdict"] = "disagreement" if bad else "match"
    entry["members"] = members
    return entry


def materialize_migration(contact: dict, dids_by_ref: dict[str, str]) -> dict:
    """Replaces {"identityRef": name} migration values with the DID the
    SAME participant derived for that identity (CHALLENGES.md step 2)."""
    contact = json.loads(json.dumps(contact))
    migration = contact.get("migration")
    if migration:
        for side in ("predecessor", "successor"):
            value = migration.get(side)
            if isinstance(value, dict) and "identityRef" in value:
                migration[side] = dids_by_ref[value["identityRef"]]
    return contact


def coordinator_derivations(challenges: dict) -> dict[str, dict]:
    """Independent coordinator-side derivation of the deterministic
    challenge outputs using the bundle's own stdlib interopkit — computed
    in this coordinator session only, never shown to a participant."""
    sys.path.insert(0, str(ic.bundle_verify_dir()))
    try:
        from interopkit import ed25519, published  # type: ignore

        out: dict[str, dict] = {}
        identities = {}
        for case in challenges["identities"]["cases"]:
            ref = case["id"].removeprefix("challenge-identity-")
            identity = published.derive_identity(
                bytes.fromhex(case["input"]["rootSeedHex"]),
                bytes.fromhex(case["input"]["revocationSeedHex"]),
            )
            identities[ref] = {"identity": identity, "seeds": case["input"]}
            out[case["id"]] = identity
        dids_by_ref = {ref: v["identity"]["did"] for ref, v in identities.items()}
        for case in challenges["records"]["cases"]:
            entry = identities[case["identityRef"]]
            contact = materialize_migration(case["input"]["contact"], dids_by_ref)
            body = published.build_record_body(
                entry["identity"],
                case["input"]["authority"],
                int(case["input"]["timestampMs"]),
                contact,
                valid_until_ms=(
                    None
                    if case["input"]["validUntilMs"] is None
                    else int(case["input"]["validUntilMs"])
                ),
                extensions=case["input"]["extensions"] or None,
            )
            structure = published.sig_structure(body)
            seed = bytes.fromhex(
                entry["seeds"][
                    "rootSeedHex"
                    if case["input"]["signingSeed"] == "root"
                    else "revocationSeedHex"
                ]
            )
            signature = ed25519.sign(seed, structure)
            out[case["id"]] = {
                "did": entry["identity"]["did"],
                "recordBodyCborHex": body.hex(),
                "recordBodyDigestHex": published.sha256_hex(body),
                "sigStructureHex": structure.hex(),
                "signatureHex": signature.hex(),
                "envelopeHex": published.envelope(body, signature).hex(),
            }
        return out
    finally:
        sys.path.pop(0)


def compare_against_coordinator(
    case_id: str, participant: dict, derived: dict
) -> dict:
    """Participant-vs-coordinator comparison for derive/author cases."""
    entry: dict = {"caseId": case_id}
    if participant.get("status") != "accepted":
        entry["verdict"] = "disagreement"
        entry["category"] = ic.CAT_ACCEPTANCE
        entry["participantStatus"] = participant.get("status")
        return entry
    result = ic.strip_diagnostic(participant["result"])
    members = []
    for key, want in derived.items():
        if key not in result:
            members.append(
                {"member": key, "verdict": "notExposed", "category": ic.CAT_COVERAGE}
            )
            continue
        same = result[key] == want
        record = {"member": key, "verdict": "match" if same else "mismatch"}
        if not same:
            record["participant"] = result[key]
            record["coordinator"] = want
        members.append(record)
    mismatched = [m for m in members if m["verdict"] == "mismatch"]
    coverage = [m for m in members if m["verdict"] == "notExposed"]
    entry["verdict"] = (
        "disagreement"
        if mismatched
        else ("coverageLimitation" if coverage else "match")
    )
    entry["members"] = members
    return entry


def identity_case_id(ref: str) -> str:
    return f"challenge-identity-{ref}"


def cross_verification(
    challenges: dict,
    rust_by_id: dict[str, dict],
    motoko_by_id: dict[str, dict],
) -> dict:
    """Each implementation verifies the envelopes the other authored
    (ACCEPTANCE.md phase 2), live through its own production interface
    engine. Targets are the verifying side's own derived DIDs; the
    frozen-output DID comparison proves both sides derived the same DID
    for every challenge identity."""
    verify_now = challenges["records"]["verifyNowMs"]
    records = challenges["records"]["cases"]

    def did_for(by_id: dict[str, dict], ref: str) -> str:
        return by_id[identity_case_id(ref)]["result"]["did"]

    rust_lines = []
    motoko_lines = []
    for case in records:
        motoko_envelope = motoko_by_id[case["id"]]["result"]["envelopeHex"]
        rust_envelope = rust_by_id[case["id"]]["result"]["envelopeHex"]
        rust_lines.append(
            ic.request_line(
                case["id"] + "/cross",
                "verifyRecord",
                {
                    "targetDid": did_for(rust_by_id, case["identityRef"]),
                    "envelopeHex": motoko_envelope,
                    "nowMs": verify_now,
                },
            )
        )
        motoko_lines.append(
            ic.request_line(
                case["id"] + "/cross",
                "verifyRecord",
                {
                    "targetDid": did_for(motoko_by_id, case["identityRef"]),
                    "envelopeHex": rust_envelope,
                    "nowMs": verify_now,
                },
            )
        )
    rust_cross = {r["caseId"]: r for r in ic.run_rust(rust_lines)}
    motoko_cross = {r["caseId"]: r for r in ic.run_motoko(motoko_lines)}

    cases = []
    for case in records:
        cross_id = case["id"] + "/cross"
        rust_verdict = rust_cross[cross_id]
        motoko_verdict = motoko_cross[cross_id]
        own_digest = rust_by_id[case["id"]]["result"]["recordBodyDigestHex"]
        entry = {
            "caseId": case["id"],
            "rustVerifiesMotokoEnvelope": rust_verdict.get("status"),
            "motokoVerifiesRustEnvelope": motoko_verdict.get("status"),
            "digestsAgree": (
                rust_verdict.get("status") == "accepted"
                and motoko_verdict.get("status") == "accepted"
                and rust_verdict["result"]["recordBodyDigestHex"] == own_digest
                and motoko_verdict["result"]["recordBodyDigestHex"] == own_digest
            ),
        }
        entry["verdict"] = (
            "match"
            if entry["rustVerifiesMotokoEnvelope"] == "accepted"
            and entry["motokoVerifiesRustEnvelope"] == "accepted"
            and entry["digestsAgree"]
            else "disagreement"
        )
        cases.append(entry)
    return {"cases": cases, "raw": {"rust": rust_cross, "motoko": motoko_cross}}


def identity_ref_resolution(
    challenges: dict,
    by_id: dict[str, dict],
    participant: str,
    verify_id,
) -> list[dict]:
    """Verifies that every migration identityRef was materialized as the
    participant's own derived DID (visible in the verified record)."""
    findings = []
    for case in challenges["records"]["cases"]:
        migration = case["input"]["contact"].get("migration")
        if not migration:
            continue
        verified = by_id[verify_id(case["id"])]
        if verified.get("status") != "accepted":
            findings.append(
                {
                    "caseId": case["id"],
                    "participant": participant,
                    "verdict": "notVerifiable",
                }
            )
            continue
        seen = verified["result"]["record"]["contact"]["migration"]
        checks = {}
        for side in ("predecessor", "successor"):
            want = migration.get(side)
            if isinstance(want, dict):
                ref = want["identityRef"]
                expected_did = by_id[identity_case_id(ref)]["result"]["did"]
                checks[side] = {
                    "identityRef": ref,
                    "resolvedDid": seen.get(side),
                    "matchesOwnDerivation": seen.get(side) == expected_did,
                }
        findings.append(
            {
                "caseId": case["id"],
                "participant": participant,
                "checks": checks,
                "verdict": (
                    "match"
                    if all(c["matchesOwnDerivation"] for c in checks.values())
                    else "disagreement"
                ),
            }
        )
    return findings


def permutation_invariance(challenges: dict, by_id: dict[str, dict]) -> list[dict]:
    groups: dict[str, list[str]] = {}
    for case in challenges["selection"]["cases"]:
        if case.get("permutationOf"):
            groups.setdefault(case["permutationOf"], []).append(case["id"])
    findings = []
    for group, ids in sorted(groups.items()):
        outcomes = set()
        for case_id in ids:
            response = by_id[case_id]
            if response.get("status") == "accepted":
                outcomes.add(
                    (
                        response["result"].get("winnerRecordBodyDigestHex"),
                        response["result"].get("authorityState"),
                    )
                )
            else:
                outcomes.add(("<" + response.get("status", "?") + ">", None))
        findings.append(
            {
                "group": group,
                "permutations": len(ids),
                "invariant": len(outcomes) == 1,
                "outcomes": sorted(
                    [list(o) for o in outcomes], key=lambda x: (str(x[0]), str(x[1]))
                ),
            }
        )
    return findings


def run() -> dict:
    pins = ic.verify_pins()
    frozen_motoko_digest, motoko_by_id, motoko_order = load_frozen_motoko()
    rust_digests, rust_by_id, _rust_order = load_frozen_rust()

    challenges = {
        "identities": ic.load_challenge("challenge-identities"),
        "records": ic.load_challenge("challenge-records"),
        "selection": ic.load_challenge("challenge-selection"),
    }
    labels = label_alignment(challenges)
    # Every Motoko case id maps to exactly one frozen Rust case id.
    aligned: list[tuple[str, str]] = [
        (case_id, labels.get(case_id, case_id)) for case_id in motoko_order
    ]
    for motoko_id, rust_id in aligned:
        assert rust_id in rust_by_id, f"no frozen Rust response for {motoko_id}"

    derived = coordinator_derivations(challenges)

    report: dict = {
        "phase": 2,
        "pins": pins,
        "frozenOutputs": {
            "motokoBlindSha256": pins["motokoBlindChallengeSha256"],
            "motokoV092Sha256": pins["motokoV092ChallengeSha256"],
            "motokoV092R2Sha256": frozen_motoko_digest,
            "rustResponseFiles": rust_digests,
        },
        "labelAlignment": {
            "note": (
                "self-verify case labels are participant-local: Rust chose "
                "`<case>-verify`, Motoko `<case>/verify`; file ordering is "
                "grouped-by-operation versus interleaved. Labels are aligned "
                "here; no value is mapped."
            ),
            "mapping": labels,
        },
        "cases": [
            compare_pair(motoko_id, rust_by_id[rust_id], motoko_by_id[motoko_id])
            for motoko_id, rust_id in aligned
        ],
        "coordinatorComparison": {
            "rust": [
                compare_against_coordinator(case_id, rust_by_id[case_id], value)
                for case_id, value in derived.items()
            ],
            "motoko": [
                compare_against_coordinator(case_id, motoko_by_id[case_id], value)
                for case_id, value in derived.items()
            ],
        },
        "identityRefResolution": {
            "rust": identity_ref_resolution(
                challenges, rust_by_id, "rust", lambda cid: cid + "-verify"
            ),
            "motoko": identity_ref_resolution(
                challenges, motoko_by_id, "motoko", lambda cid: cid + "/verify"
            ),
        },
        "permutationInvariance": {
            "rust": permutation_invariance(challenges, rust_by_id),
            "motoko": permutation_invariance(challenges, motoko_by_id),
        },
    }
    cross = cross_verification(challenges, rust_by_id, motoko_by_id)
    report["crossVerification"] = cross["cases"]
    (ic.WORK_DIR / "phase2" / "cross-verification-raw.json").write_text(
        ic.canonical_json(cross["raw"])
    )

    def tally(entries: list[dict]) -> dict:
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
        return counts

    ops = {
        "deriveIdentity": [],
        "authorRecord": [],
        "verifyRecord": [],
        "selectCurrent": [],
    }
    for motoko_id, _ in aligned:
        entry = next(c for c in report["cases"] if c["caseId"] == motoko_id)
        if motoko_id.startswith("challenge-identity-"):
            ops["deriveIdentity"].append(entry)
        elif motoko_id.endswith("/verify"):
            ops["verifyRecord"].append(entry)
        elif motoko_id.startswith("challenge-select-"):
            ops["selectCurrent"].append(entry)
        else:
            ops["authorRecord"].append(entry)
    report["totals"] = {
        "motokoVsRust": tally(report["cases"]),
        "byOperation": {op: tally(entries) for op, entries in ops.items()},
        "rustVsCoordinator": tally(report["coordinatorComparison"]["rust"]),
        "motokoVsCoordinator": tally(report["coordinatorComparison"]["motoko"]),
        "crossVerification": tally(report["crossVerification"]),
    }
    return report


if __name__ == "__main__":
    report = run()
    ic.write_result(ic.WORK_DIR / "phase2" / "phase2-report.json", report)
    print("frozen motoko r2 sha256:", report["frozenOutputs"]["motokoV092R2Sha256"])
    for name, value in report["totals"].items():
        print(name, json.dumps(value))
    pi = report["permutationInvariance"]
    print(
        "permutation invariance:",
        all(g["invariant"] for g in pi["rust"]),
        all(g["invariant"] for g in pi["motoko"]),
    )
