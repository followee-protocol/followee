# Authoring revision 2 (v0.9.2-r2) — interface correction record

Coordinator-only. This document records the second authoring revision
of the Followee v0.9.2 bundle's neutral AUTHORING subset: a correction
of `authoring/interface/INTERFACE.md` that merges the reviewed
interface integration patch (SHA-256
`ae74421993f0647e8060d075eae30e9dc7695342ba15284f54b9a27e01a654ff`)
into the sections it replaces — the value conventions, the structured
contact shape, and the `verifyRecord` accepted-result definition. The
patch is derived solely from the pinned specification and the existing
neutral interface conventions; it contains no fixture value, no
implementation-derived expectation, and no language-specific type.

**This is an authoring revision, not a specification revision.** The
pinned specification remains v0.9.2, byte-identical, SHA-256
`47af5fbf0c4505386b4e04d948ef89d013f878ea820fb02522817661d633633a`.
No normative protocol rule changes. The revision corrects the neutral
*interface contract's* description of the `verifyRecord` accepted-result
projection and makes the directional presence semantics explicit. The
revised subset is identified as **Followee v0.9.2 authoring revision 2**
(short form `v0.9.2-r2`); the previous subset is retroactively
identified as authoring revision 1 (`v0.9.2-r1`). Seal values for both
revisions are recorded in `PRECLASSIFICATION.md` under "Sealed
authoring input"; the r1 seal is preserved there as historical evidence
for the already-frozen participant input and is not overwritten.

## Predeclared expected impact

Recorded **before** any generated file was regenerated, derived solely
from the neutral contract (the pinned specification plus the corrected
interface contract), so that every observed regeneration difference can
be assessed against a prior expectation rather than rationalized after
the fact:

1. **Existing challenge inputs retain their meaning.** The corrected
   contract deliberately retains the constructor canonicalization for
   `authorRecord` input: an omitted member, `null`, an empty array, or
   an empty object still requests omission of the optional wire field.
   The sealed blind challenge inputs are therefore reinterpreted by
   nothing; their `[]` and `{}` values continue to request absent
   optional fields. The three challenge files remain byte-identical to
   the preserved v0.9.1 inputs.
2. **`authorRecord` bytes and results remain unchanged.** The input
   canonicalization is unchanged, so every authored record body,
   digest, `Sig_structure`, signature, and envelope in
   `records.json` (both audiences) regenerates byte-identically, as do
   the published-vector assertions against Appendix B.
3. **Non-`verifyRecord` operations remain unchanged.** `deriveIdentity`,
   `strictEd25519`, `nextTimestamp`, `validateCbor`,
   `receivePublishResponse`, and `selectCurrent` expectations are
   untouched: `identities.json`, `timestamps.json`,
   `publish-responses.json`, `selection.json`, `wire-b11.json`,
   `envelopes-negative.json`, and every transcript regenerate
   byte-identically.
4. **Successful `verifyRecord` results adopt the corrected
   projection.** Every accepted `verifyRecord` expectation in
   `coordinator/expected/verification.json` gains the complete
   corrected accepted-result projection (the `record` member with
   `descriptor`, `revocationKey`, `contact`, and `extensions` in the
   corrected shapes, including `null`-versus-present-empty
   distinctions). Previously stated members (`id`, `timestampMs`,
   `authority`, `validUntilMs`, `premature`, `stale`,
   `recordBodyDigestHex`) keep their exact values.
5. **Rejected `verifyRecord` cases retain their classifications.**
   Rejection paths are untouched by the projection correction: every
   negative verification case and every target-DID variant keeps its
   exact symbolic error classification.
6. **Newly added direct-wire cases are additions, not unexplained
   differences.** Because `authorRecord` cannot construct the
   present-empty encoding of an optional array or map, coverage of
   those valid protocol encodings must come from direct wire fixtures
   exercised through `verifyRecord`. New, validly signed direct-wire
   cases covering at minimum present-empty `alsoKnownAs`, a
   present-empty Contact Document extension map, and a present-empty
   record-body extension map — preserving the `[]` / `{}` / absence
   distinction — appear as new cases in
   `coordinator/expected/verification.json`. Their case identifiers
   are new; no existing case changes because of them.

Any regeneration difference outside these six categories is
unexplained and blocks the revision until resolved.

## Predeclared-versus-observed assessment (recorded after regeneration)

Every generated file for both audiences and every transcript was
regenerated after the interface merge and diffed against a byte
snapshot taken before any regeneration. Observed:

- **Exactly one generated file changed:**
  `coordinator/expected/verification.json`. Every other generated file
  — `identities.json`, `records.json`, `envelopes-negative.json`, and
  `wire-b11.json` in both audiences, `timestamps.json`,
  `selection.json`, `publish-responses.json`, and all 21 transcripts —
  regenerated byte-identically. This matches predeclared items 2
  and 3, and the byte-identical `records.json` confirms item 2's
  authored-bytes claim directly.
- **Challenge inputs untouched:** the three challenge files were not
  regenerated and remain byte-identical to the preserved v0.9.1
  inputs (verifier check). Matches item 1.
- **Within `verification.json`:** zero cases removed; zero cases
  changed except that each of the five previously existing accepted
  cases gained the `record` member carrying the corrected projection
  (every previously stated member value byte-identical); all 21
  rejected cases are byte-identical, classifications included; four
  new direct-wire cases were added
  (`verify-wire-empty-alsoKnownAs`,
  `verify-wire-empty-contact-extensions`,
  `verify-wire-empty-record-extensions`,
  `verify-wire-empty-collections-combined`); and the file's
  `description` header was updated to describe the direct-wire
  additions. Matches items 4, 5, and 6.

No difference outside the predeclared categories was observed.

## Fixture inventory — present-empty direct-wire coverage

All four fixtures are records for the published Appendix B.2 identity,
signed with its root key over the standard `Sig_structure`, timestamp
1785589200123, no `validUntilMs`, verified at `nowMs` 1785589201123.
Each is constructed directly at the wire layer; the bundle tooling
asserts for each that applying the constructor canonicalization to the
equivalent structured input omits the present-empty labels and yields
different bytes, proving the fixture is unreachable through
`authorRecord`.

| Case | Present and empty on the wire | Absent (projects to `null`) |
| --- | --- | --- |
| `verify-wire-empty-alsoKnownAs` | Contact Document label `3` = `[]` | contact labels `1`,`2`,`4`,`5`,`6`; record label `8` |
| `verify-wire-empty-contact-extensions` | Contact Document label `6` = `{}` | contact labels `1`,`2`,`3`,`4`,`5`; record label `8` |
| `verify-wire-empty-record-extensions` | record-body label `8` = `{}` | contact labels `1`,`2`,`3`,`4`,`5`,`6` |
| `verify-wire-empty-collections-combined` | contact `3` = `[]`, contact `6` = `{}`, record `8` = `{}` | contact labels `1`,`2`,`4`,`5` |

Each expected projection therefore contains `[]`, `{}`, and `null`
side by side, pinning the three-way distinction the corrected contract
requires. The combined case pins all three within one record.
