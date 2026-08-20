# Section 20.4 acceptance matrix — Campaign 2 (v0.9.2 rerun)

Specification Section 20.4 states the interoperability criterion for
Followee v1 and requires the complete conformance suite to be rerun
after a normative relay-wrapper change. Specification v0.9.2 is such a
change: it pins the Section 12.5 publish-response field-presence rule.
This matrix maps each obligation to the bundle material that prepares
it and to the step of the Campaign 2 run that discharges it. **Nothing
in this bundle discharges any obligation by itself.** No implementation
may be described as interoperable until the complete cross-
implementation run below has succeeded between two independent
implementations, and communicating with another process built from the
same core library never counts.

**Campaign 2 is a maintenance interoperability campaign between
reviewed implementations.** The Motoko participant has an independently
authored frozen ancestor (`motoko-v0.9.1-independent-freeze`,
documented in Campaign 1); Campaign 2 itself is not a new
independent-authoring exercise. The blind challenge inputs are the
v0.9.1 inputs preserved byte-for-byte, and their rerun is maintenance
confirmation. The historical first-blind evidence is the immutable
Campaign 1 archive; nothing in Campaign 2 rewrites it.

## Obligations and mapping

| # | Obligation | Bundle material | Discharged by |
| --- | --- | --- | --- |
| 1 | Byte-identical Authority Descriptors from the same structured input | authoring: published `identities.json` members and preserved `challenge-identities.json`; coordinator: full `expected/identities.json` | Phases 1 and 2 |
| 2 | Byte-identical record bodies from the same structured input | authoring: `records.json` inputs with published outputs and preserved `challenge-records.json`; coordinator: full `expected/records.json` including the unpublished B.6 outputs | Phases 1 and 2 |
| 3 | Verify the same envelopes | authoring: published envelopes, error classifications, and B.10/B.12 recipes; coordinator: `expected/verification.json`, including (v0.9.2-r2) the validly signed direct-wire cases carrying present-empty optional collections that `authorRecord` cannot construct, with the complete corrected accepted-result projection; challenge: cross-verification of the refrozen challenge envelopes | Phases 1–3 |
| 4 | Derive the same DIDs | authoring: published DIDs and preserved challenge identities; coordinator: full derivation chains | Phases 1 and 2 |
| 5 | Compute the same body digests | authoring: published digest members; challenge records; coordinator: full digest sets | Phases 1 and 2 |
| 6 | Select the same winners from candidates delivered in different orders | coordinator: `expected/selection.json` (all enumerated permutations); preserved `challenge-selection.json` permutations | Phases 1 and 2 |
| 7 | Exchange state through the HTTP/CBOR profile | authoring: Sections 12–13 plus published B.11 request bytes and response digests in `wire-b11.json`; coordinator: `transcripts/` — documented `v1/info`, `v1/resolve`, `v1/directory`, `v1/publish` (all three statuses and both permitted status-1 encodings), and `v1/changes` exchanges including the B.11.5 state-exchange example and the B.11 hostile-peer cases | Phase 3, executed live in both directions |
| 8 | Two independent implementations | Established by the recorded independent-authoring history (Campaign 1); preserved by the exposure sequence below: no coordinator material reaches a participant session before its v0.9.2 freeze | Phases 1–3 together |
| 9 (v0.9.2, Section 20.2) | Every status-dependent publish-response field combination: acceptance of status `1` without `errorCode` and with each permitted reason code, rejection of a status `0` response carrying `errorCode`, of a status `1` response carrying each registered code other than `losingRecord` and `duplicate`, of a status `2` response lacking `errorCode`, of a status `2` response carrying `losingRecord` or `duplicate`, and of an errorCode value outside the Section 15.3 registry on any status (the registry is the complete v1 wire vocabulary, probed with the first out-of-range value and the uint64 maximum) | coordinator: `expected/publish-responses.json` (the complete matrix, via the `receivePublishResponse` operation); transcripts: `publish-admit`, `publish-no-change`, `publish-no-change-diagnostic`, `publish-losing-record`, `publish-rejected` | Phase 1 (matrix) and Phase 3 (live emission and acceptance) |

