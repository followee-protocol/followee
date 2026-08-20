# AUTHORING subset — Followee v0.9.2 external interoperability

This directory — `authoring/` and nothing outside it — is the complete
material an implementation session may receive for the Followee v0.9.2
Milestone 6 interoperability experiment before that implementation's
v0.9.2 outputs are frozen. It is deliberately self-contained: a session
seeded with exactly these files has everything it needs to implement
the protocol from the specification and to produce comparable outputs,
and nothing that could leak another implementation's interpretation.

The v0.9.2 pass is a **maintenance** pass: the pinned specification
clarifies the Section 12.5 publish-response field-presence rule, and an
implementation maintained against it updates its own code and recorded
outputs from this subset alone. The blind challenge inputs are the
previous bundle version's inputs preserved byte-for-byte; their rerun
is maintenance confirmation, not a new independent-authoring exercise,
and the original independent-authoring evidence remains historical.

## Contents

| Path | What it is |
| --- | --- |
| `specification/Followee-Specification.md` | The pinned normative specification, v0.9.2. SHA-256 `47af5fbf0c4505386b4e04d948ef89d013f878ea820fb02522817661d633633a`. This document alone is normative. |
| `interface/INTERFACE.md` | Mechanical interface contract: operation names, argument and result shapes, transport framing. |
| `vectors/published/` | Machine-readable forms of the specification's Appendix B vectors, restricted to values **literally published** in the pinned document: published bytes, digests, lengths, signatures, DIDs, error classifications, and receiver states. Values the specification only determines — reconstructed envelopes, unpublished derivation members, constructed comparison cases — are deliberately absent; derive them from the specification alone. |
| `vectors/challenge/` | Blind challenge inputs. No expected output for any challenge case exists anywhere in this bundle. See `vectors/challenge/CHALLENGES.md`. |
| `NONDETERMINISM.md` | What is opaque or relay-chosen on the wire, and what must never be normalized away when comparing. |

HTTP behaviour is implemented from the specification alone: Sections 12
and 13 and the Appendix B.11 vectors — whose published request bytes,
lengths, and response digests are restated machine-readably in
`vectors/published/wire-b11.json` — are the complete authoring source
for the relay profile.

## Authoring rules

1. **The specification is the only normative source.** Vectors and
   transcripts are evidence and test material; if any file in this
   subset appears to disagree with the pinned specification, the
   specification governs and the disagreement must be reported, not
   silently resolved.
2. **Production entry points.** The interface operations must be served
   by the same code paths the implementation itself uses for
   derivation, authoring, verification, strict Ed25519, timestamps,
   CBOR validation, and selection — not by comparison-only shims that
   re-state expected behaviour.
3. **Deterministic protocol code.** No wall-clock reads, randomness,
   environment inspection, or locale dependence inside any protocol
   operation. Every clock is an explicit `nowMs` input. Signing is
   deterministic RFC 8032 Ed25519.
4. **Toolchain pinning.** The implementation records its exact compiler
   and toolchain versions at its baseline revision and keeps them
   pinned for the duration of the experiment, so that frozen outputs
   are reproducible from a clean checkout.
5. **Report ambiguity.** A genuine specification ambiguity encountered
   while implementing is recorded as a question in the implementation
   repository, never resolved by copying another implementation's
   observable behaviour — no other implementation is visible from this
   subset in any case.
6. **Blind discipline.** Challenge outputs are computed, recorded, and
   frozen at a recorded revision in the implementation repository
   before any cross-implementation result is seen. See
   `vectors/challenge/CHALLENGES.md`.
7. **Public test material only.** All seeds in this subset, published
   and challenge alike, are public fixture material and MUST NOT be
   used for a real Followee DID. No private or production secret may be
   introduced into fixtures or logs.

## Exclusion rules — what this subset must never contain

The curator of this bundle warrants, and any future update must
preserve, that the AUTHORING subset contains none of the following:

- source code, tests, or test logic from any existing Followee
  implementation, in any language;
- implementation-specific names, module layouts, error-type taxonomies,
  or comparison-harness role classifications;
- cross-implementation comparison results, fixture-status reports, or
  conformance campaign archives;
- expected outputs that exist only as the recorded behaviour of an
  implementation (everything expected here is published or normatively
  determined by the specification itself);
- implementation planning briefs or milestone documents;
- the separate protocol design-rationale document or any
  protocol-review discussion (the specification's own rationale notes
  are part of the pinned document and stay);
- verification tooling from outside this subset (the bundle's `verify/`
  tree is curator tooling and is not part of this subset).

Beyond the exclusions above, the boundary is stricter than
"implementation-derived": **no expected value, classification, winner,
or derived byte sequence that is absent from the pinned specification
appears in this subset**, even when it is deterministically computable
from published material. Bundle verification proves this mechanically.

Conversely, if a value is already visible in the pinned specification,
it is published material and is presented as such; this subset never
pretends a specification-published value is blind.

## Sequence

The experiment proceeds in a fixed order: (1) implement and produce all
outputs — published-vector results, recipe-constructed envelopes and
wire messages, and blind challenge outputs — from this subset alone;
(2) commit and tag the implementation and its recorded outputs in its
own repository as the freeze revision; (3) only after that recorded
freeze does the coordinator open the withheld comparison material and
run the cross-implementation phases. Comparison against an
implementation that saw withheld material before its freeze is void.
