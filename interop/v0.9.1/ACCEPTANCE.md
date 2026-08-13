# Section 20.4 acceptance matrix

Specification Section 20.4 states the interoperability criterion for
Followee v1. This matrix maps each obligation to the bundle material
that prepares it and to the step of the future two-direction run that
discharges it. **Nothing in this bundle discharges any obligation by
itself.** No implementation — including the existing Rust
implementation — may be described as interoperable until the complete
cross-implementation run below has succeeded between two independent
implementations, and communicating with another process built from the
same core library never counts.

## Obligations and mapping

| # | Section 20.4 obligation | Bundle material | Discharged by |
| --- | --- | --- | --- |
| 1 | Byte-identical Authority Descriptors from the same structured input | authoring: published `identities.json` members and blind `challenge-identities.json`; coordinator: full `expected/identities.json` | Run phase 1 and phase 2 |
| 2 | Byte-identical record bodies from the same structured input | authoring: `records.json` inputs with published outputs and blind `challenge-records.json`; coordinator: full `expected/records.json` including the unpublished B.6 outputs | Run phase 1 and phase 2 |
| 3 | Verify the same envelopes | authoring: published envelopes, error classifications, and B.10/B.12 recipes; coordinator: `expected/verification.json` (constructed clock and target-DID cases); blind: cross-verification of frozen challenge envelopes | Run phases 1–3 |
| 4 | Derive the same DIDs | authoring: published DIDs and blind challenge identities; coordinator: full derivation chains | Run phase 1 and phase 2 |
| 5 | Compute the same body digests | authoring: published digest members; blind: challenge records; coordinator: full digest sets | Run phase 1 and phase 2 |
| 6 | Select the same winners from candidates delivered in different orders | coordinator: `expected/selection.json` — explicitly enumerated permutations (2 orders of three pairs, all 24 orders of a four-candidate set, plus sticky/premature/cross-DID/empty singletons); blind: `challenge-selection.json` permutations in the authoring subset | Run phase 1 and phase 2 |
| 7 | Exchange state through the HTTP/CBOR profile | authoring: specification Sections 12–13 plus published B.11 request bytes and response digests in `wire-b11.json`; coordinator: `transcripts/` — documented `v1/info`, `v1/resolve`, `v1/directory`, `v1/publish`, `v1/changes` exchanges including the B.11.5 state-exchange example | Run phase 3, executed live in both directions |
| 8 | Two independent implementations | The AUTHORING subset seeds the independent implementation with literally published values only; every other expectation is withheld under `coordinator/` until its freeze | Run phases 1–3 together |

Supporting obligations from Section 20.4's second paragraph:

| Obligation | Treatment |
| --- | --- |
| Rerun the complete conformance suite after a normative CBOR-classification, relay-wrapper, or cursor-visibility change | The bundle pins specification v0.9.1; any such specification change obsoletes this bundle version and requires a regenerated bundle and a fresh run |
| Reports separately count acceptance/rejection disagreements, symbolic differences permitted by unspecified multi-fault precedence, and genuine unresolved specification ambiguities | Required report structure for phases 1–3, restated in `authoring/vectors/challenge/CHALLENGES.md`; a permitted symbolic difference is not a failure but must remain visible |

## Sequence and freeze discipline

The order is fixed and recorded (see `coordinator/COORDINATOR.md`):

1. the independent implementation is authored against the pinned
   specification plus the AUTHORING subset only;
2. the implementation and all of its recorded outputs — published-vector
   results, recipe-constructed envelopes and wire messages, and blind
   challenge outputs — are committed and tagged in its repository as
   the freeze revision;
3. only after that recorded freeze are the coordinator-only
   expectations exposed and the phases below executed. A comparison
   against an implementation that saw coordinator material before its
   freeze is void for the Section 20.4 claim.

## The two-direction interoperability run

Executed only after the independent implementation is complete and its
outputs are frozen at a recorded revision.

**Phase 1 — expected-vector agreement.** Both implementations execute
every case in `coordinator/expected/` through the interface contract.
Every result must match the published or specification-determined
expected value exactly. This proves each implementation against the
specification, not yet against each other.

**Phase 2 — blind challenge comparison.** Both implementations' frozen
challenge outputs (identities, records, verifications, selections) are
compared value for value under the interface result-equality rule.
Byte-identical descriptors, bodies, digests, signatures, envelopes, and
DIDs; identical winners across every enumerated permutation; each
implementation successfully verifies the envelopes the other authored.

**Phase 3 — live HTTP/CBOR state exchange, both directions.** With
implementation A serving the relay profile and implementation B acting
as client/receiver, and then with roles reversed:

1. `GET v1/info` — B validates A's relay-info shape (protocol version 1,
   suite -19, capability bits);
2. `POST v1/publish` — B publishes the published B.4 record and receives
   status 0, republishes for status 1, and publishes the B.8 envelope
   for status 2 with `identityBindingMismatch`;
3. `POST v1/resolve` — B resolves batches including duplicate DIDs and a
   malformed DID, receiving positionally aligned results, and locally
   verifies every Full candidate;
4. `GET v1/directory` — B resolves a Ref through the served directory
   generation;
5. `POST v1/changes` — B performs a null-cursor initial enumeration and
   an incremental pull, admits current state through its own ingress
   verification, stores the exact returned `nextCursor`, and the
   resulting current maps agree on every DID's winning body digest and
   authority state;
6. challenge records are published on one side and resolved and verified
   on the other, so state authored by each implementation crosses the
   wire to the other.

Opaque and relay-chosen values are compared per
`authoring/NONDETERMINISM.md`: never byte-compared, never normalized
away.

**Success criterion.** All three phases complete with zero unexplained
disagreements, and the run report uses the Section 20.4 reporting
categories. Only then may Followee v1 — and each participating
implementation — be described as interoperable, citing this bundle
version and both frozen revisions.
