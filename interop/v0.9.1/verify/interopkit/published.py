"""Builds the vectors/published/*.json content from the pinned specification.

Every produced value is either extracted verbatim from Appendix B of the
pinned Followee specification or reconstructed from published inputs by
the normative deterministic algorithms (deterministic CBOR, SHA-256,
base58btc multihash, RFC 8032 deterministic Ed25519) and asserted equal
to the published bytes, lengths, and digests wherever the specification
states them. Construction failure raises instead of emitting a vector.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import base58, cbor, ed25519
from .spec import (
    AAD,
    DESCRIPTOR_PREFIX,
    PROTECTED_HEADER,
    REVOCATION_PREFIX,
    SPEC_SHA256,
    SpecText,
)

BUNDLE = "followee-interop/v0.9.1"
MAX_FUTURE_SKEW_MS = 300000
U64_MAX = 2**64 - 1

_CONTACT_LABELS = (
    ("displayName", 0),
    ("summary", 1),
    ("avatar", 2),
    ("alsoKnownAs", 3),
    ("services", 4),
    ("migration", 5),
    ("extensions", 6),
)
_SERVICE_LABELS = (
    ("id", 0),
    ("type", 1),
    ("endpoint", 2),
    ("mediaType", 3),
    ("label", 4),
    ("language", 5),
    ("rel", 6),
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_key_map(pub: bytes) -> dict:
    return {0: -19, 1: pub}


def derive_identity(root_seed: bytes, revocation_seed: bytes) -> dict:
    root_pub = ed25519.public_key(root_seed)
    rev_pub = ed25519.public_key(revocation_seed)
    rev_cbor = cbor.encode(public_key_map(rev_pub))
    commitment = hashlib.sha256(REVOCATION_PREFIX + rev_cbor).digest()
    descriptor = cbor.encode({0: 1, 1: public_key_map(root_pub), 2: commitment})
    digest = hashlib.sha256(DESCRIPTOR_PREFIX + descriptor).digest()
    multihash = b"\x12\x20" + digest
    did = "did:flw:z" + base58.encode(multihash)
    return {
        "rootPublicKeyHex": root_pub.hex(),
        "revocationPublicKeyHex": rev_pub.hex(),
        "revocationPublicKeyCborHex": rev_cbor.hex(),
        "revocationCommitmentHex": commitment.hex(),
        "authorityDescriptorCborHex": descriptor.hex(),
        "authorityDescriptorDigestHex": digest.hex(),
        "multihashHex": multihash.hex(),
        "did": did,
    }


def _typed_value_to_cbor(value: dict) -> object:
    """Convert one typed extension value (INTERFACE.md convention) to CBOR."""
    kind = value["type"]
    if kind in ("uint", "nint"):
        return int(value["value"])
    if kind == "text":
        return value["value"]
    if kind == "bytes":
        return bytes.fromhex(value["hex"])
    if kind == "bool":
        return bool(value["value"])
    if kind == "null":
        return None
    if kind == "array":
        return [_typed_value_to_cbor(item) for item in value["items"]]
    if kind == "map":
        return {
            _typed_value_to_cbor(entry["key"]): _typed_value_to_cbor(entry["value"])
            for entry in value["entries"]
        }
    raise ValueError(f"unknown typed value kind: {kind}")


def _extension_value_to_cbor(extensions: dict) -> dict:
    return {
        uri: _typed_value_to_cbor(value) for uri, value in extensions.items()
    }


def contact_to_map(contact: dict) -> dict:
    out: dict = {}
    for name, label in _CONTACT_LABELS:
        value = contact.get(name)
        if value in (None, {}, []):
            continue
        if name == "services":
            services = []
            for service in value:
                smap = {}
                for sname, slabel in _SERVICE_LABELS:
                    svalue = service.get(sname)
                    if svalue is None:
                        continue
                    smap[slabel] = svalue
                services.append(smap)
            out[label] = services
        elif name == "migration":
            migration = {}
            if value.get("predecessor") is not None:
                migration[0] = value["predecessor"]
            if value.get("successor") is not None:
                migration[1] = value["successor"]
            out[label] = migration
        elif name == "extensions":
            out[label] = _extension_value_to_cbor(value)
        else:
            out[label] = value
    return out


def build_record_body(
    identity: dict, authority: str, timestamp_ms: int, contact: dict,
    valid_until_ms: int | None = None, extensions: dict | None = None,
) -> bytes:
    body: dict = {
        0: 1,
        1: identity["did"],
        2: timestamp_ms,
        3: 0 if authority == "root" else 1,
        4: cbor.decode_strict(bytes.fromhex(identity["authorityDescriptorCborHex"])),
        7: contact_to_map(contact),
    }
    if authority == "rootRevoked":
        body[5] = public_key_map(bytes.fromhex(identity["revocationPublicKeyHex"]))
    if valid_until_ms is not None:
        body[6] = valid_until_ms
    if extensions:
        body[8] = _extension_value_to_cbor(extensions)
    return cbor.encode(body)


def sig_structure(body: bytes) -> bytes:
    return cbor.encode(["Signature1", PROTECTED_HEADER, AAD, body])


def envelope(body: bytes, signature: bytes) -> bytes:
    return cbor.encode_tagged(
        18, cbor.encode([PROTECTED_HEADER, {}, body, signature])
    )


def author(identity: dict, seeds: dict, authority: str, timestamp_ms: int,
           contact: dict, signing_seed: str,
           valid_until_ms: int | None = None) -> dict:
    body = build_record_body(identity, authority, timestamp_ms, contact,
                             valid_until_ms)
    structure = sig_structure(body)
    seed = bytes.fromhex(seeds[signing_seed])
    signature = ed25519.sign(seed, structure)
    if not ed25519.verify(ed25519.public_key(seed), structure, signature):
        raise AssertionError("self-verification failed")
    return {
        "did": identity["did"],
        "recordBodyCborHex": body.hex(),
        "recordBodyDigestHex": sha256_hex(body),
        "sigStructureHex": structure.hex(),
        "signatureHex": signature.hex(),
        "envelopeHex": envelope(body, signature).hex(),
    }


def _require(label: str, actual: object, published: object) -> None:
    if actual != published:
        raise AssertionError(
            f"{label}: constructed value does not reproduce the published "
            f"specification value\n  constructed: {actual}\n  published:   {published}"
        )


def _spec_note() -> dict:
    return {
        "bundle": BUNDLE,
        "source": "authoring/specification/Followee-Specification.md",
        "sourceSha256": SPEC_SHA256,
    }


def _identity_inputs() -> dict:
    return {
        "alice": {
            "root": "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
            "revocation": "202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f",
        },
        "attacker": {
            "root": "404142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f",
            "revocation": "606162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f",
        },
        "bob": {
            "root": "808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f",
            "revocation": "a0a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebf",
        },
    }


ALICE_CONTACT = {
    "displayName": "Alice Example",
    "summary": "Writer",
    "avatar": None,
    "alsoKnownAs": ["acct:alice@example.com"],
    "services": [
        {
            "id": "feed",
            "type": "Feed",
            "endpoint": "https://alice.example/feed.xml",
            "mediaType": "application/atom+xml",
            "label": "Writing",
            "language": None,
            "rel": None,
        }
    ],
    "migration": None,
    "extensions": {},
}

BOB_CONTACT = {
    "displayName": "Bob Example",
    "summary": "Reader",
    "avatar": None,
    "alsoKnownAs": ["acct:bob@example.net"],
    "services": [
        {
            "id": "feed",
            "type": "Feed",
            "endpoint": "https://bob.example/feed.xml",
            "mediaType": "application/atom+xml",
            "label": "Reading",
            "language": None,
            "rel": None,
        }
    ],
    "migration": None,
    "extensions": {},
}

B4_TIMESTAMP = 1785589200123
B5_TIMESTAMP = 1785589201123
BOB_TIMESTAMP = 1785589201123
DEFAULT_NOW = 1785589201123
SELECTION_NOW = 1785589300000


class PublishedVectors:
    """Extracts, reconstructs, and cross-asserts every published vector."""

    def __init__(self, bundle_root: Path) -> None:
        self.spec = SpecText(bundle_root)
        self.seeds = _identity_inputs()
        self.identities = {
            name: derive_identity(
                bytes.fromhex(pair["root"]), bytes.fromhex(pair["revocation"])
            )
            for name, pair in self.seeds.items()
        }
        self._assert_identities()
        self.records = self._build_records()
        self.negatives = self._build_negative_envelopes()
        self._envelopes = {
            **{cid: case["expected"]["envelopeHex"] for cid, case in self.records.items()},
            **{cid: case["envelopeHex"] for cid, case in self.negatives.items()},
        }
        self.wire = self._build_wire()

    # -- identities ---------------------------------------------------------

    def _assert_identities(self) -> None:
        spec = self.spec
        alice = self.identities["alice"]
        _require("alice root pub", alice["rootPublicKeyHex"],
                 spec.labeled_hex("B.2 Keys", "root public key"))
        _require("alice revocation pub", alice["revocationPublicKeyHex"],
                 spec.labeled_hex("B.2 Keys", "revocation public key"))
        b3 = "B.3 Revocation commitment and descriptor"
        _require("alice revocation pk cbor", alice["revocationPublicKeyCborHex"],
                 spec.labeled_hex(b3, "revocation public-key CBOR"))
        _require("alice revocation commitment", alice["revocationCommitmentHex"],
                 spec.labeled_hex(b3, "revocation commitment"))
        _require("alice descriptor", alice["authorityDescriptorCborHex"],
                 spec.labeled_hex(b3, "Authority Descriptor CBOR"))
        _require("alice descriptor digest", alice["authorityDescriptorDigestHex"],
                 spec.labeled_hex(b3, "descriptor digest"))
        _require("alice multihash", alice["multihashHex"],
                 spec.labeled_hex(b3, "multihash bytes"))
        _require("alice DID", alice["did"], spec.labeled(b3, "Followee DID"))

        attacker = self.identities["attacker"]
        b81 = "B.8.1 Attacker keys"
        _require("attacker root pub", attacker["rootPublicKeyHex"],
                 spec.labeled_hex(b81, "attacker root public key"))
        _require("attacker revocation pub", attacker["revocationPublicKeyHex"],
                 spec.labeled_hex(b81, "attacker revocation public key"))
        _require("attacker commitment", attacker["revocationCommitmentHex"],
                 spec.labeled_hex(b81, "attacker revocation commitment"))
        _require("attacker descriptor", attacker["authorityDescriptorCborHex"],
                 spec.labeled_hex(b81, "attacker Authority Descriptor CBOR"))
        _require("attacker DID", attacker["did"],
                 spec.labeled(b81, "attacker's own legitimate DID, for contrast"))

        bob = self.identities["bob"]
        b9 = "B.9 Independent Bob identity"
        _require("bob root pub", bob["rootPublicKeyHex"],
                 spec.labeled_hex(b9, "Bob root public key"))
        _require("bob revocation pub", bob["revocationPublicKeyHex"],
                 spec.labeled_hex(b9, "Bob revocation public key"))
        _require("bob revocation pk cbor", bob["revocationPublicKeyCborHex"],
                 spec.labeled_hex(b9, "Bob revocation public-key CBOR"))
        _require("bob commitment", bob["revocationCommitmentHex"],
                 spec.labeled_hex(b9, "Bob revocation commitment"))
        _require("bob descriptor", bob["authorityDescriptorCborHex"],
                 spec.labeled_hex(b9, "Bob Authority Descriptor CBOR"))
        _require("bob descriptor digest", bob["authorityDescriptorDigestHex"],
                 spec.labeled_hex(b9, "Bob descriptor digest"))
        _require("bob multihash", bob["multihashHex"],
                 spec.labeled_hex(b9, "Bob multihash bytes"))
        _require("bob DID", bob["did"], spec.labeled(b9, "Bob Followee DID"))

    # -- records ------------------------------------------------------------

    def _author_case(self, identity_name: str, authority: str, timestamp: int,
                     contact: dict, signing_seed: str) -> dict:
        seeds = {
            "root": self.seeds[identity_name]["root"],
            "revocation": self.seeds[identity_name]["revocation"],
        }
        expected = author(self.identities[identity_name], seeds, authority,
                          timestamp, contact, signing_seed)
        return {
            "input": {
                "rootSeedHex": seeds["root"],
                "revocationSeedHex": seeds["revocation"],
                "authority": authority,
                "timestampMs": str(timestamp),
                "validUntilMs": None,
                "contact": contact,
                "extensions": {},
                "signingSeed": signing_seed,
            },
            "expected": expected,
        }

    def _build_records(self) -> dict:
        spec = self.spec
        cases: dict = {}

        b4 = self._author_case("alice", "root", B4_TIMESTAMP, ALICE_CONTACT, "root")
        section = "B.4 Root record"
        _require("B.4 body", b4["expected"]["recordBodyCborHex"],
                 spec.labeled_hex(section, "record body CBOR"))
        _require("B.4 sig-structure length",
                 len(bytes.fromhex(b4["expected"]["sigStructureHex"])),
                 spec.labeled_int(section, "COSE `Sig_structure` length"))
        _require("B.4 sig-structure", b4["expected"]["sigStructureHex"],
                 spec.labeled_hex(section, "COSE `Sig_structure` bytes"))
        _require("B.4 body digest", b4["expected"]["recordBodyDigestHex"],
                 spec.labeled_hex(section, "body digest"))
        _require("B.4 signature", b4["expected"]["signatureHex"],
                 spec.labeled_hex(section, "signature"))
        _require("B.4 envelope", b4["expected"]["envelopeHex"],
                 spec.labeled_hex(section, "complete tagged COSE Identity Record"))
        b4["publishedMembers"] = [
            "recordBodyCborHex", "recordBodyDigestHex", "sigStructureHex",
            "signatureHex", "envelopeHex",
        ]
        b4["specificationSections"] = ["Appendix B.4"]
        cases["b4-root"] = b4

        b5 = self._author_case("alice", "rootRevoked", B5_TIMESTAMP,
                               ALICE_CONTACT, "revocation")
        section = "B.5 Root-revoked record"
        _require("B.5 body", b5["expected"]["recordBodyCborHex"],
                 spec.labeled_hex(section, "record body CBOR"))
        _require("B.5 body digest", b5["expected"]["recordBodyDigestHex"],
                 spec.labeled_hex(section, "body digest"))
        _require("B.5 signature", b5["expected"]["signatureHex"],
                 spec.labeled_hex(section, "signature"))
        _require("B.5 envelope", b5["expected"]["envelopeHex"],
                 spec.labeled_hex(section, "complete tagged COSE Identity Record"))
        b5["publishedMembers"] = [
            "recordBodyCborHex", "recordBodyDigestHex", "signatureHex",
            "envelopeHex",
        ]
        b5["specificationSections"] = ["Appendix B.5"]
        cases["b5-root-revoked"] = b5

        section = "B.6 Equal-time ordering"
        for suffix, name in (("a", "Alice A"), ("b", "Alice B")):
            contact = {**ALICE_CONTACT, "displayName": name}
            case = self._author_case("alice", "root", B4_TIMESTAMP, contact, "root")
            _require(f"B.6 {name} digest", case["expected"]["recordBodyDigestHex"],
                     spec.labeled_hex(section, f'"{name}" body digest'))
            case["publishedMembers"] = ["recordBodyDigestHex"]
            case["specificationSections"] = ["Appendix B.6"]
            cases[f"b6-alice-{suffix}"] = case

        bob = self._author_case("bob", "root", BOB_TIMESTAMP, BOB_CONTACT, "root")
        section = "B.9 Independent Bob identity"
        _require("B.9 body", bob["expected"]["recordBodyCborHex"],
                 spec.labeled_hex(section, "Bob record body CBOR"))
        _require("B.9 sig-structure length",
                 len(bytes.fromhex(bob["expected"]["sigStructureHex"])),
                 spec.labeled_int(section, "Bob COSE Sig_structure length"))
        _require("B.9 sig-structure", bob["expected"]["sigStructureHex"],
                 spec.labeled_hex(section, "Bob COSE Sig_structure bytes"))
        _require("B.9 body digest", bob["expected"]["recordBodyDigestHex"],
                 spec.labeled_hex(section, "Bob body digest"))
        _require("B.9 signature", bob["expected"]["signatureHex"],
                 spec.labeled_hex(section, "Bob signature"))
        _require("B.9 envelope", bob["expected"]["envelopeHex"],
                 spec.labeled_hex(section, "Bob complete tagged COSE Identity Record"))
        bob["publishedMembers"] = [
            "recordBodyCborHex", "recordBodyDigestHex", "sigStructureHex",
            "signatureHex", "envelopeHex",
        ]
        bob["specificationSections"] = ["Appendix B.9"]
        cases["b9-bob-root"] = bob

        return cases

    # -- fault-isolated and substituted envelopes ---------------------------

    def _mutated_extension_envelope(self, section: str, label_prefix: str,
                                    expected_error: str) -> dict:
        spec = self.spec
        appended = spec.labeled_hex(section, f"{label_prefix} appended bytes")
        base_body = bytes.fromhex(self.records["b4-root"]["expected"]["recordBodyCborHex"])
        if base_body[0] != 0xA6:
            raise AssertionError("B.4 body does not start with map head a6")
        body = b"\xa7" + base_body[1:] + bytes.fromhex(appended)
        after = spec.section(section)
        anchor = after.find(f"{label_prefix} appended bytes:")
        block = after[anchor:]
        digest = _labeled_after(block, "body digest")
        sig_len = int(_labeled_after(block, "COSE Sig_structure length"), 10)
        signature = _labeled_after(block, "signature")
        _require(f"{label_prefix} body digest", sha256_hex(body), digest)
        structure = sig_structure(body)
        _require(f"{label_prefix} sig-structure length", len(structure), sig_len)
        computed = ed25519.sign(
            bytes.fromhex(self.seeds["alice"]["root"]), structure
        )
        _require(f"{label_prefix} signature", computed.hex(), signature)
        return {
            "construction": {
                "baseBody": {"vector": "records", "case": "b4-root",
                             "field": "recordBodyCborHex"},
                "mapHeadChange": "a6-to-a7",
                "appendedBytesHex": appended,
                "note": "Published recipe: start from the B.4 record body, "
                        "change the initial map head from a6 to a7, append "
                        "the bytes shown, and build the complete envelope "
                        "exactly as in Section 6.2 from the mutated raw "
                        "body and the listed signature.",
            },
            "sigStructureLength": str(sig_len),
            "recordBodyCborHex": body.hex(),
            "recordBodyDigestHex": digest,
            "signatureHex": signature,
            "envelopeHex": envelope(body, bytes.fromhex(signature)).hex(),
            "expectedError": expected_error,
        }

    def _build_negative_envelopes(self) -> dict:
        spec = self.spec
        cases: dict = {}

        section = "B.8.2 Substituted record"
        b8_envelope = spec.labeled_hex(
            section, "complete tagged COSE Identity Record"
        )
        b8_digest = spec.labeled_hex(section, "body digest")
        decoded = cbor.decode_strict(bytes.fromhex(b8_envelope), allow_outer_tag=18)
        _tag, _n, cose = decoded
        _require("B.8 payload digest", sha256_hex(cose[2]), b8_digest)
        attacker_sig = spec.labeled_hex(
            section, "signature, valid under the attacker's root key"
        )
        _require("B.8 signature", cose[3].hex(), attacker_sig)
        if not ed25519.verify(
            bytes.fromhex(self.identities["attacker"]["rootPublicKeyHex"]),
            sig_structure(cose[2]),
            cose[3],
        ):
            raise AssertionError("B.8 signature does not verify under attacker key")
        cases["b8-descriptor-substitution"] = {
            "envelopeHex": b8_envelope,
            "recordBodyDigestHex": b8_digest,
            "expectedError": "identityBindingMismatch",
            "publishedMembers": ["envelopeHex", "recordBodyDigestHex"],
            "specificationSections": ["Appendix B.8"],
        }

        b10 = "B.10 Fault-isolated basic-validity records"
        for case_id, label in (
            ("b10-duplicate-key", "duplicate-key"),
            ("b10-utf8-overlong", "overlong U+002E"),
            ("b10-utf8-surrogate", "lone U+D800 surrogate"),
            ("b10-utf8-above-max", "U+110000 above the RFC 3629 maximum"),
            ("b10-utf8-incomplete",
             "incomplete three-byte code point in a complete two-byte text string"),
        ):
            case = self._mutated_extension_envelope(b10, label, "invalidCbor")
            case["publishedMembers"] = [
                "recordBodyDigestHex", "signatureHex", "sigStructureLength",
            ]
            case["specificationSections"] = ["Appendix B.10"]
            cases[case_id] = case

        b12 = "B.12 Fault-isolated schema-disallowed-simple-value records"
        for case_id, label in (
            ("b12-simple-value-16", "simple value 16"),
            ("b12-simple-value-32", "simple value 32"),
        ):
            case = self._mutated_extension_envelope(b12, label, "schemaViolation")
            case["publishedMembers"] = [
                "recordBodyDigestHex", "signatureHex", "sigStructureLength",
            ]
            case["specificationSections"] = ["Appendix B.12"]
            cases[case_id] = case

        return cases

    # -- relay wire vectors -------------------------------------------------

    def envelope_bytes(self, case_id: str) -> bytes:
        return bytes.fromhex(self._envelopes[case_id])

    def _build_wire(self) -> dict:
        spec = self.spec
        generation = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
        alice_did = self.identities["alice"]["did"]
        bob_did = self.identities["bob"]["did"]
        attacker_did = self.identities["attacker"]["did"]
        def full(cid: str) -> dict:
            return {0: 0, 1: self.envelope_bytes(cid)}

        cases: dict = {}

        section = "B.11.1 Invalid outer request"
        body = spec.section(section)
        request_hex = _first_hex_block(body)
        _require("B.11.1 length", len(bytes.fromhex(request_hex)),
                 int(_labeled_after(body, "length"), 10))
        _require("B.11.1 sha", sha256_hex(bytes.fromhex(request_hex)),
                 _labeled_after(body, "SHA-256"))
        cases["b11-1-invalid-outer-request"] = {
            "requestBytesHex": request_hex,
            "requestSha256": sha256_hex(bytes.fromhex(request_hex)),
            "requiredBehaviour": "http-400-no-per-item-results",
            "publishedMembers": ["requestBytesHex", "requestSha256"],
            "specificationSections": ["Appendix B.11.1", "Section 12.1"],
        }

        section = "B.11.2 Invalid outer response"
        body = spec.section(section)
        response_hex = _first_hex_block(body)
        _require("B.11.2 length", len(bytes.fromhex(response_hex)),
                 int(_labeled_after(body, "length"), 10))
        _require("B.11.2 sha", sha256_hex(bytes.fromhex(response_hex)),
                 _labeled_after(body, "SHA-256"))
        cases["b11-2-invalid-outer-response"] = {
            "responseBytesHex": response_hex,
            "responseSha256": sha256_hex(bytes.fromhex(response_hex)),
            "expectedClassification": "nonDeterministicCbor",
            "requiredBehaviour": "reject-complete-response-not-absent",
            "publishedMembers": ["responseBytesHex", "responseSha256"],
            "specificationSections": ["Appendix B.11.2", "Section 12.1"],
        }

        def build_and_check(section: str, case_id: str, request: object,
                            response: object, extra: dict) -> None:
            body = spec.section(section)
            request_bytes = cbor.encode(request)
            published_request = _first_hex_block(body)
            _require(f"{case_id} request bytes", request_bytes.hex(), published_request)
            _require(f"{case_id} request length", len(request_bytes),
                     int(_labeled_after(body, "length"), 10))
            _require(f"{case_id} request sha", sha256_hex(request_bytes),
                     _labeled_after(body, "SHA-256"))
            response_bytes = cbor.encode(response)
            cases[case_id] = {
                "requestBytesHex": request_bytes.hex(),
                "requestSha256": sha256_hex(request_bytes),
                "responseBytesHex": response_bytes.hex(),
                "responseLength": str(len(response_bytes)),
                "responseSha256": sha256_hex(response_bytes),
                **extra,
            }

        build_and_check(
            "B.11.3 Resolve candidate isolation",
            "b11-3-resolve-candidate-isolation",
            {0: 1, 1: [alice_did, bob_did]},
            {0: 1, 1: generation,
             2: [full("b8-descriptor-substitution"), full("b9-bob-root")]},
            {
                "requiredBehaviour": "accept-wrapper-discard-index0-retain-index1",
                "publishedMembers": [
                    "requestBytesHex", "requestSha256", "responseLength",
                    "responseSha256",
                ],
                "specificationSections": ["Appendix B.11.3", "Section 12.3"],
            },
        )
        _require(
            "B.11.3 response length",
            len(bytes.fromhex(cases["b11-3-resolve-candidate-isolation"]["responseBytesHex"])),
            743,
        )
        _require(
            "B.11.3 response sha",
            cases["b11-3-resolve-candidate-isolation"]["responseSha256"],
            "62246877adbd56be2996ea37d05475d88c0e7932ff9b042f8ddbb9a809f8f4ca",
        )

        build_and_check(
            "B.11.4 Duplicate requested DIDs and cardinality",
            "b11-4-duplicate-dids-cardinality",
            {0: 1, 1: [alice_did, alice_did, bob_did]},
            {0: 1, 1: generation,
             2: [full("b4-root"), full("b4-root"), full("b9-bob-root")]},
            {
                "requiredBehaviour": "exact-cardinality-no-deduplication",
                "publishedMembers": [
                    "requestBytesHex", "requestSha256", "responseLength",
                    "responseSha256",
                ],
                "specificationSections": ["Appendix B.11.4", "Section 12.3"],
            },
        )
        _require(
            "B.11.4 response sha",
            cases["b11-4-duplicate-dids-cardinality"]["responseSha256"],
            "203e22e2d913359b08070c289d60889770bcdeee0584187dee25e1c8e05fdfe8",
        )
        _require(
            "B.11.4 response length",
            int(cases["b11-4-duplicate-dids-cardinality"]["responseLength"], 10),
            1106,
        )

        build_and_check(
            "B.11.5 Changes isolation and cursor progress",
            "b11-5-changes-isolation-cursor",
            {0: 1, 1: b"v08-0000", 2: 2, 3: 1048576},
            {0: 1, 1: 0,
             2: [
                 [alice_did, full("b8-descriptor-substitution"), 1001],
                 [bob_did, full("b9-bob-root"), 1002],
             ],
             3: b"v08-0002", 4: False, 5: generation},
            {
                "initialReceiverState": {
                    "alice": {
                        "entry": {"vector": "records", "case": "b4-root"},
                        "authorityState": "root",
                        "lastUpdated": "41",
                    },
                    "bob": "absent",
                    "localUpdateCounter": "41",
                    "peerCursorHex": "7630382d30303030",
                    "nowMs": "1785589201123",
                },
                "requiredPostState": {
                    "aliceUnchanged": True,
                    "bobAdmitted": {"vector": "records", "case": "b9-bob-root"},
                    "bobLastUpdated": "42",
                    "localUpdateCounter": "42",
                    "peerCursorHex": "7630382d30303032",
                },
                "requiredBehaviour": "admit-bob-reject-b8-advance-cursor",
                "publishedMembers": [
                    "requestBytesHex", "requestSha256", "responseLength",
                    "responseSha256",
                ],
                "specificationSections": ["Appendix B.11.5", "Section 13.3"],
            },
        )
        _require(
            "B.11.5 response sha",
            cases["b11-5-changes-isolation-cursor"]["responseSha256"],
            "3337aa0be1d6b8cbf856a31657490398a4b778de586e0b292da68c5c26c200f2",
        )
        _require(
            "B.11.5 response length",
            int(cases["b11-5-changes-isolation-cursor"]["responseLength"], 10),
            879,
        )

        build_and_check(
            "B.11.6 Malformed DID inside a valid batch",
            "b11-6-malformed-did-in-batch",
            {0: 1, 1: [alice_did, "did:flw:not-a-multibase", bob_did]},
            {0: 1, 1: generation,
             2: [full("b4-root"), {0: 3, 2: 0}, full("b9-bob-root")]},
            {
                "requiredBehaviour": "http-200-positional-error-invalidDid",
                "publishedMembers": [
                    "requestBytesHex", "requestSha256", "responseLength",
                    "responseSha256",
                ],
                "specificationSections": ["Appendix B.11.6", "Section 12.3"],
            },
        )
        _require(
            "B.11.6 response sha",
            cases["b11-6-malformed-did-in-batch"]["responseSha256"],
            "d8a36364ed62a8fabb905f6c20c04304fe1803df10fa1680840c5c7cd1af96fa",
        )
        _require(
            "B.11.6 response length",
            int(cases["b11-6-malformed-did-in-batch"]["responseLength"], 10),
            748,
        )

        overflow_response = cbor.encode(
            {0: 1, 1: 0,
             2: [
                 [alice_did, full("b8-descriptor-substitution"), 1001],
                 [bob_did, full("b9-bob-root"), 1002],
                 [attacker_did, {0: 1, 1: 0}, 1003],
             ],
             3: b"v08-0003", 4: False, 5: generation}
        )
        _require("B.11.7 response length", len(overflow_response), 945)
        _require(
            "B.11.7 response sha", sha256_hex(overflow_response),
            "334740ea2ce15b4b70dfcdd88f4cfc7f31bfd53f1b7615aa08df1c4137f4d795",
        )
        cases["b11-7-changes-item-limit-overflow"] = {
            "requestBytesHex": cases["b11-5-changes-isolation-cursor"]["requestBytesHex"],
            "requestSha256": cases["b11-5-changes-isolation-cursor"]["requestSha256"],
            "responseBytesHex": overflow_response.hex(),
            "responseLength": str(len(overflow_response)),
            "responseSha256": sha256_hex(overflow_response),
            "initialReceiverState":
                cases["b11-5-changes-isolation-cursor"]["initialReceiverState"],
            "requiredPostState": {
                "aliceUnchanged": True,
                "bobRemainsAbsent": True,
                "localUpdateCounter": "41",
                "peerCursorHex": "7630382d30303030",
            },
            "requiredBehaviour": "reject-complete-response-do-not-use-nextCursor",
            "publishedMembers": [
                "requestBytesHex", "requestSha256", "responseLength",
                "responseSha256",
            ],
            "specificationSections": ["Appendix B.11.7", "Section 12.6"],
        }

        return {
            "directoryGenerationHex": generation.hex(),
            "cases": cases,
        }


def _labeled_after(block: str, label: str) -> str:
    anchor = label + ":\n"
    index = block.find(anchor)
    if index < 0:
        raise ValueError(f"label not found: {label}")
    rest = block[index + len(anchor) :]
    for line in rest.split("\n"):
        line = line.strip()
        if line and line != "```":
            return line
    raise ValueError(f"empty labeled block: {label}")


def _first_hex_block(section_body: str) -> str:
    import re as _re

    fence = _re.search(r"```text\n(.*?)```", section_body, _re.DOTALL)
    if not fence:
        raise ValueError("no text fence in section")
    for line in fence.group(1).split("\n"):
        line = line.strip()
        if _re.fullmatch(r"[0-9a-f]{16,}", line):
            return line
    raise ValueError("no hex block found")
