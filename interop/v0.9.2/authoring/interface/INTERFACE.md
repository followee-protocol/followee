# Followee interoperability interface contract

**Followee v0.9.2 — mechanical operation surface for cross-implementation
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
validation (Section 6.1), candidate selection (Section 8), and
publish-response wrapper acceptance (Section 12.5). The HTTP/CBOR relay
profile (Section 12) is exercised separately over real HTTP; its
message shapes are defined by the specification itself and illustrated
in `../transcripts/`.

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

### Scalar encodings

**Canonical decimal string.** An optional leading `-`, then one or more
ASCII digits. No leading zeros except the single digit `0`. No leading
`+`. No whitespace, exponent, fractional part, or thousands separator.
The string `-0` is forbidden; zero is exactly `0`. Never a JSON number.

A leading `-` is permitted only for a field whose specified domain
includes negative values. In this contract the only such fields are the
COSE algorithm identifiers `record.descriptor.rootKeySuite` and
`record.revocationKey.suite`.

**Unsigned 64-bit fields.** A field specified as `uint64` accepts the
complete range `0` through `18446744073709551615` inclusive. It never
carries a minus sign. An implementation MUST round-trip the entire
range without precision loss or rounding, which is why these values are
canonical decimal strings and never JSON numbers. In this contract the
`uint64` fields are `timestampMs` and `validUntilMs`.

**Lowercase hex string.** Even length, characters `0`-`9` and `a`-`f`
only. No uppercase, no `0x` prefix, no separators, no whitespace. The
empty string is the encoding of zero bytes, and is valid only where the
applicable specification grammar admits a zero-length byte string.

**DIDs.** Canonical `did:flw` strings.

**Unknown members.** Any member name not defined for its position is
rejected.

### Presence is directional

Followee wire fields may be absent, or present and empty. The neutral
interface treats these differently in each direction, because
`authorRecord` constructs records and `verifyRecord` observes them.

| Direction | Rule |
| --- | --- |
| `authorRecord` input | An optional member that is omitted, `null`, an empty array, or an empty object requests omission of that optional wire field. |
| `verifyRecord` accepted output | `null` means the wire field was absent. `[]`, `{}`, and `""` mean the wire field was present and empty. |

This asymmetry is deliberate and is retained for compatibility with the
sealed challenge inputs, whose `[]` and `{}` values request absent
optional fields and continue to mean exactly that. Nothing in this
revision reinterprets them.

The constructor canonicalization applies only to optional Followee
protocol fields. It never reaches inside a typed extension value in
either direction: an extension value that is an empty array or an empty
map is a present empty collection, not an omission request, and MUST be
encoded and observed as such.

### Consequences of the input canonicalization

1. `authorRecord` cannot construct the present-empty encoding of an
   optional array or an optional map. Those encodings remain valid
   protocol values and MUST be exercised through `verifyRecord` against
   direct wire fixtures. Coverage of present-empty collections
   therefore does not follow from authoring coverage and MUST be
   provided separately.

2. The canonicalization enumerates omission, `null`, empty array, and
   empty object. The empty string is not among them. An empty string
   supplied to `authorRecord` for an optional text field is therefore a
   request for a **present empty text string**, not for omission,
   wherever the applicable specification grammar admits one. Authoring
   can consequently reach present-empty text but not present-empty
   collections.

3. Stability holds for the authored subset only, and MUST NOT be
   described as whole-operation idempotence or lossless round-tripping.

   What holds: an omission request supplied to `authorRecord` produces
   an absent wire field; verifying that record observes the field as
   `null`; supplying that `null` to `authorRecord` again produces the
   same absent field. Records produced by `authorRecord` are therefore
   a stable subset under re-verification and re-authoring.

   What does not hold: arbitrary `verifyRecord` output is not
   losslessly re-authorable. For a directly received wire record
   carrying a present-empty optional array or map, `verifyRecord`
   faithfully emits `[]` or `{}`; supplying that value to
   `authorRecord` is an omission request; the re-authored bytes omit
   the field; and the next `verifyRecord` result is `null`. The
   present-empty encoding is observed faithfully and is normalized to
   absence only if it is deliberately passed back through
   `authorRecord`.