Supporting obligations from Section 20.4's second paragraph:

| Obligation | Treatment |
| --- | --- |
| Rerun the complete conformance suite after a normative CBOR-classification, relay-wrapper, or cursor-visibility change | This bundle **is** that rerun preparation for the v0.9.2 relay-wrapper clarification; every unchanged v0.9.1 Phase 1 case is retained in `coordinator/expected/` and reruns in full |
| Reports separately count acceptance/rejection disagreements, symbolic differences permitted by unspecified multi-fault precedence, and genuine unresolved specification ambiguities | Required report structure for phases 1–3. Additionally, the publish status-1 encoding choice is **permitted diagnostic variation** under v0.9.2: it is byte-compared against the enumerated conforming set, kept visible, never normalized, and never counted as a disagreement. Campaign 1 correctly recorded this variation as an unresolved specification ambiguity at the time it ran; v0.9.2 resolves the ambiguity and this bundle classifies the variation as permitted |

## Required campaign order

The order is fixed and recorded (see also `coordinator/COORDINATOR.md`):

1. **Review.** This bundle is reviewed locally in the protocol
   repository.
2. **Expose authoring only.** Exactly the `authoring/` tree is supplied
   to the Rust participant session and to the maintained Motoko
   participant session. No coordinator file reaches either session.
3. **Freeze.** Both participants' v0.9.2 revisions — code plus their
   own recorded outputs, including refrozen challenge outputs — are
   committed and tagged in their own repositories.
4. **Expose coordinator material.** Only after both recorded freezes
   are the coordinator expectations opened.
5. **Phase 1.** Both participants execute every case in
   `coordinator/expected/` — including every unchanged v0.9.1 case and
   the complete publish-response matrix — through the interface
   contract; every result must match the expected value exactly.
6. **Phase 2.** The original pre-exposure Motoko challenge output is
   preserved and digest-checked, and the refrozen challenge outputs of
   both participants are compared value for value as maintenance
   confirmation under the interface result-equality rule.
7. **Phase 3.** Entered only after every Pre-Phase-3 gate below has
   passed for both participants. The complete bidirectional live
   HTTP/CBOR campaign:
   `v1/info`, `v1/resolve`, `v1/directory`, `v1/publish` (statuses 0,
   1 with and without the permitted reason codes, and 2), and
   `v1/changes`, plus the Appendix B.11 hostile-peer cases, with each
   implementation playing each role the run exercises.
8. **Archive.** Every raw result is preserved and every difference is
   classified: exact match, permitted diagnostic variation, permitted
   transport variation, permitted symbolic difference, coverage
   limitation, or disagreement.

A comparison performed against a participant session that saw any
coordinator material before its v0.9.2 freeze is void for the purpose
of the Section 20.4 claim.

## The two-direction interoperability run

**Phase 1 — expected-vector agreement.** Both implementations execute
every case in `coordinator/expected/` through the interface contract:
the complete unchanged v0.9.1 case set (identities, records,
verification including every negative and target-DID variant,
timestamps, selection with every enumerated permutation) plus the
v0.9.2 `publish-responses.json` matrix through the
`receivePublishResponse` operation, plus the v0.9.2-r2 direct-wire
verification cases whose present-empty optional collections are
unreachable through `authorRecord` — the campaign report states that
these fixtures were exercised, because agreement on authored records
alone establishes nothing about present-empty collection handling.
Every result must match the
published or specification-determined expected value exactly. This
proves each implementation against the specification, not yet against
each other.

**Phase 2 — challenge maintenance confirmation.** Both implementations'
refrozen challenge outputs (identities, records, verifications,
selections) are compared value for value under the interface
result-equality rule: byte-identical descriptors, bodies, digests,
signatures, envelopes, and DIDs; identical winners across every
enumerated permutation; each implementation successfully verifies the
envelopes the other authored. The original pre-exposure output digests
are preserved and checked first.

