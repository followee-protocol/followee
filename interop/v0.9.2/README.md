# Followee v0.9.2 external-interoperability bundle

This directory is the neutral, language-independent bundle for the
Followee **Campaign 2** interoperability rerun required by specification
Section 20.4 after the v0.9.2 publish-response clarification. It
retains the complete v0.9.1 authoring/coordinator separation and adds
the Section 12.5 publish-response field-presence coverage the v0.9.2
amendment introduced.

**Campaign 2 is a maintenance interoperability campaign between
reviewed implementations.** One participant has an independently
authored frozen ancestor, but Campaign 2 itself is not a new
independent-authoring exercise: the blind challenge inputs are the
v0.9.1 inputs preserved byte-for-byte, their rerun is maintenance
confirmation, and the original first-blind evidence remains the frozen
Campaign 1 record. **This bundle makes no interoperability claim.** No
implementation may be described as interoperable until the complete
two-direction cross-implementation run in `ACCEPTANCE.md` has
succeeded, and communicating with another process built from the same
core library never counts.

## Layout

```
interop/v0.9.2/
├── README.md            this file
├── MANIFEST.json        every file: SHA-256, size, provenance, audience,
│                        plus the tag/commit/digest pins for reproduction
├── PROVENANCE.md        provenance categories and their rules
├── ACCEPTANCE.md        Section 20.4 obligation matrix, campaign order,
│                        and the run plan
├── authoring/           THE AUTHORING SUBSET — the only material a
│   │                    participant-maintenance session may receive
│   │                    before its v0.9.2 freeze
│   ├── AUTHORING.md     subset charter: contents, rules, exclusions,
│   │                    and the freeze sequence
│   ├── NONDETERMINISM.md   opacity and comparison policy, including the
│   │                    enumerated permitted publish status-1 variation
│   ├── specification/   pinned normative specification v0.9.2
│   ├── interface/       mechanical operation and framing contract
│   │                    (adds `receivePublishResponse`)
│   └── vectors/
│       ├── published/   Appendix B values LITERALLY PUBLISHED in the
│       │                pinned document — nothing merely derived
│       └── challenge/   the v0.9.1 blind inputs, byte-identical — no
│                        expected outputs anywhere
├── coordinator/         WITHHELD until both participant freezes
│   ├── COORDINATOR.md   exposure rules and the campaign order
│   ├── expected/        full Phase 1 expectations, including every
│   │                    unchanged v0.9.1 case and the new
│   │                    publish-responses.json matrix
│   └── transcripts/     documented HTTP/CBOR exchanges (v1/info,
│                        v1/resolve, v1/directory, v1/publish incl. the
│                        permitted status-1 diagnostic forms, v1/changes)
├── evidence/            pins to reviewed evidence (pointers only)
└── verify/              stdlib-only deterministic verification tooling
    ├── interopkit/      deterministic CBOR, base58btc, RFC 8032 Ed25519
    ├── extract_published_vectors.py   regenerates both vector trees
    ├── gen_transcripts.py             regenerates coordinator/transcripts/
    ├── verify_bundle.py               full verification + manifest
    └── tests/                         unit and tamper tests
```

The split is deliberate: the independence boundary is a directory
boundary. `authoring/` contains only the pinned specification, the
neutral interface contract, authoring/nondeterminism instructions,
literally published Appendix B values, and the preserved blind
challenge inputs. Every expected value absent from the specification —
however deterministically derived — lives under `coordinator/`, and
`verify_bundle.py` proves mechanically that no coordinator-derived
result-like token or coordinator-only case identifier is reachable from
the authoring tree.

## What v0.9.2 adds

- `coordinator/expected/publish-responses.json`: the complete
  Section 12.5 status/`errorCode` matrix — statuses `0` and `1` bare,
  status `1` with each accurate no-change reason, per-code rejection of
  every other registered code on status `1`, status `2` with every
  registered rejection code, every malformed registered combination,
  and explicit unregistered-value probes (the first value beyond the
  registered range on every status, plus the canonical uint64 maximum
  on status `2`) — with exact classifications for the new
  `receivePublishResponse` interface operation. The Section 15.3
  registry is the complete v1 wire error-code vocabulary: Section 12.5
  requires a status `2` response to identify its rejection with a
  Section 15.3 code, so an unregistered value makes the response
  malformed on every status and the complete response is rejected
  without extracting a status or changing state.
