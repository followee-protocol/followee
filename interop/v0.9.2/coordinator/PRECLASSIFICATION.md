# Coordinator preclassification — Campaign 2 Motoko maintenance decisions

Coordinator-only. Written before Campaign 2 and before any participant
commit or tag, from the pinned v0.9.2 specification and this bundle
alone. No participant repository was accessed and no participant
comparison was run. The fourteen decisions below are reported
participant metadata for the maintained Motoko implementation; this
document classifies each against the pinned specification so the
campaign harness applies the correct comparison rule. Nothing here is
exposed to a participant session before its v0.9.2 freeze.

Revised after coordinator review, still before either participant
freeze: the transport-cap overlap band is now declared permitted
transport variation with a pinned 16385-byte normative case, the
item-11 negative checks are mandatory hostile-peer obligations, the
browser-publication scope decision is recorded, and the premature
behaviour is an executable pre-Phase-3 gate. A second revision
withdraws the earlier never-issued-cursor MUST interpretation —
never-issued positions are permitted variation, excluded from every
campaign input, with Gate G3 restructured to the two determined
cursor cases only — and pins Gate G2's cap evidence to the
participant-owned freeze declaration, because the Section 12.2 limits
map advertises only protocol limits and contains no HTTP
request-entity cap.

Classes: **1** specification-determined; **2** permitted observable
variation; **3** implementation-local or outside the Campaign 2
comparison; **4** genuine specification ambiguity.

**Result: no item is class 4.** Every decision classifies under
v0.9.2, and every decision is conforming as reported. No pre-campaign
correction is required for either participant.

