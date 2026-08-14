# Followee v0.9.1 interoperability campaign 1 — Rust ↔ Motoko

First neutral cross-implementation campaign for the
`followee-interop/v0.9.1` bundle, executed by the coordinator after the
independent Motoko freeze. This report, the adapters and orchestration
under this directory, and the deterministic archive under `results/` are
the campaign's complete deliverable. Everything is left uncommitted for
review; no participant repository, tag, or bundle file was modified.

## 1. Participants and verified starting state

| Repository | Revision | Tag | State |
| --- | --- | --- | --- |
| `followee` (protocol) | `c90742eb763cda5bd3c6e7d20ab1799590da489b` | `v0.9.1-interop-bundle-reviewed` | clean; specification SHA-256 `1c1a20c6…ce3cd71` |
| `followee-rs` | `8606a102bfb4f2bbfbc81e364bdf548c437bf123` | `milestone-5-v0.9.1-reviewed` | clean |
| `followee-motoko` | `3840d9adf07755d326d920f4711dafc4e08bcb40` | `motoko-v0.9.1-independent-freeze` | clean; parent `7f2243ef…`, grandparent `4bd922c3…`; `inputs/v0.9.1` byte-identical to the bundle's AUTHORING subset |
| `followee-conformance` | `9493e39bd738372fe1e2fc1b2e96f6a41983c1be` | `v0.8.1-fixtures-confirmed` (and `v0.8.1-differential-final` → `beb89f65…`) | clean; untouched by this campaign |

The frozen Motoko blind-challenge output
`outputs/challenge/challenge-results.jsonl` was preserved byte-for-byte
**before any comparison**; its SHA-256
`e73c5697de68df7ec0f693834165bff7a1753a077959c9d9be50553b5722478e`
matches the freeze record. Every orchestration script re-verifies all of
these pins and refuses to run otherwise. The Motoko independence record
(`docs/AUTHORING-RECORD.md`) stands as historical evidence; the frozen
tag was not amended, moved, or rewritten.

Toolchains: rustc/cargo 1.97.1 (pinned by `rust-toolchain.toml`),
moc 1.14.0 via mops (pinned), mops CLI 2.14.1 (API 1.3), core 2.6.1
(exact-pinned), Node v24, Python 3.10 (stdlib only).

Pre-campaign gates, both green and re-run by this campaign:
bundle `verify_bundle.py` (12 checks) + its 30 unit tests;
`followee-rs` `cargo fmt --check`, `cargo clippy -D warnings`,
`cargo test` (36 suites, 448 tests, 0 failures);
`followee-motoko` `mops check`, `mops format --check`, `mops test`
(11 files, 130 tests, 0 failures).

## 2. Coordinator implementation (this directory)

| Path | Role |
| --- | --- |
| `adapters/rust-iface/` | Interface adapter for the frozen Rust participant: NDJSON transport for the eight INTERFACE.md operations, path-linked read-only to `followee-rs`. Every protocol decision is a call into the frozen crate's public production API; `build.rs` refuses to build against any revision but the reviewed freeze. |
| `adapters/motoko-driver/RelayDriver.tmpl.mo` | Phase-3 relay driver: routes space-separated command lines to the frozen Motoko production modules (`RelayState`, `RelayWire`, `Verify`, `Hex`, `Errors`) via read-only imports. Contains no protocol logic; scenario-setup commands inject published inputs only. |
| `orchestrate/` | Pin verification, participant invocation, reference materialization, exact comparison, phase drivers, archive builder. The Motoko *interface* participant needs no adapter at all: phases 1–2 invoke the frozen `runner/run.sh` directly. |
| `orchestrate/tests/` | Tamper-visibility suite (10 tests): deliberately altered participant output — flipped digests, swapped symbolic errors, accept/reject flips, deleted members, tampered selection winners, bit-flipped envelopes through the phase-3 driver, altered record-shape values under the documented mapping — always remains visible as a disagreement. A live test also proves the Rust adapter is input-sensitive (it holds no expected answers to echo). |
| `results/` | Deterministic archive (Section 8). |

