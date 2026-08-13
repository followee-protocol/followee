# Followee v0.9.1 external-interoperability bundle

This directory is the neutral, language-independent bundle that prepares
the Followee Milestone 6 interoperability experiment required by
specification Section 20.4: two independent implementations producing
byte-identical Authority Descriptors, record bodies, digests, DIDs, and
signed envelopes from the same structured inputs, selecting the same
winners across permuted candidate orders, and exchanging state through
the mandatory HTTP/CBOR relay profile.

**This bundle makes no interoperability claim.** It prepares the
experiment. No implementation may be described as interoperable until
the complete two-direction cross-implementation run in `ACCEPTANCE.md`
has succeeded, and communicating with another process built from the
same core library never counts.

## Layout

```
interop/v0.9.1/
├── README.md            this file
├── MANIFEST.json        every file: SHA-256, size, provenance, audience
├── PROVENANCE.md        provenance categories and their rules
├── ACCEPTANCE.md        Section 20.4 obligation matrix and the run plan
├── authoring/           THE AUTHORING SUBSET — the only material a fresh
│   │                    independent implementation session may receive
│   ├── AUTHORING.md     subset charter: contents, rules, exclusions,
│   │                    and the freeze sequence
│   ├── NONDETERMINISM.md   opacity and comparison policy
│   ├── specification/   pinned normative specification v0.9.1
│   ├── interface/       mechanical operation and framing contract
│   └── vectors/
│       ├── published/   Appendix B values LITERALLY PUBLISHED in the
│       │                pinned specification — nothing merely derived
│       └── challenge/   blind inputs — no expected outputs anywhere
├── coordinator/         WITHHELD until the implementation freeze
│   ├── COORDINATOR.md   exposure rules and the author→freeze→compare
│   │                    sequence
│   ├── expected/        full expectations: specification-determined
│   │                    reconstructions and constructed comparison cases
│   └── transcripts/     documented HTTP/CBOR exchanges (v1/info,
│                        v1/resolve, v1/directory, v1/publish, v1/changes)
├── evidence/            pins to reviewed external evidence (pointers only)
└── verify/              stdlib-only deterministic verification tooling
    ├── interopkit/      deterministic CBOR, base58btc, RFC 8032 Ed25519
    ├── extract_published_vectors.py   regenerates both vector trees
    ├── gen_transcripts.py             regenerates coordinator/transcripts/
    ├── verify_bundle.py               full verification + manifest
    └── tests/                         unit and tamper tests
```

The split is deliberate: the independence boundary is a directory
boundary. `authoring/` contains only the pinned specification, the
neutral interface contract, authoring/nondeterminism instructions,
literally published Appendix B values, and blind challenge inputs.
Every expected value absent from the specification — however
deterministically derived — lives under `coordinator/`, and
`verify_bundle.py` proves mechanically that no coordinator-derived
result-like token is reachable from the authoring tree.

## Verifying the bundle

From this directory:

```
python3 verify/verify_bundle.py
python3 -m unittest discover -s verify/tests
```

Verification requires only a Python 3 standard library. It confirms the
manifest, the pinned specification hash, byte-identical regeneration of
every generated file from the specification, every published byte,
length, digest, and signature assertion, transcript framing,
challenge-file blindness, AUTHORING-subset hygiene, and the
independence boundary (no coordinator-derived value reachable from the
authoring tree).

## Regenerating generated files

```
python3 verify/extract_published_vectors.py --check   # or --write
python3 verify/gen_transcripts.py --check             # or --write
python3 verify/verify_bundle.py --write-manifest
```

Generation is deterministic; regenerating an unmodified bundle changes
no bytes. Everything under `authoring/vectors/published/`,
`coordinator/expected/`, and `coordinator/transcripts/` is derived from
the pinned specification copy alone.

## Version

Bundle `followee-interop/v0.9.1`, pinned to Followee specification
v0.9.1 (SHA-256
`1c1a20c639aaf90b1bfc54b5e9ea72c49f680566ba9b12ad10615412ece3cd71`).
A normative change to CBOR classification, relay wrappers, or cursor
visibility obsoletes this bundle version (Section 20.4); a new bundle
is generated under a new versioned directory and the experiment reruns.