- Transcripts for both permitted status-1 encodings
  (`publish-no-change.json`, `publish-no-change-diagnostic.json`) and a
  losing-record scenario (`publish-losing-record.json`). The permitted
  forms are byte-distinct and are never normalized into each other;
  their difference is classified `permitted-diagnostic-variation`.
- Manifest pins for the reviewed specification tag, the unchanged
  Appendix B digest, the reviewed v0.9.1 bundle, and the frozen
  Campaign 1 archive.

## Authoring revision 2 (v0.9.2-r2)

The AUTHORING subset has a second authoring revision — **not** a
specification revision; the pinned specification is byte-identical.
The neutral interface contract (`authoring/interface/INTERFACE.md`)
was corrected by merging the reviewed integration patch into the
sections it replaces: the value conventions, the structured contact
shape, and the `verifyRecord` accepted-result definition. In step:

- accepted `verifyRecord` expectations in
  `coordinator/expected/verification.json` now carry the complete
  corrected accepted-result projection;
- four validly signed **direct-wire** cases were added there, covering
  present-empty optional collections that `authorRecord` cannot
  construct (present-empty `alsoKnownAs`, a present-empty Contact
  Document extension map, and a present-empty record-body extension
  map, plus all three combined), preserving the `[]` / `{}` / absence
  distinction;
- every other generated file, every authored byte, every rejection
  classification, and the preserved blind challenge inputs are
  unchanged, as predeclared in
  `coordinator/AUTHORING-REVISION-2.md`.

Both authoring seals are recorded in
`coordinator/PRECLASSIFICATION.md` and the current one is enforced by
the verifier; the r1 seal is preserved as historical evidence for the
already-frozen participant input.

Campaign 1 correctly recorded the publish status-1 encoding difference
as an unresolved specification ambiguity at the time it ran;
specification v0.9.2 resolves that ambiguity and this bundle now
classifies the observed variation as permitted. The Campaign 1 archive
itself is immutable historical evidence and is not rewritten.

## Campaign 2 execution

Campaign 2 has been executed against this bundle at authoring
revision 2, between the recorded freezes
`rust-v0.9.2-maintained-freeze` (`d865dc3f…`) and
`motoko-v0.9.2-r2-maintained-freeze` (`bb0b0782…`); the freeze pins
are recorded in `evidence/EVIDENCE.md` and the complete campaign
deliverable — phase reports, executable gate results, raw exchanges,
classifications, and the deterministic archive — lives in
`../campaign-2/` (`CAMPAIGN.md`). All three phases and all three
pre-Phase-3 gates completed with zero unexplained disagreements; the
run report states its Section 20.4 conclusion, its coverage boundary,
and the maintained-participant framing there. This bundle itself still
asserts no interoperability claim.

## Verifying the bundle

From this directory:

```
python3 verify/verify_bundle.py
python3 -m unittest discover -s verify/tests
```

Verification requires only a Python 3 standard library. It confirms the
manifest and its pins, the pinned specification hash, the byte-identity
of the Appendix B region with v0.9.1, the byte-identity of the
challenge inputs with the v0.9.1 files, byte-identical regeneration of
every generated file from the specification, every published byte,
length, digest, and signature assertion, the complete publish-response
matrix, transcript framing, challenge-file blindness, AUTHORING-subset
hygiene, and the independence boundary.

## Regenerating generated files

```
python3 verify/extract_published_vectors.py --check   # or --write
python3 verify/gen_transcripts.py --check             # or --write
python3 verify/verify_bundle.py --write-manifest
```

Generation is deterministic; regenerating an unmodified bundle changes
no bytes. Everything under `authoring/vectors/published/`,
`coordinator/expected/`, and `coordinator/transcripts/` is derived from
the pinned specification copy alone.

## Version

Bundle `followee-interop/v0.9.2`, pinned to Followee specification
v0.9.2 (SHA-256
`47af5fbf0c4505386b4e04d948ef89d013f878ea820fb02522817661d633633a`,
tag `v0.9.2-reviewed`). The Appendix B region is byte-identical to
v0.9.1. A normative change to CBOR classification, relay wrappers, or
cursor visibility obsoletes this bundle version (Section 20.4); a new
bundle is generated under a new versioned directory and the experiment
reruns.