**Pre-Phase-3 gates.** Three executable gates run after both freezes
and after Phases 1 and 2, before any general Phase 3 execution. A gate
failure by either participant **aborts** the campaign before general
Phase 3 execution; the failure is archived, the participant corrects
and re-freezes, and the campaign restarts from the re-freeze. A gate
is discharged only by the live check described here, never by prose,
checklist notes, or participant self-attestation alone.

- **Gate G1 — premature emission and filtering.** For each participant
  in the serving role: the coordinator seeds the relay with the
  published B.4 record as Alice's current entry (`lastUpdated` 41) and
  sets the relay clock to `nowMs` 1785588900122, under which the
  retained record is premature (the `expected/verification.json`
  `verify-b4-premature` clock). It then performs (a) a null-cursor
  `POST v1/changes`, which MUST return the retained Full tuple —
  envelope bytes byte-equal to B.4 — as the
  `changes-premature-retained` transcript documents; and (b) a
  `POST v1/resolve` for Alice, which MUST return the aligned per-DID
  `Error(premature)` result `{0: 3, 2: 10}`, never Absent and never
  Full, as the `resolve-premature-retained` transcript documents.
  Both checks run in both directions (each implementation serves).
  Participant-owned regression evidence: each participant's frozen
  revision is inspected for its own regression coverage of both
  behaviours, and the test identifiers (or their absence, as a
  coverage note) are recorded in the campaign archive; that record
  supplements but never substitutes for the live gate.
- **Gate G2 — transport-cap determination for the oversized-record
  case.** The Section 12.2 `info` limits map cannot supply the
  required value: its five labels advertise only protocol limits —
  maximum complete Identity Record bytes, resolve-request DID count,
  resolve-response bytes, `changes` item count, and `changes`
  response bytes — and it contains no HTTP request-entity cap. The
  pre-parse cap acts before protocol parsing and is invisible to the
  protocol surface, and the advertised record-byte limit (limits
  label 0) is a protocol bound that must not be conflated with the
  HTTP request/body cap. The evidence source is therefore
  participant-owned: at freeze, each participant's declared pre-parse
  publish transport cap is recorded in the campaign archive (from its
  frozen configuration or freeze notes), fixed before any participant
  comparison. The normative `publish-record-too-large` case (exactly
  16385 bytes, 16 KiB + 1) is executed only after confirming
  16385 <= the minimum declared cap; the live HTTP 200 protocol-body
  outcome then corroborates empirically that the probe remained below
  the active transport cap. If either declared cap is below 16385
  bytes, the emission-side comparison for that direction is recorded
  as a coverage limitation and the raw outcomes are preserved. For any
  request that enters the band above one participant's transport cap
  but below the other's, a pre-parse HTTP 413 from one side versus an
  HTTP 200 status-2 protocol rejection from the other is **permitted
  transport variation**: both raw outcomes are preserved and reported,
  neither is normalized into the other, and the difference is never
  counted as a protocol disagreement.
- **Gate G3 — determined cursor classifications.** Exactly two
  determined cases, both mandatory. Cursor encodings are relay-local
  and opaque, so probe bytes are participant-relative, but every
  probe is obtained naturally and presented only through the ordinary
  production `v1/changes` path. (a) **Malformed cursor**: at freeze,
  each participant documents one byte string its own cursor encoding
  classifies as malformed; presented live, the response MUST be the
  status-2 `invalidCursor` classification (Section 15.3 code 18,
  "malformed"). (b) **Foreign-generation cursor**: the probe is
  obtained naturally by running a second relay instance of the same
  participant and taking a cursor genuinely returned by that second
  instance; presented to the first instance, whose independently
  generated 16-byte generation cannot match, the response MUST be the
  exact two-field status-1 `ResetRequired` encoding (Sections 12.6,
  12.7), as the `changes-reset-required` transcript documents. No
  cursor forging, cursor injection, state seeding, or test-only
  cursor-construction capability is authorized in any production
  participant, and neither probe needs one. **Never-issued cursors —
  syntactically valid current-generation positions the relay never
  returned — are not probed and are excluded from every Campaign 2
  input**: only null cursors, exact previously returned cursors, and
  the two probes above are ever presented (Section 13.3). Relay
  behaviour for a never-issued position is permitted variation, never
  a mandatory comparison (see `coordinator/PRECLASSIFICATION.md`): a
  relay tracking issuance may detect the position as unknown and
  return `invalidCursor`; a relay not tracking issuance may
  conformingly return an empty successful response whose `nextCursor`
  represents the supplied position. Neither Section 12.6 nor
  Section 12.7 requires issuance tracking or detection: the
  Section 12.6 visibility invariant governs positions assigned or
  reserved by relay ingress whose eventual visibility remains
  undecided, and a genuinely never-issued position has no tuple and
  no undecided visibility. A future specification version could
  enumerate the two conforming outcomes explicitly; Campaign 2
  proceeds under the permitted-variation classification.