4. Should authoring of present-empty collections later be required, it
   MUST be added as a new explicit input form rather than by redefining
   `[]` or `{}`, because redefining them would silently change the
   meaning of every sealed challenge input.

### General scalar presence rule for accepted output

An absent optional text field projects to `null`. A present text field
projects to its exact text, including `""` where the applicable
specification grammar admits a zero-length value. Where the grammar
does not admit a zero-length value, `""` cannot occur in a conforming
record and its appearance in an accepted result is a rejection.

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

One named Contact Document shape serves both operations. Member names,
value types, ordering rules, and scalar encodings are identical in both
directions. Only presence semantics differ, per the directional rules
under "Presence is directional":

- `authorRecord` **input** member `input.contact` uses the member names
  and value shapes below, with constructor presence semantics: an
  omitted member, `null`, an empty array, or an empty object requests
  omission of that wire field.
- `verifyRecord` **output** member `record.contact` uses the same
  member names and value shapes, with lossless presence semantics:
  `null` means absent, and `[]`, `{}`, or `""` means present and empty.

In both directions, `services` array order is the record's order and
MUST NOT be reordered, deduplicated, or filtered. In both directions,
the directional presence rules never alter a scalar value or a typed
extension value.

### Contact Document members

`record.contact` is always a JSON object in accepted output.
Specification Section 5.1 makes record-body label `7` mandatory, and
Specification Section 7.1 permits an entirely empty Contact Document,
which projects to an object whose members are all `null`.

| Label | Member | JSON type | Absent projects to | Present-empty admitted | Present-empty projects to |
| ---: | --- | --- | --- | --- | --- |
| `0` | `displayName` | string or null | `null` | Yes, no minimum length | `""` |
| `1` | `summary` | string or null | `null` | Yes, no minimum length | `""` |
| `2` | `avatar` | string or null | `null` | No, the URI grammar requires a scheme | not representable |
| `3` | `alsoKnownAs` | array or null | `null` | Yes, no minimum entry count | `[]` |
| `4` | `services` | array or null | `null` | Yes, no minimum entry count | `[]` |
| `5` | `migration` | object or null | `null` | No, at least one field is required | not representable |
| `6` | `extensions` | object or null | `null` | Yes, zero or more entries | `{}` |

`alsoKnownAs` entries are URIs and are never `""`.

`migration` has no present-empty form because Specification Section 7.4
requires a present migration map to contain at least one of its two
fields. `null` therefore denotes absence unambiguously, and in the
input direction a migration object whose members are all `null` is an
empty map and requests omission.

### Service entry members

Each entry of `services` is an object with exactly the following
members and no others.

| Label | Member | JSON type | Absent projects to | Present-empty admitted |
| ---: | --- | --- | --- | --- |
| `0` | `id` | string | member is required | No, one to 256 characters |
| `1` | `type` | string | member is required | No, token or URI |
| `2` | `endpoint` | string | member is required | No, the URI grammar requires a scheme |
| `3` | `mediaType` | string or null | `null` | No, the RFC 6838 restricted-name grammar requires at least one character |
| `4` | `label` | string or null | `null` | Yes, no minimum length, projects to `""` |
| `5` | `language` | string or null | `null` | No, RFC 5646 requires a primary subtag |
| `6` | `rel` | string or null | `null` | No, the token grammar requires a leading letter and the alternative is a URI |

In the input direction, `id`, `type`, and `endpoint` MUST be present
and non-null; a service entry cannot request their omission.

### Migration members

When `record.contact.migration` is non-null, it is an object with
exactly the members `predecessor` and `successor`, and no others.

| Label | Member | JSON type | Absent projects to | Present-empty admitted |
| ---: | --- | --- | --- | --- |
| `0` | `predecessor` | string or null | `null` | No, the value is a canonical DID |
| `1` | `successor` | string or null | `null` | No, the value is a canonical DID |

