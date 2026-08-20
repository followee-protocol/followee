# Coordinator-only material and the exposure sequence

Nothing under `coordinator/` may be supplied to a participant session
before that implementation's v0.9.2 outputs are frozen. This tree holds
every expected value, classification, winner, and byte sequence that is
*absent from the pinned normative specification* — even where it was
computed deterministically from the specification and cross-confirmed
afterwards. "Specification-determined" is not
"specification-published", and only published material reaches the
authoring audience.

Campaign 2 is a maintenance campaign between reviewed implementations
(see `../ACCEPTANCE.md`). The maintenance framing weakens nothing here:
the exposure boundary is identical to the v0.9.1 boundary, and a
comparison against a participant session that saw any coordinator
material before its v0.9.2 freeze is void for the Section 20.4 claim.

## Contents

| Path | What it is |
| --- | --- |
| `expected/identities.json` | Full derivation chains, including members Appendix B does not print |
| `expected/records.json` | Full authoring outputs, including the unpublished B.6 bodies, Sig_structures, signatures, and envelopes and the unpublished B.5 Sig_structure |
| `expected/envelopes-negative.json` | Composited B.10/B.12 record bodies and complete envelopes (the authoring tree carries only the published recipe, digests, lengths, and signatures) |
| `expected/wire-b11.json` | Reconstructed Appendix B.11 response bytes (the authoring tree carries the published request bytes, lengths, and digests) |
| `expected/verification.json` | Constructed verification comparison cases: clock scenarios and target-DID classification variants |
| `expected/selection.json` | Constructed winner-selection cases and their explicitly enumerated permutations |
| `expected/timestamps.json` | Constructed Section 5.3 timestamp comparison cases |
| `expected/publish-responses.json` | **New in v0.9.2**: the complete Section 12.5 publish-response field-presence matrix with exact classifications, including the enumerated permitted status-1 diagnostic encodings (byte-distinct, never normalized) and explicit unregistered-errorCode probes — the Section 15.3 registry is the complete v1 wire vocabulary, so an unregistered value is rejected on every status |
| `transcripts/` | Documented HTTP/CBOR exchanges for the Section 20.4 state-exchange requirement, including both permitted publish status-1 forms and the hostile-peer cases |

The mechanical guarantee that none of this is reachable from the
authoring subset is enforced by `verify/verify_bundle.py`: every
result-like token in this tree that does not appear verbatim in the
pinned specification is proven absent from every authoring file, every
coordinator-only constructed-case identifier is proven absent as well,
and every authoring vector case is a value-identical subset of its
coordinator counterpart.

## The sequence

1. **Review.** This bundle is reviewed locally.
2. **Author (maintenance).** Each participant session receives exactly
   the `authoring/` tree — the pinned v0.9.2 specification, the
   interface contract (now including `receivePublishResponse`), the
   authoring rules, the published-value vectors, and the preserved
   blind challenge inputs — and updates its implementation against the
   specification alone. It recomputes and records its own results for
   every published vector and its challenge outputs.
3. **Freeze.** Both participants' v0.9.2 revisions and recorded outputs
   are committed and tagged in their own repositories. Both freeze
   revisions are recorded before anything outside `authoring/` is shown
   to either participant session.
4. **Expose and compare.** Only after both recorded freezes may
   coordinator expectations be opened: Phase 1 compares both
   implementations against `expected/` (all unchanged cases plus the
   publish-response matrix), Phase 2 preserves and digest-checks the
   original pre-exposure challenge outputs and compares the refrozen
   sets as maintenance confirmation, and Phase 3 runs the live
   two-direction HTTP/CBOR exchange guided by `transcripts/`. The full
   protocol and success criterion are defined in `../ACCEPTANCE.md`;
   disagreement reporting follows the Section 20.4 categories with
   permitted diagnostic variation kept visible and never counted as a
   disagreement.
5. **Archive.** Every raw result is preserved and every difference is
   classified.

Campaign 1's archive (`interop/campaign-1`, tag
`v0.9.1-interop-campaign-1`) is immutable historical evidence. Its W1
finding correctly recorded an unresolved specification ambiguity at the
time it ran; specification v0.9.2 resolves that ambiguity and this
bundle classifies the observed variation as permitted. The historical
entry is not rewritten.
