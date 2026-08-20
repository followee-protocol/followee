# Followee v0.9.2 interoperability campaign 2 — Rust ↔ Motoko (maintenance)

Second neutral cross-implementation campaign, executed by the
coordinator against the `followee-interop/v0.9.2` bundle at **authoring
revision 2** (v0.9.2-r2), after both maintained participants froze
their revisions on the identical sealed authoring subset. This report,
the orchestration under this directory, and the deterministic archive
under `results/` are the campaign's complete deliverable. Everything is
left uncommitted for review; no participant repository, tag, or bundle
file outside the coordinator's own evidence documents was modified.

**Maintenance framing.** This is a maintenance interoperability
campaign between reviewed implementations. Both participants received
the identical v0.9.2-r2 authoring subset, so their agreement is
maintained-implementation agreement under the shared neutral authoring
contract — never a second independent-convergence result. The
independence evidence remains the immutable Campaign 1 archive
(`v0.9.1-interop-campaign-1`) and the
`motoko-v0.9.1-independent-freeze` ancestry.

## 1. Participants and verified starting state

| Repository | Revision | Tag | State |
| --- | --- | --- | --- |
| `followee` (protocol) | `ac5a794f2fdadc13cddf5367fa3e047617e3e950` | `v0.9.2-reviewed` | tracked tree clean; specification SHA-256 `47af5fbf…633a`; `interop/v0.9.2` uncommitted, sealed at the r2 aggregate `1b6514da…855e` (r1 `cec54f10…ae6b` preserved), bundle verifier 19/19 and 52 bundle tests green before any participant material was imported |
| `followee-rs` | `d865dc3fae52b3e2a54d573c298de7b01a1539c9` | `rust-v0.9.2-maintained-freeze` (tag object `165533f54839aba9c25e6a37e58c85a406f9a8cb`) | clean temporary clone from `github.com/followee-protocol/followee-rs.git`, detached at the peeled commit |
| `followee-motoko` | `bb0b0782e96bea9169ddb723815d191b58de65d7` | `motoko-v0.9.2-r2-maintained-freeze` (tag object `527b3f0c0618d96b484f21ee641a59fec1e3ebc6`) | clean temporary clone from `github.com/followee-protocol/followee-motoko.git`, detached at the peeled commit |

Pins verified before every phase (each orchestration script refuses to
run otherwise): both annotated tag objects and peeled commits; clean
trees; the Motoko `inputs/v0.9.2-r2` subset byte-identical to the
bundle's authoring tree (aggregate `1b6514da…`), its `inputs/v0.9.2`
equal to the historical r1 aggregate `cec54f10…`; the Rust freeze
manifest's authoring aggregate and per-file hashes equal to the
bundle's; and the preserved participant outputs — Motoko blind
(`e73c5697…`, untouched since Campaign 1), Motoko v0.9.2-r1
(`d6c4e556…`), Motoko v0.9.2-r2 (`5c53c787…`), and every frozen Rust
output file against its own `MANIFEST.json` — all checked **before any
comparison**. `followee-python-cleanroom` and `followee-conformance`
were not consulted at any stage.

Toolchains: rustc/cargo 1.97.1 (pinned), moc 1.14.0 via mops (pinned),
mops CLI 2.14.1 (API 1.3), core 2.6.1 exact-pinned, Node v24.17.0
(byte-transport shim/bridge only), Python 3.10 stdlib (coordinator).

Participant local gates, re-run by this campaign on the frozen
revisions: `followee-rs` — `cargo fmt --check` clean,
`cargo clippy --release --all-targets -- -D warnings` clean,
`cargo test --release` 25 suites / 331 tests / 0 failures;
`followee-motoko` — `mops check` clean, `mops format --check` clean,
`mops test` 17 files / 213 tests all passing, `mops build` release
wasm builds with the pinned compiler.

## 2. Coordinator implementation (this directory)

