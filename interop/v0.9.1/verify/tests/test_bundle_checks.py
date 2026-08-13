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


if __name__ == "__main__":
    unittest.main()