At least one member is non-null in accepted output.

### Extension maps

Two distinct extension maps exist in one record: record-body label `8`
and Contact Document label `6`. They appear as `input.extensions` and
`input.contact.extensions` in the input direction, and as
`record.extensions` and `record.contact.extensions` in the output
direction. They MUST NOT be merged, substituted for one another, or
omitted in favour of one another, and a value present in one MUST NOT
appear in the other.

In accepted output each projects to `null` when its label is absent,
and to a JSON object otherwise, including `{}` when the map is present
and empty. Member names are the extension keys exactly as carried.
Extension keys are URIs and are never `""`.

Member values use the typed extension-value encoding defined under
"Typed extension values", preserved exactly in both directions. A
zero-length text value, a zero-length byte value, an empty nested
array, and an empty nested map are distinct present values and MUST be
preserved as such.

### Non-normative input example

The following illustrates `authorRecord` input presence semantics. It
is an illustration only. It is not a test vector, not a fixture, and no
value in it is normative.

```json
{
  "contact": {
    "displayName": "Example Name",
    "summary": null,
    "avatar": null,
    "alsoKnownAs": [],
    "services": [
      {
        "id": "example-service",
        "type": "Website",
        "endpoint": "https://example.invalid/",
        "mediaType": null,
        "label": "",
        "language": null,
        "rel": null
      }
    ],
    "migration": null,
    "extensions": {}
  }
}
```

Interpretation under the directional presence rules, for this
illustration only:

- `summary`, `avatar`, and `migration` are `null` and request omission
  of Contact Document labels `1`, `2`, and `5`.
- `alsoKnownAs` is an empty array and `extensions` is an empty object;
  both request omission of labels `3` and `6`. Neither produces a
  present-empty wire collection.
- `services` is a non-empty array and is encoded at label `4` in the
  given order.
- the service `label` member is `""`, which is a present empty text
  string rather than an omission request, because the empty string is
  not one of the canonicalized forms and Specification Section 7.3
  imposes no minimum length on that field.
- verifying the resulting record yields `summary`, `avatar`,
  `migration`, `alsoKnownAs`, and `extensions` as `null`, and the
  service `label` as `""`.

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
  (array of strings), `operations` (array of operation names, including
  `receivePublishResponse`).

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
- Accepted result: the complete object defined under "`verifyRecord`
  accepted result" below, subject to the accepted-result coherence
  relationships and rejection rules that follow it.
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

### `receivePublishResponse`

- Input: `responseHex` (the complete publish-response bytes exactly as
  received from a relay).
- Accepted result: `status` (`"0"` | `"1"` | `"2"`) and `errorCode`
  (canonical decimal string, or null when the response carries none).
  Acceptance means the response satisfies Section 6.1 and the
  Section 12.5 status-dependent field-presence rules; it is not a
  judgement about the underlying publication.
- Rejected result: one symbolic Followee error. A response violating
  the Section 12.5 presence rules is rejected completely; no status is
  extracted from it and no local state changes.
- Production entry point: the same wrapper-acceptance path the
  implementation's own publishing client uses for relay responses.

### `selectCurrent`

- Input: `targetDid`, `candidateEnvelopesHex` (array of hex strings,
  in delivery order), `nowMs`, `stickyAuthority`
  (`"unknown"` | `"root"` | `"rootRevoked"`).
- Result: `winnerRecordBodyDigestHex` (or null), `authorityState`
  (`"unknown"` | `"root"` | `"rootRevoked"`). Every candidate is
  verified for the explicit target through complete record
  verification; the subject is never inferred from a candidate.

## `verifyRecord` accepted result

### Top level

An object with exactly the following members and no others.