| # | Decision (abbreviated) | Class | Specification basis | Rust and Motoko must agree observably | Campaign 2 treatment |
| --- | --- | --- | --- | --- | --- |
| 1 | 404 unknown path / 405 wrong method, empty bodies | 3 | §12.1 (operations defined only at the five v1 paths), §15.4 (status vocabulary for protocol operations; clients bound non-200 bodies) | No | Exclude; outside the normative surface |
| 2 | Transport caps 64 KiB publish / 2 MiB other POST → 413 pre-parse; over-16-KiB record within cap → status-2 `recordTooLarge` on HTTP 200 | 3 (threshold values); 1 (below-both-caps outcome); 2 (the 413-versus-200 overlap band, declared **permitted transport variation**) | §15.4 (`413` SHOULD for pre-parse entity rejection, no thresholds named); §15.1, §15.2 (thresholds sit above every conforming minimum: 16 KiB record, 64-DID/1 MiB resolve); §15.3 code 3, §13.1 step 1, §6.1.3 fault isolation, §15.4 HTTP-200 rule | Threshold values: no. Below both caps: yes — status-2 `recordTooLarge` under HTTP 200. In the overlap band: no — 413 from one side versus 200/status-2 from the other is conforming variation, both raws preserved, never normalized | Compare the pinned minimally oversized case: the `publish-record-too-large` transcript (exactly 16385 bytes, validly signed, fault-isolated) under the Gate G2 transport-cap determination; report any overlap-band case as permitted transport variation, never a disagreement |
| 3 | CORS `Access-Control-Allow-Origin: *` on the four reads, omitted on publish | 2 | §12.1 (read operations SHOULD return it; ingress publication is local policy) | No (headers are transport-layer; transcripts capture method, path, status, content type, body only) | Record only, per `authoring/NONDETERMINISM.md` transport rule; the deliberate browser-publication scope decision below is part of the campaign record |
| 4 | Case-insensitive type/subtype match, parameters → 415, case-insensitive header names, lowercase emission | 3 (accept-side strictness); emitted types class 1 | §12.1 operation table, §6.4 (the exact generic types), §15.4 (`415` SHOULD); parameter handling unaddressed — generic HTTP applies; no conforming peer emits parameters | Emitted content types: yes (transcript framing). Accept-side strictness: no | Compare emitted content-type strings; record accept-side policy |
| 5 | Publish target identity = the record's own signed DID, complete §8.1 applied | 1 | §12.5 (request is the bare `application/cose` record; no target field), §13.1 step 2, §8.1 (invariant `body id = target = DID(descriptor)` collapses to `body id = DID(descriptor)`; steps 8–9 enforce it for any target instantiation) | Yes | Compare (`publish-rejected` transcript, `expected/verification.json` target variants) |
| 6 | Premature retained current tuple emitted by `changes`, receiver classifies under its own clock; filtered from `resolve` | 1 (by composition) | §13.1 step 8 (admission makes the tuple eligible for `v1/changes`), §5.4 (premature reclassification removes nothing, alters no `lastUpdated`; the Full-serving prohibition names the Relay Resolver path and the §12.3 Error fallback), §12.6 (no advancing past omitted eligible entries), §13.3 and §16.16 (receiver-side handling of locally premature candidates in the stream presupposes emission), §14.1 (no imported premature diagnosis) | Yes, both directions of the contrast | Compare; **directly** pinned by the `changes-premature-retained` and `resolve-premature-retained` transcripts, ACCEPTANCE Phase 3 step 6a, and the executable pre-Phase-3 **Gate G1**, which aborts the campaign before general Phase 3 execution if either participant fails either half |
| 7 | Cursor = 16-byte generation + 8-byte big-endian position; foreign generation → `ResetRequired`; malformed length or never-issued → `invalidCursor` | Split: **1** foreign generation → `ResetRequired`; **1** malformed (relay-relative) → `invalidCursor`; **2** every syntactically valid current-generation never-issued position (issuance tracking and detection not required: `invalidCursor` when detected, or an empty success whose `nextCursor` represents the supplied position when not); **3** the encoding itself (relay-local, opaque) | §12.7 (encoding relay-local and opaque; generation reset contract), §12.6 (status 1 sole `ResetRequired` encoding; "If no entry is returned, it represents the supplied position"), §15.3 code 18, §13.3 (only exact returned cursors are ever presented back) | Foreign-generation and malformed classes: yes, per relay — mandatory Gate G3. Never-issued: no — permitted variation, excluded from every campaign input. Cursor bytes: never | `changes-reset-required` transcript; **Gate G3** determined probes only (malformed = participant-documented bytes via the production path; foreign generation = a cursor naturally returned by a second relay instance of the same participant; no forging, injection, seeding, or test-only surface); never-issued cursors never presented |
| 8 | `byteLimit`: drop trailing entries until fit, set `hasMore`; no entry fits → `responseTooLarge` | 1 (core); truncation point class 2 | §12.6 (ordering + no skipping forces prefix-only omission; "If the next single entry cannot fit within `byteLimit`, it returns `responseTooLarge`…" verbatim; `hasMore` semantics), §12.2 limits label 4, §15.3 code 16 | Outcome classes: yes. Exact prefix length under a squeezing `byteLimit`: no (maximal packing is not mandated) | Compare pinned transcripts byte-for-byte (limits generous); compare squeezed scenarios structurally if ever exercised |
| 9 | Oversized resolve batch: Full results degrade to position-aligned per-DID `Error(responseTooLarge)`, other classifications intact | 2 | §12.3 ("MAY return `responseTooLarge` for a requested batch whose results cannot fit its advertised bound"; per-DID alignment and cardinality rules), §15.2, §12.2 limits | No — one conforming policy among several (Refs, different degraded subsets) | Record; no pinned scenario exercises it and Phase 3 batches stay within bounds |
| 10 | Client caps 1 MiB non-changes / request `byteLimit` for changes; non-200 bodies not parsed as protocol bodies | 3 | §14.1 ("Suggested v1 defaults", 1 MiB total response bytes), §12.6/§12.2 (`byteLimit` bound), §15.4 (protocol body on HTTP 200; a 400 response has no normative per-item CBOR body; bound error bodies before parsing) | No | Exclude; local resource policy consistent with the spec |
| 11 | Client rejects info/directory missing version 1 or suite -19 with `schemaViolation`; rejects duplicate directory indices | 1 | §12.2 (MUST include 1 and -19 — a content requirement on the message), §11.4 (indices MUST NOT be reused within a generation), §12.1 (client MUST reject a non-schema-conforming outer response), Appendix A closing note (CDDL acceptance alone never sufficient; normative text rules are part of the applicable schema), §15.3 code 6 with §6.1.3 fallback | Yes — now exercised | **Mandatory** hostile-peer comparison, no longer optional: the `info-missing-version`, `info-missing-suite`, and `directory-duplicate-index` transcripts are presented to each production client path in Phase 3 step 6; each complete response MUST be rejected with `schemaViolation` and MUST yield no usable protocol state |
| 12 | Status-1 diagnostic: emitter verifies `losingRecord` vs `duplicate` accuracy; decoder accepts bare, code-12, code-13 as byte-distinct permitted forms | 2 (the sole enumerated wire variation); accuracy and acceptance rules class 1 | §12.5 (presence is the Relay's choice; when present MUST be accurate and MUST be 12 or 13), §15.3, §20.2 publish-response bullet, Appendix A closing note | Acceptance/classification: yes (`expected/publish-responses.json`). Raw emission choice: no — byte-compared against the enumerated set, recorded, never normalized, never a disagreement | Fully covered: matrix + `publish-no-change`, `publish-no-change-diagnostic`, `publish-losing-record` transcripts |
| 13 | Invalid status/errorCode combination → `schemaViolation`; deeper CBOR faults retain `invalidCbor`/`nonDeterministicCbor` | 1 | §12.5 final paragraphs (any other combination fails the applicable v1 schema; reject completely, extract no status), §6.1.1–§6.1.3 (layering: schema classification only after the CBOR layers pass), §15.3 codes 4, 5, 6 | Yes | Compare via `expected/publish-responses.json` and the CBOR-layer vectors |
| 14 | Loopback configuration: explicit deterministic test constants, no wall clock or randomness, local orchestration only | 3 | `authoring/AUTHORING.md` rule 3 (deterministic protocol code; every clock an explicit `nowMs` input), `INTERFACE.md` (wall time must not be consulted); not a protocol surface | No | Exclude; orchestration plumbing |

## Explicit determinations

- **§15.4 and the 413 thresholds.** §15.4 permits only the general
  pre-parse use of `413` (a SHOULD); it names no thresholds. The
  reported 64 KiB / 2 MiB values are implementation-local transport
  policy, conforming because they sit strictly above every conforming
  minimum the specification obliges the relay to accept (§15.1 16 KiB
  record; §15.2 64-DID resolve batch within 1 MiB). The observable
  consequence of differing caps is explicitly classified, not
  excluded: for a record above the 16 KiB protocol limit whose
  complete request stays below both participants' transport caps, the
  spec-determined outcome is a status-2 `recordTooLarge` publish
  response under HTTP 200; for a request in the band above one
  participant's pre-parse cap but below the other's, HTTP 413 from
  one side versus HTTP 200/status-2 from the other is **permitted
  transport variation** — both raw outcomes preserved and reported,
  neither normalized into the other, never a protocol disagreement.
  The normative Campaign 2 comparison is pinned to the
  `publish-record-too-large` transcript: a validly signed,
  fault-isolated envelope of exactly 16385 bytes (16 KiB + 1).
  Below-both-caps determination is mechanical (ACCEPTANCE Gate G2):
  each participant's declared pre-parse publish transport cap is
  recorded at freeze, the case runs only after confirming
  16385 <= min(declared caps), and the live HTTP 200 outcome confirms
  the determination empirically; a declared cap below 16385 is
  recorded as a coverage limitation for that direction. The
  participant-owned declaration is the only available evidence
  source: the §12.2 limits map (labels 0-4) advertises exactly five
  protocol limits — maximum complete Identity Record bytes,
  resolve-request DID count, resolve-response bytes, `changes` item
  count, and `changes` response bytes — and contains no HTTP
  request-entity cap, so the production `info` path cannot supply the
  pre-parse value; and the 16 KiB record limit (like any advertised
  label-0 record bound) is a protocol limit, never to be conflated
  with the HTTP request/body cap.
- **404/405 and publish CORS.** Unknown-path and wrong-method handling
  is outside normative interoperability (class 3). Read-operation CORS
  is SHOULD-level permitted variation (class 2), followed as
  recommended; publish CORS is unconstrained. None is pinned
  behaviour.
- **Foreign-generation, malformed, and never-issued cursors.** Two
  determined obligations and one permitted variation. A well-formed
  cursor from a non-current generation is the §12.7 reset condition
  and receives the status-1 `ResetRequired` encoding — pinned by
  `changes-reset-required` and probed naturally in Gate G3 with a
  cursor genuinely returned by a second relay instance of the same
  participant, never forged. A cursor the relay's own encoding
  classifies as malformed is `invalidCursor` (§15.3 code 18,
  "malformed"; relay-relative, Gate G3, participant-documented probe
  bytes presented through the production path). A syntactically
  valid current-generation position the relay never issued is
  **permitted variation**, not a MUST: an earlier revision of this
  document read the §12.6 visibility invariant as requiring
  `invalidCursor` beyond the watermark, and that interpretation is
  withdrawn. The invariant governs positions assigned or reserved by
  relay ingress whose eventual visibility may remain undecided; a
  genuinely never-issued position has no tuple and no undecided
  visibility, and neither §12.6 nor §12.7 requires issuance tracking
  or detection. §15.3 code 18 *permits* `invalidCursor` when a relay
  detects such a position as unknown; a relay not tracking issuance
  may conformingly return an empty successful response whose
  `nextCursor` represents the supplied position (§12.6: "If no entry
  is returned, it represents the supplied position"). Never-issued
  cursors are excluded from every Campaign 2 input — never a
  mandatory comparison, and never generated through forging, state
  seeding, or any test-only production participant surface; the
  bundle verifier mechanically proves no transcript input carries a
  cursor outside the enumerated set. A future specification version
  could enumerate the two conforming outcomes explicitly if desired;
  no v0.9.3 is drafted, and Campaign 2 proceeds under the
  permitted-variation classification. The encoding itself stays
  relay-local, opaque, never byte-compared.
- **Premature tuple in `changes`.** Yes — it MUST appear. The
  composition §13.1 step 8 → §5.4 (no removal, no `lastUpdated`
  change) → §12.6 (no advancing past omitted eligible entries) leaves
  emission as the only conforming behaviour, and §13.3/§16.16 receiver
  semantics presuppose it. This is now directly pinned by the
  `changes-premature-retained` and `resolve-premature-retained`
  transcripts and ACCEPTANCE Phase 3 step 6a; it no longer rests on
  indirect reasoning alone. Enforcement is executable, not prose:
  pre-Phase-3 **Gate G1** exercises both halves live against each
  frozen participant in both directions and **aborts the campaign
  before general Phase 3 execution** if either participant fails
  either half. Participant-owned regression evidence (each frozen
  revision's own tests for both behaviours) is recorded in the
  campaign archive alongside the coordinator's gate log; it
  supplements but never substitutes for the live gate. The bundle
  verifier's pre-Phase-3 gate check mechanically asserts the gate
  transcripts and the ACCEPTANCE anchoring stay consistent.
- **`byteLimit` tail-dropping.** The prefix shape is required — the
  §12.6 ordering and no-skip rules mean any omission is necessarily a
  trailing truncation — and the zero-fit case is verbatim
  specification text: `responseTooLarge`, never an unchanged success
  cursor loop. Only the exact truncation point (maximal versus shorter
  prefix) is unpinned.
- **Oversized resolve-batch degradation.** Merely one conforming
  policy under the §12.3 MAY; the per-DID alignment rules bound the
  space but do not select the reported policy. Not required, not
  compared.
- **Scope of permitted raw-byte variation.** The publish status-1
  reason-code choice is the only enumerated permitted raw-byte wire
  variation in v1. §6.1.2 deterministic encoding makes every other
  wrapper encoding unique for given protocol content, and
  `PROVENANCE.md` restricts the category to sets the pinned
  specification itself enumerates. It cannot be generalized to
  arbitrary responses.

## Deliberate scope decision — browser publication

Item 3's conformance classification stands unchanged. The following
product-scope consequence is recorded deliberately for the campaign
record (it amends neither the reviewed specification nor the
whitepaper):

- v1 conformance does **not** guarantee direct cross-origin browser
  publication;
- publish CORS and preflight support are relay/operator capabilities,
  not v1 conformance requirements;
- a browser-hosted client must use a relay that explicitly supports
  its origin and policy, or a same-origin intermediary;
- omission of `Access-Control-Allow-Origin` on `v1/publish` is never a
  Campaign 2 disagreement.

The same statement is anchored in `ACCEPTANCE.md` so campaign reports
carry it.

## Participant corrections

None required. Every reported Motoko decision is conforming under
v0.9.2. What were previously checklist notes for the future Rust
maintenance pass are now executable pre-Phase-3 obligations on **both**
participants, enforced by ACCEPTANCE Gates G1–G3 with an abort rule:
premature emission in `v1/changes` with resolve-side filtering
(Gate G1), a declared pre-parse publish transport cap recorded at
freeze and admitting the 16385-byte normative case (Gate G2), and the
two determined cursor classification probes — malformed and naturally
obtained foreign-generation (Gate G3). The mandatory hostile-peer
info/directory rejection cases (item 11) bind both participants'
production client paths in Phase 3 step 6.

## Sealed authoring input

The Campaign 2 classification above required no change to any
`authoring/` file. The v0.9.2 AUTHORING subset has since had two
authoring revisions; the pinned specification is byte-identical in
both, so neither identifies a specification revision. The aggregate
recipe is unchanged: SHA-256 over the path-sorted `sha256sum`-style
lines of the twelve files, paths relative to `authoring/` with a `./`
prefix.

**Authoring revision 1 (v0.9.2-r1) — historical.** The subset sealed
in the Motoko repository input commit
d97c328c93fb523104328c9c07f0c774299ced9d, and the exact input the
already-frozen Motoko v0.9.2 maintenance revision received. Its
aggregate digest was, and as historical evidence for that freeze
remains,

```
cec54f10520535b405c2eb11952cbe2e14976be3962cb26cacff29031c89ae6b
```

This record is preserved deliberately and is never overwritten; a
comparison against the frozen Motoko revision is a comparison against
the r1 input.

**Authoring revision 2 (v0.9.2-r2) — current corrected neutral
interface seal.** Only `authoring/interface/INTERFACE.md` changed: the
reviewed interface integration patch was merged into the sections it
replaces (value conventions, structured contact shape, and the
`verifyRecord` accepted-result definition). See
`AUTHORING-REVISION-2.md` for the predeclared impact record and the
present-empty direct-wire fixture inventory. The r2 aggregate digest,
mechanically enforced by the bundle verifier, is

```
1b6514da0c1a0c5289e0909b648b5de73a302e91b346440624badacf5747855e
```
