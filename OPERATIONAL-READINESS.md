# Followee operational-readiness plan

Status: milestone plan, authored 2026-08-20. Nothing in this document is
itself evidence; it predeclares gates whose evidence does not yet exist.

## 1. Purpose and evidential scope

This plan defines the operational-readiness milestone that follows
interoperability Campaign 2. It answers one question: **what remains to
be demonstrated, and under what predeclared gates, before any of the
four release claims in Section 12 may be made.**

Evidential rules:

- Campaigns 1 and 2 are complete, frozen, and are consulted as
  preserved evidence only. Nothing here reinterprets them. In
  particular, Campaign 2 remains **maintained-implementation agreement
  under one shared neutral authoring contract**, never a second
  independent-convergence result
  (`interop/campaign-2/CAMPAIGN.md`, Section 1 framing and Section 11).
- An obligation counts as **proven** only when a preserved artifact is
  cited by exact path, test name, campaign gate, or result file. An
  unmentioned test is treated as nonexistent.
- This plan does not change the specification. Where the audit exposed
  a normative ambiguity or a scope choice, its disposition is recorded
  explicitly — as a maintainer decision for this milestone
  (Section 13) or as a still-open decision (Section 14) — never
  silently embedded in gate criteria.
- No historical tag, bundle, campaign archive, manifest, participant
  output, or maintenance record may be modified or retargeted
  (Section 11).

Every obligation below is classified with one of six statuses:

| Code | Meaning |
| --- | --- |
| **P** | Already proven by preserved evidence (citation required) |
| **L** | Implemented and tested locally in at least one participant, not tested interoperably |
| **R** | Required by the specification but not yet demonstrated |
| **H** | Operational hardening beyond the specification |
| **G** | Registration or publication work, not implementation testing |
| **X** | Genuinely out of scope for this milestone |

## 2. Frozen starting pins

All verified on 2026-08-20 against clean working trees.

| Item | Pin |
| --- | --- |
| `followee` baseline and `origin/main` | `c52a48b377def0b7ed98ce8af8337c691f875024` |
| Reviewed v0.9.2 authoring-revision-2 bundle | tag `v0.9.2-interop-bundle-reviewed`, peeled commit `66e36dab1e7e34a496cc73ebfbabf896ccf78e95` |
| Campaign 2 | tag `v0.9.2-interop-campaign-2`, peeled commit `c52a48b377def0b7ed98ce8af8337c691f875024` |
| Rust participant | tag `rust-v0.9.2-maintained-freeze`, peeled commit `d865dc3fae52b3e2a54d573c298de7b01a1539c9` |
| Motoko participant | tag `motoko-v0.9.2-r2-maintained-freeze`, peeled commit `bb0b0782e96bea9169ddb723815d191b58de65d7` |
| Shared authoring-revision-2 aggregate | `1b6514da0c1a0c5289e0909b648b5de73a302e91b346440624badacf5747855e` |
| Specification SHA-256 (v0.9.2) | `47af5fbf0c4505386b4e04d948ef89d013f878ea820fb02522817661d633633a` |
| Campaign 2 results archive aggregate | `25095eff996b0ab7e3269e6d6105c7393d9d99e416783114c2ee1a162732d343` |
| Campaign 1 results archive aggregate | `13efa5fd8a1f4b3c34786eba0e6be7c16b1dc2f85d6585a675183c4cda062a36` (as pinned in `interop/v0.9.2/evidence/EVIDENCE.md`) |
| Conformance harness (v0.8.1-era, frozen) | `followee-conformance` @ `9493e39bd738372fe1e2fc1b2e96f6a41983c1be` |
| Python clean-room (v0.8.1-era, frozen) | `followee-python-cleanroom` @ `a94e9a8a7bd2f9c2e0947715ec387b6c3967e4e6` |

Every readiness gate execution MUST re-verify the pins it consumes
before producing evidence, and MUST record the pins it ran against.

## 3. Track separation

Readiness work is divided into six tracks that MUST NOT be conflated in
any claim:

1. **Specification conformance** — the untested normative requirements
   of specification §20.2 and §20.3 (gates RN-A, RN-B).
2. **Implementation robustness** — lifecycle, persistence, and
   resource behavior; partly normative (§12.6, §13.5, §16.7),
   partly hardening (gates RL-C, RL-F).
3. **Public-network operation** — real HTTPS/DNS/WebFinger deployment
   behavior (gates RT-D, RT-E).
4. **Reproducible and inspectable artifacts** — builds, pins, hashes,
   provenance (gate RA-G).
5. **Security review** — dependency, threat-model, fuzz/mutation,
   hygiene, residual-risk reporting (gate RS-H).
6. **Registration** — specification §21 items; publication work, not
   testing (Section 12, claim 4 only).

Passing any gate in tracks 1–5 does not advance track 6, and no track
combination short of the Section 12 requirements supports a
"production" claim of any wording.

## 4. Requirement / evidence / gap matrix

Column key: *Basis* = specification clause or operational rationale;
*Rust* / *Motoko* = participant-local evidence at the frozen tags;
*Cross* = cross-implementation evidence preserved by Campaign 1 or 2;
*Status* = Section 1 code (worst applicable across participants);
*Gate* = additional gate required (Section 5).

### 4.1 Relay obligations (specification §20.2)