| Path | Role |
| --- | --- |
| `orchestrate/interop_common.py` | Pin verification, bundle-vector loading (including the r2 inline-envelope direct-wire cases), participant invocation, exact comparison. No expected protocol answer, no protocol semantics. |
| `orchestrate/phase1.py` / `phase2.py` | Phase drivers (Sections 4–5). |
| `orchestrate/gates.py` | Executable pre-Phase-3 gates G1–G3, both directions (Section 6). |
| `orchestrate/phase3.py` | Live two-direction HTTP/CBOR campaign (Section 7). |
| `orchestrate/motoko_bridge.js` | Coordinator bridge over the participant's own semantic-free loopback shim (`shim/loopback.js`): routes commands, ports, and raw bytes; adds a client-carry that can represent a production build refusal, and a byte-identical HTTP server over the gate driver. Transport only. |
| `orchestrate/motoko-driver/GateNode.mo` | Coordinator gate driver over the frozen production `RelayHttp`/`RelayServe` modules: the relay clock as the explicit per-call production parameter and the opaque instance identifiers as configuration. Materialized under the checkout's gitignored `runner/generated/`. |
| `orchestrate/clockshim/clockshim.c` | Environment scenario clock (LD_PRELOAD, realtime clock only) for the Rust `relay serve` process in the G1 premature scenario. Participant code unchanged. |
| `orchestrate/tests/test_tamper.py` | Tamper-visibility suite (13 tests): flipped digests, accept/reject flips, swapped symbolic errors, deleted members, presence-projection reversion, bit-flipped envelopes, nulled revocationKey, tampered winners always remain visible as disagreements; live input-sensitivity of both interface engines (a bit-flipped envelope changes the production answer — no expected answers to echo). |
| `results/` | Deterministic archive (Section 10). |

Participant invocation surfaces (black-box): the Rust production
`followee` binary (`interop` NDJSON engine, `relay serve/publish/
resolve/changes/sync`, `resolve`) built `--release --locked` from the
clean checkout, and the Motoko production `runner/run.sh` NDJSON engine
and `shim/loopback.js`+`shim/RelayNode.mo` loopback participant. No
participant protocol source (`src/`) was opened during this campaign;
the consulted participant files were the freeze/maintenance records,
`tests/REQUIREMENTS.md` (for the Gate G1 regression-evidence
identifiers ACCEPTANCE prescribes recording), and the shim/runner
invocation surfaces themselves. One black-box probe (`strings` over the
built binary) located the documented `--now-ms` flags; no discrepancy
ever required source inspection.

## 3. Evidence chronology

1. Coordinator bundle re-verified (19/19 checks incl. the r2 seal
   check; 52 bundle tests; deterministic regeneration) **before** any
   participant evidence was imported.
2. Frozen tags fetched into clean temporary clones; every pin above
   recorded and verified; participant-owned manifests and output
   hashes recorded.
3. Phases 1–2 executed and compared against the predeclared
   expectations (bundle expectations and `coordinator/
   PRECLASSIFICATION.md`) before any Phase 3 exposure.
4. Gates G1–G3, then Phase 3, then archive; every difference
   classified against the predeclared classes before any source
   inspection (none was needed).

## 4. Phase 1 — published and specification-determined vectors

All **129** interface-contract cases in `coordinator/expected/` were
executed on both frozen participants through their own production
neutral-interface engines and compared member-exactly against the
bundle expectation, with per-member provenance. Agreement with one
participant was never counted for the other.

| Operation | Cases | Motoko | Rust |
| --- | ---: | --- | --- |
| deriveIdentity | 3 | 3 exact | 3 exact (incl. `multihashHex` — Campaign 1 finding I1 closed) |
| authorRecord | 5 | 5 exact | 5 exact |
| verifyRecord (all negatives, target-DID variants, and the four v0.9.2-r2 direct-wire present-empty cases) | 30 | 30 exact | 30 exact |
| nextTimestamp | 8 | 8 exact | 8 exact |
| selectCurrent (every enumerated permutation) | 34 | 34 exact | 34 exact |
| receivePublishResponse (complete Section 12.5/20.2 matrix incl. unregistered-code probes) | 49 | 49 exact | 49 exact |

The accepted `verifyRecord` comparisons include the complete
v0.9.2-r2 `record` projection — closed eight-member descriptor,
authority-dependent `revocationKey`, structured Contact Document, two
distinct extension maps, lossless `null` / `[]` / `{}` presence — deep
and exact, with **no name mapping**: Campaign 1 finding I2 is closed;
both participants implement the identical contract shape. The four
direct-wire cases (present-empty `alsoKnownAs`, contact extensions,
record extensions, combined) **were exercised** on both participants,
as the interface's evidential-scope section asks reports to state:
agreement on authored records alone establishes nothing about
present-empty collection handling. Cross-participant comparison of all
nine accepted results: 0 mismatches on every member including
`record`. Permutation invariance held for every group on both sides.

**Result: 129/129 exact on both participants; zero disagreements.**

## 5. Phase 2 — challenge maintenance confirmation

