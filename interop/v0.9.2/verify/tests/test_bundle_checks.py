"""Integration tests: bundle checks pass on the real bundle and fail on
tampered copies."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import verify_bundle  # noqa: E402


def real_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class PassesOnRealBundle(unittest.TestCase):
    def test_all_checks_pass(self):
        root = real_root()
        for name, fn in verify_bundle.CHECKS:
            fn(root)  # raises Failure on regression


class TamperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "bundle"
        shutil.copytree(
            real_root(), self.root,
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_manifest_detects_added_file(self):
        (self.root / "stray.txt").write_text("stray\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_manifest(self.root)

    def test_manifest_detects_content_change(self):
        path = self.root / "README.md"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_manifest(self.root)

    def test_spec_tamper_detected(self):
        path = self.root / "authoring" / "specification" / "Followee-Specification.md"
        path.write_bytes(path.read_bytes().replace(b"Followee", b"F0llowee", 1))
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_spec(self.root)

    def test_vector_tamper_detected(self):
        path = (self.root / "authoring" / "vectors" / "published" /
                "records.json")
        doc = json.loads(path.read_text())
        doc["cases"][0]["expected"]["signatureHex"] = "00" * 64
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_published_regeneration(self.root)

    def test_coordinator_vector_tamper_detected(self):
        path = self.root / "coordinator" / "expected" / "selection.json"
        doc = json.loads(path.read_text())
        doc["cases"][0]["expected"]["winnerRecordBodyDigestHex"] = "11" * 32
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_published_regeneration(self.root)

    def test_leak_of_coordinator_value_detected(self):
        expected = json.loads(
            (self.root / "coordinator" / "expected" / "records.json").read_text())
        b6a = next(c for c in expected["cases"] if c["id"] == "b6-alice-a")
        leaked = b6a["expected"]["envelopeHex"]
        path = self.root / "authoring" / "AUTHORING.md"
        path.write_text(path.read_text() + f"\nExample: {leaked}\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_leakproof(self.root)

    def test_authoring_member_beyond_coordinator_detected(self):
        path = (self.root / "authoring" / "vectors" / "published" /
                "identities.json")
        doc = json.loads(path.read_text())
        doc["cases"][0]["expected"]["extraMember"] = "surprise"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_authoring_projection(self.root)

    def test_transcript_body_tamper_detected(self):
        path = self.root / "coordinator" / "transcripts" / "changes-sync.json"
        doc = json.loads(path.read_text())
        body = doc["response"]["bodyHex"]
        doc["response"]["bodyHex"] = ("0" if body[0] != "0" else "1") + body[1:]
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_transcripts(self.root)

    def test_premature_gate_entry_tamper_detected(self):
        transcripts = self.root / "coordinator" / "transcripts"
        other = json.loads(
            (transcripts / "changes-initial-enumeration.json").read_text())
        path = transcripts / "changes-premature-retained.json"
        doc = json.loads(path.read_text())
        doc["response"]["bodyHex"] = other["response"]["bodyHex"]
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_campaign_gates(self.root)

    def test_oversized_publish_length_tamper_detected(self):
        transcripts = self.root / "coordinator" / "transcripts"
        other = json.loads((transcripts / "publish-admit.json").read_text())
        path = transcripts / "publish-record-too-large.json"
        doc = json.loads(path.read_text())
        doc["request"]["bodyHex"] = other["request"]["bodyHex"]
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_campaign_gates(self.root)

    def test_hostile_info_fault_isolation_tamper_detected(self):
        # Restoring version 1 to the missing-version probe removes the
        # documented fault entirely.
        transcripts = self.root / "coordinator" / "transcripts"
        other = json.loads((transcripts / "info.json").read_text())
        path = transcripts / "info-missing-version.json"
        doc = json.loads(path.read_text())
        doc["response"]["bodyHex"] = other["response"]["bodyHex"]
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_campaign_gates(self.root)

    def test_acceptance_gate_text_tamper_detected(self):
        path = self.root / "ACCEPTANCE.md"
        text = path.read_text()
        path.write_text(text.replace("Pre-Phase-3 gates", "notes"))
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_campaign_gates(self.root)

    def test_never_issued_cursor_input_detected(self):
        from interopkit import cbor
        transcripts = self.root / "coordinator" / "transcripts"
        path = transcripts / "changes-reset-required.json"
        doc = json.loads(path.read_text())
        forged = cbor.encode({0: 1, 1: b"never-issued-pos", 2: 100,
                              3: 1048576})
        doc["request"]["bodyHex"] = forged.hex()
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_campaign_gates(self.root)

    def test_forging_prohibition_text_tamper_detected(self):
        path = self.root / "ACCEPTANCE.md"
        text = path.read_text()
        path.write_text(text.replace("cursor forging, cursor injection",
                                     "cursor tricks"))
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_campaign_gates(self.root)

    def test_watermark_language_reintroduction_detected(self):
        path = self.root / "ACCEPTANCE.md"
        text = path.read_text()
        path.write_text(text + "\nProbe positions beyond the visibility "
                        "watermark MUST be rejected.\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_campaign_gates(self.root)

    def test_challenge_expected_output_detected(self):
        path = (self.root / "authoring" / "vectors" / "challenge" /
                "challenge-records.json")
        doc = json.loads(path.read_text())
        doc["cases"][0]["expected"] = {"recordBodyDigestHex": "00" * 32}
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_challenges(self.root)

    def test_challenge_published_seed_detected(self):
        path = (self.root / "authoring" / "vectors" / "challenge" /
                "challenge-identities.json")
        doc = json.loads(path.read_text())
        doc["cases"][0]["input"]["rootSeedHex"] = (
            "000102030405060708090a0b0c0d0e0f"
            "101112131415161718191a1b1c1d1e1f")
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_challenges(self.root)

    def test_authoring_hygiene_detects_implementation_reference(self):
        path = self.root / "authoring" / "AUTHORING.md"
        path.write_text(path.read_text() + "\nSee the followee-rs sources.\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_authoring_hygiene(self.root)

    def test_appendix_b_tamper_detected(self):
        path = (self.root / "authoring" / "specification" /
                "Followee-Specification.md")
        text = path.read_text()
        index = text.find(verify_bundle.APPENDIX_B_HEADING)
        assert index > 0
        path.write_text(text[:index] + text[index:].replace(
            "test vectors", "test vect0rs", 1))
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_appendix_b(self.root)

    def test_challenge_input_replacement_detected(self):
        path = (self.root / "authoring" / "vectors" / "challenge" /
                "challenge-identities.json")
        doc = json.loads(path.read_text())
        doc["description"] = (doc.get("description") or "") + " altered"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_challenge_preservation(self.root)

    def test_publish_response_flipped_outcome_detected(self):
        path = (self.root / "coordinator" / "expected" /
                "publish-responses.json")
        doc = json.loads(path.read_text())
        case = next(c for c in doc["cases"]
                    if c["id"] == "publish-reject-status-1-invalidSignature")
        case["expected"] = {"outcome": "accepted", "status": "1",
                            "errorCode": "9"}
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_publish_responses(self.root)

    def test_publish_response_no_change_code_on_status_2_detected(self):
        path = (self.root / "coordinator" / "expected" /
                "publish-responses.json")
        doc = json.loads(path.read_text())
        case = next(c for c in doc["cases"]
                    if c["id"] == "publish-reject-status-2-duplicate")
        case["expected"] = {"outcome": "accepted", "status": "2",
                            "errorCode": "13"}
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_publish_responses(self.root)

    def test_publish_response_normalized_variation_detected(self):
        # Normalizing the coded status-1 form into the bare form must be
        # visible: the byte-distinctness rule fails.
        path = (self.root / "coordinator" / "expected" /
                "publish-responses.json")
        doc = json.loads(path.read_text())
        bare = next(c for c in doc["cases"]
                    if c["id"] == "publish-accept-status-1-bare")
        coded = next(c for c in doc["cases"]
                     if c["id"] == "publish-accept-status-1-duplicate")
        coded["input"]["responseHex"] = bare["input"]["responseHex"]
        coded["expected"]["errorCode"] = None
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_publish_responses(self.root)

    def test_publish_response_missing_per_code_case_detected(self):
        path = (self.root / "coordinator" / "expected" /
                "publish-responses.json")
        doc = json.loads(path.read_text())
        doc["cases"] = [c for c in doc["cases"]
                        if c["id"] != "publish-reject-status-1-rateLimited"]
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_publish_responses(self.root)

    def test_unregistered_probe_flipped_to_accepted_detected(self):
        path = (self.root / "coordinator" / "expected" /
                "publish-responses.json")
        doc = json.loads(path.read_text())
        case = next(c for c in doc["cases"]
                    if c["id"] == "publish-reject-status-2-unregistered-20")
        case["expected"] = {"outcome": "accepted", "status": "2",
                            "errorCode": "20"}
        del case["requiredBehaviour"]
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_publish_responses(self.root)

    def test_deleted_unregistered_probe_family_detected(self):
        path = (self.root / "coordinator" / "expected" /
                "publish-responses.json")
        doc = json.loads(path.read_text())
        doc["cases"] = [c for c in doc["cases"]
                        if "unregistered" not in c["id"]]
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_publish_responses(self.root)

    def test_authoring_seal_interface_tamper_detected(self):
        path = self.root / "authoring" / "interface" / "INTERFACE.md"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_authoring_seal(self.root)

    def test_historical_seal_removal_detected(self):
        path = self.root / "coordinator" / "PRECLASSIFICATION.md"
        text = path.read_text()
        path.write_text(text.replace(
            verify_bundle.AUTHORING_AGGREGATE_SHA256_R1, "0" * 64))
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_authoring_seal(self.root)

    def test_wire_fixture_signature_tamper_detected(self):
        path = (self.root / "coordinator" / "expected" /
                "verification.json")
        doc = json.loads(path.read_text())
        case = next(c for c in doc["cases"]
                    if c["id"] == "verify-wire-empty-alsoKnownAs")
        body = case["input"]["envelopeHex"]
        case["input"]["envelopeHex"] = body[:-2] + (
            "00" if body[-2:] != "00" else "01")
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_present_empty_wire_fixtures(self.root)

    def test_wire_fixture_normalized_projection_detected(self):
        # Normalizing the present-empty [] into null in the expected
        # projection must be visible: the distinction rule fails.
        path = (self.root / "coordinator" / "expected" /
                "verification.json")
        doc = json.loads(path.read_text())
        case = next(c for c in doc["cases"]
                    if c["id"] == "verify-wire-empty-alsoKnownAs")
        case["expected"]["record"]["contact"]["alsoKnownAs"] = None
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_present_empty_wire_fixtures(self.root)

    def test_wire_fixture_missing_case_detected(self):
        path = (self.root / "coordinator" / "expected" /
                "verification.json")
        doc = json.loads(path.read_text())
        doc["cases"] = [c for c in doc["cases"]
                        if c["id"] != "verify-wire-empty-collections-combined"]
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_present_empty_wire_fixtures(self.root)

    def test_coordinator_case_id_leak_detected(self):
        path = self.root / "authoring" / "NONDETERMINISM.md"
        path.write_text(path.read_text() +
                        "\nSee publish-accept-status-1-duplicate.\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_coordinator_case_id_leak(self.root)

    def test_authoring_counterpart_of_coordinator_only_file_detected(self):
        path = (self.root / "authoring" / "vectors" / "published" /
                "publish-responses.json")
        path.write_text("{}\n")
        with self.assertRaises(verify_bundle.Failure):
            verify_bundle.check_coordinator_case_id_leak(self.root)


if __name__ == "__main__":
    unittest.main()