| Member | JSON type | Nullable | Content |
| --- | --- | --- | --- |
| `envelopeHex` | string | No | Lowercase hex of the complete verified envelope bytes |
| `recordBodyCborHex` | string | No | Lowercase hex of the exact received record-body payload bytes |
| `recordBodyDigestHex` | string | No | Lowercase hex of the 32-byte body digest |
| `id` | string | No | Canonical `did:flw` string from record-body label `1` |
| `timestampMs` | string | No | Canonical decimal string of the `uint64` at record-body label `2` |
| `authority` | string | No | Exactly `"root"` or `"rootRevoked"`, per record-body label `3` |
| `validUntilMs` | string or null | Yes | Canonical decimal string of the `uint64` at record-body label `6`, or `null` when that label is absent |
| `premature` | boolean | No | Classification under Specification Section 5.4 |
| `stale` | boolean | No | Classification under Specification Section 5.5 |
| `record` | object | No | Projected record content per "`record`" below |

### `record`

An object with exactly the members `descriptor`, `revocationKey`,
`contact`, and `extensions`, and no others.

| Member | JSON type | Nullable | Source |
| --- | --- | --- | --- |
| `descriptor` | object | No | Record-body label `4`, projected per "`record.descriptor`" below |
| `revocationKey` | object or null | Conditional | Record-body label `5`, projected per "`record.revocationKey`" below |
| `contact` | object | No | Record-body label `7`, projected per "Structured contact shape" |
| `extensions` | object or null | Yes | Record-body label `8`, projected per "Extension maps" |

Record-body label `0` is not projected. Specification Section 8.1
step 5 requires it to equal `1` in every accepted result, so it carries
no information.

Record-body labels `1`, `2`, `3`, and `6` are projected at the top
level as `id`, `timestampMs`, `authority`, and `validUntilMs`. They
MUST NOT also appear inside `record`. No wire field is projected at two
positions.

### `record.descriptor`

A projection of the Authority Descriptor of Specification Section 4.1.
Exactly the following eight members and no others. No member is
nullable.

| Member | JSON type | Nullable | Content |
| --- | --- | --- | --- |
| `descriptorVersion` | string | No | Canonical decimal string of Authority Descriptor label `0` |
| `rootKeySuite` | string | No | Canonical decimal string of label `0` of the root-key object at Authority Descriptor label `1` |
| `rootPublicKeyHex` | string | No | Lowercase hex of the 32 raw public-key bytes at label `1` of that root-key object |
| `revocationCommitmentHex` | string | No | Lowercase hex of the 32 commitment bytes at Authority Descriptor label `2` |
| `authorityDescriptorCborHex` | string | No | Lowercase hex of the deterministic CBOR encoding of the complete Authority Descriptor as carried in the verified record |
| `authorityDescriptorDigestHex` | string | No | Lowercase hex of the 32-byte descriptor digest of Specification Section 4.3 |
| `multihashHex` | string | No | Lowercase hex of the 34-byte multihash of Specification Section 4.3 |
| `did` | string | No | Canonical `did:flw` string constructed under Specification Section 4.3 |

**Eligibility criterion and closed set.** A value is *eligible* for
`record.descriptor` only if it is Authority Descriptor content or a
total function of the Authority Descriptor bytes alone. Eligibility is
a necessary condition, not a sufficient one: this contract includes
exactly the eight members listed above and no other content or derived
member is permitted, even where some further derived value would also
be eligible.

A value requiring any non-descriptor input is ineligible and MUST NOT
appear here under any name. The revealed revocation public key is the
case of interest: the descriptor carries only a one-way commitment to
it under Specification Section 4.2, and that section states the
revocation public key is not carried in ordinary root records. It is
record-body label `5`, not descriptor content, and is projected at
`record.revocationKey`.

### `record.revocationKey`

The projection of record-body label `5`, whose wire type is the
`public-key` object of Specification Section 3.2.

When `authority` is `"root"`, this member MUST be JSON `null`.
Specification Section 5.1 requires label `5` to be absent, so no key
exists to project. Emitting an object, or an empty string, is a
rejection.

When `authority` is `"rootRevoked"`, this member MUST be an object with
exactly the following three members and no others. Emitting `null` is a
rejection.

