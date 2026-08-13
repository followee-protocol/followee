# Followee interoperability interface contract

**Followee v0.9.1 — mechanical operation surface for cross-implementation
comparison**

This document defines only operation names, argument types, result
shapes, and transport framing. It contains no fixture outcomes, no
expected values, and no interpretation derived from any implementation.
The pinned Followee specification in this bundle alone governs protocol
behaviour; where this contract and the specification could be read to
differ, the specification governs.

An implementation participating in the Milestone 6 interoperability
experiment exposes these operations so that identical structured inputs
can be submitted to two implementations and the results compared
mechanically. The operations mirror protocol roles defined by the
specification: identity creation (Section 4), record authoring and
signing (Sections 5–6), record verification (Section 8.1), strict
Ed25519 (Section 3.3), timestamp generation (Section 5.3), CBOR
validation (Section 6.1), and candidate selection (Section 8). The
HTTP/CBOR relay profile (Section 12) is exercised separately over real
HTTP; its message shapes are defined by the specification itself and
illustrated in `../transcripts/`.

## Transport framing

- Newline-delimited UTF-8 JSON over stdin/stdout: one complete JSON
  object per line, terminated by `\n`.
- No byte-order mark, no blank lines, no output other than response
  lines on stdout. Diagnostics go only to stderr.
- Maximum line length: 1 MiB.
- Unknown object members, duplicate members, and bare JSON numbers are
  rejected as input-contract violations.
- Every response repeats the request's `interfaceProtocol` and `caseId`.

## Value conventions

- **Integers** are canonical decimal strings with no leading zeros
  (`"1785589200123"`), never bare JSON numbers. The full `uint64` range
  must survive round-tripping.
- **Binary values** are lowercase even-length hexadecimal strings.
- **Absent optional values** are JSON `null`. An optional protocol field
  that is `null`, an empty array, or an empty object is omitted from the
  encoded CBOR entirely.
- **DIDs** are canonical `did:flw:` strings.

## Request and response envelope

Request:

```json
{"interfaceProtocol": "1", "caseId": "<opaque>", "operation": "<name>",
 "input": { ... }}
```

Response, one of:

```json
{"interfaceProtocol": "1", "caseId": "<opaque>", "status": "accepted",
 "result": { ... }}
{"interfaceProtocol": "1", "caseId": "<opaque>", "status": "rejected",
 "error": "<followee-symbolic-error>"}
{"interfaceProtocol": "1", "caseId": "<opaque>", "status": "error",
 "errorSymbol": "<namespaced-symbol>", "message": "<text>"}
```

`rejected` carries exactly one symbolic Followee classification from the
specification (for example `invalidCbor`, `identityBindingMismatch`).
`status: "error"` reports an infrastructure failure and is never a
protocol comparison result.

## Structured contact shape

The `contact` argument is the Contact Document of specification
Section 7 in named-field form:

```json
{
  "displayName": "..." | null,
  "summary": "..." | null,
  "avatar": "<uri>" | null,
  "alsoKnownAs": ["<uri>", ...],
  "services": [
    {"id": "...", "type": "...", "endpoint": "<uri>",
     "mediaType": "..." | null, "label": "..." | null,
     "language": "..." | null, "rel": "..." | null}
  ],
  "migration": {"predecessor": "<did>" | null,
                "successor": "<did>" | null} | null,
  "extensions": { "<uri>": <typed value>, ... }
}
```

Field names map to the integer labels of Sections 5.1, 7.1, 7.3, and
7.4. Null, empty-array, and empty-object members are absent fields.

## Typed extension values

Extension values form a typed tree:

```json
{"type": "uint", "value": "<decimal>"}
{"type": "nint", "value": "-<decimal>"}
{"type": "text", "value": "<string>"}
{"type": "bytes", "hex": "<hex>"}
{"type": "bool", "value": true | false}
{"type": "null"}
{"type": "array", "items": [<typed value>, ...]}
{"type": "map", "entries": [{"key": <typed value>, "value": <typed value>}, ...]}
```