Adapter integrity: no expected protocol answer, no reimplementation of
protocol semantics, no output repair, no error mapping, no bypass of
production verification/ordering/CBOR/state logic. Two deliberate,
documented exceptions are *shim* territory in phase 3 and are excluded
from Motoko's claimed coverage (Section 6): the publish shim receives
the scenario target DID (published values; the frozen Motoko surface has
no publish DID-extraction entry point), and HTTP media-type/status
transport in the Motoko-serving direction is coordinator glue.

One comparison-layer mapping exists and is visible in every report: the
`verifyRecord` `record` member's descriptor sub-shape is unspecified by
INTERFACE.md and the participants chose different member names
(Rust adapter follows the reviewed conformance schema; Motoko chose
`rootPublicKeyHex`-style naming). Values are compared exactly under a
documented name mapping; the shape gap itself is reported, never
silently normalized (finding I2 below).

## 3. Phase 1 — published and specification-determined vectors

All 76 interface-contract cases in `coordinator/expected/` were executed
on both frozen participants through production-backed neutral
interfaces and compared member-exactly against the bundle expectation,
with per-member provenance (`publishedMembers` ⇒ normative-specification
vs specification-determined). Agreement with one participant was never
counted for the other.

| Operation | Cases | Motoko | Rust |
| --- | ---: | --- | --- |
| deriveIdentity | 3 | 3 exact | 3 all-members-exact except `multihashHex` (not exposed — finding I1) |
| authorRecord | 5 | 5 exact | 5 exact |
| verifyRecord (incl. all B.8/B.10/B.12 negatives and target-DID variants) | 26 | 26 exact | 26 exact |
| nextTimestamp | 8 | 8 exact | 8 exact |
| selectCurrent (incl. all enumerated permutations: 2 orders of three pairs, all 24 orders of the four-candidate set, sticky/premature/cross-DID/empty singletons) | 34 | 34 exact | 34 exact |

Permutation invariance held for every group on both participants.
Cross-participant comparison of complete accepted `verifyRecord`
results (envelope, body, digest, id, timestamp, authority, validUntil,
premature, stale, and the mapped `record` member): 0 mismatches.
Coordinator analysis for I1: the expected multihash base58btc-encodes to
exactly the Rust-produced DID in all 3 cases.

**Result: zero protocol disagreements.** Every published byte, digest,
length, signature, DID, error classification, winner, and flag matched
exactly on both sides.

## 4. Phase 2 — blind challenge comparison

The frozen Motoko output (36 responses, digest above) was preserved
before comparison and never regenerated. The same challenge inputs were
then executed on the frozen Rust participant, with `identityRef`
materialization using Rust's own derived DIDs and own authored
envelopes, exactly as CHALLENGES.md prescribes. A third, independent
coordinator derivation (bundle stdlib `interopkit`) was computed in this
session only.

