# Provenance model

Every file in this bundle carries exactly one provenance category in
`MANIFEST.json`, and vector and transcript files additionally mark
finer-grained provenance per case or per message. The categories:

## `normative-specification`

Material literally published in the pinned Followee specification
v0.9.2 (SHA-256
`47af5fbf0c4505386b4e04d948ef89d013f878ea820fb02522817661d633633a`):
the pinned specification copy itself and the AUTHORING vector files,
whose every value — bytes, digests, lengths, signatures, DIDs, error
classifications, receiver states — appears verbatim in the document.
Nothing in this category is merely derivable; it is printed in the
specification. The Appendix B region is byte-identical to v0.9.1.

## `specification-determined`

Values computed for this bundle by the specification's deterministic
algorithms from published inputs, but **absent from the document
itself**: reconstructed B.10/B.12 bodies and envelopes, reconstructed
Appendix B.11 response bytes, unpublished derivation-chain members, the
unpublished B.6 full outputs, constructed comparison cases (target-DID
variants, selection permutations, clock and timestamp scenarios), and
the v0.9.2 publish-response classification matrix, whose exact
accept/reject rule is normative Section 12.5 text while the encoded
case bytes themselves are constructed. Cross-confirmed against reviewed
evidence where available. **Coordinator-only**: the distinction between
this category and `normative-specification` is the independence
boundary, and the verifier proves no value in this category is
reachable from the AUTHORING subset.

## `mechanically-derived`

Neutral material produced mechanically from normative sources without
interpretive freedom and without expected values: the interface
contract (operation names, shapes, and framing restated from the
reviewed neutral conformance-runner surface, plus the
`receivePublishResponse` operation restated from the Section 12.5
receiver rule, with all harness- and adapter-specific language
removed). At authoring revision 2 (v0.9.2-r2) the contract additionally
incorporates the reviewed integration patch correcting the value
conventions, the structured contact shape, and the `verifyRecord`
accepted-result projection; the patch is derived solely from the pinned
specification and the existing neutral conventions and, like the rest
of this category, contains no fixture value and no
implementation-derived expectation.

## `challenge-input`

The blind challenge inputs, preserved byte-for-byte from bundle
v0.9.1 (each file's embedded `bundle` member keeps its original
version marker as provenance). No expected output for any challenge
case appears anywhere in this bundle. See
`authoring/vectors/challenge/CHALLENGES.md`. In the v0.9.2 maintenance
pass these inputs serve as maintenance confirmation; the original
first-blind run is completed historical evidence.

## `illustrative-nonnormative`

Example values for wire fields the specification leaves relay-chosen or
opaque (relay identifiers, generations, cursors, limits, base URIs),
appearing only inside coordinator transcript messages explicitly marked
`illustrative-nonnormative`, plus the transcript framing metadata
itself. Never a byte-comparison target.

## `permitted-diagnostic-variation`

One member of a **specification-enumerated** set of conforming
encodings for the same protocol outcome — in v1, exactly the publish
status `1` response with and without an accurate `losingRecord` or
`duplicate` reason code (specification Section 12.5). The category has
two distinct roles, and both are deliberately narrow:

- **As provenance** (this manifest and per-message markings), it
  answers why one exact byte sequence appears in the bundle even
  though the specification permits more than one encoding for the
  stated scenario: the bytes shown are one enumerated member,
  reconstructed deterministically by the bundle tooling from the
  normative rule — never captured from, or chosen to match, any
  implementation's output. Each member is itself byte-deterministic
  and **is** a byte-comparison target against the enumerated set.
- **As a comparison classification** (campaign reports), it answers
  why two conforming raw responses may differ without constituting a
  disagreement: the specification itself makes the choice among the
  enumerated members the emitting Relay's. Harnesses byte-compare each
  observed response against the enumerated set, keep the members
  byte-distinct, never normalize one into another, and report which
  member was chosen — visibly, and never as a disagreement
  (Section 20.4 reporting rule).

The category applies only where the pinned specification itself
enumerates the complete conforming set. It is never a device for
treating arbitrary implementation output as normative: a byte sequence
outside the enumerated set — including any `errorCode` value outside
the complete Section 15.3 wire vocabulary — is not "variation" but a
malformed response, classified and rejected as such.

## `confirmed-evidence-pointer`

Pointers — commit hashes, tags, and aggregate digests only, never
copies — to independently confirmed evidence outside this directory:
the reviewed v0.9.1 bundle, the frozen Campaign 1 archive, and the
reviewed implementation revisions listed in `evidence/EVIDENCE.md`.

## `bundle-infrastructure`

The bundle's own documentation, manifest, and verification tooling.
The `verify/` tree is stdlib-only Python written for this bundle from
the pinned specification; it imports no Followee implementation and is
excluded from the AUTHORING subset.

## Directory-to-category mapping

| Path | Category |
| --- | --- |
| `authoring/specification/` | normative-specification |
| `authoring/vectors/published/` | normative-specification (literally published values only) |
| `authoring/interface/INTERFACE.md` | mechanically-derived |
| `authoring/vectors/challenge/` | challenge-input |
| `authoring/AUTHORING.md`, `authoring/NONDETERMINISM.md` | bundle-infrastructure (authoring-facing) |
| `coordinator/expected/` | specification-determined |
| `coordinator/transcripts/*.json` | specification-determined, except the example-value exchanges (`info`, `directory`, `changes-initial-enumeration`, `changes-premature-retained`, `changes-reset-required`, and the constructed hostile responses `info-missing-version`, `info-missing-suite`, `directory-duplicate-index`, whose bytes carry example relay values while their required rejection classification is normative), which are illustrative-nonnormative, and the publish status-1 exchanges (`publish-no-change`, `publish-no-change-diagnostic`, `publish-losing-record`), which are permitted-diagnostic-variation; finer provenance is marked per message inside each file |
| `coordinator/COORDINATOR.md`, `coordinator/transcripts/TRANSCRIPTS.md` | bundle-infrastructure |
| `evidence/` | confirmed-evidence-pointer |
| `verify/`, top-level documents, `MANIFEST.json` | bundle-infrastructure |

## Audience

`MANIFEST.json` assigns each file an audience by a pure directory rule:

- `authoring` — exactly the `authoring/` tree; the only material a
  participant-maintenance session may receive before its v0.9.2 freeze.
- `coordinator` — everything else. Coordinator files must never be
  supplied to a participant session before its v0.9.2 outputs are
  frozen; see `coordinator/COORDINATOR.md` for the exposure sequence.

The verifier enforces the boundary mechanically: every result-like
token in the coordinator tree that does not appear verbatim in the
pinned specification is proven absent from the entire AUTHORING subset,
every coordinator-only constructed-case identifier is proven absent as
well, and every authoring vector case is a value-identical subset of
its coordinator counterpart.