The frozen pre-exposure outputs were preserved and digest-checked
first (Section 1). The two participants' frozen v0.9.2-r2 challenge
outputs (36 responses each) were compared value for value under the
interface result-equality rule; the coordinator computed a third
independent derivation with the bundle's stdlib `interopkit`; and each
implementation **live-verified the envelopes the other authored**
through its own production interface engine at the challenge
`verifyNowMs`.

| Comparison | Result |
| --- | --- |
| Motoko vs Rust, all 36 cases (deep, incl. full r2 `record` projections) | 36 exact |
| byte-identical members | all descriptors, bodies, digests, Sig_structures, signatures, envelopes, DIDs, multihashes |
| Rust vs coordinator derivation (14 derive/author cases) | 14 exact |
| Motoko vs coordinator derivation | 14 exact |
| cross-verification (each side verifies the other's 11 envelopes, live) | 11/11 accepted, digests agree |
| identityRef resolution (migration DIDs = own derivation, both sides) | all match |
| permutation invariance (all challenge selection groups) | invariant on both sides, winners identical |

Participant-local labeling differences (recorded, not values): Rust
labels its self-verify responses `<case>-verify` and groups its output
files by operation; Motoko labels them `<case>/verify` and interleaves.
The alignment maps labels only.

**Result: zero disagreements — maintenance confirmation, not a new
independent-authoring result.**

## 6. Pre-Phase-3 gates — all live, both directions, 19/19

- **G1 (premature emission and filtering).** Each serving side was
  seeded with B.4 through its production ingress at an admissible
  clock, then served at the pinned premature clock `1785588900122`
  (Rust: `relay serve` under the coordinator environment clock shim;
  Motoko: production `RelayHttp.handle` at its explicit `nowMs`
  parameter behind the gate driver). Both sides: null-cursor
  `v1/changes` returned the retained Full tuple with **exact B.4
  bytes**; `v1/resolve` returned the aligned per-DID
  `Error(premature)` `{0:3, 2:10}` — never Absent, never Full. The
  receiving half ran live in both directions: each receiver admitted
  the premature-served tuple under its own clock `1785589201123`
  without importing the sender's diagnosis. Participant-owned
  regression evidence recorded in `results/gates-report.json`
  (Rust `relay_core::sec_12_3_locally_premature_current_record_is_error_not_absent`
  and the REQUIREMENTS §5.4/12.6 rows; Motoko
  `test/relayserve.test.mo` premature serving rows).
- **G2 (transport-cap determination).** Declared pre-parse publish
  caps recorded at freeze: Rust 65,536 bytes (freeze README), Motoko
  65,536 bytes (maintenance record item 2); 16,385 ≤ min. The
  transcript's exactly-16,385-byte validly signed fault-isolated
  record was published live to both serving sides: **HTTP 200 with the
  exact status-2 `recordTooLarge` bytes** both times. Client-side
  extras, recorded visibly: the Rust client surfaced the protocol
  rejection; the Motoko production client refuses to construct a
  publish request for an over-16-KiB record at all (`build-refused`,
  its own Section 15.1 client bound) — a conforming client-side
  outcome, not a disagreement; the serving-side comparison is the
  normative gate check.
- **G3 (determined cursor classifications).** Per serving side:
  (a) malformed probe — a 1-byte truncation of a cursor genuinely
  returned by the probed relay (wrong length under both participants'
  declared bounded generation+position encodings; neither freeze note
  names a literal probe byte string, recorded as a declaration
  remark) → exact status-2 `invalidCursor` bytes (Section 12.6 label 6
  = code 18); (b) foreign-generation probe — a cursor genuinely
  returned by a second instance of the same participant (fresh Rust
  database / independently configured gate instance) → **exact
  two-field `ResetRequired` bytes** (`a200010101`). No cursor was
  forged, no state seeded through a test-only surface, no never-issued
  position probed. Coordinator-tooling note (not a finding): the
  coordinator's first G3(a) expectation was wrong — see finding N1
  (Section 8) for the exact original expectation
  (`{0:1, 1:2, 2:18}`), the observed participant bytes
  (`{0:1, 1:2, 6:18}`), the Section 12.6 CDDL basis, and the
  chronology: both participants' live answers agreed with each other
  and with the specification before any harness change was made, and
  the complete gate suite was re-run after the correction.

## 7. Phase 3 — live HTTP/CBOR state exchange, both directions

**67/67 checks; 55 raw exchanges preserved** in
`results/phase3-report.json`. Recipient clocks fixed per scenario;
opaque relay-chosen values compared structurally per
NONDETERMINISM.md.

**Direction R — Rust serves (production `relay serve` binary), Motoko
as client/producer/receiver (production `RelayClient`/ingress behind
its own byte-only shim):** info and directory served 200
`application/cbor` and **validated by the Motoko production client**
(both were frozen-surface gaps in Campaign 1 — now closed); publish
B.4 → exact `publish-admit` bytes; republish → exact bare status-1
bytes, accepted by the Motoko decoder (`noChange bare`); losing B.6
scenario → exact bare status-1, accepted; B.8 → exact
`publish-rejected` bytes under HTTP 200; resolve with duplicate DIDs
and with a malformed DID → positionally aligned, every Full candidate
locally verified by Motoko, malformed index answered `error:0`
(`invalidDid`); changes: initial null-cursor enumeration admitted both
records through Motoko's own ingress with the returned cursor stored
exactly, B.5 revocation propagated exactly once, second pull empty,
itemLimit-1 pagination walked each record exactly once through a fresh
receiver; final agreement alice=B.5 (rootRevoked) / bob=B.9 verified
by Motoko; B.11.1 hostile request → HTTP 400, empty body.

**Direction M — Motoko serves the complete relay HTTP profile
(production `RelayHttp`/`RelayServe` behind its own loopback shim —
the Campaign 1 "Motoko wire-transport milestone" remainder, now
exercised live), Rust as client/producer/receiver (production CLI):**
info and directory 200 `application/cbor`; publish B.4 admitted;
republish → **exact coded duplicate bytes** `a300010101020d`, accepted
by the Rust production decoder (`reason: duplicate`); losing B.6
scenario → **exact coded losingRecord bytes** `a300010101020c`,
accepted (`reason: losingRecord`); B.8 → exact rejection bytes under
HTTP 200, surfaced as `identityBindingMismatch`; resolve with
duplicates and a malformed DID → aligned, all Full candidates verified
by Rust, malformed index `invalidDid`; sync: initial admits both
records through Rust's own two-phase ingress with the exact returned
cursor persisted, B.5 exactly once, further sync empty, itemLimit-1
sync paginated each record exactly once; **final state agreement: the
Rust receiver database (served by the Rust relay) and the
Motoko-served view returned byte-identical winning records for alice
and bob**; B.11.1 → HTTP 400, empty body.

**Hostile-peer client behaviour (coordinator fixture serving the
published/constructed bytes to both production client paths —
mandatory step 6):** `info-missing-version`, `info-missing-suite` →
Motoko `reject protocol schemaViolation`; Rust `relay sync` complete
rejection with no usable state (no follow-up request issued; composite
`outerResponseRejected` symbol naming the schema layer — the
documented Campaign 1 client-surface naming difference, same rejection
decision). `directory-duplicate-index` → Motoko
`reject protocol schemaViolation`; Rust multi-relay resolver fetched
the directory on a Ref result and rejected it completely, using no
reference target. B.11.2 → both clients rejected completely at the
outer layer. B.11.5 → both receivers admitted Bob, rejected the B.8
candidate alone (`identityBindingMismatch`), left Alice untouched, and
stored the exact returned cursor `7630382d30303032`. B.11.7 → both
receivers rejected the over-itemLimit response completely; cursor
preservation proven live (Motoko state probe; Rust's next emitted
request still presented the exact stored cursor). Malformed publish
response (status 1 + `invalidDid`) → both publish clients rejected the
complete response without extracting a status.

**Challenge crossing (step 7):** with the serving relays at the
challenge clock (`verifyNowMs` 1790001000000 — the sealed challenge
timestamps lie beyond both default scenario clocks, and both
participants initially classified them `premature` **identically**
until the coordinator scenario clock was corrected), Motoko-authored
records (carol-root-full, dave-continues, erin-revoked-empty) were
published to Rust, admitted by Rust's production ingress, served back
**byte-for-byte**, and verified through the Motoko production
interface; Rust-authored records crossed to Motoko, were admitted by
Motoko's production ingress, and were resolved and locally verified by
the Rust client. (The two participants' authored challenge bytes are
byte-identical, so each direction still exercises the receiving
ingress verification on foreign-published state.)

## 8. Findings — every difference, visibly classified

**Zero disagreements. Zero unresolved specification ambiguities. No
class-4 preclassification item.** Classified observations:

| # | Classification | Observation |
| --- | --- | --- |
| V1 | permitted diagnostic variation (PRECLASSIFICATION item 12) | Publish status-1 encoding: Rust emits the bare form (`a200010101`), Motoko the coded accurate form (`a300010101020d` duplicate / `a300010101020c` losingRecord). Each side's production client accepted the other's choice; every raw byte compared against the enumerated conforming set, preserved, never normalized. Campaign 1's W1 ambiguity is resolved by v0.9.2 exactly as the bundle classifies. |
| V2 | conforming client-side bound (recorded; not a disagreement) | The Motoko production client refuses to construct a publish request for an over-16-KiB record (`build-refused`); the Rust client sends it and surfaces the relay's protocol rejection. The normative serving-side comparison (Gate G2) was exact on both sides. |
| V3 | client-surface naming (noted, not counted; carried from Campaign 1) | Rust reports hostile-response rejections under its composite `outerResponseRejected` symbol with the layer named in the message; Motoko reports the layer symbol (`schemaViolation`, …) directly. Same rejection decisions everywhere, including the new mandatory info/directory cases. |
| V4 | participant-local labeling (outside result equality) | Challenge self-verify labels (`-verify` vs `/verify`) and output-file ordering differ; aligned visibly, values untouched. |
| V5 | identification metadata (outside comparison) | `hello` metadata conventions differ: Rust reports the freeze commit (via its documented flag) and the specification revision commit; Motoko reports its revision-2 baseline commit (`6c0af5a9…`, as its predeclaration states) and the specification SHA-256. |
| N1 | coordinator-tooling correction (not a participant difference) | The coordinator's first Gate G3(a) expectation encoded the status-2 `invalidCursor` changes response as `{0:1, 1:2, 2:18}` (bytes `a3000101020212`), placing `errorCode` at label 2 by analogy with the publish-response layout. Chronology: the gate ran first with that expectation; **both participants independently returned the identical bytes `a3000101020612`** = `{0:1, 1:2, 6:18}`; the coordinator then consulted the pinned specification, whose Section 12.6 `changes-response` CDDL assigns labels 2–5 to entries/`nextCursor`/`hasMore`/`directoryGeneration` and reserves label **6** for `errorCode` (`? 6: uint`, here Section 15.3 code 18, `invalidCursor`); the harness constant was corrected to `{0:1, 1:2, 6:18}` and the complete gate suite was re-run. The participants agreed with each other and with the specification throughout; only the coordinator's expectation was ever wrong, and no participant output was reinterpreted or normalized. |
| N2 | gate-evidence remark | Neither freeze note documents a literal malformed-cursor probe byte string; both document the bounded encoding/behaviour, and the probe used was a truncation of a genuinely returned cursor (malformed under both declared encodings). A literal probe byte string in future freeze notes would discharge G3(a) exactly as written. |

Predeclared-versus-observed: every exercised PRECLASSIFICATION row
held — item 5 (publish target = signed DID; B.8 rejected both
directions), item 6/G1 (premature emission + filtering, both
directions), item 7/G3 (cursor classes; never-issued excluded), item 8
(pagination prefix behaviour), item 11 (mandatory hostile
info/directory rejections, both production client paths), item 12
(status-1 variation), item 13 (publish-response schema rejections),
item 2/G2 (transport caps). Items 1, 3, 4 (accept-side), 9, 10, 14
remain excluded/record-only exactly as preclassified; CORS on reads
was observed as recommended and publish-CORS absence falls under the
recorded browser-publication scope decision.

## 9. Coverage boundary

No interoperability claim exceeds what was exercised. Exercised: the
nine interface operations against every coordinator expectation
(including the complete publish-response matrix and the r2
direct-wire present-empty cases); frozen challenge comparison with
live cross-verification; gates G1–G3 live in both directions; the
complete five-operation live HTTP/CBOR exchange in both directions
with publish statuses 0, 1-bare, 1-coded (duplicate and losingRecord),
and 2 (identityBindingMismatch and recordTooLarge), duplicate and
malformed resolve batches, initial/incremental/paginated/exactly-once
changes, cursor reset and malformed-cursor classification, hostile
material against both serving sides and both production client paths,
the premature-retention contrast both ways, and challenge-authored
state crossing both ways. Not exercised: multi-relay resolver
traversal beyond the single-relay Ref/directory rejection path,
WebFinger handles, concurrency behaviour, public (non-loopback)
deployment, and the Rust container-based binary-reproducibility
demonstration (participant-owned at its freeze; instructions recorded
there).

Shim scope: the Motoko participant was driven through its own
semantic-free loopback shim exactly as its maintenance record and
IMPLEMENTATION.md's transport-milestone rule prescribe (sockets and
byte transport only; shim-transparency tamper tests are the
participant's own, re-run green in its local gates). The coordinator's
gate driver adds only scenario configuration the production API
exposes (per-call clock, configured opaque identifiers). The Campaign
1 publish target-DID shim exception no longer exists: publish target
extraction ran through both participants' production paths.

## 10. Deterministic archive and gates

`results/` (14 files + `MANIFEST.json`, aggregate SHA-256
`25095eff996b0ab7e3269e6d6105c7393d9d99e416783114c2ee1a162732d343`):
campaign metadata with pins, toolchains, reproduction commands, and
the scope statement; complete per-case phase 1/2 reports with all raw
phase-1 requests/responses; the byte-preserved frozen Motoko r2
challenge output and frozen Rust challenge response files; the
phase-2 live cross-verification raws; the complete gate report; and
the phase-3 report with all 55 raw exchanges. Machine-local paths are
redacted to `~`-relative form; no timestamps, usernames, or
credentials.

- Archive rebuilt twice: **byte-identical** (same aggregate).
- Phases 1 and 2 re-executed end to end: reports and raw responses
  **byte-identical** across reruns. Phase-3/gate raw exchanges contain
  relay-chosen opaque values that differ between live executions,
  exactly as NONDETERMINISM.md prescribes.
- Gates all green at campaign end: bundle verifier (19 checks, incl.
  the r2 seal check) + 52 bundle tests; both participants' local gates
  (Section 1); campaign tamper suite (13); pin checks in every script
  run; archive hygiene scan clean.

## 11. Section 20.4 conclusion

All three phases and all three gates completed with **zero unexplained
disagreements**; permitted diagnostic variation was kept visible and
never normalized. Against the Section 20.4 obligations as mapped by
`interop/v0.9.2/ACCEPTANCE.md`:

- Obligations 1–6 (byte-identical descriptors, bodies, digests, DIDs,
  signatures, envelopes; identical verification including every
  negative, target-DID variant, and the present-empty direct-wire
  cases; identical winners over every enumerated permutation):
  **discharged** (Phases 1–2).
- Obligation 9 (the complete v0.9.2 publish-response field matrix):
  **discharged** (Phase 1 matrix and live Phase 3 emission and
  acceptance of both permitted status-1 encodings).
- Obligation 7 (HTTP/CBOR state exchange, both directions):
  **discharged in both directions** — the Campaign 1 remainder
  (Motoko serving of info/directory/changes over HTTP, its
  publish-response client decoding, and publish target-DID extraction
  through production paths) was exercised live; both directions
  covered all five operations, the hostile-peer set, the premature
  contrast, and state authored by each implementation crossing the
  wire to the other.
- Obligation 8 (two independent implementations): carried by the
  recorded Campaign 1 independent-authoring history and preserved by
  the exposure discipline (both freezes verifiably preceded any
  coordinator exposure; the sealed r2 subset was the only shared
  input). Campaign 2 agreement is maintained-implementation agreement.

**Subject to coordinator review of this campaign, the Section 20.4
interoperability criterion is satisfied for specification v0.9.2
between `rust-v0.9.2-maintained-freeze`
(`d865dc3fae52b3e2a54d573c298de7b01a1539c9`) and
`motoko-v0.9.2-r2-maintained-freeze`
(`bb0b0782e96bea9169ddb723815d191b58de65d7`), citing the v0.9.2
bundle at authoring revision 2 (seal `1b6514da…`).** Each
implementation may be described as interoperable only with that
citation and within the Section 9 coverage boundary; the description
of the pair remains "maintained participants under one neutral
authoring contract", never "independently convergent". Campaign 1's
W1 is resolved (permitted variation under v0.9.2, observed live in
both encodings); W2's scenario class was re-covered by the live
premature-retention and candidate-isolation checks with no
recurrence; I1 and I2 are closed in both participants and verified
member-exactly.

## 12. Integrity statement

Both participant clones remained bit-identical to their pinned frozen
revisions with clean trees throughout (the only writes were the
participants' own gitignored build caches and `runner/generated/`
embeddings, where the coordinator gate driver is also materialized).
Nothing was committed, amended, tagged, pushed, released, published,
or deployed in any repository. The specification, whitepaper, v0.9.1
bundle, Campaign 1 archive, authoring revision 1 and 2 seals, and all
existing tags are untouched. All campaign material is uncommitted in
`interop/campaign-2/` (plus the coordinator evidence-document updates
inside `interop/v0.9.2/`) awaiting coordinator review.
