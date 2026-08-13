# Provenance model

Every file in this bundle carries exactly one provenance category in
`MANIFEST.json`, and vector and transcript files additionally mark
finer-grained provenance per case or per message. The categories:

## `normative-specification`

Material literally published in the pinned Followee specification
v0.9.1 (SHA-256
`1c1a20c639aaf90b1bfc54b5e9ea72c49f680566ba9b12ad10615412ece3cd71`):
the pinned specification copy itself and the AUTHORING vector files,
whose every value — bytes, digests, lengths, signatures, DIDs, error
classifications, receiver states — appears verbatim in the document.
Nothing in this category is merely derivable; it is printed in the
specification.

## `specification-determined`

Values computed for this bundle by the specification's deterministic
algorithms from published inputs, but **absent from the document
itself**: reconstructed B.10/B.12 bodies and envelopes, reconstructed
Appendix B.11 response bytes, unpublished derivation-chain members, the
unpublished B.6 full outputs, and constructed comparison cases
(target-DID variants, selection permutations, clock and timestamp
scenarios). Cross-confirmed against reviewed evidence where available.
**Coordinator-only**: the distinction between this category and
`normative-specification` is the Motoko independence boundary, and the
verifier proves no value in this category is reachable from the
AUTHORING subset.

## `mechanically-derived`

Neutral material produced mechanically from normative sources without
interpretive freedom and without expected values: the interface
contract (operation names, shapes, and framing restated from the
reviewed neutral conformance-runner surface with all harness- and
adapter-specific language removed).

## `challenge-input`

New neutral blind inputs authored for this bundle: fresh seeds and
structured authoring/selection inputs whose outputs appear nowhere in
the bundle. See `authoring/vectors/challenge/CHALLENGES.md`. No
private or production secret; seed patterns are disjoint from every
published Appendix B seed.

## `illustrative-nonnormative`

Example values for wire fields the specification leaves relay-chosen or
opaque (relay identifiers, generations, cursors, limits, base URIs),
appearing only inside coordinator transcript messages explicitly marked
`illustrative-nonnormative`, plus the transcript framing metadata
itself. Never a byte-comparison target.

## `confirmed-evidence-pointer`

Pointers — commit hashes, tags, and aggregate digests only, never
copies — to independently confirmed evidence outside this repository:
the reviewed differential-conformance archives and reviewed
implementation revisions listed in `evidence/EVIDENCE.md`.

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
| `coordinator/transcripts/*.json` | specification-determined, except the example-value exchanges (`info`, `directory`, `changes-initial-enumeration`, `changes-reset-required`), which are illustrative-nonnormative; finer provenance is marked per message inside each file |
| `coordinator/COORDINATOR.md`, `coordinator/transcripts/TRANSCRIPTS.md` | bundle-infrastructure |
| `evidence/` | confirmed-evidence-pointer |
| `verify/`, top-level documents, `MANIFEST.json` | bundle-infrastructure |

## Audience

`MANIFEST.json` assigns each file an audience by a pure directory rule:

- `authoring` — exactly the `authoring/` tree; safe to hand to a fresh
  independent implementation session.
- `coordinator` — everything else. Coordinator files must never be
  supplied to a fresh implementation session before its outputs are
  frozen; see `coordinator/COORDINATOR.md` for the exposure sequence.

The verifier enforces the boundary mechanically: every result-like
token in the coordinator tree that does not appear verbatim in the
pinned specification is proven absent from the entire AUTHORING subset,
and every authoring vector case is a value-identical subset of its
coordinator counterpart.