| Member | JSON type | Nullable | Content |
| --- | --- | --- | --- |
| `suite` | string | No | Canonical decimal string of label `0` of the revealed `public-key` object |
| `publicKeyHex` | string | No | Lowercase hex of the 32 raw public-key bytes at label `1` |
| `publicKeyCborHex` | string | No | Lowercase hex of the deterministic CBOR encoding of the complete revealed `public-key` object |

The member name `revocationKey` is always present in `record`. Only its
value varies with authority. Omitting the member name itself is a
rejection in both authority states.

## Accepted-result coherence relationships

Every relationship below MUST hold for an accepted result. Any
violation rejects the complete result. A consumer MUST NOT repair,
normalize, or partially accept a result that violates one.

1. `record.descriptor.descriptorVersion` equals `"1"`.
2. `record.descriptor.rootKeySuite` equals the canonical decimal string
   of the sole v1 Ed25519 COSE algorithm identifier required by
   Specification Section 3.2.
3. `record.descriptor.rootPublicKeyHex` is exactly 64 hex characters.
4. `record.descriptor.revocationCommitmentHex` is exactly 64 hex
   characters.
5. `record.descriptor.authorityDescriptorCborHex` decodes, under the
   deterministic profile of Specification Section 6.1, to exactly the
   three-member Authority Descriptor of Specification Section 4.1,
   whose label `0` value, root-key label `0` value, root-key label `1`
   bytes, and label `2` bytes reproduce `descriptorVersion`,
   `rootKeySuite`, `rootPublicKeyHex`, and `revocationCommitmentHex`
   respectively. Equivalently, the descriptor CBOR is reconstructible
   from the four preceding members and no other input.
6. `record.descriptor.authorityDescriptorDigestHex` equals the
   descriptor digest defined in Specification Section 4.3, computed
   over the bytes denoted by `authorityDescriptorCborHex`.
7. `record.descriptor.multihashHex` equals the multihash construction
   of Specification Section 4.3 applied to
   `authorityDescriptorDigestHex`, and is exactly 68 hex characters.
8. `record.descriptor.did` equals the DID construction of Specification
   Section 4.3 applied to the bytes denoted by `multihashHex`.
9. `record.descriptor.did` equals the top-level `id` byte for byte.
   Specification Section 8.1 makes
   `body id = target = DID(authorityDescriptor)` a single invariant of
   any accepted record, so a result in which these differ is internally
   inconsistent regardless of which member is correct.
10. `record.revocationKey` is `null` if and only if `authority` is
    `"root"`.
11. When `record.revocationKey` is an object, `suite` equals
    `record.descriptor.rootKeySuite`, `publicKeyHex` is exactly 64 hex
    characters, and `publicKeyCborHex` decodes under the deterministic
    profile to exactly the `public-key` object of Specification
    Section 3.2 whose label `0` value reproduces `suite` and whose
    label `1` bytes reproduce `publicKeyHex`.
12. When `record.revocationKey` is an object, the revocation-key
    commitment defined in Specification Section 4.2, computed over the
    bytes denoted by `publicKeyCborHex`, equals
    `record.descriptor.revocationCommitmentHex`.
13. When top-level `validUntilMs` is non-null, its value is greater
    than or equal to `timestampMs` under numeric comparison of the two
    canonical decimal strings over the full `uint64` range.
14. `record.contact.migration`, when non-null, contains at least one
    non-null member, and no non-null member equals the top-level `id`.

Rules 5 through 8, 11 and 12 make every derived member independently
recomputable from the members preceding it. An implementation that
emits a derived member from a cached, hardcoded, or separately obtained
value produces an accepted result only where that value happens to
agree; these rules are the mechanism by which disagreement becomes
observable rather than absorbed.

Rules 13 and 14 are deliberately redundant with Specification
Section 8.1 step 16 and Specification Section 7.4, both of which any
accepted record already satisfies. They are retained because their
subject is the projection rather than the record: a result violating
either exposes a projection defect in a value the verification path had
already established, which no other rule in this section would detect.