| Comparison | Result |
| --- | --- |
| Motoko vs Rust, all 36 cases | 33 exact matches; 3 deriveIdentity cases exact on every member except `multihashHex` (finding I1) |
| byte-identical members | all descriptors, bodies, digests, Sig_structures, signatures, envelopes, DIDs |
| Rust vs coordinator derivation (14 derive/author cases) | all exposed members exact |
| Motoko vs coordinator derivation | all 14 exact, including multihash |
| cross-verification (each side verifies the other's 11 envelopes) | 11/11 accepted, digests agree |
| identityRef resolution (migration DIDs = own derivation, both sides) | all match, and cross-side equal |
| permutation invariance (carol-trio ×6, carol-authority ×2, dave-timestamps ×2, sticky singleton) | invariant on both sides, winners identical |

**Result: zero protocol disagreements on values neither implementation
had ever seen asserted.**

## 5. Phase 3 — live two-direction HTTP/CBOR exchange

52/52 checks passed; 23 live exchanges preserved byte-for-byte; 2
findings recorded (Section 7). Recipient clock fixed at
`1785589201123`; opaque relay-chosen values compared structurally per
NONDETERMINISM.md, never byte-compared, never normalized.

**Rust serves (production `relay serve` binary), Motoko as
client/producer/receiver (production message/state modules):**
- `v1/info`, `v1/directory`: 200/`application/cbor`; structure verified
  by the coordinator (protocol version 1, suite −19, opaque 16-byte
  identifiers, relay capability bit) — a documented gap: Motoko has no
  info/directory validator.
- `v1/publish`: Motoko-authored B.4 → exact `publish-admit` bytes;
  republish → exact `publish-no-change` bytes; B.8 → exact
  `publish-rejected` bytes (status 2, `identityBindingMismatch`); B.9
  and B.5 admitted. Motoko-authored state crossed the wire to Rust.
- `v1/resolve`: Motoko's production client emitted byte-exact published
  B.11.4 and B.11.6 requests; live responses were wrapper-accepted,
  positionally aligned, every Full candidate locally verified by
  Motoko's production verifier; malformed-DID index answered
  positionally with wire error 0 (`invalidDid`); published B.11.1
  invalid outer request → HTTP 400 with no per-item body.
- `v1/changes`: null-cursor initial enumeration admitted both records
  through Motoko's own ingress; stored peer cursor byte-identical to the
  returned `nextCursor`; after publishing the B.5 revocation, the
  incremental pull made the update visible exactly once; itemLimit-1
  pagination walked both records exactly once with cursor progress;
  against a reset relay (fresh database, new cursor generation) the old
  cursor produced the exact two-field ResetRequired bytes and Motoko's
  receiver discarded only its cursor.
- Final agreement: Motoko's receiver map and Rust's served view agreed
  on every DID's winning body digest and authority state (Alice: B.5
  digest, rootRevoked; Bob: B.9 digest, root).

**Motoko serves (production `ingress`/`handleResolve` behind the
transport shim), Rust as client/producer (production CLI):**
- `v1/publish`: Rust-authored B.4/B.9 admitted (exact `publish-admit`
  bytes), B.8 rejected — the Rust client surfaced
  `identityBindingMismatch`; the status-1 republish response differed in
  encoding (finding W1). Rust-authored state crossed the wire to Motoko.
- `v1/resolve`: Rust's production client emitted byte-exact published
  B.11.4/B.11.6/B.11.3 requests; Motoko's production serving produced
  byte-exact published B.11.4 and B.11.6 responses (pinned published
  example generation); B.11.1 bytes → Motoko outer-fault classification,
  transported as HTTP 400 with no body; the B.11.3 seeded-scenario
  response diverged (finding W2) while the Rust client preserved
  alignment and verified the valid candidate.
- Not exercised (frozen-surface gaps, not failures): Motoko serving of
  `v1/info`, `v1/directory`, `v1/changes`; Motoko publish-response
  client decoding; Motoko HTTP-binding behaviour (shim territory).

**Hostile-peer client behaviour (published B.11 bytes served to both
production clients):** B.11.2 invalid outer response → both clients
rejected completely at the deterministic-CBOR-profile layer (Rust folds
the layer into its `outerResponseRejected` client symbol — a
client-surface naming difference, noted, not a protocol disagreement);
B.11.7 oversize response → both rejected completely without using its
cursor, with the exact published request bytes emitted by both clients
for the published parameters, and the B.11.7 required post-state held on
both sides; B.11.5 → both receivers admitted Bob at the next update
number, rejected the B.8 candidate with `identityBindingMismatch`, left
Alice untouched, and stored the exact returned cursor
(`7630382d30303032`), matching the published required post-state.

## 6. Coverage boundary

