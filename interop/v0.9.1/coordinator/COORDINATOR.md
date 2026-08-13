# Coordinator-only material and the exposure sequence

Nothing under `coordinator/` may be supplied to a fresh implementation
session before that implementation's outputs are frozen. This tree
holds every expected value, classification, winner, and byte sequence
that is *absent from the pinned normative specification* — even where
it was computed deterministically from the specification and
cross-confirmed afterwards. "Specification-determined" is not
"specification-published", and only published material reaches the
authoring audience.

## Contents

| Path | What it is |
| --- | --- |
| `expected/identities.json` | Full derivation chains, including members Appendix B does not print (for example the attacker identity's descriptor digest and multihash) |
| `expected/records.json` | Full authoring outputs, including the unpublished B.6 bodies, Sig_structures, signatures, and envelopes and the unpublished B.5 Sig_structure |
| `expected/envelopes-negative.json` | Composited B.10/B.12 record bodies and complete envelopes (the authoring tree carries only the published recipe, digests, lengths, and signatures) |
| `expected/wire-b11.json` | Reconstructed Appendix B.11 response bytes (the authoring tree carries the published request bytes, lengths, and digests) |
| `expected/verification.json` | Constructed verification comparison cases: clock scenarios and target-DID classification variants |
| `expected/selection.json` | Constructed winner-selection cases and their explicitly enumerated permutations |
| `expected/timestamps.json` | Constructed Section 5.3 timestamp comparison cases |
| `transcripts/` | Documented HTTP/CBOR exchanges for the Section 20.4 state-exchange requirement |

The mechanical guarantee that none of this is reachable from the
authoring subset is enforced by `verify/verify_bundle.py`: every
result-like token in this tree that does not appear verbatim in the
pinned specification is proven absent from every authoring file, and
every authoring vector case is a value-identical subset of its
coordinator counterpart.

## The sequence

1. **Author.** A fresh implementation session receives exactly the
   `authoring/` tree — the pinned specification, the interface
   contract, the authoring rules, the published-value vectors, and the
   blind challenge inputs — and implements against the specification
   alone. It computes and records its own results for every published
   vector, constructs the B.10/B.12 envelopes and B.11 responses from
   the published recipes, and produces its blind challenge outputs.
2. **Freeze.** The implementation, its recorded challenge outputs, and
   its toolchain pins are committed and tagged in its own repository.
   The freeze revision is recorded before anything outside `authoring/`
   is shown to that implementation's session or authors.
3. **Expose and compare.** Only after the recorded freeze may
   coordinator expectations be opened: phase 1 compares both
   implementations against `expected/`, phase 2 compares the two frozen
   blind challenge output sets against each other, and phase 3 runs the
   live two-direction HTTP/CBOR exchange guided by `transcripts/`. The
   full protocol and success criterion are defined in
   `../ACCEPTANCE.md`; disagreement reporting follows the Section 20.4
   categories.

A comparison performed against an implementation that saw any
coordinator material before its freeze is void for the purpose of the
Section 20.4 interoperability claim.