| Obligation | Basis | Rust evidence | Motoko evidence | Cross evidence | Status | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Concurrent-ingress cursor safety, deterministic interleaving (pause before commit/visibility) | §20.2, §12.6, §13.2, §16.17 | `tests/relay_concurrency.rs` (7 tests, `GatedStore` pauses inside `commit_current` before allocation-and-commit, memory + SQLite; cancelled-writer hole test; SQLite rollback test) + `tests/relay_properties.rs` model-equivalence | None as a concurrency test. `src/followee/RelayState.mo:1-5` documents single-writer serialization; `test/property.test.mo:277` is named for cursor overtaking but its body ingests one record and repeats one identical call (see RQ-3) | None — both campaigns list "concurrency behaviour" as not exercised (`interop/campaign-2/CAMPAIGN.md` §9) | **L** (Rust) / **R** (Motoko serialization argument untested) | RN-A1 |
| Cursor-generation reset | §12.7, §20.2 | `tests/relay_core.rs::sec_12_7_generation_reset_permits_bounded_reenumeration`; `tests/relay_http.rs::sec_12_7_naturally_obtained_foreign_and_corrupted_cursors_over_http` | `test/relayserve.test.mo:297,307,325,475`; client side `test/client.test.mo:346` | Campaign 2 Gate G3, live both directions: foreign-generation cursor → exact two-field `ResetRequired`; malformed → `invalidCursor` (`interop/campaign-2/results/gates-report.json` G3) | **P** for reset-on-foreign-generation; never-issued current-generation cursors deliberately excluded (`interop/v0.9.2/coordinator/PRECLASSIFICATION.md` item 7) | RN-A2 (residual cases only) |
| Incompatible restore behaviour | §12.7, §13.5, §20.2 "restore-time behaviour" | Not found: `src/store/sqlite.rs` has no `user_version`, no schema versioning, no corrupt/foreign-DB test; `SqliteStore::open` silently adopts a persisted identity | Not found: no persistence layer exists at all (no `stable` vars, no upgrade hooks) | None | **R** (Rust); n/a for the frozen Motoko participant (Section 13, RQ-5) | RN-A2, RL-C |
| Restore-time sticky-authority / current-state behaviour | §13.5, §20.2 | Partial: `tests/relay_store_parity.rs::sec_13_1_sqlite_commits_survive_an_ungraceful_reopen`; `tests/relay_http.rs::sec_13_5_restart_preserves_identity_generation_and_sticky_state`; no restore-from-**older-snapshot** test, no refresh-marking / peer re-resolution behaviour | Not found (no restore path) | None | **R** (Rust); n/a for the frozen Motoko participant (Section 13, RQ-5) | RN-A2, RL-C |
| Bounded resource use under invalid and Sybil input; finite current-map bound | §20.2, §16.7, §11.1 ("bounded partial map") | Per-message bounds extensively tested (`tests/relay_http.rs` 413/caps, `tests/validate_cbor_api.rs` boundaries, 10 fuzz targets); **Sybil / aggregate-growth: not found**; no entry cap, per-peer quota, or admission throttle exists — the current map is effectively unbounded | Per-message bounds tested (`test/http.test.mo:127,188`; `test/relayserve.test.mo:346,381`); `RelayState.Relay.entries` is an unbounded map with no cap; no Sybil test | None | **L** (per-message) / **R** (finite map bound and behaviour under Sybil load — both participants' unbounded maps are readiness gaps for a Relay claim) | RN-A3, RL-F |
| Sticky RootRevoked, ingress, batch alignment, wrapper faults, publish-response matrix, changes field combinations, coalescing, pagination | §20.2 remainder | `tests/relay_core.rs`, `tests/relay_http.rs`, `tests/negative_b7.rs`, `tests/b11_vectors.rs`, `tests/sync_receiver.rs` | `test/relay.test.mo`, `test/relayserve.test.mo`, `test/http.test.mo`, `test/publishresponse.test.mo` | Campaign 2 Phases 1–3 and G1–G2: publish statuses 0/1-bare/1-coded/2, duplicate and malformed batches, initial/incremental/paginated/exactly-once changes, premature-retention contrast, hostile wrappers — live both directions (`interop/campaign-2/results/phase3-report.json`, 67 checks) | **P** at the tested scope | none (rerun rule of §20.4 only) |

### 4.2 Client obligations (specification §20.3)

| Obligation | Basis | Rust evidence | Motoko evidence | Cross evidence | Status | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Live multi-relay candidate selection | §20.3, §14.1 | `tests/resolution.rs` (20 tests) over `MockTransport` (no sockets); `tests/three_relay_demo.rs` runs three real relay processes but never has ≥2 relays serve competing Full winners | Not found: `src/followee/RelayClient.mo` is single-relay; no relay set, no selection loop | None — "multi-relay resolver traversal beyond the single-relay Ref/directory rejection path" not exercised (`interop/campaign-2/CAMPAIGN.md` §9) | **L** (Rust, mock) / **R** (live); outside Motoko's claimed roles (Section 13, RQ-2) | RN-B1, RT-D |
| Continuation past Absent / Error / rejected outer responses | §20.3, §14.1 | `tests/resolution.rs::sec_14_1_continues_past_absent_and_error_results_to_a_further_relay`, `sec_b11_2_rejected_outer_response_does_not_terminate_or_become_absent`, state-non-mutation twins | In-response isolation only (`test/client.test.mo:183,232`; `test/relay.test.mo:77`); no multi-relay continuation exists to test | Single-relay rejection paths only | **L** (Rust); Motoko outside RN-B scope (Section 13, RQ-2) | RN-B1 |
| Shared contacted-relay / response-byte / concurrency / hop / deadline budgets | §20.3, §14.1 | All enforced and tested **except concurrency**: `ResolverBudgets.max_concurrent_requests` is declared and defaulted (src/resolver.rs:48,65) but never read; scheduler is sequential by design (see RQ-4). Others: `tests/resolution.rs`, `tests/migration_states.rs`, `tests/relay_client.rs::sec_14_1_budgets_are_charged_and_exhaust_without_reset`, `tests/webfinger_client.rs::sec_14_1_lookups_charge_the_shared_budget` | Response-byte budget only (`test/client.test.mo:160`); contacted-relay, concurrency, hop, deadline budgets not found | None | **L** (Rust, minus concurrency); Motoko outside RN-B scope (Section 13, RQ-2) | RN-B2 |
| Cycle detection across relay references and migration traversal | §20.3, §14.1 | `tests/resolution.rs::sec_14_1_reference_cycles_are_rejected_and_terminate`; migration counterpart dedup + self-guard in `src/resolver.rs::check_migration`; no multi-hop migration-cycle test (bounded by `max_migration_hops = 2`) | Not found (no traversal code) | None; "cycle" appears only in specification prose within campaign material | **L** (Rust); Motoko outside RN-B scope (Section 13, RQ-2) | RN-B3 |
| WebFinger mapping, redirects, exact matching, inverse verification, caching, hostile responses | §10, §20.3 | Comprehensive: `tests/webfinger_client.rs` (27 tests), `tests/handle_verification.rs` (7), `tests/handle_bootstrap.rs` (12), `tests/handle_authority.rs` (14, incl. real sockets); caching/TTL (§10.4): no cache exists — conforming (Section 13, RQ-6) | Not found in full — no WebFinger code of any kind | None — "WebFinger handles" not exercised in either campaign | **L** (Rust); Motoko outside RN-B scope (Section 13, RQ-2) | RN-B4, RT-E |
| Migration verification and presentation, incl. stale-reciprocation "Checked but unverified" | §14.2–14.4, §20.3 | `tests/migration_states.rs` (12 tests, incl. `sec_14_2_stale_counterpart_is_checked_but_unverified_even_when_reciprocal`), CLI presentation tests | Structural record validation only (`src/followee/Body.mo`); §14.2–14.4 state machine not found | Value-level `identityRef` comparison only (`interop/campaign-2/results/phase2-report.json`) | **L** (Rust); Motoko outside RN-B scope (Section 13, RQ-2) | RN-B5 |
| Positional isolation, independent premature classification, withheld/stale records | §20.3 | `tests/resolution.rs`, `tests/relay_client.rs` | `test/client.test.mo:183` (positional isolation) | Campaign 2 Phase 3 + Gate G1 both directions (premature contrast without importing diagnosis) | **P** at tested scope | none |

### 4.3 Lifecycle and persistence

| Obligation | Basis | Rust evidence | Motoko evidence | Cross evidence | Status | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Clean start / graceful restart | §13.5 (implied), robustness | `tests/relay_serve_shell.rs` (real binary, SIGTERM exit 0, restart persistence); `tests/cli_handle_shell.rs` | Not found — per-process in-memory state only; loopback node teardown is end-of-scenario kill | None | **L** (Rust); Motoko n/a under the Section 13 role decision | RL-C |
| Abrupt termination / crash recovery | robustness; §13.1 atomicity | Drop-without-close reopen only (`tests/relay_store_parity.rs::sec_13_1_sqlite_commits_survive_an_ungraceful_reopen`); WAL + `synchronous=FULL` configured; no SIGKILL / torn-WAL / mid-commit kill test | Not found | None | **R**/**H** | RL-C |
| Crash points around publication / current-map commitment and visibility | §12.6, §13.2 | `tests/relay_concurrency.rs` cancelled-writer and SQLite-rollback tests (in-process fault injection); no process-kill at the commit point | Not found | None | **L** (Rust) / **R** | RL-C |
| Compatible restore | §13.5 | `tests/relay_http.rs::sec_13_5_restart_preserves_identity_generation_and_sticky_state`; `tests/sync_receiver.rs::sec_13_5_sqlite_peer_state_survives_restart` | Not found | None | **L** / **R** | RL-C |
| Incompatible restore + cursor-generation reset on restore + refresh marking | §13.5, §12.7 | Not found (no schema version, no older-snapshot test) | Not found | None | **R** | RL-C |
| Upgrade behaviour (schema/data migration; canister upgrade for Motoko) | robustness | Not found (`user_version` absent) | Not found (no `stable`/`preupgrade`/`postupgrade`; IC deployment "not begun" per README) | None | **R**/**H** | RL-C |
| Preservation or intentional reset of current state, sticky RootRevoked, directory generation, update numbers, cursors across each lifecycle event | §11.1, §12.7, §13.5 | Partial per rows above | Not found | None | **R** | RL-C |

Applicability note for this subsection: per the Section 13 decisions
(RQ-2, RQ-5), normative restore behaviour is conditional on offering a
restore/persistence mechanism. The frozen Motoko participant offers
none, records these rows as **not applicable**, and consequently can
make no persistent-deployment or corresponding operational-readiness
claim; Motoko persistence and any ICP apex-canister deployment are
future integration work under a descendant claim, not properties of
the frozen participant. RL-C binds every participant and deployment
profile for which persistence or deployment durability **is** claimed.

### 4.4 Topology, network, load

| Obligation | Basis | Rust evidence | Motoko evidence | Cross evidence | Status | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Mixed ≥3-relay topology, both implementations, Full/Ref tiers, traversal, loops, duplicates, unavailability, staleness, hostility, partitions | §11, §14.1, robustness | `demo/three_relay_demo.sh` — three real Rust relays, Ref hop, lazy compression, restart (single implementation) | Not found | None — campaigns are single-relay per direction | **R** (mixed) | RT-D |
| Public network: real HTTPS, DNS, WebFinger, certificates, redirects, non-loopback | §10.2, §12.1, §16.6 | Handle authority deployed publicly once (`demo/public-authority/README.md`, Railway probe 2026-08-13, real HTTPS) — WebFinger serving only; **zero `https://` occurrences in `tests/*.rs`**; no TLS client test, no certificate-failure test; relay never publicly deployed | Not found; loopback plain HTTP via semantic-free shim only | None — "public (non-loopback) deployment" not exercised in either campaign | **R** (normative HTTPS/WebFinger paths) / **H** (deployment practice) | RT-E |
| Latency, timeouts, disconnects, partial reads, malformed/truncated bodies, reconnection, bounded retries | §16.7, robustness | Timeouts tested (`tests/relay_client.rs::sec_14_1_transport_timeout_is_reported_distinctly`); malformed bodies via mock; partial reads / mid-body resets / retries: not found (retries deliberately absent by design) | Tamper hooks over real loopback sockets (`shim/scenario.js:168-199`); timeouts/partial reads not found | None | **R**/**H** | RT-E |
| Controlled clock offsets at and around normative time boundaries | §5.4, §16.8 | Exact boundary tests with injected clocks; backwards-correction test (`tests/relay_core.rs::sec_13_3_retained_premature_tuple…`); no live cross-participant offset | Boundary tests (`test/verify.test.mo:175`, `test/select.test.mo:161,174`); no live offset | Campaign 2 Gate G1: fixed offset clocks live in both directions (`clockshim`, `nowMs`) | **P** (fixed points) / **R** (offset sweeps around boundaries, live) | RT-E |
| Sustained valid workloads; invalid-CBOR/signature, oversized, deeply nested, high-cardinality, reference-loop, cursor, Sybil workloads; resource ceilings; rate limiting; backpressure; overload recovery | §16.7 (bounds), otherwise **H** | Not found. `rateLimited` exists only as wire-code symbol (`src/error.rs:111`); no rate limiter, connection cap, queue bound, load test | Not found. Same: `#rateLimited` enum only (`src/followee/Errors.mo:19`) | None | **R** (bounds before expensive work: §16.7 MUST) / **H** (SLO-style thresholds) | RL-F |

### 4.5 Artifacts, security, registration

| Obligation | Basis | Rust evidence | Motoko evidence | Cross evidence | Status | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Deterministic participant outputs | §20.4 | `interop/v0.9.2/outputs/` + MANIFEST, regenerated `diff -r`-identical; generator refuses on aggregate mismatch | `outputs/v0.9.2-r2/` five byte-identical runs (`DETERMINISM.md`), predeclaration gate | Campaign 2 archive rebuilt twice byte-identical (aggregate `25095eff…`) | **P** | none |
| Reproducible deployable binary/Wasm, two separately created clean environments | supply-chain hardening | Instructions only (digest-pinned `rust:1.97.1-slim-bookworm`, `--locked`); **no executed two-environment reproduction, no recorded binary digest**; the "release record" referenced at `interop/v0.9.2/README.md:167` does not exist as a file (RQ-1) | Not found; wasm gitignored, one historical hash in `docs/AUTHORING-RECORD.md:96`, no rebuild-and-compare | None | **R** (for any reproducible-artifact claim) / **H** | RA-G |
| Dependency/toolchain pins | supply-chain | `rust-toolchain.toml` 1.97.1, committed `Cargo.lock`, `--locked` in CI; CI actions pinned by major tag not SHA; fuzz job floating nightly | `mops.toml` moc 1.14.0; `mops.lock` per-file SHA-256 of both deps; no CI at all | Campaign meta records toolchains | **L** | RA-G |
| SBOM / dependency inventory | supply-chain | Not found (no SBOM, no cargo-vet) — `cargo audit` + `cargo deny` run in CI | `mops.lock` is a complete hash inventory; no vulnerability scanning | None | **R** (for release claims) / **H** | RA-G, RS-H |
| Parser fuzz / property / mutation evidence | §16.15, robustness | 10 cargo-fuzz targets (45 s CI smoke each), 3 proptest properties, cargo-mutants at milestone gates with committed outputs (`mutants.*`, `tests/MUTATION-REVIEW.md`); no dedicated COSE fuzz target; no long fuzz campaign | Fixed-seed LCG property tests (8, `test/property.test.mo`); no external fuzzer; no mutation testing | None | **L** | RS-H |
| Threat-model review against §16–17 | release practice | Not recorded as a distinct review artifact | Not recorded | None | **R** (for release claims) | RS-H |
| Secret / machine-path hygiene | release practice | Keyfile tests (`tests/cli.rs` no-seed-leakage); campaign archives redact machine paths | Provenance audit (`scripts/provenance-audit.sh`, 74 files, withheld-value sweep) | Archive hygiene scans in both campaigns | **P** (at archive scope) / **L** (repo-wide sweep pre-release) | RS-H |
| §21 registration items 1–7 (`flw` registry check, stable release URL, DID Extensions submission, JSON-LD context at w3id.org, WebFinger rel redirects, published CDDL+vectors, extension process) | §21 | None (rel URIs are "proposed" in spec §10.2) | None | None | **G** | Section 12 claim 4 only |
| Conformance-harness reuse at v0.9.2 | §20.4 rerun rule | — | — | `followee-conformance` + clean-room frozen at v0.8.1 with hard pin refusal; Sections 3–8 and Appendix B byte-identical to v0.9.2 except one B.9 prose hunk, so vector **bytes** carry over; all 210 manifests and `harness/pins.py` pin v0.8.1 and would need a metadata re-pin pass; neither harness implementation has any relay/HTTP surface | **X** for this milestone (see RQ-9) | optional side-track |

## 5. Gates

Each gate lists predeclared acceptance criteria. A gate passes only if
every criterion holds and the Section 8 archive rules were followed.
Criteria marked (M) are maintainer-judgment thresholds that MUST be
fixed in writing before the gate executes (Section 14).

### Gate RN-A — remaining normative relay tests (track 1)

**RN-A1 Concurrent-ingress cursor safety, cross-checked.**
- Rust: the existing `tests/relay_concurrency.rs` suite is accepted as
  the deterministic interleaving evidence for the §20.2 shape (pause
  point before commit/visibility; both backends) and is re-run at the
  RC commit.
- Motoko: either (a) a test demonstrating the single-writer
  serialization argument mechanically — a deterministic interleaving in
  the participant's execution model showing B and a `changes` request
  cannot observe a position that overtakes paused A, or (b) a written,
  reviewed serialization proof note committed with a test that pins the
  single-writer property it relies on. The mislabeled
  `test/property.test.mo:277` MUST be corrected (descendant commit,
  RQ-3) so no test name overstates coverage.
- Cross: the neutral coordinator drives an interleaved
  publish/publish/changes schedule against each serving implementation
  where its execution model permits external interleaving, and records
  the §12.6 invariant check (no successful `nextCursor` overtakes a
  later-visible entry).
- Accept: all schedules pass; any cursor overtaking is a Class-1 stop
  (Section 9).

**RN-A2 Cursor-generation reset and restore-time behaviour.**

Two distinct restore cases, never conflated:

- **Compatible older-snapshot restore** — restore each persistent
  relay from an older, format-compatible snapshot; accept only if
  cursor generation is reset (§13.5 MUST), the snapshot's current
  state and sticky RootRevoked authority are retained, an initial
  null-cursor scan enumerates every retained current entry
  (§12.7 MUST), and restored Root/Unknown entries are marked or
  handled per the participant's documented §13.5 refresh SHOULD
  posture (posture recorded, not invented).
- **Incompatible-schema, foreign, or corrupt store** — opening such a
  store MUST either fail closed or perform an explicitly tested
  migration/reset; it MUST never silently serve misinterpreted state.
  The chosen posture is predeclared per participant; either posture is
  acceptable when tested.
- Applicability: per the Section 13 decision (RQ-5), the normative
  restore behaviour binds implementations that offer a
  restore/persistence mechanism. An implementation without
  persistence records the case as not applicable, and thereby forgoes
  any persistent-deployment claim.
- Accept: predeclared expected outcomes match exactly; sticky-state
  loss is Class-1.

**RN-A3 Bounded resource use under invalid and Sybil input.**
- Predeclared workloads (sizes fixed in writing before the run, per
  Section 14): invalid-CBOR floods, invalid-signature floods,
  oversized and deeply nested inputs, high-cardinality maps, N
  distinct Sybil identities publishing valid records, cursor floods.
- A **finite, enforceable current-map bound** — configured or
  structural — is mandatory for any Relay conformance claim: §11.1
  defines the Relay state as a *bounded* partial map and §16.7
  requires resource limits. The exact numerical capacity and the
  admission/quota/eviction/sponsorship/payment policy are local
  operator choices (§11.1), and may differ per participant, but *some*
  finite bound must exist and be demonstrated. Both participants'
  currently unbounded maps are readiness gaps unless another existing
  mechanism actually bounds them.
- Reaching capacity MUST produce a documented bounded local-policy
  outcome — rejection, eviction (respecting the §11.3 retention
  preference for sticky RootRevoked state), sponsorship/payment
  gating, or equivalent. Silent unbounded growth cannot pass this
  gate. The `rateLimited` wire response specifically remains optional:
  it is required only where an implementation chooses that response as
  its capacity behaviour.
- Accept: memory/storage/socket growth stays within the predeclared
  envelope; the configured bound is actually enforced at capacity; no
  crash; no state corruption (post-run full-scan equals pre-run state
  plus admitted records); rejects happen before expensive work where
  §16.7 requires it.

### Gate RN-B — remaining normative client tests (track 1)

Scope note: per the Section 13 role decision (RQ-2), RN-B binds only
implementations claiming DID Resolver / Followee-client conformance —
under the current provisional claim scope, the Rust participant.
Motoko's low-level single-relay HTTP client is not a complete
§14/§20.3 DID Resolver and enters RN-B only under a future descendant
claim (a future Motoko, browser, or ICP application resolver would
enter here). Criteria below apply to every claiming participant.

**RN-B1 Live multi-relay candidate selection and continuation.**
- At least three live socket-bound relays; at least two serve
  competing Full candidates for the same DID; expected §8.3 winner
  predeclared. Continuation past Absent, per-DID Error, and rejected
  outer responses to a further selected relay, with budget accounting
  observed and no cached/sticky state mutation.
- Accept: winner exact; continuation happens iff budgets permit;
  rejected outer response is never interpreted as Absent.

**RN-B2 Shared budgets.**
- Contacted-relay, response-byte, concurrency, hop (reference and
  migration), and deadline budgets each driven to exact exhaustion in
  one shared operation crossing relay and migration hops; no budget
  resets on any hop (§14.1 MUST).
- Rust concurrency budget: per the Section 13 decision (RQ-4), a
  sequential scheduler with effective concurrency one conforms to a
  maximum-concurrency budget of at least one — sequential execution
  is not a normative violation. The unused configurable
  `max_concurrent_requests = 4` is nevertheless misleading
  behaviour/API debt: before the Rust DID Resolver RC, either enforce
  the configured field or replace it with the documented effective
  posture, in both cases with a pinning test.
- Accept: exhaustion at the exact boundary, one-under passes,
  one-over stops.

**RN-B3 Cycle detection.**
- Relay-reference cycles across ≥3 relays (A→B→C→A), duplicate relay
  identities under distinct base URIs, duplicate base URIs, and an
  **operation-local migration cycle**: within one resolution
  operation, a migration traversal of shape A→B→A (or A→B→C→A where
  the migration-hop budget permits), subject to the v1 default limit
  of 2 migration hops. The predeclaration states which cycle shape is
  reachable under that limit, the expected §14.2 state recorded at
  the cutoff, and the exact budget charges.
- Accept: termination within budgets, each newly contacted base URI
  charged (§14.1), no infinite traversal, no budget reset.

**RN-B4 WebFinger.**
- Exact resource matching, redirect policy (HTTPS-only, bounded,
  §10.2), inverse verification, and hostile responses (malformed JRD,
  duplicate members, oversized, wrong media type, wrong subject,
  multi-link ambiguity) — against a coordinator-controlled hostile
  WebFinger fixture server, then live under RT-E.
- Caching boundaries per the Section 13 decision (RQ-6): §10.4
  constrains caching *when caching occurs*; the current no-cache
  posture is trivially bounded, conforming, and is recorded as such.
  If a cache is later introduced, exact TTL-expiry and cache-keying
  tests become mandatory before that descendant's RC.
- Accept: every hostile case rejected without state mutation; mapping
  only on the §10.2 five-condition success.

**RN-B5 Migration verification and presentation.**
- The three §14.2 states driven end-to-end over live relays, including
  the stale-reciprocation Checked-but-unverified case (§20.3) and
  predecessor-impersonation suppression (§14.3).
- Accept: exact state classification per predeclared table; no
  automatic following-list migration.

### Gate RL-C — lifecycle and persistence (track 2)

- Applies to every participant and deployment profile claiming
  persistence or deployment durability (Section 13, RQ-2/RQ-5); the
  frozen Motoko participant records this gate as not applicable, and a
  future Motoko canister deployment (`preupgrade`/`postupgrade` with
  stable state) enters under its own descendant claim.
- Matrix per claiming participant: clean start, graceful restart
  (SIGTERM), abrupt termination (SIGKILL at predeclared crash points,
  including between publish acceptance and response, and around
  current-map commitment and visibility), recovery, compatible
  older-snapshot restore and incompatible/foreign/corrupt-store
  handling (both per the RN-A2 split), and upgrade (schema-versioned
  open of a prior-version store).
- For each event, predeclare and verify the fate of: current entries,
  sticky RootRevoked knowledge, directory generation, update numbers,
  cursor generation, peer cursors.
- Accept — three distinct requirements, not to be conflated:
  1. **Normative durability**: an acknowledged, newly observed
     RootRevoked transition survives every crash point — §13.1 step 5
     requires it to be persisted before admission is acknowledged.
     Sticky state never regresses. Violation is Class-1.
  2. **Normative cursor/atomicity invariants**: the §12.6/§13.2
     visibility and atomic-commit rules hold across every lifecycle
     event; visibility never runs ahead of durability at any crash
     point. Violation is Class-1.
  3. **Operational durability (this plan's requirement, beyond the
     specification)**: every acknowledged admission — not only
     RootRevoked transitions — survives crash-recovery. §13.1 does
     not itself require this for ordinary Root admissions; it is an
     operational-readiness requirement of this gate, and a violation
     is Class-3 unless it also breaks requirement 1 or 2.

### Gate RT-D — mixed multi-relay topology (track 2/3 bridge)

- Topology fixed in writing before execution: at least three relays,
  both implementations in mixed serving roles, plus at least one
  client of each claiming implementation. The predeclaration MUST
  name: which relays hold Full vs Ref tiers per DID, the directory
  contents, the intended reference chains and the loop, the duplicate
  relay-identity and duplicate base-URI placements, which relay is
  unavailable, which serves stale state, which serves hostile
  material, and the expected end-state of every relay's current map
  and every client's resolution result.
- Runs: directory traversal, lazy path compression where implemented
  (§11.5 is MAY — absence is recorded, not failed), partial
  responses, convergence after a partition (relay isolated then
  rejoined) and after a mid-campaign restart of one relay.
- Convergence mechanism: §13.4 leaves pull policy and synchronization
  frequency to operators, so this gate does not require autonomous
  convergence from an implementation that does not claim automatic
  polling. The predeclaration states, per relay, whether convergence
  is driven by participant-native polling, explicit client-initiated
  pulls, or coordinator-triggered protocol operations, and the gate
  tests exactly the declared mechanism without presenting local pull
  policy as normative.
- Accept: every predeclared end-state matches; disagreements are
  classified under Section 9 before any fix.

### Gate RT-E — public-network test deployment (track 3)

- Real HTTPS with valid certificates, real DNS names, real WebFinger
  endpoints on disposable test domains; test identities only; no
  production handles or identities. Non-loopback addressing
  throughout; at least two machines so no evidence depends on one
  developer machine or unpublished local state.
- Certificate validation: expired, self-signed, and
  hostname-mismatched endpoints MUST fail closed. WebFinger redirect
  policy per §10.2 (HTTPS-only, client security policy) exercised
  against a live redirecting server; relay-endpoint redirect handling
  is exercised as operational hardening, with redirect targets charged
  as contacted base URIs per §14.1.
- Fault program (predeclared): induced latency, timeouts, mid-body
  disconnects, truncated and malformed bodies, reconnection, bounded
  retries (or the documented no-retry posture), all against
  production transports.
- Clock offsets: participant clocks stepped to the exact §5.4
  boundary, one-under, one-over, and a backwards correction, live.
- Accept: every fault yields a classified transport or protocol
  failure, never wrong protocol state; budgets and deadlines hold
  under latency.
- **This gate does not discharge any specification §21 registration item**,
  including the WebFinger relation-URI redirects; disposable-domain
  evidence is not registration evidence.

### Gate RL-F — load, resource, and abuse (track 2)

- Calibration before thresholds (Section 13, RQ-7 disposition):
  explicitly labelled **exploratory calibration runs** are permitted
  first; they produce no gate evidence and appear in no acceptance
  claim. After calibration, the RL-F predeclaration is committed with
  fixed workload sizes, durations, concurrency levels, measurement
  method (RSS, CPU, storage bytes, fd/socket counts, response sizes,
  queue depths, cursor/update-number growth), thresholds, and failure
  criteria; only then does the evidentiary run execute. This plan
  deliberately sets no production SLOs; the exact numbers remain the
  open decision of Section 14, fixed empirically through calibration
  rather than invented here.
- Workloads: sustained valid publish/resolve/directory/changes;
  invalid-CBOR, invalid-signature, oversized, deeply nested,
  high-cardinality, reference-loop, cursor, and Sybil floods; overload
  then recovery.
- Capacity behaviour: consistent with RN-A3, each Relay participant
  must demonstrate its finite bound under sustained load — reaching
  capacity produces the documented bounded outcome (rejection,
  eviction, or other bounded local policy), never silent unbounded
  growth. The `rateLimited` response and any backpressure signal
  remain optional mechanisms: they are tested exactly where a
  participant's documented posture chooses them.
- Accept: bounded growth per the predeclared envelope; the documented
  capacity posture holds at and beyond the bound; after overload,
  full state scan shows zero corruption and cursor invariants intact.

### Gate RA-G — reproducible and inspectable artifacts (track 4)

Both implementations, not only Rust.

- Distinguish and separately evidence: (a) deterministic participant
  outputs — already proven (Section 4.5); (b) reproducible deployable
  artifacts — every binary or Wasm artifact that a release actually
  distributes or advertises as reproducible, whichever participant
  produces it.
- Requirements for any reproducible-artifact claim: clean-environment
  source build from the RC tag; toolchain and dependency pins recorded
  (`rust-toolchain.toml` + `Cargo.lock`; `mops.toml` + `mops.lock`);
  **two separately created clean environments** (different machines or
  independently created containers from digest-pinned images) yielding
  byte-identical artifacts; artifact SHA-256 recorded with full
  provenance (source tag, toolchain, image digest, command line);
  SBOM or dependency inventory emitted per artifact (`cargo` metadata
  or CycloneDX for Rust; `mops.lock`-derived inventory for Motoko).
- The missing Rust "release record" (RQ-1) is produced here, on a
  descendant commit — the frozen tag is not amended.
- Accept: digests match across the two environments; any mismatch is
  Class-3 until root-caused.

### Gate RS-H — security and release review (track 5)

- Dependency and supply-chain: `cargo audit` + `cargo deny` clean at
  the RC commit; advisory triage recorded; CI action SHA-pinning and
  tool-version pinning reviewed (currently major-tag/floating);
  Motoko dependency hashes re-verified against `mops.lock`.
- Threat-model review: a written walk of §16.1–16.17 and §17 against
  both implementations, each subsection marked
  mitigated-with-citation / accepted-risk / gap.
- Parser evidence: a long fuzz campaign (duration M, predeclared) on
  the 10 existing targets plus a dedicated COSE-envelope target
  (closing the `IMPLEMENTATION.md` §11.5 gap); mutation-testing pass
  at the RC commit for Rust; for Motoko, the seeded property suite
  extended or an equivalence argument recorded (M).
- Secret and machine-path hygiene: repo-wide sweep of both
  participants and all readiness archives (no credentials, no
  non-redacted machine paths, no private keys outside test fixtures).
- Deployment configuration review: TLS termination, listener policy
  (`NetworkPolicy` postures), container/base-image digests, systemd/
  Caddy/nginx examples in `demo/public-authority/`.
- **Residual-risk and untested-scope report**: an explicit document
  listing everything still untested (at minimum: any Section 4 row not
  raised to P, plus fuzz coverage limits, single-maintainer review
  risk, and the RQ list), published alongside the RC.
- Accept: every checklist item has a written disposition; no claim of
  "production ready", "production standardized", or equivalent
  wording appears anywhere in the release material until Section 12
  claim 4's requirements are met, which this gate alone cannot
  satisfy.

## 6. Predeclaration discipline

For every gate: expected outcomes, workload numbers, topologies, and
clock values are committed in writing (a `PREDECLARATION.md` under the
campaign directory) **before** the first evidentiary execution,
following the Campaign 2 pattern (`interop/v0.9.2/ACCEPTANCE.md`
gates, `followee-motoko/outputs/v0.9.2-r2/PREDECLARATION.md`).
Evidence produced without a prior predeclaration is void for that
gate. Explicitly labelled exploratory calibration runs (RL-F) are
permitted before the predeclaration is committed; they produce no
gate evidence and are never cited in an acceptance claim.

## 7. Required raw outputs

Preservation is tiered so that evidential completeness does not demand
archiving millions of load-test exchanges.

**Complete raw bytes** — for every control case, boundary case,
failure, and hostile fixture exchange: full raw request/response bytes
(hex or NDJSON framing, as in
`interop/campaign-2/results/phase1-requests.jsonl`), with per-check
reports placing the exact predeclared expectation next to the observed
value.

**Bulk and load traffic** (RL-F sustained workloads and comparable
high-volume phases) — instead of complete bytes, preserve: the
generator version and configuration, all seeds, corpus/input hashes,
aggregate counters and digests per workload, bounded trace samples at
a predeclared sampling rate, **every unexpected response in full**,
and enough recorded information for deterministic reproduction of the
workload.

**Always** —

- participant logs at a predeclared verbosity;
- for lifecycle/load gates: resource measurement series and the
  post-run state-scan output;
- for RT-E: DNS names used, certificate chains observed, and the
  fault-injection schedule as executed;
- for RA-G: full build transcripts and environment manifests from both
  clean environments;
- pins of every repository, tag, seal, and toolchain consumed.

Credentials and secret material are never archived, in any tier.

## 8. Deterministic archive rules

Following the Campaign 2 recipe (`interop/campaign-2/orchestrate/make_archive.py`):

- one `results/` directory per readiness campaign with a
  `MANIFEST.json` recording per-file SHA-256, byte sizes, and the
  aggregate SHA-256 over the sorted `"{sha256}  ./{name}\n"` lines;
- machine-local paths redacted to `~`-relative form; no usernames or
  credentials anywhere;
- wall-clock timestamps are excluded from deterministic artifacts, but
  operational evidence naturally contains nondeterministic times —
  TLS certificate validity windows, live logs, latency and resource
  measurements. Each such field MUST be either declared in the
  campaign's `NONDETERMINISM.md`, normalized where normalization
  preserves the evidence, or retained as measured evidence with its
  permitted variability documented; a timestamp that is itself the
  measured value is predeclared as such;
- deterministic phases MUST rebuild byte-identically; live phases with
  relay-chosen opaque values MUST document exactly which fields are
  permitted to differ (the `NONDETERMINISM.md` pattern);
- the archive is committed with its campaign record and never
  modified afterward; corrections go in a successor file.

## 9. Failure classification and stop conditions

Every disagreement or unexpected outcome is classified before any fix:

| Class | Definition | Consequence |
| --- | --- | --- |
| 1 | Normative violation: sticky-state regression, cursor overtaking, wrong-state service after crash/restore, verification bypass, budget reset | **Stop the campaign.** Root-cause; fix on a descendant participant commit; re-freeze; the affected gate restarts from its predeclaration |
| 2 | Divergence between implementations under a determined expectation | Stop the affected gate; classify against the specification; if the spec is ambiguous, record a review question (Section 13) — never decide silently |
| 3 | Robustness defect without normative violation (leak, unbounded growth within a passing run, reproducibility mismatch) | Continue other gates; the affected gate cannot pass until resolved or explicitly accepted as residual risk in RS-H |
| 4 | Permitted variation (documented diagnostic choice, opaque values, operator policy) | Record; no action; MUST remain visible in the report (§20.4) |
| 5 | Harness/fixture defect | Fix the harness; the affected run is void and repeats; participant state untouched |

Exposure/void rule — deliberately narrower than Campaign 2's:
readiness is not a new independent-authoring experiment. The Campaign
2 rule ("a comparison performed against a participant session that saw
coordinator material before its freeze is void") applies **only** to
any future blind comparison or independent-convergence claim.
Descendant implementations MAY be developed with full knowledge of the
public readiness expectations; their evidence remains valid for
conformance and operational-readiness claims provided expectations
were predeclared before the evidentiary run, production outputs are
demonstrably input-sensitive, and every comparator carries tamper
tests. Such evidence simply can never become new
independent-convergence evidence.

## 10. Historical tags and descendant release candidates

- Existing tags are immutable and are never retargeted:
  `v0.9.1-interop-bundle-reviewed`, `v0.9.1-interop-campaign-1`,
  `v0.9.2-reviewed`, `v0.9.2-interop-bundle-reviewed`,
  `v0.9.2-interop-campaign-2`, all `followee-rs` milestone tags,
  `rust-v0.9.2-maintained-freeze`, all `followee-motoko` freeze tags,
  and every conformance/clean-room tag.
- Any participant change required by a readiness gate (e.g. RQ-3,
  RQ-4, the COSE fuzz target, schema versioning) is made on a
  **descendant commit** of the participant's current freeze, then
  frozen under a new annotated tag before re-entering a live gate.
  Proposed names: `rust-v0.9.2-rc1`, `motoko-v0.9.2-rc1`
  (incrementing per re-freeze).
- Historical evidence referencing the old freeze remains valid at its
  recorded scope; new gates cite the new tag. A gate that already
  passed against an older freeze does not need re-execution unless the
  change touches its tested surface — the §20.4 rerun rule applies to
  normative CBOR-classification, relay-wrapper, or cursor-visibility
  changes.
- Readiness campaign records live under `readiness/campaign-1/`,
  `readiness/campaign-2/`, … in this repository — a top-level
  `readiness/` tree rather than `interop/`, because these campaigns
  include lifecycle, load, deployment, artifact, and security work
  that is not merely interoperability. Each completed campaign is
  preserved with an annotated tag `v0.9.2-readiness-<n>` on the
  commit that adds its archive.

## 11. Trust boundary

Readiness gates are engineered openly: participants, coordinator
material, and gate expectations are mutually visible, and descendant
participant work may consult the public readiness expectations freely.
The evidential safeguards are the ones that do not depend on
blindness — predeclaration before every evidentiary run (Section 6),
input-sensitivity demonstrations for production outputs, tamper tests
on every comparator, and pin verification in every script run. The
strict Campaign 2 blindness/void discipline is reserved for any future
blind comparison or independent-convergence claim (Section 9); no
readiness gate makes such a claim.

## 12. Release decision matrix

Four distinct claims. Each requires all listed gates **plus** every
lower claim's requirements. No gate combination implies a higher claim.

| # | Claim | Requirements | Current status |
| --- | --- | --- | --- |
| 1 | **Source milestone** — specification v0.9.2 with preserved Campaign 1 independent-convergence evidence and Campaign 2 maintained interoperability evidence at documented scope | Already defined by existing tags and archives | **Met** (tags `v0.9.2-reviewed`, `v0.9.2-interop-bundle-reviewed`, `v0.9.2-interop-campaign-2`) |
| 2 | **GitHub pre-release / release candidate** (project publication, distinct from participant artifacts) | The RC names exactly which participant roles and artifacts it includes. Every included participant passes the RN gates applicable to its claimed roles (Section 13, RQ-2). RA-G is mandatory for every binary/Wasm artifact the RC actually distributes or advertises as reproducible; a source-only RC explicitly states that no reproducible-binary claim is made. RS-H dependency + hygiene items and a published residual-risk report are mandatory. RC tags per Section 10 | Not met — formal GitHub release-candidate publication stays **deferred** until these gates pass |
| 3 | **Operationally tested implementation** (per implementation, per deployment profile, per claimed role) | Claim 2 plus RL-C, RT-D, RT-E, RL-F for that implementation in that deployment profile and its claimed roles | Not met |
| 4 | **Production interoperability / public-launch claim** | Claim 3 for at least two implementations covering the advertised roles; the complete §21 publication/registration program (registry check, stable release URL, DID Extensions submission, JSON-LD context, WebFinger rel redirects, published CDDL and vectors, extension process); and a qualified **independent external security review** of the specification's §16–17 surface and of every implementation included in the claim (Section 13, RQ-8). Registry publication is discovery metadata (§21) — it does not itself make Followee a formal standard, and no release material may imply that it does | Not met; `did:flw` and the proposed Followee relation URIs are not registered |

## 13. Maintainer decisions for this milestone

The audit's review questions were dispositioned in review. Decisions
below are taken for this milestone; identifiers are kept for
traceability with the gate text.

- **RQ-1 — resolved.** `followee-rs/interop/v0.9.2/README.md:167`
  refers to a "release record at freeze" (binary SHA-256, audit/deny
  evidence) that does not exist as a file. Retained as a historical
  Rust documentation defect: the record is to be corrected and
  supplied on an RA-G descendant commit; the freeze is never
  rewritten.
- **RQ-2 — resolved provisionally from current evidence.** Neither
  participant repository declares roles in the specification's formal
  vocabulary, so the following is **this plan's proposed claim
  scope**, phrased from each repository's own documentation. Rust
  claims the Record Verifier, DID Resolver/client, Relay, and Ingress
  Relay surfaces its repository documents (README "Repository role":
  core rules, CLI authoring/resolving, bounded SQLite-backed
  HTTP/CBOR relay, synchronization, reference traversal, WebFinger
  discovery and inverse verification). Motoko currently claims Record
  Verifier plus its implemented single-relay Relay/Ingress serving
  surfaces and a low-level single-relay HTTP client (README scope:
  Sections 3–8, relay wire/state semantics, the five-operation HTTP
  surface and client); that low-level client is **not** a complete
  §14/§20.3 DID Resolver. RN-B applies only to implementations
  claiming DID Resolver/Followee-client conformance. A future Motoko,
  browser, or ICP application resolver may enter RN-B under a
  descendant claim. Motoko persistence/ICP apex-canister deployment
  is future integration work, not a property of the frozen
  participant.
- **RQ-3 — resolved.** The overstated Motoko test name at
  `test/property.test.mo:277` is corrected on the first readiness
  descendant, and real cursor-safety evidence is added before RN-A1
  accepts the Motoko side. The name must not stand as cursor-safety
  evidence.
- **RQ-4 — resolved.** A sequential scheduler with effective
  concurrency one conforms to a maximum-concurrency budget of at
  least one; sequential execution is not a normative violation. The
  unused configurable `max_concurrent_requests = 4` is
  behaviour/API debt: before the Rust DID Resolver RC, either enforce
  the configured field or replace it with the documented effective
  posture, with a pinning test (RN-B2).
- **RQ-5 — resolved.** Normative restore behaviour is conditional
  upon offering a restore mechanism. An implementation without
  persistence records the normative case as not applicable, but
  cannot make a persistent-deployment or corresponding
  operational-readiness claim. RL-C applies whenever
  persistence/deployment durability is claimed.
- **RQ-6 — resolved.** §10.4's "cache the result only for a bounded,
  domain-policy TTL" constrains caching when caching occurs. No cache
  is trivially bounded and is conforming. If a cache is later added,
  exact TTL-expiry and cache-keying tests become mandatory. RN-B4
  still tests mapping, redirects, inverse verification, and hostile
  responses.
- **RQ-8 — resolved.** A qualified independent external security
  review of the specification's §16–17 surface and of every
  implementation included in the production claim **blocks claim 4
  only**. Claims 1–3 can be proven internally.
- **RQ-9 — resolved.** Both v0.8.1 repositories
  (`followee-conformance`, `followee-python-cleanroom`) stay frozen
  as historical evidence for now. A v0.9.2 metadata re-pin is an
  optional, separately reviewed maintenance descendant and is **not**
  credited for relay/client coverage.
- **RQ-10 — resolved: yes.** During readiness preparation, add to
  `followee` CI the self-contained v0.9.2 bundle verifier, its 52
  bundle tests, and archive/manifest integrity checks (read-only; no
  frozen evidence regenerated). Participant clones are not required
  in ordinary protocol-repository CI unless a deterministic pinned
  mechanism is designed for them.
- **RQ-11 — resolved.** The frozen clean-room is left untouched; its
  repository-root `Followee-Specification.md` (v0.7 draft, while the
  approved v0.8/v0.8.1 inputs live under `inputs/`) is recorded as
  potentially misleading historical documentation debt, to be
  clarified only in a future descendant if that repository is
  maintained again.

## 14. Open decisions

Genuinely unresolved matters only:

- **RQ-7 — open (numbers only).** The exact RL-F numeric thresholds
  (workload sizes, durations, growth envelopes, overload-recovery
  bounds) remain open. Process is decided: explicitly labelled
  exploratory calibration runs first (no gate evidence), then the
  committed RL-F predeclaration fixes every number, measurement
  method, and failure criterion before the evidentiary run (Gate
  RL-F).
- Any further choices that require empirical calibration surface here
  before their gate's predeclaration is committed.
- Campaign names and gate-to-campaign packing (Section 15) remain
  provisional until the first predeclaration is committed.

## 15. Proposed campaign and tag names

Provisional until the first predeclaration is committed (Section 14).

| Item | Name |
| --- | --- |
| Readiness campaign 1 (gates RN-A, RN-B) | `readiness/campaign-1/`, tag `v0.9.2-readiness-1` |
| Readiness campaign 2 (gates RL-C, RT-D) | `readiness/campaign-2/`, tag `v0.9.2-readiness-2` |
| Readiness campaign 3 (gates RT-E, RL-F) | `readiness/campaign-3/`, tag `v0.9.2-readiness-3` |
| Artifact and review record (RA-G, RS-H) | `readiness/campaign-4/`, tag `v0.9.2-readiness-4` |
| Participant re-freezes as required | `rust-v0.9.2-rc1`, `motoko-v0.9.2-rc1` (incrementing) |
| GitHub pre-release (claim 2, when its gates pass) | `v0.9.2-rc1` |

Gate-to-campaign packing may be adjusted before execution; the gate
definitions and acceptance criteria of Section 5 may not be weakened
after any corresponding evidence exists.