No interoperability claim exceeds what was exercised. Exercised: the
eight interface operations; live relay roles — Rust as full relay
(info, directory, publish, resolve, changes incl. pagination and
reset), Motoko as relay for publish+resolve at the CBOR message and
state layer only; both sides as publish producers, resolve clients with
full local verification, and synchronization receivers. Not exercised:
Motoko-as-relay info/directory/changes serving and HTTP binding (frozen
participant defers these to its wire-transport milestone), Motoko
publish-response decoding, multi-relay resolver traversal, WebFinger
handles, concurrency behaviour, and public (non-loopback) deployment.

## 7. Findings — every disagreement, visibly classified

Zero unexplained disagreements. Four classified findings:

| # | Classification (Section 20.4 category) | Finding |
| --- | --- | --- |
| **W1** | genuine unresolved specification ambiguity | Publish status-1 response encoding: Motoko emits `{0:1, 1:1, 2:13 (duplicate)}`, Rust and the bundle transcript emit `{0:1, 1:1}`. Section 12.5 marks `errorCode` optional without a per-status presence rule (unlike Section 12.6, which pins presence exactly). Both encodings satisfy the published schema; the live Rust client accepted Motoko's response and reported `noChange`. Flagged for specification maintenance: 12.5 should pin `errorCode` presence the way 12.6 does. The bundle's `publish-no-change` transcript is marked specification-determined but rests on the absent-unless-rejected reading. |
| **W2** | real serving disagreement with the published B.11.3 vector (scenario-conditional) | Serving a *held unverifiable candidate*: Motoko's `handleResolve` re-verifies stored envelope bytes at serving time and answers `{0:3, 2:19 (internalError)}` where the published B.11.3 response serves the retained invalid B.8 envelope verbatim as Full (Section 12.3: a Full result "carries the exact admitted complete envelope bytes as a candidate, not a validity assertion"). The state was coordinator-seeded through Motoko's production `seed` entry point; Motoko's own ingress rejects unverifiable candidates, so the state is unreachable through its production ingress alone. Client-side candidate isolation — the Section 20.4 obligation — agreed on both sides throughout. Proposed correction (post-freeze, as a later reviewed commit descended from `motoko-v0.9.1-independent-freeze`; the frozen tag is untouched): serve retained bytes verbatim per Section 12.3. |
| **I1** | production-surface coverage limitation (not a protocol disagreement) | The frozen `followee-rs` public API exposes no raw-multihash accessor, so the Rust adapter omits `multihashHex` rather than reconstructing protocol bytes in the adapter. Coordinator verification: the expected multihash base58btc-encodes to exactly the Rust-produced DID in every affected case (3 phase-1 + 3 phase-2 cases); Motoko's multihash matched expectations exactly everywhere. |
| **I2** | interface-contract documentation gap (not a protocol disagreement) | INTERFACE.md leaves the `verifyRecord` `record` descriptor sub-shape unspecified; the participants chose different member names (already flagged in the Motoko authoring record). Compared under a documented name mapping; all mapped values agreed in every case. Proposed: pin the sub-shape in the next interface revision. |

Also noted (not counted): Rust's client CLI reports hostile-response
rejections under its composite `outerResponseRejected` symbol with the
layer named in the message; Motoko reports the layer symbol directly.
Same rejection decisions everywhere.

## 8. Deterministic archive and gates

`results/` (10 files + `MANIFEST.json` with per-file SHA-256): campaign
metadata with pins, toolchains, reproduction commands, and the explicit
scope boundary; complete per-case phase 1/2/3 reports; all raw phase-1
requests/responses; the byte-preserved frozen Motoko challenge output;
Rust challenge results; all 23 phase-3 raw exchanges with digests.

- Archive rebuilt twice from clean `results/` state: **byte-identical**
  (aggregate SHA-256 `13efa5fd8a1f4b3c34786eba0e6be7c16b1dc2f85d6585a675183c4cda062a36`,
  `MANIFEST.json` SHA-256 `31adc5aaea790e2f976c2d3c36d1b93c41d64569b001f16b65fbc72274e211f0`).