Map keys are restricted to `uint`, `nint`, and `text` (specification
Appendix A `extension-inner-key`). Entries are encoded in deterministic
CBOR key order regardless of their JSON order.

## Operations

### `hello`

- Input: `{}`.
- Result: `implementation` (name string), `implementationRepository`,
  `implementationCommit`, `specificationCommit`, `interfaceProtocols`
  (array of strings), `operations` (array of operation names).

### `deriveIdentity`

- Input: `rootSeedHex` (32 bytes), `revocationSeedHex` (32 bytes).
- Result: `rootPublicKeyHex`, `revocationPublicKeyHex`,
  `revocationPublicKeyCborHex`, `revocationCommitmentHex`,
  `authorityDescriptorCborHex`, `authorityDescriptorDigestHex`,
  `multihashHex`, `did`.

### `authorRecord`

- Input: `rootSeedHex`, `revocationSeedHex`, `authority`
  (`"root"` | `"rootRevoked"`), `timestampMs`, `validUntilMs` (or
  null), `contact` (structured contact shape), `extensions` (typed
  value map keyed by URI; record label 8), `signingSeed`
  (`"root"` | `"revocation"`). An incoherent authority/signingSeed
  pairing is an input-contract violation, never silently re-keyed.
- Result: `did`, `recordBodyCborHex`, `recordBodyDigestHex`,
  `sigStructureHex`, `signatureHex`, `envelopeHex`. All members are
  deterministic functions of the input.

### `verifyRecord`

- Input: `targetDid` (arbitrary string; malformed targets are
  legitimate inputs), `envelopeHex`, `nowMs` (recipient clock; wall
  time must not be consulted).
- Accepted result: `envelopeHex` (the exact received bytes),
  `recordBodyCborHex`, `recordBodyDigestHex`, `id`, `timestampMs`,
  `authority` (`"root"` | `"rootRevoked"`), `validUntilMs` (or null),
  `premature` (boolean), `stale` (boolean), and `record` — the complete
  semantic record (descriptor, contact document, migration, extensions)
  in the structured shapes above.
- Rejected result: one symbolic Followee error.

### `strictEd25519`

- Input: `publicKeyHex`, `messageHex`, `signatureHex` (lengths
  deliberately unconstrained; the strict verifier classifies them).
- Result: `valid` (boolean). `valid: false` is a successful execution.

### `nextTimestamp`

- Input: `nowMs`, `previousTimestampMs` (or null).
- Result: `timestampMs` with `error: null`, or `timestampMs: null` with
  `error: "overflow"` for the checked-arithmetic overflow case of
  specification Section 5.3.

### `validateCbor`

- Input: `cborHex`, `maxDepth` (`"0"`..`"8"`), `maxMembers`
  (`"0"`..`"256"`); out-of-domain limits are input errors, not protocol
  results.
- Result: `valid: true`, or rejection with `invalidCbor`,
  `nonDeterministicCbor`, or `schemaViolation`.
- Layer boundary: validates exactly (1) CBOR well-formedness and basic
  validity (specification Section 6.1.1), (2) the Followee
  deterministic profile (Section 6.1.2), and (3) the supplied
  depth/member limits. It applies no record, envelope, or other v1
  schema; schema-layer classification of complete records belongs to
  `verifyRecord`.

### `selectCurrent`

- Input: `targetDid`, `candidateEnvelopesHex` (array of hex strings,
  in delivery order), `nowMs`, `stickyAuthority`
  (`"unknown"` | `"root"` | `"rootRevoked"`).
- Result: `winnerRecordBodyDigestHex` (or null), `authorityState`
  (`"unknown"` | `"root"` | `"rootRevoked"`). Every candidate is
  verified for the explicit target through complete record
  verification; the subject is never inferred from a candidate.

## Result equality

Every result member above is compared exactly across implementations —
string equality for hex and decimal-string members, value equality for
booleans and nulls, structural equality for objects. Extra data may be
attached only under a namespaced `diagnostic` member, which is excluded
from comparison.