## Accepted-result rejection rules

A consumer MUST reject, and MUST NOT normalize, repair, or partially
accept:

- a missing member name at any level of an accepted result, including a
  member whose required value is `null`;
- any member name not defined for its position;
- a JSON number, boolean, array, or object where a string is required;
- a string where `null` is required, or `null` where a string or object
  is required;
- `{}`, `[]`, or `""` where `null` is required, or `null` where `{}`,
  `[]`, or `""` is required;
- `""` for any field whose applicable specification grammar admits no
  zero-length value, as enumerated under "Structured contact shape";
- uppercase hex, odd-length hex, `0x` prefixes, or non-hex characters;
- a non-canonical decimal string, including leading zeros, a leading
  `+`, the string `-0`, or surrounding whitespace;
- a leading `-` on a field whose specified domain is unsigned,
  including any `uint64` field;
- a decimal value outside the `uint64` range for a field specified as
  `uint64`;
- a hex string of any length other than the exact length required;
- an `authority` value other than `"root"` or `"rootRevoked"`;
- a `record.contact.services` array whose order differs from the
  record's order;
- any failure of the accepted-result coherence relationships 1
  through 14;
- any hex-encoded CBOR member whose bytes are well-formed CBOR but
  violate the deterministic profile, or which carry trailing bytes.

Rejection is of the complete `verifyRecord` result. A projection defect
is an interface-contract failure and MUST NOT be reported as a Followee
wire error code from Specification Section 15.3.

## Relationship to `deriveIdentity`

`record.descriptor` deliberately reuses six `deriveIdentity` member
names with identical encodings and identical meanings:
`rootPublicKeyHex`, `revocationCommitmentHex`,
`authorityDescriptorCborHex`, `authorityDescriptorDigestHex`,
`multihashHex`, and `did`. For any identity, those six MUST be equal,
member by member, between `deriveIdentity` for that identity and
`record.descriptor` projected from any record accepted for that
identity.

The remaining two `deriveIdentity` members do not appear in
`record.descriptor`, because the revocation public key is not derivable
from the Authority Descriptor. They correspond instead to:

| `deriveIdentity` member | Corresponding accepted-result location |
| --- | --- |
| `revocationPublicKeyHex` | `record.revocationKey.publicKeyHex` |
| `revocationPublicKeyCborHex` | `record.revocationKey.publicKeyCborHex` |

That correspondence holds only when `authority` is `"rootRevoked"`. For
a root record, `record.revocationKey` is `null` and no correspondence
exists, because Specification Section 4.2 withholds the revocation
public key from ordinary root records. The asymmetry is a property of
the protocol, not of the interface: an authoring party knows the
revocation key, and a verifying party of a root record does not.

`descriptorVersion` and `rootKeySuite` have no `deriveIdentity`
counterpart because that operation's inputs already fix them. They are
included so that `record.descriptor` is a faithful projection of
descriptor content, and because the convention that unknown members are
rejected would make their later addition a breaking interface change.

Reuse of `deriveIdentity` member names is permitted only where the
member satisfies the `record.descriptor` eligibility criterion and
appears in the closed set defined there. Name convenience MUST NOT
place a value inside a projection of a structure that does not contain
it.

## Evidential scope

The shapes defined here are an interface contract supplied identically
to every participant. Agreement between participants on this structure
demonstrates conformance to the contract. It is not evidence of
independent convergence and MUST NOT be reported as such.

The directional-presence asymmetry has one consequence for coverage
claims. Because `authorRecord` cannot construct a present-empty
optional array or map, agreement on authored records establishes
nothing about present-empty collection handling. Any claim of coverage
for those encodings MUST rest on `verifyRecord` against direct wire
fixtures, and a report SHOULD state whether such fixtures were
exercised.

## Result equality

Every result member above is compared exactly across implementations —
string equality for hex and decimal-string members, value equality for
booleans and nulls, structural equality for objects. Extra data may be
attached only under a namespaced `diagnostic` member, which is excluded
from comparison.
