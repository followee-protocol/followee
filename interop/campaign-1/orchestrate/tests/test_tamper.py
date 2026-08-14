"""Tamper-visibility tests for the coordinator comparison layer and the
adapter path: a deliberately altered participant output must remain
visible as a disagreement — the comparison layer must be unable to
absorb, normalize, or repair it.

Run: python3 -m unittest discover -s orchestrate/tests -t orchestrate
"""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import interop_common as ic
import phase1


def load_phase1_raw():
    raw = ic.WORK_DIR / "phase1"
    responses = {}
    for line in (raw / "motoko-responses.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            responses[r["caseId"]] = r
    return responses


class TamperVisibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = ic.ExpectedVectors()
        cls.cases = {c["id"]: c for c in phase1.build_cases(cls.vectors)}
        cls.responses = load_phase1_raw()

    def compare(self, case_id, response):
        return phase1.compare_case(self.cases[case_id], response)

    def test_baseline_matches(self):
        r = self.compare("verify-b4-accept", self.responses["verify-b4-accept"])
        self.assertEqual(r["verdict"], "match")

    def test_flipped_digest_member_is_a_disagreement(self):
        tampered = copy.deepcopy(self.responses["verify-b4-accept"])
        digest = tampered["result"]["recordBodyDigestHex"]
        tampered["result"]["recordBodyDigestHex"] = (
            ("0" if digest[0] != "0" else "1") + digest[1:]
        )
        r = self.compare("verify-b4-accept", tampered)
        self.assertEqual(r["verdict"], "disagreement")
        bad = [m for m in r["members"] if m["verdict"] == "mismatch"]
        self.assertEqual([m["member"] for m in bad], ["recordBodyDigestHex"])

    def test_accept_reject_flip_is_an_acceptance_disagreement(self):
        tampered = {
            "interfaceProtocol": "1",
            "caseId": "verify-b4-accept",
            "status": "rejected",
            "error": "invalidSignature",
        }
        r = self.compare("verify-b4-accept", tampered)
        self.assertEqual(r["verdict"], "disagreement")
        self.assertEqual(r["category"], ic.CAT_ACCEPTANCE)

    def test_swapped_symbolic_error_is_a_visible_symbolic_difference(self):
        tampered = copy.deepcopy(self.responses["verify-b10-duplicate-key"])
        tampered["error"] = "nonDeterministicCbor"
        r = self.compare("verify-b10-duplicate-key", tampered)
        self.assertEqual(r["verdict"], "disagreement")
        self.assertEqual(r["category"], ic.CAT_SYMBOLIC)

    def test_missing_member_is_never_silently_skipped(self):
        tampered = copy.deepcopy(self.responses["b4-root"])
        del tampered["result"]["signatureHex"]
        r = self.compare("b4-root", tampered)
        self.assertIn(r["verdict"], ("coverageLimitation", "disagreement"))
        bad = [m for m in r["members"] if m["verdict"] == "notExposed"]
        self.assertEqual([m["member"] for m in bad], ["signatureHex"])

    def test_selection_winner_tamper_is_visible(self):
        case_id = "select-authority-precedence-perm-00"
        tampered = copy.deepcopy(self.responses[case_id])
        tampered["result"]["authorityState"] = "root"
        r = self.compare(case_id, tampered)
        self.assertEqual(r["verdict"], "disagreement")

    def test_record_shape_mapping_cannot_absorb_value_changes(self):
        rust_like = {
            "protocolVersion": "1",
            "id": "did:flw:zX",
            "timestampMs": "1",
            "authority": "root",
            "authorityDescriptor": {
                "descriptorVersion": "1",
                "rootKey": {"suite": "-19", "publicKeyHex": "aa"},
                "revocationCommitmentHex": "bb",
            },
            "revocationKey": None,
            "validUntilMs": None,
            "contact": {"displayName": "x"},
            "extensions": {},
        }
        motoko_like = {
            "authorityDescriptor": {
                "descriptorVersion": "1",
                "rootPublicKeyHex": "aa",
                "revocationCommitmentHex": "bb",
            },
            "revocationPublicKeyHex": None,
            "contact": {"displayName": "x"},
            "extensions": {},
        }
        self.assertEqual(
            ic.map_rust_record_to_common_shape(rust_like),
            ic.map_motoko_record_to_rust_shape(motoko_like),
        )
        tampered = copy.deepcopy(motoko_like)
        tampered["authorityDescriptor"]["rootPublicKeyHex"] = "ab"
        self.assertNotEqual(
            ic.map_rust_record_to_common_shape(rust_like),
            ic.map_motoko_record_to_rust_shape(tampered),
        )
        tampered2 = copy.deepcopy(motoko_like)
        tampered2["contact"]["displayName"] = "y"
        self.assertNotEqual(
            ic.map_rust_record_to_common_shape(rust_like),
            ic.map_motoko_record_to_rust_shape(tampered2),
        )

    def test_diagnostic_members_are_the_only_excluded_data(self):
        value = {"a": "1", "diagnostic": {"x": "y"}, "nested": [{"diagnostic": {}}]}
        self.assertEqual(
            ic.strip_diagnostic(value), {"a": "1", "nested": [{}]}
        )


class MotokoDriverTamper(unittest.TestCase):
    """The phase-3 relay driver delegates every decision to the frozen
    Motoko production modules: a bit-flipped envelope must be rejected by
    production ingress — the driver/shim glue cannot admit or repair it."""

    def test_bit_flipped_envelope_is_rejected_by_production_ingress(self):
        motoko = {}
        for line in (ic.WORK_DIR / "phase1" / "motoko-responses.jsonl").read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                motoko[r["caseId"]] = r
        envelope = motoko["b4-root"]["result"]["envelopeHex"]
        did = motoko["b4-root"]["result"]["did"]
        # Flip one bit inside the signature region (last byte).
        tampered = envelope[:-2] + ("00" if envelope[-2:] != "00" else "01")
        out = ic.run_motoko_driver([
            f"publish t {did} {tampered} 1785589201123",
            f"publish t {did} {envelope} 1785589201123",
        ])
        self.assertEqual(out[0]["status"], 2, out[0])  # rejected
        self.assertEqual(out[0]["ingress"], {"rejected": "invalidSignature"})
        self.assertEqual(out[1]["status"], 0, out[1])  # the real one admits


class LiveAdapterTamper(unittest.TestCase):
    """End-to-end: altered *input* to the real Rust adapter changes its
    output (the adapter cannot be echoing stored expectations), and the
    altered output disagrees with the bundle expectation."""

    def test_bit_flipped_seed_produces_a_visible_disagreement(self):
        vectors = ic.ExpectedVectors()
        cases = {c["id"]: c for c in phase1.build_cases(vectors)}
        case = copy.deepcopy(cases["identity-alice"])
        tampered_input = dict(case["input"])
        tampered_input["rootSeedHex"] = "01" + tampered_input["rootSeedHex"][2:]
        [response] = ic.run_rust(
            [ic.request_line("identity-alice", "deriveIdentity", tampered_input)]
        )
        r = phase1.compare_case(case, response)
        self.assertEqual(r["verdict"], "disagreement")
        mismatched = {m["member"] for m in r["members"] if m["verdict"] == "mismatch"}
        self.assertIn("did", mismatched)
        self.assertIn("rootPublicKeyHex", mismatched)


if __name__ == "__main__":
    unittest.main()
