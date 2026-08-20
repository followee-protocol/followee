"""Phase 1 — published and specification-determined vectors (v0.9.2-r2).

Executes every interface-contract case in `coordinator/expected/`
(identities, records, verification — including every negative,
target-DID variant, and the four v0.9.2-r2 direct-wire present-empty
cases — timestamps, selection with every enumerated permutation, and
the complete v0.9.2 publish-response matrix) through both frozen
participants' production neutral-interface engines, and compares every
result member exactly against the bundle expectation.

Each participant is compared against the bundle expectation
independently; agreement with one participant is never treated as
evidence for the other. Per-member provenance distinguishes literally
published members (`normative-specification`) from coordinator-derived
`specification-determined` members using the bundle's
`publishedMembers` markings.
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
            "envelopeHex": vectors.verification_envelope_hex(case),
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
                "directWire": "envelopeHex" in case["input"],
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

    for case in vectors.files["publish-responses"]["cases"]:
        cases.append(
            {
                "file": "publish-responses",
                "id": case["id"],
                "operation": "receivePublishResponse",
                "input": case["input"],
                "expected": case["expected"],
                "publishedMembers": case.get("publishedMembers", []),
            }
        )

    return cases


def outcome_of(response: dict) -> str:
    return response.get("status", "error")


def compare_case(case: dict, response: dict) -> dict:
    """Compares one participant response against the bundle expectation."""
    expected = case["expected"]
    result: dict = {
        "caseId": case["id"],
        "file": case["file"],
        "operation": case["operation"],
    }
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

    # Accepted-path member comparison (includes the complete v0.9.2-r2
    # `record` projection where the expectation carries it).
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


CROSS_MEMBERS = (
    "envelopeHex",
    "recordBodyCborHex",
    "recordBodyDigestHex",
    "id",
    "timestampMs",
    "authority",
    "validUntilMs",
    "premature",
    "stale",
    "record",
)


def cross_compare_records(case: dict, rust: dict, motoko: dict) -> dict | None:
    """Cross-participant comparison of the full `verifyRecord` result.

    The v0.9.2-r2 interface contract pins the complete accepted-result
    shape, so the `record` member — descriptor, revocationKey, contact,
    extensions — is compared deep and exactly with no name mapping (the
    Campaign 1 I2 shape gap is closed)."""
    if case["operation"] != "verifyRecord":
        return None
    if rust.get("status") != "accepted" or motoko.get("status") != "accepted":
        return None
    r = ic.strip_diagnostic(rust["result"])
    m = ic.strip_diagnostic(motoko["result"])
    verdicts = []
    for member in CROSS_MEMBERS:
        same = r.get(member) == m.get(member)
        verdicts.append({"member": member, "verdict": "match" if same else "mismatch"})
    mismatches = [v for v in verdicts if v["verdict"] == "mismatch"]
    return {
        "caseId": case["id"],
        "verdict": "match" if not mismatches else "disagreement",
        "members": verdicts,
    }


def permutation_invariance(
    cases: list[dict], responses: dict[str, dict]
) -> list[dict]:
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


def run() -> dict:
    pins = ic.verify_pins()
    ic.run_bundle_verifier()
    vectors = ic.ExpectedVectors()
    cases = build_cases(vectors)
    lines = [
        ic.request_line(case["id"], case["operation"], case["input"])
        for case in cases
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
        "directWireCaseIds": [c["id"] for c in cases if c.get("directWire")],
        "permutationInvariance": {
            "rust": permutation_invariance(cases, rust_by_id),
            "motoko": permutation_invariance(cases, motoko_by_id),
        },
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
        return {
            "total": len(report["cases"]),
            "byVerdict": counts,
            "byOperation": by_operation,
        }

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