**Phase 3 — live HTTP/CBOR state exchange, both directions.** With
implementation A serving the relay profile and implementation B acting
as client/receiver, and then with roles reversed:

1. `GET v1/info` — B validates A's relay-info shape (protocol version 1,
   suite -19, capability bits);
2. `POST v1/publish` — B publishes the published B.4 record and receives
   status 0; republishes for status 1, where A MAY answer with or
   without the accurate `duplicate` reason and B accepts both permitted
   encodings, reporting the choice as permitted diagnostic variation;
   publishes a valid losing record for status 1 (optionally with
   `losingRecord`); publishes the B.8 envelope for status 2 with
   `identityBindingMismatch`, an ordinary HTTP 200 protocol-body
   outcome (Section 15.4); and publishes the constructed minimally
   oversized 16385-byte record for status 2 with `recordTooLarge`
   under HTTP 200, per the `publish-record-too-large` transcript and
   Gate G2's transport-cap precondition;
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
6. hostile-peer behaviour — the published B.11.1/B.11.2/B.11.5/B.11.7
   bytes are presented to each side's production paths with the exact
   required outcomes, and malformed publish responses are rejected
   completely without extracting a status or mutating state; in
   addition — mandatorily, not optionally — the constructed hostile
   responses `info-missing-version`, `info-missing-suite`, and
   `directory-duplicate-index` are presented to each side's production
   client path, and each MUST be rejected as a complete response with
   the `schemaViolation` classification, yielding no usable protocol
   state — no relay identifier, limits, generations, or reference
   targets (Sections 6.1.3, 11.4, 12.1, 12.2, 15.3);
6a. premature-retention contrast — with the serving side holding a
   current Full record its own clock classifies as premature
   (Sections 5.4, 12.3, 12.6, 13.1, 13.3), `v1/resolve` returns the
   aligned per-DID `Error(premature)` (never Absent, never Full)
   while `v1/changes` still emits the retained current tuple, which
   the receiving side classifies under its own clock without
   importing the sender's diagnosis — as documented by the
   `resolve-premature-retained` and `changes-premature-retained`
   transcripts, in both directions;
7. challenge records are published on one side and resolved and verified
   on the other, so state authored by each implementation crosses the
   wire to the other.

Opaque and relay-chosen values are compared per
`authoring/NONDETERMINISM.md`: never byte-compared, never normalized
away. The publish status-1 reason-code choice is compared against the
enumerated conforming set and reported as permitted diagnostic
variation.

HTTP response headers are transport-layer detail outside the
comparison. In particular — a deliberate, recorded scope decision, see
`coordinator/PRECLASSIFICATION.md` — CORS and preflight support on
`v1/publish` are relay/operator capabilities, not v1 conformance
requirements: v1 conformance does not guarantee direct cross-origin
browser publication, a browser-hosted client must use a relay that
explicitly supports its origin and policy or a same-origin
intermediary, and the presence or absence of
`Access-Control-Allow-Origin` on any operation is never counted as a
Campaign 2 disagreement.

**Success criterion.** All three phases complete with zero unexplained
disagreements, and the run report uses the Section 20.4 reporting
categories with permitted diagnostic variation kept visible. Only then
may Followee v1 — and each participating implementation — be described
as interoperable, citing this bundle version and both frozen revisions.
