"""Phase 1 — published and specification-determined vectors.

Executes every interface-contract case in `coordinator/expected/`
(identities, records, verification, timestamps, selection; the
envelopes-negative cases are executed through the verification cases that
reference them) through both frozen participants' production-backed
neutral interfaces, and compares every result member exactly against the
bundle expectation.

Each participant is compared against the bundle expectation
independently; agreement with one participant is never treated as
evidence for the other. Per-member provenance distinguishes literally
published members (`normative-specification`) from coordinator-derived
`specification-determined` members using the bundle's `publishedMembers`
markings.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interop_common as ic


def build_cases(vectors: ic.ExpectedVectors) -> list[dict]:
    """The ordered phase 1 case list. Every case records the request to
    send, the expected members, and their published-member marking."""
    cases = []

    for case in vectors.files["identities"]["cases"]:
        cases.append(
            {
                "file": "identities",
                "id": case["id"],
                "operation": "deriveIdentity",
                "input": case["input"],
                "expected": case["expected"],
                "publishedMembers": case.get("publishedMembers", []),
            }
        )

    for case in vectors.files["records"]["cases"]:
        cases.append(
            {
                "file": "records",
                "id": case["id"],
                "operation": "authorRecord",
                "input": case["input"],
                "expected": case["expected"],
                "publishedMembers": case.get("publishedMembers", []),
            }
        )

    for case in vectors.files["verification"]["cases"]:
        request_input = {
            "targetDid": case["input"]["targetDid"],
            "envelopeHex": vectors.envelope_hex(case["input"]["envelope"]),
            "nowMs": case["input"]["nowMs"],
        }
        cases.append(
            {
                "file": "verification",
                "id": case["id"],
                "operation": "verifyRecord",
                "input": request_input,
                "expected": case["expected"],
                "publishedMembers": case.get("publishedMembers", []),
            }
        )

    for case in vectors.files["timestamps"]["cases"]:
        cases.append(
            {
                "file": "timestamps",
                "id": case["id"],
                "operation": "nextTimestamp",
                "input": case["input"],
                "expected": case["expected"],
                "publishedMembers": case.get("publishedMembers", []),
            }
        )

    for case in vectors.files["selection"]["cases"]:
        request_input = {
            "targetDid": case["input"]["targetDid"],
            "candidateEnvelopesHex": [
                vectors.envelope_hex(ref) for ref in case["input"]["candidates"]
            ],
            "nowMs": case["input"]["nowMs"],
            "stickyAuthority": case["input"]["stickyAuthority"],
        }
        cases.append(
            {
                "file": "selection",
                "id": case["id"],
                "operation": "selectCurrent",
                "input": request_input,
                "expected": case["expected"],
                "publishedMembers": case.get("publishedMembers", []),
                "permutationOf": case.get("permutationOf"),
            }
        )

    return cases


def outcome_of(response: dict) -> str:
    return response.get("status", "error")


def compare_case(case: dict, response: dict) -> dict:
    """Compares one participant response against the bundle expectation."""
    expected = case["expected"]
    result: dict = {"caseId": case["id"], "file": case["file"], "operation": case["operation"]}
    expected_outcome = expected.get("outcome", "accepted")
    actual_outcome = outcome_of(response)
    if actual_outcome == "error":
        result["verdict"] = "infrastructureError"
        result["response"] = response
        return result
    if expected_outcome == "accepted" and actual_outcome != "accepted":
        result["verdict"] = "disagreement"
        result["category"] = ic.CAT_ACCEPTANCE
        result["expectedOutcome"] = expected_outcome
        result["actual"] = response
        return result
    if expected_outcome == "rejected":
        if actual_outcome != "rejected":
            result["verdict"] = "disagreement"
            result["category"] = ic.CAT_ACCEPTANCE
            result["expectedOutcome"] = expected_outcome
            result["actual"] = response
            return result
        want_error = expected["error"]
        got_error = response.get("error")
        if want_error == got_error:
            result["verdict"] = "match"
            result["members"] = [
                {
                    "member": "error",
                    "verdict": "match",
                    "provenance": (
                        "normative-specification"
                        if "error" in (case.get("publishedMembers") or [])
                        or "expectedError" in (case.get("publishedMembers") or [])
                        else "specification-determined"
                    ),
                }
            ]
        else:
            result["verdict"] = "disagreement"
            result["category"] = ic.CAT_SYMBOLIC
            result["expectedError"] = want_error
            result["actualError"] = got_error
        return result

    # Accepted-path member comparison.
    members = ic.compare_members(
        {k: v for k, v in expected.items() if k != "outcome"},
        response.get("result", {}),
        case.get("publishedMembers") or [],
    )
    not_exposed = [m for m in members if m["verdict"] == "notExposed"]
    mismatched = [m for m in members if m["verdict"] == "mismatch"]
    if mismatched:
        result["verdict"] = "disagreement"
        result["category"] = ic.CAT_SYMBOLIC
    elif not_exposed:
        result["verdict"] = "coverageLimitation"
        result["category"] = ic.CAT_COVERAGE
    else:
        result["verdict"] = "match"
    result["members"] = members
    return result


def cross_compare_records(case: dict, rust: dict, motoko: dict) -> dict | None:
    """Cross-participant comparison of the full `verifyRecord` result,
    including the `record` member under the documented shape mapping."""
    if case["operation"] != "verifyRecord":
        return None
    if rust.get("status") != "accepted" or motoko.get("status") != "accepted":
        return None
    r = ic.strip_diagnostic(rust["result"])
    m = ic.strip_diagnostic(motoko["result"])
    verdicts = []
    for member in (
        "envelopeHex",
        "recordBodyCborHex",
        "recordBodyDigestHex",
        "id",
        "timestampMs",
        "authority",
        "validUntilMs",
        "premature",
        "stale",
    ):
        same = r.get(member) == m.get(member)
        verdicts.append(
            {"member": member, "verdict": "match" if same else "mismatch"}
        )
    record_same = ic.map_rust_record_to_common_shape(
        r["record"]
    ) == ic.map_motoko_record_to_rust_shape(m["record"])
    verdicts.append(
        {
            "member": "record",
            "verdict": "match" if record_same else "mismatch",
            "note": (
                "compared under the documented interface-shape mapping; the "
                "descriptor sub-shape of INTERFACE.md is unspecified and the "
                "participants chose different member names"
            ),
            "category": ic.CAT_SHAPE,
        }
    )
    mismatches = [v for v in verdicts if v["verdict"] == "mismatch"]
    return {
        "caseId": case["id"],
        "verdict": "match" if not mismatches else "disagreement",
        "members": verdicts,
    }


def permutation_invariance(cases: list[dict], responses: dict[str, dict]) -> list[dict]:
    """Per participant: every permutation of one group selects one winner."""
    groups: dict[str, list[str]] = {}
    for case in cases:
        if case.get("permutationOf"):
            groups.setdefault(case["permutationOf"], []).append(case["id"])
    findings = []
    for group, ids in sorted(groups.items()):
        outcomes = set()
        for case_id in ids:
            response = responses[case_id]
            if response.get("status") == "accepted":
                result = response["result"]
                outcomes.add(
                    (
                        result.get("winnerRecordBodyDigestHex"),
                        result.get("authorityState"),
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


def multihash_analysis(vectors: ic.ExpectedVectors, rust_responses: dict[str, dict]) -> list[dict]:
    """Coordinator-side analysis for the Rust `multihashHex` coverage
    limitation: checks that the expected multihash base58btc-encodes to
    exactly the DID the Rust production path returned. This is coordinator
    verification tooling, not participant output."""
    findings = []
    for case in vectors.files["identities"]["cases"]:
        response = rust_responses.get(case["id"])
        if not response or response.get("status") != "accepted":
            continue
        expected_multihash = case["expected"]["multihashHex"]
        rust_did = response["result"]["did"]
        encoded = "did:flw:z" + ic.base58btc_encode(bytes.fromhex(expected_multihash))
        findings.append(
            {
                "caseId": case["id"],
                "expectedMultihashHex": expected_multihash,
                "rustDid": rust_did,
                "expectedMultihashEncodesToRustDid": encoded == rust_did,
            }
        )
    return findings


def run() -> dict:
    pins = ic.verify_pins()
    vectors = ic.ExpectedVectors()
    cases = build_cases(vectors)
    lines = [
        ic.request_line(case["id"], case["operation"], case["input"]) for case in cases
    ]

    rust_responses = ic.run_rust(lines)
    motoko_responses = ic.run_motoko(lines)
    rust_by_id = {r["caseId"]: r for r in rust_responses}
    motoko_by_id = {r["caseId"]: r for r in motoko_responses}
    assert len(rust_by_id) == len(cases) and len(motoko_by_id) == len(cases)

    raw_dir = ic.WORK_DIR / "phase1"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "requests.jsonl").write_text("\n".join(lines) + "\n")
    (raw_dir / "rust-responses.jsonl").write_text(
        "\n".join(ic.canonical_json_line(r) for r in rust_responses) + "\n"
    )
    (raw_dir / "motoko-responses.jsonl").write_text(
        "\n".join(ic.canonical_json_line(r) for r in motoko_responses) + "\n"
    )

    report = {
        "phase": 1,
        "pins": pins,
        "cases": [],
        "crossVerifyRecord": [],
        "permutationInvariance": {
            "rust": permutation_invariance(cases, rust_by_id),
            "motoko": permutation_invariance(cases, motoko_by_id),
        },
        "rustMultihashCoverageAnalysis": multihash_analysis(vectors, rust_by_id),
    }
    for case in cases:
        entry = {
            "caseId": case["id"],
            "file": case["file"],
            "operation": case["operation"],
            "rust": compare_case(case, rust_by_id[case["id"]]),
            "motoko": compare_case(case, motoko_by_id[case["id"]]),
        }
        report["cases"].append(entry)
        cross = cross_compare_records(
            case, rust_by_id[case["id"]], motoko_by_id[case["id"]]
        )
        if cross:
            report["crossVerifyRecord"].append(cross)

    def tally(side: str) -> dict:
        counts: dict[str, int] = {}
        by_operation: dict[str, dict[str, int]] = {}
        for entry in report["cases"]:
            verdict = entry[side]["verdict"]
            counts[verdict] = counts.get(verdict, 0) + 1
            op = entry["operation"]
            by_operation.setdefault(op, {})
            by_operation[op][verdict] = by_operation[op].get(verdict, 0) + 1
        return {"total": len(report["cases"]), "byVerdict": counts, "byOperation": by_operation}

    report["totals"] = {"rust": tally("rust"), "motoko": tally("motoko")}
    return report


if __name__ == "__main__":
    report = run()
    ic.write_result(ic.WORK_DIR / "phase1" / "phase1-report.json", report)
    totals = report["totals"]
    print("phase1 rust:", totals["rust"]["byVerdict"])
    print("phase1 motoko:", totals["motoko"]["byVerdict"])
    cross_bad = [c for c in report["crossVerifyRecord"] if c["verdict"] != "match"]
    print("cross verifyRecord mismatches:", len(cross_bad))
    pi = report["permutationInvariance"]
    print(
        "permutation invariance:",
        all(g["invariant"] for g in pi["rust"]),
        all(g["invariant"] for g in pi["motoko"]),
    )
