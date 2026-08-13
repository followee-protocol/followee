# HTTP/CBOR transcript examples (coordinator-only)

These files document complete exchanges of the mandatory HTTP/CBOR relay
profile (specification Section 12) for the Section 20.4 state-exchange
requirement. They cover `v1/info`, `v1/resolve`, `v1/directory`,
`v1/publish`, and `v1/changes`, including the published Appendix B.11
wrapper vectors and the required rejection behaviours.

**Audience.** Transcripts are coordinator material: several carry
reconstructed response bytes or example values that are not literally
published in the specification. A fresh implementation session builds
its HTTP behaviour from the pinned specification alone (Sections 12–13
and Appendix B.11, all of which it holds); it receives these transcripts
only after its freeze, when they guide the live two-direction run.

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
    specification for the stated scenario (for example, the
    deterministic encoding of a defined publish response);
  - `illustrative-nonnormative` — example values for fields the
    specification leaves to the relay (identifiers, generations,
    cursors, limits, base URIs). See
    `../../authoring/NONDETERMINISM.md`.
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
| `publish-admit.json` | Sections 12.5, 13.1 admitted-and-current |
| `publish-no-change.json` | Sections 12.5, 13.2 valid-but-no-change |
| `publish-rejected.json` | Sections 8.1, 12.5, 15.3 rejection with symbolic error |
| `changes-sync.json` | Sections 12.6, 13.3, 20.4 + Appendix B.11.5 state exchange, candidate isolation, cursor progress |
| `changes-item-limit-overflow.json` | Section 12.6 + Appendix B.11.7 item-limit rejection |
| `changes-initial-enumeration.json` | Sections 12.6, 12.7 null-cursor initial enumeration |
| `changes-reset-required.json` | Sections 12.6, 12.7 exact two-field ResetRequired |

The two-direction interoperability run described in `../../ACCEPTANCE.md`
executes the `changes-sync` exchange live in both directions between the
two implementations, alongside `v1/info`, `v1/directory`, `v1/publish`,
and `v1/resolve` round trips.
