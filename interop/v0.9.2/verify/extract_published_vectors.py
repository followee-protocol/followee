#!/usr/bin/env python3
"""Regenerate the published-vector files for both audiences.

Usage:
  python3 extract_published_vectors.py --write   # (re)write the files
  python3 extract_published_vectors.py --check   # verify byte-identical

Two deterministic projections of the same extraction are emitted:

- ``authoring/vectors/published/`` — the AUTHORING projection. Every
  value here is literally published in Appendix B of the pinned
  specification (bytes, digests, lengths, signatures, DIDs, error
  classifications, receiver states). Values the specification only
  *determines* — reconstructed envelopes, unpublished derivation
  members, constructed cases — are absent.
- ``coordinator/expected/`` — the full coordinator expectations,
  including specification-determined reconstructions and constructed
  comparison cases. This tree is withheld from any fresh
  implementation session until its outputs are frozen.

Every emitted value was extracted from, or reconstructed and asserted
against, the pinned specification; construction failure raises instead
of emitting a vector. The script is deterministic and embeds no
timestamps, paths, or environment data.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from interopkit import base58  # noqa: E402
from interopkit.published import (  # noqa: E402
    BUNDLE,
    DEFAULT_NOW,
    SELECTION_NOW,
    U64_MAX,
    PublishedVectors,
    project_accepted_result,
    publish_response,
    wire_error_registry,
)
from interopkit.spec import SPEC_SHA256  # noqa: E402

SOURCE = {
    "document": "authoring/specification/Followee-Specification.md",
    "sha256": SPEC_SHA256,
    "specificationVersion": "v0.9.2",
}

IDENTITY_PUBLISHED_MEMBERS = {
    "alice": [
        "rootPublicKeyHex", "revocationPublicKeyHex",
        "revocationPublicKeyCborHex", "revocationCommitmentHex",
        "authorityDescriptorCborHex", "authorityDescriptorDigestHex",
        "multihashHex", "did",
    ],
    "bob": [
        "rootPublicKeyHex", "revocationPublicKeyHex",
        "revocationPublicKeyCborHex", "revocationCommitmentHex",
        "authorityDescriptorCborHex", "authorityDescriptorDigestHex",
        "multihashHex", "did",
    ],
    "attacker": [
        "rootPublicKeyHex", "revocationPublicKeyHex",
        "revocationCommitmentHex", "authorityDescriptorCborHex", "did",
    ],
}


def _file_header(name: str, provenance: str, description: str) -> dict:
    return {
        "bundle": BUNDLE,
        "file": name,
        "provenance": provenance,
        "source": SOURCE,
        "description": description,
    }


# ---------------------------------------------------------------------------
# Full (coordinator) files


def identities_file(pv: PublishedVectors) -> dict:
    cases = []
    for name in ("alice", "attacker", "bob"):
        cases.append({
            "id": f"identity-{name}",
            "operation": "deriveIdentity",
            "input": {
                "rootSeedHex": pv.seeds[name]["root"],
                "revocationSeedHex": pv.seeds[name]["revocation"],
            },
            "expected": {
                key: pv.identities[name][key]
                for key in (
                    "rootPublicKeyHex", "revocationPublicKeyHex",
                    "revocationPublicKeyCborHex", "revocationCommitmentHex",
                    "authorityDescriptorCborHex", "authorityDescriptorDigestHex",
                    "multihashHex", "did",
                )
            },
            "publishedMembers": IDENTITY_PUBLISHED_MEMBERS[name],
            "specificationSections":
                ["Appendix B.2", "Appendix B.3"] if name == "alice"
                else ["Appendix B.8.1"] if name == "attacker"
                else ["Appendix B.9"],
        })
    return {
        **_file_header(
            "identities.json", "specification-determined",
            "Appendix B identities with their complete derivation chains. "
            "Members listed in publishedMembers appear verbatim in the "
            "specification; the remainder are reconstructed by its "
            "deterministic algorithms.",
        ),
        "cases": cases,
    }


def records_file(pv: PublishedVectors) -> dict:
    cases = []
    for case_id, case in pv.records.items():
        cases.append({
            "id": case_id,
            "operation": "authorRecord",
            "input": case["input"],
            "expected": case["expected"],
            "publishedMembers": case["publishedMembers"],
            "specificationSections": case["specificationSections"],
        })
    return {
        **_file_header(
            "records.json", "specification-determined",
            "Deterministic record-authoring vectors. Members listed in "
            "publishedMembers appear verbatim in Appendix B; all other "
            "expected members are reconstructed by the specification's "
            "deterministic algorithms and re-asserted by bundle tooling.",
        ),
        "cases": cases,
    }


def negative_envelopes_file(pv: PublishedVectors) -> dict:
    cases = []
    for case_id, case in pv.negatives.items():
        entry = {"id": case_id}
        entry.update(case)
        cases.append(entry)
    return {
        **_file_header(
            "envelopes-negative.json", "specification-determined",
            "Complete negative envelopes from Appendix B.8, B.10, and B.12 "
            "with their normative error classifications. B.10 and B.12 "
            "bodies and envelopes are reconstructed from the published "
            "mutation recipe and re-asserted against the published digests "
            "and signatures.",
        ),
        "cases": cases,
    }


def _did_variants(pv: PublishedVectors) -> list[dict]:
    alice_digest = bytes.fromhex(
        pv.identities["alice"]["authorityDescriptorDigestHex"]
    )
    alice_did = pv.identities["alice"]["did"]

    def z58(payload: bytes) -> str:
        return "did:flw:z" + base58.encode(payload)

    return [
        {
            "id": "target-foreign-valid-attacker",
            "targetDid": pv.identities["attacker"]["did"],
            "expectedError": "identityBindingMismatch",
            "note": "Unchanged internally consistent envelope verified "
                    "against a different syntactically valid target "
                    "(Appendix B.7 item 1, first form).",
        },
        {
            "id": "target-foreign-valid-bob",
            "targetDid": pv.identities["bob"]["did"],
            "expectedError": "identityBindingMismatch",
            "note": "Second foreign valid target.",
        },
        {
            "id": "target-unsupported-hash-code",
            "targetDid": z58(b"\x13\x20" + alice_digest),
            "expectedError": "unsupportedHash",
            "note": "Structurally well-formed multihash with code 0x13 "
                    "(Appendix B.7 item 2).",
        },
        {
            "id": "target-unsupported-digest-length",
            "targetDid": z58(b"\x12\x1f" + alice_digest[:31]),
            "expectedError": "unsupportedHash",
            "note": "Code 0x12 with well-formed declared digest length 0x1f "
                    "matching the bytes present.",
        },
        {
            "id": "target-trailing-byte",
            "targetDid": z58(b"\x12\x20" + alice_digest + b"\x00"),
            "expectedError": "invalidDid",
            "note": "Trailing byte after the multihash.",
        },
        {
            "id": "target-length-disagreement",
            "targetDid": z58(b"\x12\x20" + alice_digest[:31]),
            "expectedError": "invalidDid",
            "note": "Declared digest length 0x20 disagrees with 31 bytes present.",
        },
        {
            "id": "target-non-minimal-varint",
            "targetDid": z58(b"\x92\x00\x20" + alice_digest),
            "expectedError": "invalidDid",
            "note": "Non-minimal unsigned-varint encoding of code 0x12.",
        },
        {
            "id": "target-missing-multibase-prefix",
            "targetDid": "did:flw:" + base58.encode(b"\x12\x20" + alice_digest),
            "expectedError": "invalidDid",
            "note": "Method-specific identifier does not begin with 'z'.",
        },
        {
            "id": "target-wrong-multibase-prefix",
            "targetDid": "did:flw:Z" + base58.encode(b"\x12\x20" + alice_digest),
            "expectedError": "invalidDid",
            "note": "Uppercase 'Z' is not the base58btc multibase prefix.",
        },
        {
            "id": "target-invalid-base58-character",
            "targetDid": "did:flw:z0" + base58.encode(b"\x12\x20" + alice_digest)[1:],
            "expectedError": "invalidDid",
            "note": "'0' is not in the Bitcoin base58 alphabet.",
        },
        {
            "id": "target-percent-encoded",
            "targetDid": alice_did.replace("Q", "%51", 1),
            "expectedError": "invalidDid",
            "note": "Percent-encoding is malformed in the method-specific id.",
        },
        {
            "id": "target-uppercase-did-prefix",
            "targetDid": "did:FLW:" + alice_did[len("did:flw:"):],
            "expectedError": "invalidDid",
            "note": "The did:flw: prefix MUST be lowercase (Section 3.1).",
        },
        {
            "id": "target-empty-method-id",
            "targetDid": "did:flw:",
            "expectedError": "invalidDid",
            "note": "Empty method-specific identifier.",
        },
    ]


def verification_file(pv: PublishedVectors) -> dict:
    def ref(vector, case):
        return {"vector": vector, "case": case}

    cases: list[dict] = []

    def accepted(case_id, target, env, now, ts, authority, digest,
                 premature=False, sections=None):
        # The complete corrected accepted-result projection, recomputed
        # from the referenced envelope bytes alone and cross-asserted
        # against the independently stated scalar expectations.
        projected = project_accepted_result(
            pv.envelope_bytes(env["case"]).hex(), target, now)
        stated = {
            "id": target, "timestampMs": str(ts), "authority": authority,
            "validUntilMs": None, "premature": premature, "stale": False,
            "recordBodyDigestHex": digest,
        }
        for member, value in stated.items():
            if projected[member] != value:
                raise AssertionError(
                    f"{case_id}: projected {member} disagrees with the "
                    "stated expectation")
        cases.append({
            "id": case_id,
            "operation": "verifyRecord",
            "input": {
                "targetDid": target,
                "envelope": env,
                "nowMs": str(now),
            },
            "expected": {
                "outcome": "accepted",
                **stated,
                "record": projected["record"],
            },
            "specificationSections": sections or ["Section 8.1"],
        })

    alice = pv.identities["alice"]["did"]
    bob = pv.identities["bob"]["did"]
    b4_digest = pv.records["b4-root"]["expected"]["recordBodyDigestHex"]
    accepted("verify-b4-accept", alice, ref("records", "b4-root"),
             DEFAULT_NOW, 1785589200123, "root", b4_digest,
             sections=["Appendix B.4", "Section 8.1"])
    accepted("verify-b5-accept", alice, ref("records", "b5-root-revoked"),
             DEFAULT_NOW, 1785589201123, "rootRevoked",
             pv.records["b5-root-revoked"]["expected"]["recordBodyDigestHex"],
             sections=["Appendix B.5", "Section 8.2"])
    accepted("verify-b9-accept", bob, ref("records", "b9-bob-root"),
             DEFAULT_NOW, 1785589201123, "root",
             pv.records["b9-bob-root"]["expected"]["recordBodyDigestHex"],
             sections=["Appendix B.9", "Section 8.1"])
    accepted("verify-b4-premature", alice, ref("records", "b4-root"),
             1785588900122, 1785589200123, "root", b4_digest, premature=True,
             sections=["Section 5.4"])
    accepted("verify-b4-premature-boundary", alice, ref("records", "b4-root"),
             1785588900123, 1785589200123, "root", b4_digest, premature=False,
             sections=["Section 5.4"])

    # Direct-wire present-empty fixtures: valid, correctly signed
    # records carrying present-empty optional collections that the
    # authorRecord input canonicalization cannot construct. Exercised
    # through verifyRecord only, with the complete corrected
    # accepted-result expectation, preserving the [] / {} / absence
    # distinction.
    for wire_id, wire_case in pv.wire_records.items():
        projected = project_accepted_result(
            wire_case["envelopeHex"], alice, DEFAULT_NOW)
        cases.append({
            "id": f"verify-{wire_id}",
            "operation": "verifyRecord",
            "input": {
                "targetDid": alice,
                "envelopeHex": wire_case["envelopeHex"],
                "nowMs": str(DEFAULT_NOW),
            },
            "expected": {
                "outcome": "accepted",
                **projected,
            },
            "construction": wire_case["construction"],
            "specificationSections": wire_case["specificationSections"],
        })

    for case_id, case in pv.negatives.items():
        cases.append({
            "id": f"verify-{case_id}",
            "operation": "verifyRecord",
            "input": {
                "targetDid": alice,
                "envelope": ref("envelopes-negative", case_id),
                "nowMs": str(DEFAULT_NOW),
            },
            "expected": {
                "outcome": "rejected",
                "error": case["expectedError"],
            },
            "specificationSections": case["specificationSections"],
        })

    for variant in _did_variants(pv):
        cases.append({
            "id": f"verify-{variant['id']}",
            "operation": "verifyRecord",
            "input": {
                "targetDid": variant["targetDid"],
                "envelope": ref("records", "b4-root"),
                "nowMs": str(DEFAULT_NOW),
            },
            "expected": {
                "outcome": "rejected",
                "error": variant["expectedError"],
            },
            "note": variant["note"],
            "specificationSections": ["Section 3.1", "Appendix B.7"],
        })

    return {
        **_file_header(
            "verification.json", "specification-determined",
            "Record-verification comparison cases over the published "
            "envelopes, including constructed clock scenarios, "
            "constructed target-DID classification variants whose error "
            "classifications are normative under Section 3.1 and "
            "Appendix B.7, and constructed direct-wire cases carrying "
            "present-empty optional collections that the authorRecord "
            "input canonicalization cannot produce. Accepted "
            "expectations carry the complete corrected accepted-result "
            "projection of the interface contract. Envelope references "
            "resolve within coordinator/expected/; direct-wire cases "
            "carry their envelope bytes inline.",
        ),
        "cases": cases,
    }


def _permutations(items: tuple) -> list[tuple]:
    import itertools

    return list(itertools.permutations(items))


def selection_file(pv: PublishedVectors) -> dict:
    alice = pv.identities["alice"]["did"]
    b4 = {"vector": "records", "case": "b4-root"}
    b5 = {"vector": "records", "case": "b5-root-revoked"}
    b6a = {"vector": "records", "case": "b6-alice-a"}
    b6b = {"vector": "records", "case": "b6-alice-b"}
    b8 = {"vector": "envelopes-negative", "case": "b8-descriptor-substitution"}
    b9 = {"vector": "records", "case": "b9-bob-root"}
    digest = {
        "b4": pv.records["b4-root"]["expected"]["recordBodyDigestHex"],
        "b5": pv.records["b5-root-revoked"]["expected"]["recordBodyDigestHex"],
        "b6a": pv.records["b6-alice-a"]["expected"]["recordBodyDigestHex"],
    }
    key = {"b4": b4, "b5": b5, "b6a": b6a, "b6b": b6b, "b8": b8, "b9": b9}

    sets = [
        ("authority-precedence", ("b4", "b5"), alice, SELECTION_NOW, "unknown",
         digest["b5"], "rootRevoked",
         "A signature-valid RootRevoked record outranks every Root record "
         "(Section 8.2)."),
        ("binding-rejection", ("b4", "b8"), alice, SELECTION_NOW, "unknown",
         digest["b4"], "root",
         "The B.8 substituted-descriptor candidate is rejected with "
         "identityBindingMismatch; the valid Root record wins."),
        ("equal-time-digest", ("b6a", "b6b"), alice, SELECTION_NOW, "unknown",
         digest["b6a"], "root",
         "At equal authority and timestamp the lexicographically lower body "
         "digest wins (Section 8.3, Appendix B.6)."),
        ("full-mixed", ("b4", "b5", "b8", "b9"), alice, SELECTION_NOW, "unknown",
         digest["b5"], "rootRevoked",
         "Cross-DID candidate (Bob) and substituted descriptor are rejected; "
         "RootRevoked precedence decides among the survivors."),
    ]

    cases: list[dict] = []
    for set_id, members, target, now, sticky, winner, state, note in sets:
        for index, perm in enumerate(_permutations(members)):
            cases.append({
                "id": f"select-{set_id}-perm-{index:02d}",
                "operation": "selectCurrent",
                "permutationOf": set_id,
                "candidateOrder": list(perm),
                "input": {
                    "targetDid": target,
                    "candidates": [key[name] for name in perm],
                    "nowMs": str(now),
                    "stickyAuthority": sticky,
                },
                "expected": {
                    "winnerRecordBodyDigestHex": winner,
                    "authorityState": state,
                },
                "note": note,
                "specificationSections": ["Section 8", "Section 20.4"],
            })

    singles = [
        ("select-sticky-suppression", [b4], alice, SELECTION_NOW, "rootRevoked",
         None, "rootRevoked",
         "Sticky RootRevoked state excludes every Root candidate "
         "(Section 8.2); there is no last-good-Root fallback."),
        ("select-cross-did-only", [b9], alice, SELECTION_NOW, "unknown",
         None, "unknown",
         "A candidate bound to another DID yields no winner for this target."),
        ("select-premature-only", [b4], alice, 1785588900122, "unknown",
         None, "unknown",
         "A premature candidate is not currently admissible (Section 5.4)."),
        ("select-empty-candidates", [], alice, SELECTION_NOW, "unknown",
         None, "unknown", "No candidates yields no winner."),
    ]
    for case_id, candidates, target, now, sticky, winner, state, note in singles:
        cases.append({
            "id": case_id,
            "operation": "selectCurrent",
            "input": {
                "targetDid": target,
                "candidates": candidates,
                "nowMs": str(now),
                "stickyAuthority": sticky,
            },
            "expected": {
                "winnerRecordBodyDigestHex": winner,
                "authorityState": state,
            },
            "note": note,
            "specificationSections": ["Section 8"],
        })

    return {
        **_file_header(
            "selection.json", "specification-determined",
            "Constructed winner-selection comparison cases with explicitly "
            "enumerated candidate permutations over the published records. "
            "Expected winners are determined by Section 8; every "
            "permutation of one candidate set must select the same winner.",
        ),
        "cases": cases,
    }


def timestamps_file(pv: PublishedVectors) -> dict:
    cases = [
        ("next-first-record", "1785589200123", None, "1785589200123", None),
        ("next-now-ahead", "2000", "1000", "2000", None),
        ("next-now-behind", "1000", "2000", "2001", None),
        ("next-equal", "2000", "2000", "2001", None),
        ("next-boundary", "2001", "2000", "2001", None),
        ("next-zero-now", "0", None, "0", None),
        ("next-now-max", str(U64_MAX), None, str(U64_MAX), None),
        ("next-overflow", "5", str(U64_MAX), None, "overflow"),
    ]
    return {
        **_file_header(
            "timestamps.json", "specification-determined",
            "Constructed timestamp-generation comparison cases for the "
            "Section 5.3 rule max(now_ms, previous + 1) with checked "
            "arithmetic.",
        ),
        "cases": [
            {
                "id": case_id,
                "operation": "nextTimestamp",
                "input": {"nowMs": now, "previousTimestampMs": prev},
                "expected": {"timestampMs": out, "error": err},
                "specificationSections": ["Section 5.3"],
            }
            for case_id, now, prev, out, err in cases
        ],
    }


def wire_file(pv: PublishedVectors) -> dict:
    cases = []
    for case_id, case in pv.wire["cases"].items():
        entry = {"id": case_id}
        entry.update(case)
        cases.append(entry)
    return {
        **_file_header(
            "wire-b11.json", "specification-determined",
            "Appendix B.11 relay-wrapper vectors. Members marked in "
            "publishedMembers appear verbatim in the specification; "
            "complete response bytes are reconstructed from their "
            "published structural description and published component "
            "envelopes, then asserted against the published lengths and "
            "SHA-256 digests.",
        ),
        "directoryGenerationHex": pv.wire["directoryGenerationHex"],
        "cases": cases,
    }


NO_CHANGE_CODES = (12, 13)  # losingRecord, duplicate (Section 15.3)


def publish_responses_file(pv: PublishedVectors) -> dict:
    """The v0.9.2 Section 12.5 publish-response field-presence matrix.

    Every case submits one deterministically encoded publish response to
    the receiver-side wrapper-acceptance operation
    (`receivePublishResponse`) and states the exact normative
    classification: statuses `0` and `1` without `errorCode` and status
    `1` with an accurate `losingRecord` or `duplicate` reason are
    accepted; status `1` with any other registered code, status `0` with
    any code, status `2` without a code, status `2` with `losingRecord`
    or `duplicate`, and any status with an errorCode value outside the
    registered Section 15.3 set fail the applicable v1 schema and the
    complete response is rejected without extracting a status
    (Sections 12.1, 12.5, 15.3, 20.2). Section 15.3 is the complete v1
    wire error-code vocabulary: Section 12.5 requires status `2` to
    identify its rejection with a Section 15.3 code, so an unregistered
    value is malformed, never a forward-compatible extension point.

    The three accepted status-1 encodings are deliberately byte-distinct
    permitted forms of the same protocol outcome: the reason code is the
    Relay's optional diagnostic. Comparison harnesses MUST keep them
    byte-distinct and MUST NOT normalize one form into another; the
    difference is classified `permitted-diagnostic-variation`, never a
    disagreement (Section 20.4 reporting rule).
    """
    registry = wire_error_registry(pv.spec)

    def accepted(case_id: str, status: int, error_code: int | None,
                 note: str, extra: dict | None = None) -> dict:
        body = publish_response(status, error_code)
        case = {
            "id": case_id,
            "operation": "receivePublishResponse",
            "input": {"responseHex": body.hex()},
            "expected": {
                "outcome": "accepted",
                "status": str(status),
                "errorCode": None if error_code is None else str(error_code),
            },
            "note": note,
            "specificationSections": ["Section 12.5"],
        }
        if extra:
            case.update(extra)
        return case

    def rejected(case_id: str, status: int, error_code: int | None,
                 note: str) -> dict:
        body = publish_response(status, error_code)
        return {
            "id": case_id,
            "operation": "receivePublishResponse",
            "input": {"responseHex": body.hex()},
            "expected": {
                "outcome": "rejected",
                "error": "schemaViolation",
            },
            "requiredBehaviour":
                "reject-complete-response-no-status-no-state-change",
            "note": note,
            "specificationSections": ["Section 12.1", "Section 12.5"],
        }

    cases: list = []
    cases.append(accepted(
        "publish-accept-status-0", 0, None,
        "Admitted and current: errorCode MUST be absent."))
    cases.append(accepted(
        "publish-accept-status-1-bare", 1, None,
        "Valid but no current-state change, without the optional "
        "diagnostic reason.",
        {"variationGroup": "publish-status-1"}))
    for code in NO_CHANGE_CODES:
        cases.append(accepted(
            f"publish-accept-status-1-{registry[code]}", 1, code,
            f"Valid but no current-state change with the accurate "
            f"`{registry[code]}` reason: one of the enumerated permitted "
            "status-1 encodings. Byte-distinct from the bare form; never "
            "normalized into it.",
            {
                "variationGroup": "publish-status-1",
                "comparisonRule": "permitted-diagnostic-variation",
                "diagnosticVariationOf": "publish-accept-status-1-bare",
            }))
    for code in sorted(registry):
        if code in NO_CHANGE_CODES:
            continue
        cases.append(rejected(
            f"publish-reject-status-1-{registry[code]}", 1, code,
            f"Status 1 may carry only `losingRecord` or `duplicate`; "
            f"`{registry[code]}` ({code}) fails the applicable v1 schema."))
    cases.append(rejected(
        "publish-reject-status-0-duplicate", 0, 13,
        "Status 0 forbids errorCode even for a no-change reason code."))
    cases.append(rejected(
        "publish-reject-status-0-identityBindingMismatch", 0, 7,
        "Status 0 forbids errorCode even for a rejection code."))
    cases.append(rejected(
        "publish-reject-status-2-missing-errorCode", 2, None,
        "Status 2 requires errorCode."))
    for code in NO_CHANGE_CODES:
        cases.append(rejected(
            f"publish-reject-status-2-{registry[code]}", 2, code,
            f"A duplicate or losing-but-valid record is the status 1 "
            f"no-change outcome, never a rejection; status 2 MUST NOT "
            f"carry `{registry[code]}`."))
    # Unregistered errorCode probes. Section 15.3 is the complete wire
    # error-code vocabulary for protocol v1, and Section 12.5 requires a
    # status 2 response to identify its rejection *with a Section 15.3
    # code*; statuses 0 and 1 already forbid everything outside their
    # enumerated shapes. An unsigned value outside the registered set is
    # therefore not an unspecified or forward-compatible extension point:
    # it fails the applicable v1 schema (`schemaViolation`), and the
    # complete response is rejected without extracting a status or
    # changing state. The uint64-maximum probe exists so rejection
    # cannot be implemented accidentally as a one-byte range check.
    first_unregistered = max(registry) + 1
    if first_unregistered in registry:
        raise AssertionError("probe value is registered")
    for status in (0, 1, 2):
        cases.append(rejected(
            f"publish-reject-status-{status}-unregistered-"
            f"{first_unregistered}",
            status, first_unregistered,
            f"errorCode {first_unregistered} is the first value beyond "
            "the registered Section 15.3 range. The registry is the "
            "complete v1 wire vocabulary, so an unregistered value fails "
            "the applicable v1 schema on every status; the complete "
            "response is rejected without extracting a status."))
    cases.append(rejected(
        "publish-reject-status-2-unregistered-uint64-max", 2, U64_MAX,
        "The canonical uint64 maximum as errorCode: unregistered, so the "
        "complete response is rejected. This wide probe proves the "
        "complete-vocabulary rule is enforced over the full unsigned "
        "range, not as a one-byte range check."))
    for code in sorted(registry):
        if code in NO_CHANGE_CODES:
            continue
        cases.append(accepted(
            f"publish-accept-status-2-{registry[code]}", 2, code,
            f"Status 2 with the registered rejection code "
            f"`{registry[code]}` ({code}) is schema-conforming wrapper "
            "content; whether the code is appropriate for a given "
            "publication is the emitting Relay's Section 13.1 "
            "classification, exercised by the live campaign, not by "
            "wrapper acceptance. A conforming status-2 rejection is "
            "ordinary successful protocol processing at the HTTP layer "
            "and is normally carried by HTTP 200 (Section 15.4)."))
    return {
        **_file_header(
            "publish-responses.json", "specification-determined",
            "Section 12.5 publish-response field-presence matrix "
            "introduced by specification v0.9.2: exact accept/reject "
            "classification for every status and errorCode combination "
            "over the registered Section 15.3 codes plus explicit "
            "unregistered-value probes (the Section 15.3 registry is the "
            "complete v1 wire vocabulary, so an unregistered errorCode "
            "makes the response malformed on every status), including "
            "the enumerated permitted status-1 diagnostic encodings. The "
            "permitted status-1 forms are byte-distinct conforming "
            "encodings of the same protocol outcome; their difference "
            "is permitted diagnostic variation, never a disagreement, "
            "and is never normalized away.",
        ),
        "cases": cases,
    }


# ---------------------------------------------------------------------------
# AUTHORING projection — literally published members only

AUTHORING_DESCRIPTION = (
    "AUTHORING projection: every value in this file is literally published "
    "in Appendix B of the pinned specification. Values the specification "
    "only determines (reconstructed envelopes, unpublished derivation "
    "members, constructed comparison cases) are deliberately absent and "
    "must be derived from the specification alone."
)


def project_identities(full: dict) -> dict:
    out = copy.deepcopy(full)
    out["provenance"] = "normative-specification"
    out["description"] = AUTHORING_DESCRIPTION
    for case in out["cases"]:
        published = set(case["publishedMembers"])
        case["expected"] = {
            key: value for key, value in case["expected"].items()
            if key in published
        }
    return out


def project_records(full: dict) -> dict:
    out = copy.deepcopy(full)
    out["provenance"] = "normative-specification"
    out["description"] = AUTHORING_DESCRIPTION
    for case in out["cases"]:
        published = set(case["publishedMembers"]) | {"did"}
        case["expected"] = {
            key: value for key, value in case["expected"].items()
            if key in published
        }
    return out


def project_negatives(full: dict) -> dict:
    out = copy.deepcopy(full)
    out["provenance"] = "normative-specification"
    out["description"] = AUTHORING_DESCRIPTION
    for case in out["cases"]:
        if case["id"].startswith(("b10-", "b12-")):
            for member in ("recordBodyCborHex", "envelopeHex"):
                case.pop(member, None)
    return out


def project_wire(full: dict) -> dict:
    out = copy.deepcopy(full)
    out["provenance"] = "normative-specification"
    out["description"] = AUTHORING_DESCRIPTION
    for case in out["cases"]:
        if "responseBytesHex" in case.get("publishedMembers", []):
            continue
        if case["id"] == "b11-2-invalid-outer-response":
            continue  # response bytes are published verbatim
        case.pop("responseBytesHex", None)
    return out


def build_all(bundle_root: Path) -> dict[tuple[str, str], dict]:
    pv = PublishedVectors(bundle_root)
    identities = identities_file(pv)
    records = records_file(pv)
    negatives = negative_envelopes_file(pv)
    wire = wire_file(pv)
    return {
        ("coordinator", "identities.json"): identities,
        ("coordinator", "records.json"): records,
        ("coordinator", "envelopes-negative.json"): negatives,
        ("coordinator", "wire-b11.json"): wire,
        ("coordinator", "verification.json"): verification_file(pv),
        ("coordinator", "selection.json"): selection_file(pv),
        ("coordinator", "timestamps.json"): timestamps_file(pv),
        ("coordinator", "publish-responses.json"): publish_responses_file(pv),
        ("authoring", "identities.json"): project_identities(identities),
        ("authoring", "records.json"): project_records(records),
        ("authoring", "envelopes-negative.json"): project_negatives(negatives),
        ("authoring", "wire-b11.json"): project_wire(wire),
    }


def target_path(bundle_root: Path, audience: str, name: str) -> Path:
    if audience == "authoring":
        return bundle_root / "authoring" / "vectors" / "published" / name
    return bundle_root / "coordinator" / "expected" / name


def render(content: dict) -> bytes:
    return (json.dumps(content, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    bundle_root = Path(__file__).resolve().parent.parent
    files = build_all(bundle_root)

    failures = 0
    for (audience, name), content in files.items():
        rendered = render(content)
        path = target_path(bundle_root, audience, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if args.write:
            path.write_bytes(rendered)
            print(f"wrote {audience}/{name} ({len(rendered)} bytes)")
        else:
            existing = path.read_bytes() if path.exists() else None
            if existing != rendered:
                print(f"MISMATCH: {audience}/{name}")
                failures += 1
            else:
                print(f"ok {audience}/{name}")
    if args.check and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
