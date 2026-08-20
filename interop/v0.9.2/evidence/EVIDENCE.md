# Reviewed evidence pins

Pointers only — this bundle copies no implementation-derived content.
These pins record the reviewed state of the surrounding evidence at
bundle creation so Campaign 2 can verify it starts from the same
evidence. Category: `confirmed-evidence-pointer` (see
`../PROVENANCE.md`). The same pins appear machine-readably in
`../MANIFEST.json` under `pins`.

## Protocol repository (this repository)

| Artifact | Pin |
| --- | --- |
| Specification v0.9.2 (reviewed) | tag `v0.9.2-reviewed`, commit `ac5a794f2fdadc13cddf5367fa3e047617e3e950`; specification-content revision `f1d19fec0dba455d90d473bfad625d1c288e0c15` |
| `Followee-Specification.md` SHA-256 | `47af5fbf0c4505386b4e04d948ef89d013f878ea820fb02522817661d633633a` |
| Appendix B region SHA-256 | `02bbaea79b26e2648d1f669f7175fbc074f90404916ab351175ce0dc8b658758` — byte-identical to v0.9.1; every published vector unchanged |
| Whitepaper | draft v0.10.1 at the same commit, SHA-256 `dc106ee10741d5a8b157447b0f256eb61435ea036a4616e862387658e60c8387` (design rationale; excluded from the AUTHORING subset) |
| v0.9.1 interoperability bundle | tag `v0.9.1-interop-bundle-reviewed`, commit `c90742eb763cda5bd3c6e7d20ab1799590da489b`; `interop/v0.9.1` remains byte-identical to that revision |
| Campaign 1 (first neutral Rust↔Motoko run) | tag `v0.9.1-interop-campaign-1`, commit `515f37d86a35937b3539bfafdd671291d6abb443`; `interop/campaign-1` remains byte-identical to that revision; results aggregate SHA-256 `13efa5fd8a1f4b3c34786eba0e6be7c16b1dc2f85d6585a675183c4cda062a36` |

Campaign 1 is immutable historical evidence. Its W1 finding correctly
recorded the publish status-1 encoding difference as an unresolved
specification ambiguity at the time it ran; specification v0.9.2
resolves that ambiguity and this bundle classifies the observed
variation as permitted diagnostic variation. The historical entry is
not rewritten. Campaign 1's W2 finding (serving a held unverifiable
candidate) is an implementation finding already decided by
Section 12.3 and Appendix B.11.3; it required no specification change
and no bundle change beyond the unchanged B.11.3 material.

## Participant repositories

Campaign 1 recorded the participant freezes:

| Artifact | Pin |
| --- | --- |
| Rust participant reviewed at Campaign 1 | commit `8606a102bfb4f2bbfbc81e364bdf548c437bf123`, tag `milestone-5-v0.9.1-reviewed` |
| Motoko independent freeze | commit `3840d9adf07755d326d920f4711dafc4e08bcb40`, tag `motoko-v0.9.1-independent-freeze` |
| Motoko frozen challenge output SHA-256 | `e73c5697de68df7ec0f693834165bff7a1753a077959c9d9be50553b5722478e` (preserved pre-comparison bytes; also archived in Campaign 1) |

Neither participant repository was accessed, inspected, or modified
during the preparation of this bundle; the pins above are carried
forward from the reviewed Campaign 1 archive in this repository.

## Campaign 2 freeze pins (recorded before coordinator exposure)

Both maintained participants froze on the identical sealed v0.9.2-r2
authoring subset (aggregate `1b6514da0c1a0c5289e0909b648b5de73a302e91b346440624badacf5747855e`)
before any coordinator material was opened to them. The Campaign 2
coordinator verified every pin below in clean temporary checkouts
before any comparison; the campaign evidence lives in
`interop/campaign-2/`.

| Artifact | Pin |
| --- | --- |
| Rust maintained freeze | tag `rust-v0.9.2-maintained-freeze`, tag object `165533f54839aba9c25e6a37e58c85a406f9a8cb`, peeled commit `d865dc3fae52b3e2a54d573c298de7b01a1539c9` |
| Motoko maintained freeze (revision 2) | tag `motoko-v0.9.2-r2-maintained-freeze`, tag object `527b3f0c0618d96b484f21ee641a59fec1e3ebc6`, peeled commit `bb0b0782e96bea9169ddb723815d191b58de65d7` |
| Motoko r2 challenge output SHA-256 | `5c53c78735a05d81bc6a51bb813a003a6f181e604d334f1a6972203a6913315d` (frozen before comparison) |
| Motoko r1 challenge output SHA-256 | `d6c4e55650c03e5382abfe2caa77c8bc56ab2514d2f366d71526ee40e96311d3` (historical, preserved) |
| Motoko blind challenge output SHA-256 | `e73c5697de68df7ec0f693834165bff7a1753a077959c9d9be50553b5722478e` (Campaign 1 record, unchanged) |
| Rust frozen outputs | per-file SHA-256 in the participant's own `interop/v0.9.2/outputs/MANIFEST.json` at the freeze commit, verified byte-for-byte |
| Campaign 2 results archive aggregate SHA-256 | `25095eff996b0ab7e3269e6d6105c7393d9d99e416783114c2ee1a162732d343` |

## Cross-checks performed at curation

- The pinned specification copy in `../authoring/specification/` is
  byte-identical to the repository document at the reviewed tag.
- The Appendix B region digest above was verified against both the
  pinned copy and the v0.9.1 bundle's specification copy.
- The three challenge-input files are byte-identical to the v0.9.1
  bundle's files (per-file SHA-256 pinned in the verifier).
- Every value the bundle tooling reconstructs (public keys,
  commitments, descriptors, DIDs, bodies, digests, Sig_structures,
  signatures, envelopes, B.11 wrapper bytes, publish-response
  wrappers) was asserted against the bytes, lengths, and digests
  published in Appendix B or constructed by the normative Section 12.5
  rule, with construction failure aborting generation.
