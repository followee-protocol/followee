# HTTP/CBOR transcript examples (coordinator-only)

These files document complete exchanges of the mandatory HTTP/CBOR relay
profile (specification Section 12) for the Section 20.4 state-exchange
requirement. They cover `v1/info`, `v1/resolve`, `v1/directory`,
`v1/publish`, and `v1/changes`, including the published Appendix B.11
wrapper vectors, the required rejection behaviours, and — new in
v0.9.2 — both permitted publish status-1 encodings and a losing-record
scenario.

**Audience.** Transcripts are coordinator material: several carry
reconstructed response bytes or example values that are not literally
published in the specification. A participant session builds its HTTP
behaviour from the pinned specification alone (Sections 12–13 and
Appendix B.11, all of which it holds); it receives these transcripts
only after its v0.9.2 freeze, when they guide the live two-direction
run.

## File format

Each transcript is one JSON object:

- `operation` — the relay operation path;
- `scenario` — the relay/receiver state the exchange assumes, using the
  structured state published in Appendix B.11 where applicable;
- `request` / `response` — method and path or HTTP status, content type,
  and exact body bytes (`bodyHex`, with `bodyLength` and `bodySha256`);
- `requiredPostState` — where the specification pins the receiver-side
  outcome (the `changes` vectors);
- `bodyProvenance` per message, one of:
  - `normative-specification` — bytes the specification publishes
    verbatim or pins by length and SHA-256 digest;
  - `specification-determined` — bytes fully determined by the
    specification for the stated scenario;
  - `permitted-diagnostic-variation` — one member of the enumerated
    conforming set for the stated scenario (the publish status-1
    response with or without its accurate reason code). Each member is
    byte-deterministic and byte-compared against the enumerated set;
    the choice among members is the relay's, is reported as permitted
    diagnostic variation, and is never normalized away. Messages in
    this category carry a `variationGroup`, and coded forms name the
    bare transcript they vary from;
  - `illustrative-nonnormative` — example values for fields the
    specification leaves to the relay (identifiers, generations,
    cursors, limits, base URIs). See `../../authoring/NONDETERMINISM.md`.
- `sameAs` — present where the body equals a value in `../expected/`;
  bundle verification asserts that equality.

HTTP framing beyond method, path, status, and content type is
deliberately omitted; see `../../authoring/NONDETERMINISM.md` for the
transport variation rule. A body marked `illustrative-nonnormative` is
documentation of shape, not a byte-comparison target; its structural
requirements are listed alongside it.

## Coverage

| Transcript | Requirement documented |
| --- | --- |
| `info.json` | Section 12.2 relay information shape |
| `directory.json` | Sections 11.4, 12.4 directory and generation scoping |
| `resolve-candidate-isolation.json` | Section 12.3 + Appendix B.11.3 opaque-candidate isolation |
| `resolve-duplicate-dids.json` | Section 12.3 + Appendix B.11.4 cardinality without deduplication |
| `resolve-malformed-did.json` | Sections 12.1, 12.3 + Appendix B.11.6 per-DID error alignment |
| `resolve-invalid-request-400.json` | Sections 12.1, 15.4 + Appendix B.11.1 outer-fault HTTP 400 |
| `resolve-premature-retained.json` | Sections 5.4, 12.3 retained-but-premature record filtered from resolve: per-DID `Error(premature)`, never Absent or Full |
| `publish-admit.json` | Sections 12.5, 13.1 admitted-and-current (status 0, no errorCode) |
| `publish-no-change.json` | Sections 12.5, 13.2 valid-but-no-change, bare status-1 form |
| `publish-no-change-diagnostic.json` | Section 12.5 (v0.9.2) valid-but-no-change with the accurate `duplicate` reason — the other permitted status-1 form |
| `publish-losing-record.json` | Sections 8.3, 12.5, 13.1, 13.2 (v0.9.2) valid-but-losing publication with the accurate `losingRecord` reason |
| `publish-rejected.json` | Sections 8.1, 12.5, 15.3, 15.4 rejection with required symbolic error, carried by HTTP 200 |
| `publish-record-too-large.json` | Sections 8.1, 13.1, 15.1, 15.3, 15.4 minimally oversized record (16 KiB + 1, fault-isolated) → status-2 `recordTooLarge` under HTTP 200; transport-cap precondition and 413-band variation rule in ACCEPTANCE Gate G2 |
| `info-missing-version.json` | Sections 6.1.3, 12.1, 12.2, 15.3 hostile info response omitting protocol version 1 → mandatory complete client rejection, `schemaViolation`, no usable state |
| `info-missing-suite.json` | Sections 6.1.3, 12.1, 12.2, 15.3 hostile info response omitting suite -19 → mandatory complete client rejection, `schemaViolation`, no usable state |
| `directory-duplicate-index.json` | Sections 6.1.3, 11.4, 12.1, 12.4, 15.3 hostile directory reusing one index within a generation → mandatory complete client rejection, `schemaViolation`, no reference followed |
| `changes-sync.json` | Sections 12.6, 13.3, 20.4 + Appendix B.11.5 state exchange, candidate isolation, cursor progress |
| `changes-item-limit-overflow.json` | Section 12.6 + Appendix B.11.7 item-limit rejection |
| `changes-initial-enumeration.json` | Sections 12.6, 12.7 null-cursor initial enumeration |
| `changes-premature-retained.json` | Sections 5.4, 12.6, 13.1, 13.3, 16.16 premature retained current tuple emitted by `changes` and classified by each receiver's own clock — the direct counterpart of the resolve-side filtering |
| `changes-reset-required.json` | Sections 12.6, 12.7 exact two-field ResetRequired |

The two-direction interoperability run described in `../../ACCEPTANCE.md`
executes the `changes-sync` exchange live in both directions between the
two implementations, alongside `v1/info`, `v1/directory`, `v1/publish`
(all three statuses, accepting both permitted status-1 encodings), and
`v1/resolve` round trips, plus the Appendix B.11 hostile-peer cases.
