"""Tamper-visibility suite for the Campaign 2 comparison layer.

Every test deliberately alters participant output (or a comparison
input) and asserts the alteration remains visible as a disagreement —
the comparison layer must never absorb, repair, or normalize it. A live
input-sensitivity test per participant proves the interface engines
compute their answers rather than echoing expectations.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import interop_common as ic
import phase1
import phase2


def sample_verify_case() -> dict:
    vectors = ic.ExpectedVectors()
    cases = phase1.build_cases(vectors)
    return next(
        c for c in cases if c["operation"] == "verifyRecord" and c["id"] == "verify-b4-accept"
    )


def accepted_response_for(case: dict) -> dict:
    """A synthetic exact-match response built FROM the expectation (the
    tamper tests then mutate it; the untampered control must match)."""
    return {
        "interfaceProtocol": "1",
        "caseId": case["id"],
        "status": "accepted",
        "result": json.loads(json.dumps({k: v for k, v in case["expected"].items() if k != "outcome"})),
    }


class Phase1TamperVisibility(unittest.TestCase):
    def setUp(self):
        self.case = sample_verify_case()

    def test_untampered_control_matches(self):
        result = phase1.compare_case(self.case, accepted_response_for(self.case))
        self.assertEqual(result["verdict"], "match")

    def test_flipped_digest_is_a_disagreement(self):
        response = accepted_response_for(self.case)
        digest = response["result"]["recordBodyDigestHex"]
        response["result"]["recordBodyDigestHex"] = digest[:-1] + ("0" if digest[-1] != "0" else "1")
        result = phase1.compare_case(self.case, response)
        self.assertEqual(result["verdict"], "disagreement")

    def test_accept_reject_flip_is_a_disagreement(self):
        response = {"caseId": self.case["id"], "status": "rejected", "error": "signatureInvalid"}
        result = phase1.compare_case(self.case, response)
        self.assertEqual(result["verdict"], "disagreement")
        self.assertEqual(result["category"], ic.CAT_ACCEPTANCE)

    def test_deleted_member_stays_visible(self):
        response = accepted_response_for(self.case)
        del response["result"]["authority"]
        result = phase1.compare_case(self.case, response)
        self.assertEqual(result["verdict"], "coverageLimitation")

    def test_record_projection_presence_tamper_is_a_disagreement(self):
        # Reverting the r2 lossless projection (null -> []) must stay
        # visible: presence distinctions are part of the compared value.
        response = accepted_response_for(self.case)
        record = response["result"]["record"]
        self.assertIsNone(record["extensions"])
        record["extensions"] = {}
        result = phase1.compare_case(self.case, response)
        self.assertEqual(result["verdict"], "disagreement")

    def test_swapped_symbolic_error_is_a_disagreement(self):
        vectors = ic.ExpectedVectors()
        rejected = next(
            c
            for c in phase1.build_cases(vectors)
            if c["operation"] == "verifyRecord" and c["expected"].get("outcome") == "rejected"
        )
        want = rejected["expected"]["error"]
        other = "invalidCbor" if want != "invalidCbor" else "signatureInvalid"
        response = {"caseId": rejected["id"], "status": "rejected", "error": other}
        result = phase1.compare_case(rejected, response)
        self.assertEqual(result["verdict"], "disagreement")

    def test_publish_response_outcome_flip_is_a_disagreement(self):
        vectors = ic.ExpectedVectors()
        case = next(
            c
            for c in phase1.build_cases(vectors)
            if c["operation"] == "receivePublishResponse"
            and c["expected"]["outcome"] == "rejected"
        )
        response = {
            "caseId": case["id"],
            "status": "accepted",
            "result": {"status": "1", "errorCode": None},
        }
        result = phase1.compare_case(case, response)
        self.assertEqual(result["verdict"], "disagreement")


class Phase2TamperVisibility(unittest.TestCase):
    def frozen_pair(self, case_id: str):
        rust = json.loads(
            json.dumps(
                next(
                    json.loads(line)
                    for line in (
                        ic.RUST_REPO
                        / "interop"
                        / "v0.9.2"
                        / "outputs"
                        / "challenge-records.responses.ndjson"
                    ).read_text().splitlines()
                    if json.loads(line)["caseId"] == case_id
                )
            )
        )
        motoko = json.loads(
            json.dumps(
                next(
                    json.loads(line)
                    for line in (
                        ic.MOTOKO_REPO
                        / "outputs"
                        / "v0.9.2-r2"
                        / "challenge-results.jsonl"
                    ).read_text().splitlines()
                    if json.loads(line)["caseId"] == case_id
                )
            )
        )
        return rust, motoko

    def test_untampered_control_matches(self):
        rust, motoko = self.frozen_pair("challenge-carol-root-full")
        self.assertEqual(phase2.compare_pair("x", rust, motoko)["verdict"], "match")

    def test_bit_flipped_envelope_is_a_disagreement(self):
        rust, motoko = self.frozen_pair("challenge-carol-root-full")
        envelope = motoko["result"]["envelopeHex"]
        motoko["result"]["envelopeHex"] = envelope[:-1] + ("0" if envelope[-1] != "0" else "1")
        self.assertEqual(phase2.compare_pair("x", rust, motoko)["verdict"], "disagreement")

    def test_nulled_revocation_key_is_a_disagreement(self):
        # Frozen verify responses use participant-local labels: Rust
        # `challenge-carol-revoked-verify`, Motoko `…/verify`.
        rust = next(
            json.loads(line)
            for line in (
                ic.RUST_REPO
                / "interop"
                / "v0.9.2"
                / "outputs"
                / "challenge-verify.responses.ndjson"
            ).read_text().splitlines()
            if json.loads(line)["caseId"] == "challenge-carol-revoked-verify"
        )
        motoko = next(
            json.loads(line)
            for line in (
                ic.MOTOKO_REPO / "outputs" / "v0.9.2-r2" / "challenge-results.jsonl"
            ).read_text().splitlines()
            if json.loads(line)["caseId"] == "challenge-carol-revoked/verify"
        )
        self.assertEqual(phase2.compare_pair("x", rust, motoko)["verdict"], "match")
        motoko["result"]["record"]["revocationKey"] = None
        self.assertEqual(phase2.compare_pair("x", rust, motoko)["verdict"], "disagreement")

    def test_tampered_selection_winner_is_a_disagreement(self):
        rust = {"status": "accepted", "result": {"winnerRecordBodyDigestHex": "aa", "authorityState": "root"}}
        motoko = {"status": "accepted", "result": {"winnerRecordBodyDigestHex": "bb", "authorityState": "root"}}
        self.assertEqual(phase2.compare_pair("x", rust, motoko)["verdict"], "disagreement")


class LiveInputSensitivity(unittest.TestCase):
    """The engines hold no expected answers to echo: a bit-flipped input
    envelope changes the production answer."""

    @classmethod
    def setUpClass(cls):
        vectors = ic.ExpectedVectors()
        case = vectors.by_case["verification"]["verify-b4-accept"]
        cls.envelope = vectors.by_case["records"]["b4-root"]["expected"]["envelopeHex"]
        cls.input = {
            "targetDid": case["input"]["targetDid"],
            "envelopeHex": cls.envelope,
            "nowMs": case["input"]["nowMs"],
        }

    def tampered(self):
        flipped = self.envelope[:-1] + ("0" if self.envelope[-1] != "0" else "1")
        return {**self.input, "envelopeHex": flipped}

    def test_rust_engine_is_input_sensitive(self):
        lines = [
            ic.request_line("control", "verifyRecord", self.input),
            ic.request_line("tampered", "verifyRecord", self.tampered()),
        ]
        control, tampered = ic.run_rust(lines)
        self.assertEqual(control["status"], "accepted")
        self.assertEqual(tampered["status"], "rejected")

    def test_motoko_engine_is_input_sensitive(self):
        lines = [
            ic.request_line("control", "verifyRecord", self.input),
            ic.request_line("tampered", "verifyRecord", self.tampered()),
        ]
        control, tampered = ic.run_motoko(lines)
        self.assertEqual(control["status"], "accepted")
        self.assertEqual(tampered["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