- Phases 1 and 2 re-executed end to end: outputs byte-identical to the
  first run. Phase-3 raw exchanges necessarily contain relay-chosen
  opaque values that differ between live executions, exactly as
  NONDETERMINISM.md prescribes; the archive records this campaign's
  execution.
- Gates, all green at the end of the campaign: bundle verifier + 30
  bundle tests; both participants' complete local gates (Section 1);
  adapter `cargo fmt --check` / `clippy -D warnings` / tests (5);
  orchestration + tamper suite (10); pin checks in every script run;
  `git diff --check` clean; hygiene scan of every review file — no
  timestamps, absolute paths, usernames, credentials, or
  nondeterministic metadata (machine-local paths in recorded CLI output
  are redacted to `~`-relative form in the archive).

## 9. Section 20.4 conclusion

**Section 20.4 is not yet fully satisfied, and no interoperability claim
is made for either implementation.**

Discharged by this campaign with zero unexplained disagreements:
obligations 1–6 (byte-identical descriptors, bodies, digests, DIDs,
signatures and envelopes from the same structured inputs, published and
blind; identical envelope verification including negative
classifications; identical winners across every enumerated permutation)
and obligation 8 (two genuinely independent implementations under the
recorded freeze discipline). Obligation 7 (HTTP/CBOR state exchange,
both directions) is discharged for the Rust-serving direction in full
and for the Motoko-serving direction only for publish and resolve at
the CBOR message/state layer behind a transport shim.

Remaining before Section 20.4 can be declared satisfied:
1. the Motoko wire-transport milestone (HTTP serving; `v1/info` and
   `v1/directory` encoders; changes-feed serving; publish-response
   client decoding; publish target-DID extraction), followed by a
   completing two-direction run of the missing exchanges;
2. resolution of W2 (either the proposed Motoko serving correction as a
   reviewed descendant of the frozen tag, or a specification ruling
   that serve-time re-verification is conforming) and a specification
   clarification for W1;
3. review of I1/I2 interface-surface gaps (multihash accessor;
   `record` sub-shape pinning).

## 10. Milestone 6 completion audit

| Deliverable | Status |
| --- | --- |
| Published neutral fixture bundle | **Complete as content** — `interop/v0.9.1` reviewed and tagged (`v0.9.1-interop-bundle-reviewed`), verifier green. "Published" beyond the repository (public release/announcement) is not evidenced. |
| Documented HTTP transcript examples | **Complete** — 13 coordinator transcripts, deterministically regenerable, now corroborated by live byte-exact exchanges in this campaign. |
| Release binaries or reproducible build instructions | **Outstanding.** No release binaries, no release tag, and no reproducible-build instructions for the `followee` executable exist (toolchain and dependency pins exist, and the demo authority has a reproducible container path, but the README itself notes the first executable release has not happened). |
| Interoperability run against the independent Motoko implementation | **First campaign executed; evidence prepared for review (this directory), uncommitted.** Partially discharges the run: see Section 9 for the exact remainder. |

**Milestone 6 is therefore not complete**: release/reproducible-build
evidence is outstanding, and the interoperability run is partial pending
the Motoko wire-transport milestone and the W1/W2 resolutions.

## 11. Integrity statement

Both participant repositories and all four evidence repositories remain
bit-identical to their pinned revisions with clean working trees (the
only writes anywhere outside this campaign directory were the Motoko
runner's own gitignored `runner/generated/` embeddings and the
participants' own gitignored build caches). Nothing was committed,
amended, squashed, tagged, pushed, released, published, or deployed. The
Motoko independent-freeze tag and its ancestry are untouched. All
campaign changes are uncommitted in `interop/campaign-1/` awaiting
coordinator review.
