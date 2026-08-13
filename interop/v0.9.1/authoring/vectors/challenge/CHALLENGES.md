# Blind challenge protocol

The three `challenge-*.json` files in this directory are **inputs only**.
Nothing in this bundle — and nothing a fresh implementation session may
receive — contains a DID, record body, digest, signature, envelope,
winner, or authority-state result for any challenge case. That absence
is deliberate and is what keeps this portion of the interoperability
experiment genuinely blind: the published Appendix B vectors prove that
an implementation can reproduce values it can also read, while the
challenge cases prove agreement on values neither implementation has
seen asserted anywhere.

The challenge seeds are public fixture material in the sense of the
specification's Appendix B.1 warning. They MUST NOT be used for a real
Followee DID. No private or production secret appears in this bundle.

## How a fresh implementation session uses these files

1. Derive the complete identity chain for each case in
   `challenge-identities.json` with the `deriveIdentity` operation.
2. Author every record in `challenge-records.json` with the
   `authorRecord` operation. An `identityRef` member names the
   challenge identity whose seeds supply `rootSeedHex` and
   `revocationSeedHex`; a migration value of the form
   `{"identityRef": "<name>"}` is replaced by the canonical Followee DID
   the implementation itself derived for that identity.
3. Self-verify each authored envelope with `verifyRecord` at the
   file-level `verifyNowMs`.
4. Run every case in `challenge-selection.json` with `selectCurrent`,
   materialising each `{"challengeCase": ...}` reference as the envelope
   authored in step 2. Every permutation of one `permutationOf` group
   MUST select the same winner.
5. Record all outputs in the implementation's own repository and freeze
   them at a recorded revision.

## How results are compared

Only after both implementations have frozen their challenge outputs at
recorded revisions are the outputs compared, value for value, under the
result-equality rule of the interface contract:

- derived identity chains and DIDs — byte identity;
- record bodies, digests, Sig_structures, signatures, envelopes — byte
  identity;
- verification outcomes and flags — exact equality;
- selection winners and authority states — exact equality across every
  enumerated permutation.

A disagreement is investigated against the pinned specification alone.
The comparison report follows the Section 20.4 reporting rule:
acceptance/rejection disagreements, symbolic differences permitted by
explicitly unspecified multi-fault precedence, and genuine unresolved
specification ambiguities are counted separately, and permitted symbolic
differences remain visible in the report.

Challenge outputs from one implementation MUST NOT be shown to the other
implementation's authoring session before both are frozen. After the
comparison succeeds, the outputs may be promoted into ordinary shared
fixture material for regression use.
