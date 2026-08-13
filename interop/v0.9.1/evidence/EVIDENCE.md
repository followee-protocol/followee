# Reviewed evidence pins

Pointers only — this bundle copies no implementation-derived content.
These pins record the reviewed state of the surrounding repositories at
bundle creation so the interoperability run can verify it starts from
the same evidence. Category: `confirmed-evidence-pointer`
(see `../PROVENANCE.md`).

## Protocol repository (this repository)

| Artifact | Pin |
| --- | --- |
| Specification v0.9.1 | commit `5bea128f2800cc3fd443fa7440f8c247b9d4a9c8` introduced the reviewed document; bundle baseline commit `fd8f6a8b2311677be38bd22a0a3265539dca2158` |
| `Followee-Specification.md` SHA-256 | `1c1a20c639aaf90b1bfc54b5e9ea72c49f680566ba9b12ad10615412ece3cd71` |
| Whitepaper | draft v0.10, reviewed, at the same baseline commit (design rationale; excluded from the AUTHORING subset) |

## Rust implementation (`followee-rs`)

| Artifact | Pin |
| --- | --- |
| Milestone 5 reviewed | commit `8606a102bfb4f2bbfbc81e364bdf548c437bf123`, tag `milestone-5-v0.9.1-reviewed` |

The Rust implementation is one intended participant in the
interoperability run. It is **not** described as interoperable by this
bundle; see `../ACCEPTANCE.md`.

## Conformance repository (`followee-conformance`)

| Artifact | Pin |
| --- | --- |
| Frozen v0.8.1 differential archive | tag `v0.8.1-differential-final` at commit `beb89f656e1ca8398fd09b0be4799339a4fc1d98`; fixture-bundle aggregate SHA-256 `896e2591dab6a2d80b9dcdae111ad6df08960bfe8b064936a7f405b080b53350` |
| Confirmed fixture corpus | tag `v0.8.1-fixtures-confirmed` at commit `9493e39bd738372fe1e2fc1b2e96f6a41983c1be` — 53 implementation-status cases promoted to confirmed after 218/218 agreed comparisons; 158 specification-status cases byte-identical to the frozen archive |

The confirmed corpus and differential archives are comparison-stage
evidence for the future run. They are implementation-associated
material and are therefore excluded from the AUTHORING subset; the
independent implementation meets them only after its own outputs are
frozen.

## Independent clean-room model (`followee-python-cleanroom`)

| Artifact | Pin |
| --- | --- |
| Reviewed v0.8.1 conformance correction | commit `a94e9a8a7bd2f9c2e0947715ec387b6c3967e4e6` |

## Independent Motoko implementation (`followee-motoko`)

| Artifact | Pin |
| --- | --- |
| Clean tooling baseline | commit `4bd922c301ed8f1583bcca37ac988b6493badfae` |

The Motoko repository was verified to exist at its clean tooling
baseline and was not inspected further during bundle curation. Its
implementation sessions receive the AUTHORING subset only.

## Cross-checks performed at curation

- The pinned specification copy in `../authoring/specification/` is
  byte-identical to the repository document at the baseline commit.
- Every value the bundle tooling reconstructs (public keys,
  commitments, descriptors, DIDs, bodies, digests, Sig_structures,
  signatures, envelopes, B.11 wrapper bytes) was asserted against the
  bytes, lengths, and digests published in Appendix B.
- Bundle-computed values for the specification-status derivation and
  authoring cases were additionally confirmed equal to the reviewed
  neutral conformance corpus (`derive-identity-*`, `author-b4-root`,
  `author-b5-root-revoked`, `author-b6-alice-{a,b}` digest members,
  `author-bob-root`) — independent confirmation, not a source.
