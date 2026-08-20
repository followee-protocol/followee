#!/usr/bin/env python3
"""Regenerate coordinator/transcripts/*.json.

Usage:
  python3 gen_transcripts.py --write
  python3 gen_transcripts.py --check

Each transcript documents one HTTP/CBOR exchange of the Section 12
mandatory relay profile. Transcripts are coordinator-only material:
several carry reconstructed or example byte sequences that are not
literally published in the specification, so none of them may reach a
fresh implementation session before its freeze. Body bytes are always
inline; where a body equals a coordinator expected-vector value the
transcript also carries a `sameAs` reference that verification asserts.
Body provenance is stated per message: `normative-specification` for
bytes the specification publishes or pins by digest,
`specification-determined` for bytes fully determined by the
specification for the stated scenario,
`permitted-diagnostic-variation` for one member of the enumerated
conforming publish status-1 set (byte-distinct forms, never normalized
into each other), and `illustrative-nonnormative` for example values
(relay identifiers, generations, cursors, limits) that the
specification leaves to the relay. Illustrative values are
documentation, not comparison targets; see authoring/NONDETERMINISM.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from interopkit import cbor, ed25519  # noqa: E402
from interopkit.published import (  # noqa: E402
    ALICE_CONTACT, B4_TIMESTAMP, BUNDLE, PublishedVectors,
    _identity_inputs, build_record_body, envelope, sig_structure,
)
from interopkit.spec import SPEC_SHA256  # noqa: E402

OVERSIZED_ENVELOPE_BYTES = 16385  # 16 KiB + 1: minimally over Section 15.1
OVERSIZED_PAD_KEY = "https://example.org/followee-interop/size-pad"


def oversized_envelope(identity: dict, root_seed_hex: str) -> bytes:
    """Deterministically author a validly signed complete envelope of
    exactly 16385 bytes: one byte over the Section 15.1 hard cap, with
    every other record rule satisfied, so the `recordTooLarge`
    assertion is fault-isolated (Section 6.1.3)."""

    def build(pad_len: int) -> bytes:
        body = build_record_body(
            identity, "root", B4_TIMESTAMP, ALICE_CONTACT,
            extensions={OVERSIZED_PAD_KEY:
                        {"type": "bytes", "hex": "00" * pad_len}})
        structure = sig_structure(body)
        seed = bytes.fromhex(root_seed_hex)
        signature = ed25519.sign(seed, structure)
        if not ed25519.verify(ed25519.public_key(seed), structure,
                              signature):
            raise AssertionError("self-verification failed")
        return envelope(body, signature)

    pad = 8000
    env = build(pad)
    while len(env) != OVERSIZED_ENVELOPE_BYTES:
        pad += OVERSIZED_ENVELOPE_BYTES - len(env)
        env = build(pad)
    return env

RELAY_ID = bytes.fromhex("a1a2a3a4a5a6a7a8a9aaabacadaeafb0")
PEER_RELAY_ID = bytes.fromhex("b1b2b3b4b5b6b7b8b9babbbcbdbebfc0")
CURSOR_GENERATION = bytes.fromhex("c1c2c3c4c5c6c7c8c9cacbcccdcecfd0")
BASE_URI = "https://relay.example/followee/"
PEER_BASE_URI = "https://relay-b.example/followee/"


def message(method_or_status, content_type, body: bytes | None,
            provenance: str, same_as: dict | None = None) -> dict:
    out: dict = {}
    if isinstance(method_or_status, int):
        out["httpStatus"] = method_or_status
    else:
        out["method"], out["path"] = method_or_status
    if content_type is not None:
        out["contentType"] = content_type
    if body is None:
        out["body"] = None
    else:
        out["bodyHex"] = body.hex()
        out["bodyLength"] = str(len(body))
        out["bodySha256"] = hashlib.sha256(body).hexdigest()
        out["bodyProvenance"] = provenance
        if same_as is not None:
            out["sameAs"] = same_as
    return out


def build_all(bundle_root: Path) -> dict[str, dict]:
    pv = PublishedVectors(bundle_root)
    wire = pv.wire["cases"]
    generation = bytes.fromhex(pv.wire["directoryGenerationHex"])
    alice_did = pv.identities["alice"]["did"]
    bob_did = pv.identities["bob"]["did"]
    b4_envelope = pv.envelope_bytes("b4-root")

    def wire_body(case_id: str, side: str) -> bytes:
        return bytes.fromhex(wire[case_id][f"{side}BytesHex"])

    def wire_ref(case_id: str, side: str) -> dict:
        return {"vector": "wire-b11", "case": case_id, "field": f"{side}BytesHex"}

    transcripts: dict[str, dict] = {}

    def add(name: str, doc: dict) -> None:
        transcripts[name] = {
            "bundle": BUNDLE,
            "file": name,
            "source": {
                "document": "authoring/specification/Followee-Specification.md",
                "sha256": SPEC_SHA256,
            },
            **doc,
        }

    info_body = cbor.encode({
        0: 1,
        1: RELAY_ID,
        2: 0x07,
        3: [1],
        4: [-19],
        5: {0: 16384, 1: 256, 2: 1048576, 3: 1024, 4: 4194304},
        6: CURSOR_GENERATION,
        7: generation,
        8: BASE_URI,
    })
    add("info.json", {
        "id": "transcript-info",
        "description": "Relay information. Protocol version, capability "
                       "bits, supported versions and suites, and the limits "
                       "map are schema-constrained by Section 12.2; the "
                       "relay identifier, generations, limit values, and "
                       "base URI shown here are example values a real relay "
                       "chooses itself.",
        "operation": "v1/info",
        "specificationSections": ["Section 12.1", "Section 12.2"],
        "scenario": "Any state.",
        "request": message(("GET", "v1/info"), None, None, ""),
        "response": message(200, "application/cbor", info_body,
                            "illustrative-nonnormative"),
        "structuralRequirements": [
            "label 0 MUST be 1",
            "label 3 MUST include protocol version 1",
            "label 4 MUST include signature suite -19",
            "labels 1, 6, and 7 are opaque 16-byte values",
            "capability bit 0x01 is set by every Relay Resolver and 0x02 "
            "by every Relay",
        ],
    })

    directory_body = cbor.encode({
        0: 1,
        1: generation,
        2: [
            {0: 0, 1: RELAY_ID, 2: BASE_URI, 3: 0x07},
            {0: 1, 1: PEER_RELAY_ID, 2: PEER_BASE_URI, 3: 0x03},
        ],
    })
    add("directory.json", {
        "id": "transcript-directory",
        "description": "Relay directory under the same directory generation "
                       "used by the published Appendix B.11 vectors. Entry "
                       "contents are example values; indices are meaningful "
                       "only with this generation (Section 11.4). Index 0 is "
                       "usable, as the Appendix B.11.7 scenario assumes.",
        "operation": "v1/directory",
        "specificationSections": ["Section 11.4", "Section 12.4"],
        "scenario": "Any state.",
        "request": message(("GET", "v1/directory"), None, None, ""),
        "response": message(200, "application/cbor", directory_body,
                            "illustrative-nonnormative"),
        "structuralRequirements": [
            "label 1 is the 16-byte directory generation; an index is "
            "interpreted only against the matching generation",
            "generation value 000102030405060708090a0b0c0d0e0f is the "
            "published Appendix B.11 example generation",
        ],
    })

    add("resolve-candidate-isolation.json", {
        "id": "transcript-resolve-candidate-isolation",
        "description": "Published Appendix B.11.3 exchange: a two-DID batch "
                       "whose first Full candidate (B.8) fails local "
                       "verification while the second (B.9) verifies. The "
                       "client accepts the wrapper, discards only index 0, "
                       "and keeps index 1.",
        "operation": "v1/resolve",
        "specificationSections": ["Section 12.3", "Appendix B.11.3"],
        "scenario": "Relay returns the B.8 substituted-descriptor envelope "
                    "for Alice and the valid B.9 envelope for Bob.",
        "request": message(("POST", "v1/resolve"), "application/cbor",
                           wire_body("b11-3-resolve-candidate-isolation", "request"),
                           "normative-specification",
                           wire_ref("b11-3-resolve-candidate-isolation", "request")),
        "response": message(200, "application/cbor",
                            wire_body("b11-3-resolve-candidate-isolation", "response"),
                            "normative-specification",
                            wire_ref("b11-3-resolve-candidate-isolation", "response")),
    })

    add("resolve-duplicate-dids.json", {
        "id": "transcript-resolve-duplicate-dids",
        "description": "Published Appendix B.11.4 exchange: duplicate "
                       "requested DIDs preserved positionally with exact "
                       "response cardinality.",
        "operation": "v1/resolve",
        "specificationSections": ["Section 12.3", "Appendix B.11.4"],
        "scenario": "Request [Alice, Alice, Bob]; relay is current for both.",
        "request": message(("POST", "v1/resolve"), "application/cbor",
                           wire_body("b11-4-duplicate-dids-cardinality", "request"),
                           "normative-specification",
                           wire_ref("b11-4-duplicate-dids-cardinality", "request")),
        "response": message(200, "application/cbor",
                            wire_body("b11-4-duplicate-dids-cardinality", "response"),
                            "normative-specification",
                            wire_ref("b11-4-duplicate-dids-cardinality", "response")),
    })

    add("resolve-malformed-did.json", {
        "id": "transcript-resolve-malformed-did",
        "description": "Published Appendix B.11.6 exchange: a syntactically "
                       "malformed DID inside a valid batch produces HTTP 200 "
                       "with a positionally aligned per-DID Error result, "
                       "not HTTP 400.",
        "operation": "v1/resolve",
        "specificationSections": ["Section 12.1", "Section 12.3",
                                  "Appendix B.11.6"],
        "scenario": "Request [Alice, did:flw:not-a-multibase, Bob].",
        "request": message(("POST", "v1/resolve"), "application/cbor",
                           wire_body("b11-6-malformed-did-in-batch", "request"),
                           "normative-specification",
                           wire_ref("b11-6-malformed-did-in-batch", "request")),
        "response": message(200, "application/cbor",
                            wire_body("b11-6-malformed-did-in-batch", "response"),
                            "normative-specification",
                            wire_ref("b11-6-malformed-did-in-batch", "response")),
    })

    add("resolve-invalid-request-400.json", {
        "id": "transcript-resolve-invalid-request-400",
        "description": "Published Appendix B.11.1 exchange: an outer request "
                       "with adjacent duplicate top-level keys is a "
                       "CBOR-layer fault. The relay rejects the complete "
                       "request with HTTP 400 and returns no per-item "
                       "results. No response CBOR body is normative for "
                       "this case.",
        "operation": "v1/resolve",
        "specificationSections": ["Section 12.1", "Section 15.4",
                                  "Appendix B.11.1"],
        "scenario": "Client sends the published invalid request bytes.",
        "request": message(("POST", "v1/resolve"), "application/cbor",
                           wire_body("b11-1-invalid-outer-request", "request"),
                           "normative-specification",
                           wire_ref("b11-1-invalid-outer-request", "request")),
        "response": message(400, None, None, ""),
    })

    publish_admit = cbor.encode({0: 1, 1: 0})
    add("publish-admit.json", {
        "id": "transcript-publish-admit",
        "description": "First publication of the published B.4 root record "
                       "to a relay with no entry for Alice. The record is "
                       "admitted and current: response status 0 "
                       "(Section 12.5), fully determined for this scenario.",
        "operation": "v1/publish",
        "specificationSections": ["Section 12.5", "Section 13.1"],
        "scenario": "Relay has no current entry for Alice; recipient clock "
                    "nowMs=1785589201123 makes the record time-admissible.",
        "request": message(("POST", "v1/publish"), "application/cose",
                           b4_envelope, "normative-specification",
                           {"vector": "records", "case": "b4-root",
                            "field": "envelopeHex"}),
        "response": message(200, "application/cbor", publish_admit,
                            "specification-determined"),
    })

    publish_no_change = cbor.encode({0: 1, 1: 1})
    no_change_response = message(200, "application/cbor", publish_no_change,
                                 "permitted-diagnostic-variation",
                                 {"vector": "publish-responses",
                                  "case": "publish-accept-status-1-bare",
                                  "field": "responseHex"})
    no_change_response["variationGroup"] = "publish-status-1"
    add("publish-no-change.json", {
        "id": "transcript-publish-no-change",
        "description": "Republication of the identical B.4 record. The body "
                       "digest is already current, so the record is valid "
                       "but changes nothing: status 1, no new relay-local "
                       "update number (Sections 12.5, 13.2). Shown without "
                       "the optional diagnostic reason; under specification "
                       "v0.9.2 a relay MAY instead answer with the accurate "
                       "`duplicate` reason code, as the companion "
                       "publish-no-change-diagnostic transcript documents. "
                       "The two encodings are byte-distinct permitted forms "
                       "of the same outcome and are never normalized into "
                       "each other.",
        "operation": "v1/publish",
        "specificationSections": ["Section 12.5", "Section 13.2",
                                  "Section 15.3"],
        "scenario": "Relay is already current with the B.4 record for Alice.",
        "request": message(("POST", "v1/publish"), "application/cose",
                           b4_envelope, "normative-specification",
                           {"vector": "records", "case": "b4-root",
                            "field": "envelopeHex"}),
        "response": no_change_response,
    })

    publish_no_change_diag = cbor.encode({0: 1, 1: 1, 2: 13})
    diag_response = message(200, "application/cbor", publish_no_change_diag,
                            "permitted-diagnostic-variation",
                            {"vector": "publish-responses",
                             "case": "publish-accept-status-1-duplicate",
                             "field": "responseHex"})
    diag_response["variationGroup"] = "publish-status-1"
    diag_response["diagnosticVariationOf"] = "publish-no-change.json"
    add("publish-no-change-diagnostic.json", {
        "id": "transcript-publish-no-change-diagnostic",
        "description": "The same republication of the identical B.4 record, "
                       "answered with the optional accurate `duplicate` "
                       "reason code permitted on status 1 by specification "
                       "v0.9.2 (Sections 12.5, 15.3). This is a conforming "
                       "byte-distinct encoding of the same no-change "
                       "outcome as the publish-no-change transcript; the "
                       "difference is permitted diagnostic variation, "
                       "never a disagreement, and neither form is "
                       "normalized into the other.",
        "operation": "v1/publish",
        "specificationSections": ["Section 12.5", "Section 13.2",
                                  "Section 15.3"],
        "scenario": "Relay is already current with the B.4 record for Alice.",
        "request": message(("POST", "v1/publish"), "application/cose",
                           b4_envelope, "normative-specification",
                           {"vector": "records", "case": "b4-root",
                            "field": "envelopeHex"}),
        "response": diag_response,
    })

    publish_losing = cbor.encode({0: 1, 1: 1, 2: 12})
    losing_response = message(200, "application/cbor", publish_losing,
                              "permitted-diagnostic-variation",
                              {"vector": "publish-responses",
                               "case": "publish-accept-status-1-losingRecord",
                               "field": "responseHex"})
    losing_response["variationGroup"] = "publish-status-1-losing"
    add("publish-losing-record.json", {
        "id": "transcript-publish-losing-record",
        "description": "Publication of the valid B.6 \"Alice B\" record "
                       "while the relay is current with the equal-timestamp "
                       "lower-digest B.6 \"Alice A\" record. The candidate "
                       "verifies but loses current ordering (Sections 8.3, "
                       "13.1, 13.2): status 1, shown with the optional "
                       "accurate `losingRecord` reason code permitted by "
                       "specification v0.9.2. The bare status-1 form is "
                       "equally conforming for this scenario; the presence "
                       "of the reason code is the relay's choice and is "
                       "classified as permitted diagnostic variation.",
        "operation": "v1/publish",
        "specificationSections": ["Section 12.5", "Section 13.1",
                                  "Section 13.2", "Section 15.3"],
        "scenario": "Relay is current for Alice with the B.6 \"Alice A\" "
                    "record; the client publishes the valid equal-timestamp "
                    "higher-digest B.6 \"Alice B\" record; recipient clock "
                    "nowMs=1785589201123.",
        "request": message(("POST", "v1/publish"), "application/cose",
                           pv.envelope_bytes("b6-alice-b"),
                           "specification-determined",
                           {"vector": "records", "case": "b6-alice-b",
                            "field": "envelopeHex"}),
        "response": losing_response,
    })

    publish_rejected = cbor.encode({0: 1, 1: 2, 2: 7})
    add("publish-rejected.json", {
        "id": "transcript-publish-rejected",
        "description": "Publication of the published B.8 "
                       "substituted-descriptor envelope for Alice's DID. "
                       "Verification fails at descriptor binding, so the "
                       "relay rejects with status 2 and error code 7, "
                       "identityBindingMismatch (Sections 8.1, 15.3).",
        "operation": "v1/publish",
        "specificationSections": ["Section 12.5", "Section 8.1",
                                  "Section 15.3", "Appendix B.8"],
        "scenario": "Any state; the candidate never affects the current map.",
        "request": message(("POST", "v1/publish"), "application/cose",
                           pv.envelope_bytes("b8-descriptor-substitution"),
                           "normative-specification",
                           {"vector": "envelopes-negative",
                            "case": "b8-descriptor-substitution",
                            "field": "envelopeHex"}),
        "response": message(200, "application/cbor", publish_rejected,
                            "specification-determined"),
    })

    add("changes-sync.json", {
        "id": "transcript-changes-sync",
        "description": "Published Appendix B.11.5 exchange: the Section 20.4 "
                       "state-exchange example. A receiving relay pulls "
                       "current-state changes from a peer, admits Bob's "
                       "valid record, rejects the B.8 candidate without "
                       "stalling, and stores the exact returned nextCursor. "
                       "In the two-direction interoperability run each "
                       "implementation plays each side of this exchange.",
        "operation": "v1/changes",
        "specificationSections": ["Section 12.6", "Section 13.3",
                                  "Section 20.4", "Appendix B.11.5"],
        "scenario": wire["b11-5-changes-isolation-cursor"]["initialReceiverState"],
        "requiredPostState": wire["b11-5-changes-isolation-cursor"]["requiredPostState"],
        "request": message(("POST", "v1/changes"), "application/cbor",
                           wire_body("b11-5-changes-isolation-cursor", "request"),
                           "normative-specification",
                           wire_ref("b11-5-changes-isolation-cursor", "request")),
        "response": message(200, "application/cbor",
                            wire_body("b11-5-changes-isolation-cursor", "response"),
                            "normative-specification",
                            wire_ref("b11-5-changes-isolation-cursor", "response")),
    })

    add("changes-item-limit-overflow.json", {
        "id": "transcript-changes-item-limit-overflow",
        "description": "Published Appendix B.11.7 exchange: a success "
                       "response carrying more entries than the requested "
                       "itemLimit. The receiver rejects the complete "
                       "response, processes no entry, and does not use its "
                       "nextCursor.",
        "operation": "v1/changes",
        "specificationSections": ["Section 12.6", "Appendix B.11.7"],
        "scenario": wire["b11-7-changes-item-limit-overflow"]["initialReceiverState"],
        "requiredPostState": wire["b11-7-changes-item-limit-overflow"]["requiredPostState"],
        "request": message(("POST", "v1/changes"), "application/cbor",
                           wire_body("b11-7-changes-item-limit-overflow", "request"),
                           "normative-specification",
                           wire_ref("b11-7-changes-item-limit-overflow", "request")),
        "response": message(200, "application/cbor",
                            wire_body("b11-7-changes-item-limit-overflow", "response"),
                            "normative-specification",
                            wire_ref("b11-7-changes-item-limit-overflow", "response")),
    })

    initial_request = cbor.encode({0: 1, 1: None, 2: 100, 3: 1048576})
    initial_response = cbor.encode({
        0: 1,
        1: 0,
        2: [
            [alice_did, {0: 0, 1: b4_envelope}, 41],
            [bob_did, {0: 0, 1: pv.envelope_bytes("b9-bob-root")}, 42],
        ],
        3: b"c-42",
        4: False,
        5: generation,
    })
    add("changes-initial-enumeration.json", {
        "id": "transcript-changes-initial-enumeration",
        "description": "Bounded initial enumeration with a null cursor "
                       "(Section 12.6). The relay returns its current "
                       "tuples in increasing lastUpdated order. The cursor "
                       "bytes and lastUpdated values shown are relay-local "
                       "example values; the entry payloads are the published "
                       "B.4 and B.9 envelopes.",
        "operation": "v1/changes",
        "specificationSections": ["Section 12.6", "Section 12.7"],
        "scenario": "Relay is current for Alice (B.4, lastUpdated 41) and "
                    "Bob (B.9, lastUpdated 42); a new peer starts with a "
                    "null cursor.",
        "request": message(("POST", "v1/changes"), "application/cbor",
                           initial_request, "specification-determined"),
        "response": message(200, "application/cbor", initial_response,
                            "illustrative-nonnormative"),
    })

    premature_changes_response = cbor.encode({
        0: 1,
        1: 0,
        2: [
            [alice_did, {0: 0, 1: b4_envelope}, 41],
        ],
        3: b"c-41",
        4: False,
        5: generation,
    })
    add("changes-premature-retained.json", {
        "id": "transcript-changes-premature-retained",
        "description": "A retained current tuple whose record is premature "
                       "under the serving relay's own clock is still emitted "
                       "by v1/changes. Admission made the tuple eligible for "
                       "v1/changes (Section 13.1 step 8), and the "
                       "serving-time premature classification neither "
                       "removes the stored record nor alters lastUpdated "
                       "(Section 5.4), so the tuple remains an eligible "
                       "current entry that Section 12.6 forbids the cursor "
                       "to advance past if omitted. The Section 5.4 "
                       "prohibition on returning the record as Full governs "
                       "the Relay Resolver serving path with the "
                       "Section 12.3 Error fallback; the synchronization "
                       "stream instead delivers untrusted candidate bytes "
                       "that each receiver classifies under its own clock "
                       "(Sections 13.3, 16.16), never importing the "
                       "sender's premature diagnosis (Section 14.1). The "
                       "cursor bytes and lastUpdated values shown are "
                       "relay-local example values; the entry payload is "
                       "the published B.4 envelope. The companion "
                       "resolve-premature-retained transcript pins the "
                       "resolve-side filtering of the same relay state.",
        "operation": "v1/changes",
        "specificationSections": ["Section 5.4", "Section 12.6",
                                  "Section 13.1", "Section 13.3",
                                  "Section 14.1", "Section 16.16"],
        "scenario": {
            "alice": {
                "entry": {"vector": "records", "case": "b4-root"},
                "authorityState": "root",
                "lastUpdated": "41",
            },
            "localUpdateCounter": "41",
            "relayNowMs": "1785588900122",
            "relayClassifiesRetainedRecord": "premature",
        },
        "requiredPostState": {
            "sender": {
                "aliceEntryUnchanged": True,
                "aliceLastUpdated": "41",
                "noNewUpdateNumber": True,
            },
            "receiverWithNowMs1785589201123": {
                "aliceAdmitted": {"vector": "records", "case": "b4-root"},
                "classification": "time-admissible",
            },
            "receiverWithNowMs1785588900122": {
                "aliceClassification": "premature",
                "aliceRejectedOrDeferred": True,
                "noReceiverUpdateNumber": True,
                "peerCursorStoredAndAdvanced": True,
            },
        },
        "request": message(("POST", "v1/changes"), "application/cbor",
                           initial_request, "specification-determined"),
        "response": message(200, "application/cbor",
                            premature_changes_response,
                            "illustrative-nonnormative"),
        "structuralRequirements": [
            "the retained current tuple MUST appear in the changes "
            "response; omitting it while advancing nextCursor would "
            "advance past an omitted eligible entry (Section 12.6), and "
            "withholding nextCursor would stall the stream",
            "emitting the tuple assigns no new update number and does not "
            "alter lastUpdated (Sections 5.4, 13.2)",
            "each receiver classifies the candidate under its own nowMs "
            "and never imports the sender's clock (Sections 13.3, 14.1)",
            "a receiver that rejects or defers the locally premature "
            "candidate still stores the returned nextCursor "
            "(Sections 13.3, 16.16)",
        ],
    })

    premature_resolve_request = cbor.encode({0: 1, 1: [alice_did]})
    premature_resolve_response = cbor.encode({
        0: 1,
        1: generation,
        2: [{0: 3, 2: 10}],
    })
    add("resolve-premature-retained.json", {
        "id": "transcript-resolve-premature-retained",
        "description": "The same relay state as the "
                       "changes-premature-retained transcript, queried "
                       "through v1/resolve: the relay retains a Full record "
                       "for Alice that its present clock classifies as "
                       "premature (for example after a backwards clock "
                       "correction) and holds no usable Ref. Section 5.4 "
                       "forbids returning the record as Full, and "
                       "Section 12.3 requires the aligned per-DID Error "
                       "result with code 10 (premature), never Absent. The "
                       "contrast with the changes emission of the identical "
                       "state is deliberate: resolve filters the premature "
                       "record; the synchronization stream carries it.",
        "operation": "v1/resolve",
        "specificationSections": ["Section 5.4", "Section 12.3",
                                  "Section 14.1", "Section 15.3"],
        "scenario": {
            "alice": {
                "entry": {"vector": "records", "case": "b4-root"},
                "authorityState": "root",
                "lastUpdated": "41",
            },
            "usableRef": False,
            "relayNowMs": "1785588900122",
            "relayClassifiesRetainedRecord": "premature",
        },
        "request": message(("POST", "v1/resolve"), "application/cbor",
                           premature_resolve_request,
                           "specification-determined"),
        "response": message(200, "application/cbor",
                            premature_resolve_response,
                            "specification-determined"),
        "structuralRequirements": [
            "the relay MUST NOT return the retained record as Full while "
            "its clock classifies it as premature (Section 5.4)",
            "the result MUST be the aligned per-DID Error result "
            "{0: 3, 2: 10}, not Absent (Section 12.3)",
            "the serving-time classification removes nothing, alters no "
            "lastUpdated, and assigns no update number (Section 5.4)",
            "a client MUST NOT import this per-relay diagnostic into "
            "another candidate or defer the DID because of it "
            "(Section 14.1)",
        ],
    })

    reset_response = cbor.encode({0: 1, 1: 1})
    add("changes-reset-required.json", {
        "id": "transcript-changes-reset-required",
        "description": "ResetRequired after a cursor-generation reset "
                       "(Sections 12.6, 12.7). Status 1 is the sole v1 wire "
                       "encoding of ResetRequired and the response contains "
                       "exactly labels 0 and 1; these five bytes are fully "
                       "determined. The stale cursor value in the request "
                       "is an example. In the live campaign this probe is "
                       "obtained naturally — a cursor issued before a "
                       "genuine generation reset, or a cursor returned by a "
                       "second relay instance of the same participant — "
                       "never by forging or injection (ACCEPTANCE Gate G3).",
        "operation": "v1/changes",
        "specificationSections": ["Section 12.6", "Section 12.7"],
        "scenario": "The relay reset its cursor generation; the peer "
                    "presents a cursor from the old generation.",
        "request": message(("POST", "v1/changes"), "application/cbor",
                           cbor.encode({0: 1, 1: b"old-gen-cursor", 2: 100,
                                        3: 1048576}),
                           "illustrative-nonnormative"),
        "response": message(200, "application/cbor", reset_response,
                            "specification-determined"),
    })

    oversized = oversized_envelope(pv.identities["alice"],
                                   _identity_inputs()["alice"]["root"])
    publish_too_large = cbor.encode({0: 1, 1: 2, 2: 3})
    add("publish-record-too-large.json", {
        "id": "transcript-publish-record-too-large",
        "description": "Publication of a validly signed complete envelope "
                       "of exactly 16385 bytes — one byte over the "
                       "Section 15.1 hard cap, with every other record rule "
                       "satisfied, so the assertion is fault-isolated "
                       "(Section 6.1.3). The relay enforces the outer byte "
                       "limit before allocating from declared inner lengths "
                       "(Sections 15.1, 13.1 step 1, 8.1 step 1) and "
                       "rejects with status 2 and error code 3, "
                       "recordTooLarge, carried by HTTP 200 as ordinary "
                       "successful protocol processing (Section 15.4). "
                       "Transport-cap precondition: this normative case is "
                       "valid for comparison only when the complete "
                       "16385-byte request is below every participant's "
                       "declared pre-parse publish transport cap, as "
                       "recorded and confirmed by ACCEPTANCE Gate G2. A "
                       "request in the band above one participant's "
                       "transport cap may instead receive a pre-parse "
                       "HTTP 413 (Section 15.4); the differing raw HTTP "
                       "outcomes in that band are permitted transport "
                       "variation, preserved and reported, never "
                       "normalized, and never a protocol disagreement.",
        "operation": "v1/publish",
        "specificationSections": ["Section 6.1.3", "Section 8.1",
                                  "Section 13.1", "Section 15.1",
                                  "Section 15.3", "Section 15.4"],
        "scenario": "Any state; the candidate is rejected by the outer "
                    "byte-limit check before parsing and never affects the "
                    "current map. Recipient clock nowMs=1785589201123. The "
                    "complete request is below every declared participant "
                    "transport cap (Gate G2).",
        "request": message(("POST", "v1/publish"), "application/cose",
                           oversized, "specification-determined"),
        "response": message(200, "application/cbor", publish_too_large,
                            "specification-determined",
                            {"vector": "publish-responses",
                             "case": "publish-accept-status-2-recordTooLarge",
                             "field": "responseHex"}),
        "structuralRequirements": [
            "the request is exactly 16385 bytes: minimally over the "
            "16 KiB Section 15.1 cap",
            "outer byte limits MUST be enforced before allocating from "
            "declared inner lengths (Section 15.1)",
            "the rejection is expressed by protocol status 2 with "
            "errorCode 3 under HTTP 200, not by a non-200 HTTP status "
            "(Section 15.4)",
            "no state changes and no update number is assigned",
        ],
    })

    hostile_client_behaviour = {
        "rejectCompleteResponse": True,
        "classification": "schemaViolation",
        "noUsableProtocolState": True,
    }

    info_missing_version = cbor.encode({
        0: 1,
        1: RELAY_ID,
        2: 0x07,
        3: [2],
        4: [-19],
        5: {0: 16384, 1: 256, 2: 1048576, 3: 1024, 4: 4194304},
        6: CURSOR_GENERATION,
        7: generation,
        8: BASE_URI,
    })
    add("info-missing-version.json", {
        "id": "transcript-info-missing-version",
        "description": "Hostile-peer case: a relay-info response whose "
                       "supported-versions array omits the required "
                       "protocol version 1 (Section 12.2: a v1 "
                       "implementation MUST include protocol version 1). "
                       "The content requirement is part of the applicable "
                       "v1 schema (Appendix A closing note), so the "
                       "receiving client MUST reject the complete response "
                       "(Section 12.1) with the schemaViolation "
                       "classification (Sections 15.3, 6.1.3) and extract "
                       "no usable protocol state from it. Every other "
                       "member is valid example content, so the assertion "
                       "is fault-isolated.",
        "operation": "v1/info",
        "specificationSections": ["Section 6.1.3", "Section 12.1",
                                  "Section 12.2", "Section 15.3"],
        "scenario": "A hostile or non-conforming peer serves an otherwise "
                    "well-formed info response advertising only an unknown "
                    "protocol version.",
        "request": message(("GET", "v1/info"), None, None, ""),
        "response": message(200, "application/cbor", info_missing_version,
                            "illustrative-nonnormative"),
        "requiredClientBehaviour": hostile_client_behaviour,
        "structuralRequirements": [
            "label 3 omits protocol version 1; label 4 still carries "
            "suite -19, isolating the fault",
            "the client MUST reject the complete response and MUST NOT "
            "extract a relay identifier, limits, generations, or any "
            "other protocol state from it",
            "the local classification is schemaViolation (Section 15.3 "
            "code 6, Section 6.1.3 fallback)",
        ],
    })

    info_missing_suite = cbor.encode({
        0: 1,
        1: RELAY_ID,
        2: 0x07,
        3: [1],
        4: [-8],
        5: {0: 16384, 1: 256, 2: 1048576, 3: 1024, 4: 4194304},
        6: CURSOR_GENERATION,
        7: generation,
        8: BASE_URI,
    })
    add("info-missing-suite.json", {
        "id": "transcript-info-missing-suite",
        "description": "Hostile-peer case: a relay-info response whose "
                       "supported-suites array omits the required signature "
                       "suite -19 (Section 12.2: a v1 implementation MUST "
                       "include signature suite -19). As with the missing "
                       "version marker, the content requirement is part of "
                       "the applicable v1 schema (Appendix A closing note); "
                       "the receiving client MUST reject the complete "
                       "response (Section 12.1) with schemaViolation "
                       "(Sections 15.3, 6.1.3) and extract no usable "
                       "protocol state. Every other member is valid example "
                       "content, isolating the fault.",
        "operation": "v1/info",
        "specificationSections": ["Section 6.1.3", "Section 12.1",
                                  "Section 12.2", "Section 15.3"],
        "scenario": "A hostile or non-conforming peer serves an otherwise "
                    "well-formed info response advertising only an unknown "
                    "signature suite.",
        "request": message(("GET", "v1/info"), None, None, ""),
        "response": message(200, "application/cbor", info_missing_suite,
                            "illustrative-nonnormative"),
        "requiredClientBehaviour": hostile_client_behaviour,
        "structuralRequirements": [
            "label 4 omits suite -19; label 3 still carries protocol "
            "version 1, isolating the fault",
            "the client MUST reject the complete response and MUST NOT "
            "extract any protocol state from it",
            "the local classification is schemaViolation (Section 15.3 "
            "code 6, Section 6.1.3 fallback)",
        ],
    })

    directory_duplicate_index = cbor.encode({
        0: 1,
        1: generation,
        2: [
            {0: 0, 1: RELAY_ID, 2: BASE_URI, 3: 0x07},
            {0: 0, 1: PEER_RELAY_ID, 2: PEER_BASE_URI, 3: 0x03},
        ],
    })
    add("directory-duplicate-index.json", {
        "id": "transcript-directory-duplicate-index",
        "description": "Hostile-peer case: a directory response assigning "
                       "the same index to two different endpoints within "
                       "one generation. Section 11.4 forbids reusing an "
                       "index for another endpoint within the same "
                       "generation, so the mapping is not schema-conforming "
                       "content and reference interpretation against it "
                       "would be ambiguous. The receiving client MUST "
                       "reject the complete response (Section 12.1) with "
                       "schemaViolation (Sections 15.3, 6.1.3) and follow "
                       "no reference through it. The outer CBOR remains "
                       "well-formed and deterministic; the fault is the "
                       "duplicate index assignment alone.",
        "operation": "v1/directory",
        "specificationSections": ["Section 6.1.3", "Section 11.4",
                                  "Section 12.1", "Section 12.4",
                                  "Section 15.3"],
        "scenario": "A hostile or non-conforming peer serves a directory "
                    "reusing index 0 for two different endpoints under one "
                    "generation.",
        "request": message(("GET", "v1/directory"), None, None, ""),
        "response": message(200, "application/cbor",
                            directory_duplicate_index,
                            "illustrative-nonnormative"),
        "requiredClientBehaviour": hostile_client_behaviour,
        "structuralRequirements": [
            "two entries carry index 0 with different relay identifiers "
            "and endpoints under the same generation (Section 11.4)",
            "the client MUST reject the complete response, resolve no "
            "reference through it, and cache nothing from it",
            "the local classification is schemaViolation (Section 15.3 "
            "code 6, Section 6.1.3 fallback)",
        ],
    })

    return transcripts


def render(content: dict) -> bytes:
    return (json.dumps(content, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    bundle_root = Path(__file__).resolve().parent.parent
    target_dir = bundle_root / "coordinator" / "transcripts"
    target_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name, content in build_all(bundle_root).items():
        rendered = render(content)
        path = target_dir / name
        if args.write:
            path.write_bytes(rendered)
            print(f"wrote {name} ({len(rendered)} bytes)")
        else:
            if (path.read_bytes() if path.exists() else None) != rendered:
                print(f"MISMATCH: {name}")
                failures += 1
            else:
                print(f"ok {name}")
    return 1 if (args.check and failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
