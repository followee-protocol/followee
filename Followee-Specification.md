# Followee

## `did:flw` DID Method and Relay Protocol Specification

**Author: Mats Helander**
**Draft v0.8.1**
**8 August 2026**
**Licence: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)**

---

## Abstract

Followee resolves a permanent, self-certifying identifier to its controller's current public contact information through an open network of independently operated relays. It is designed to let a person or organisation be followed independently of the websites, feeds, applications, domains, and platforms it currently uses.

This document defines the `did:flw` DID method and the Followee v1 relay protocol. It specifies identifier construction, Authority Descriptors, deterministic CBOR Identity Records, COSE signatures, one-way root revocation, record ordering, Contact Documents, DID Document projection, WebFinger handle discovery, relay resolution and synchronization, client traversal, limits, errors, and conformance requirements.

Followee has no canonical registry, global ledger, shared history, consensus group, token, or mandatory relay. A conforming resolver verifies every full record locally. Relays are availability infrastructure, not identity authorities.

## 1. Status, scope, and requirements language

### 1.1 Status

This is the first implementer's draft of the Followee specification. It is intended to be complete enough for independent proof-of-concept implementations and adversarial interoperability testing. The `flw` method name, relation URIs, media-type usage, extension context, and registries described here remain subject to the relevant registration processes before a production interoperability claim is made.

Draft v0.8 clarifies CBOR well-formedness, basic validity, deterministic-profile, and schema-error boundaries after independent implementations exposed a classification ambiguity. It also makes relay batch alignment, opaque-candidate isolation, and synchronization cursor progress explicit. These changes do not alter DID construction, signature bytes, authority precedence, or record ordering.

Draft v0.8.1 clarifies one consequence of that layered CBOR model: a well-formed, basically valid, deterministically encoded simple value that no v1 schema admits produces `schemaViolation`, not `nonDeterministicCbor`. It adds fault-isolated signed vectors for both CBOR simple-value encoding forms. No wire encoding, cryptographic rule, authority rule, ordering rule, or relay behaviour changes.

The design rationale is given separately in the *Followee: A Relay Protocol for Following People, Not Platforms* whitepaper. If the two documents differ on wire behaviour, this specification governs implementations of the version it defines.

### 1.2 Requirements language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **NOT RECOMMENDED**, **MAY**, and **OPTIONAL** are to be interpreted as described in [BCP 14](https://www.rfc-editor.org/info/bcp14) when, and only when, they appear in all capitals.

Unless expressly marked non-normative, this document is normative.

### 1.3 Scope

Followee v1 defines one narrow operation:

> Given a `did:flw` identifier, discover and independently select its winning admissible public Contact Document.

Followee does not establish civil identity, one-person-one-identifier uniqueness, truth of profile claims, private messaging, a social graph, content hosting, content ranking, global availability, or a globally agreed event history.

This document combines the DID method and relay protocol for v1 so their shared record semantics cannot drift apart. A later editorial revision may split them without changing normative behaviour.

### 1.4 Conforming implementation roles

An implementation may claim one or more roles:

| Role | Required behaviour |
| --- | --- |
| **Record Verifier** | Parse and verify Followee DIDs, Authority Descriptors, and full Identity Records |
| **DID Resolver** | Resolve a Followee DID, select a record, and produce a DID resolution result |
| **Relay Resolver** | Expose bounded single and batch record resolution |
| **Relay** | Relay Resolver plus relay metadata, directory, and current-state synchronization |
| **Ingress Relay** | Relay plus record publication and local admission |
| **History Relay** | Relay plus an optional relay-local history interface defined outside the core protocol |

Every Relay, Ingress Relay, and DID Resolver MUST also conform as a Record Verifier. A sender's verification claim never substitutes for recipient verification.

## 2. Terminology

**Followee DID**
A DID using the `flw` method, whose method-specific identifier commits to an immutable Authority Descriptor.

**Authority Descriptor**
The immutable deterministic-CBOR object containing the initial root public key and a commitment to one revocation public key.

**root key**
The initial signing key for a Followee DID.

**revocation key**
The precommitted key that can irreversibly revoke the root and thereafter becomes the DID's permanent active signing key.

**Identity Record**
A tagged COSE Sign1 object whose payload is a complete deterministic-CBOR record body.

**Contact Document**
The complete current set of self-authored public profile fields and service endpoints carried by an Identity Record.

**full record**
The complete COSE Identity Record bytes. A full record is locally verifiable without history.

**reference**
An unverified routing hint to another relay. A reference says where a full record may be found; it says nothing authoritative about the record.

**admissible record**
A schema-conforming, descriptor-bound, signature-valid record whose timestamp is not premature under the recipient's clock and whose authority state is not excluded by sticky root revocation.

**fresh record**
An admissible record whose optional `validUntil_ms` has not passed.

**stale record**
An admissible record whose optional `validUntil_ms` has passed. Staleness affects freshness and presentation, not signature authenticity or activation of root revocation.

**winning record**
The record selected by authority precedence, timestamp, and body-digest ordering from the admissible candidates known to the selecting participant.

**handle authority**
The HTTPS domain responsible for resolving a name under that domain to a Followee DID.

**relay-local update number**
A number assigned by one relay when its current map changes. It is never an Identity Record version and is never compared across relays.

## 3. Identifier and cryptographic profile

### 3.1 Method name and syntax

The method name is:

```text
flw
```

The canonical DID form is:

```text
did:flw:<base58btc-multihash>
```

The method-specific identifier MUST:

1. begin with the multibase base58btc prefix `z`;
2. decode using the Bitcoin base58 alphabet without padding;
3. decode to exactly one structurally well-formed multihash consisting of a minimally encoded unsigned-varint code, a minimally encoded unsigned-varint digest length, exactly that many digest bytes, and no trailing bytes;
4. contain multihash code `0x12` (`sha2-256`), encoded as the one-byte unsigned varint `12` hexadecimal;
5. contain digest-length value `0x20`, encoded as the one-byte unsigned varint `20` hexadecimal; and
6. contain exactly 32 digest bytes, making the supported v1 multihash exactly 34 bytes.

Malformed multibase or base58btc encoding, a missing or non-minimal varint, disagreement between the declared digest length and the bytes present, trailing bytes, alternate spelling, or percent-encoding produces `invalidDid`. A structurally well-formed multihash that names a code other than `0x12` or a digest length other than `0x20` instead produces `unsupportedHash`; it remains unacceptable to a v1 verifier and MUST NOT be reinterpreted as the v1 profile. This syntax-versus-profile distinction is solely an error-classification rule and does not enlarge the set of Followee v1 DIDs that can be created or successfully resolved.

The method-specific identifier is case-sensitive because base58btc is case-sensitive. The `did:flw:` prefix MUST be lowercase.

Generic DID URL path, query, and fragment syntax remains available under DID Core. This specification assigns the fragment `#active` to the currently applicable projected verification method and fragments beginning `#service-` to projected service entries. The native relay API resolves bare Followee DIDs, not DID URLs.

### 3.2 v1 signature suite

Followee v1 defines exactly one signature suite:

| Suite | Followee suite value | COSE `alg` | Public key | Signature |
| --- | ---: | ---: | ---: | ---: |
| Ed25519 | `-19` | `-19` | 32 bytes | 64 bytes |

The value `-19` is the fully specified Ed25519 COSE algorithm assigned by [RFC 9864](https://www.rfc-editor.org/rfc/rfc9864). The deprecated polymorphic COSE value `-8` MUST NOT be accepted.

Implementation note: implementations should inspect the numeric COSE algorithm value actually emitted or accepted by their cryptographic library rather than relying on a constant, type, or routine name. APIs predating RFC 9864 may expose Ed25519 signing under the deprecated polymorphic `EdDSA` value `-8`. A symbol or operation named `Ed25519` does not by itself establish conformance; Followee v1 requires the encoded value `-19`.

A v1 public-key descriptor is the deterministic-CBOR map:

```cbor
{
  0: -19,       / suite /
  1: h'...'      / 32-byte compressed Ed25519 public key /
}
```

Its CDDL type is `public-key` in Appendix A.

Future specifications may define additional suites or descriptor versions. A v1 verifier MUST NOT reinterpret an existing descriptor or DID under a later suite. Unsupported suites produce `unsupportedSuite`; they are not silently approximated.

The one-suite v1 profile is deliberate. Optional P-256 support would make two implementations nominally conforming while unable to exchange some v1 identities, and mandatory P-256 would add ECDSA encoding and malleability rules before the proof of concept needs them. A later descriptor version can add a fully specified P-256 suite for hardware integration without changing any existing DID.

### 3.3 Strict Ed25519 verification

Ed25519 signing and verification MUST follow the pure Ed25519 variant of [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032). In addition, a Followee v1 verifier MUST enforce all of the following:

1. the public key is exactly 32 bytes;
2. the signature is exactly 64 bytes;
3. the public key encoding and the signature's encoded `R` point are canonical;
4. the scalar `S` is less than the Ed25519 group order `L`;
5. the public key decodes to a non-identity point in the prime-order subgroup;
6. `R` decodes to a point in the prime-order subgroup; and
7. the uncofactored verification equation `[S]B = R + [k]A` holds.

An implementation whose general-purpose Ed25519 library accepts non-canonical encodings, small-order public keys, or a broader verification equation MUST add the missing checks or use a strict verification routine. Batch verification, if used, MUST satisfy RFC 8032's randomness requirements and MUST produce the same accept/reject result as individual strict verification.

### 3.4 Domain-separation values

The following byte strings are exact ASCII bytes. The first two include the terminal zero byte shown as `00`; the COSE external AAD does not.

| Purpose | Bytes |
| --- | --- |
| Authority Descriptor hash prefix | `Followee/AuthorityDescriptor/v1` followed by `00` |
| Revocation-key commitment prefix | `Followee/RevocationKey/v1` followed by `00` |
| Identity Record COSE external AAD | `Followee/IdentityRecord/v1` |

Implementations MUST concatenate bytes exactly as defined. They MUST NOT substitute a Unicode look-alike, a length-prefixed string, an omitted terminal zero, or a trailing newline.

## 4. Authority Descriptor and DID creation

### 4.1 Authority Descriptor

The v1 Authority Descriptor is:

```cbor
{
  0: 1,                                  / descriptorVersion /
  1: { 0: -19, 1: h'...32 bytes...' },  / rootKey /
  2: h'...32 bytes...'                   / revocationCommitment /
}
```

No other keys are permitted in a version 1 descriptor. The descriptor MUST use the deterministic encoding rules in Section 6.

### 4.2 Revocation-key commitment

Let `revocationKey` be the canonical v1 `public-key` object for the independently generated revocation public key. Define:

```text
revocationCommitment =
    SHA-256(
        ASCII("Followee/RevocationKey/v1") || 0x00 ||
        deterministicCBOR(revocationKey)
    )
```

The commitment is exactly 32 bytes. It binds both the suite and public-key bytes.

The revocation public key is not carried in ordinary root records. It is revealed only in a root-revoked record. A controller SHOULD validate and test the revocation key before publishing the DID; a commitment to an unusable key creates a DID with no usable recovery path.

### 4.3 Descriptor digest and DID construction

Let `descriptor` be the canonical Authority Descriptor and `descriptorBytes` its deterministic-CBOR encoding. Define:

```text
descriptorDigest =
    SHA-256(
        ASCII("Followee/AuthorityDescriptor/v1") || 0x00 ||
        descriptorBytes
    )

multihash = 0x12 || 0x20 || descriptorDigest

methodSpecificId = "z" || base58btc(multihash)

did = "did:flw:" || methodSpecificId
```

The full 32-byte digest is retained. Followee v1 permits no hash choice by the creator and therefore no hash downgrade surface.

### 4.4 Creation operation

To create a Followee DID, a controller:

1. generates independent Ed25519 root and revocation key pairs using a cryptographically secure random number generator;
2. validates both public keys under Section 3.3;
3. stores the revocation private key under controls materially separate from routine root-key use;
4. constructs the revocation-key commitment and Authority Descriptor;
5. derives the Followee DID under Section 4.3;
6. creates a complete initial Contact Document;
7. creates and signs the first root Identity Record; and
8. publishes that full record to one or more chosen Ingress Relays or domain-hosted current-record endpoints.

No central creation transaction or registration is required. Derivation creates the identifier; publication creates discoverability.

Root and revocation private keys are secret keying material. They MUST NOT appear in the Authority Descriptor, Identity Record, relay API, DID Document, test logs, or diagnostic output. Test-vector private keys in Appendix B are public and MUST NOT be used for any real identity.

## 5. Identity Record data model

### 5.1 Record body

The Identity Record payload is one `record-body` map:

| Label | Name | Type | Required | Meaning |
| ---: | --- | --- | --- | --- |
| `0` | `protocolVersion` | unsigned integer | Yes | MUST equal `1` |
| `1` | `id` | text string | Yes | Canonical Followee DID |
| `2` | `timestamp_ms` | `uint64` | Yes | Ordering value in Unix milliseconds |
| `3` | `authority` | unsigned integer | Yes | `0` = root; `1` = root revoked |
| `4` | `authorityDescriptor` | map | Yes | Complete immutable descriptor |
| `5` | `revocationKey` | `public-key` | Conditional | Present exactly when `authority = 1` |
| `6` | `validUntil_ms` | `uint64` | No | Optional freshness horizon |
| `7` | `contact` | map | Yes | Complete Contact Document |
| `8` | `extensions` | extension map | No | Namespaced record extensions |

For `authority = 0`, label `5` MUST be absent and the record is signed by the descriptor's root key. For `authority = 1`, label `5` MUST be present, MUST reproduce the descriptor's revocation commitment, and the record is signed by that revealed key.

The signed `id` is deliberate redundancy. It provides an early context check and prevents accidental cross-context use, but it is not sufficient proof of binding. A verifier MUST independently hash the carried Authority Descriptor and reproduce the same DID.

Unknown integer labels in the v1 record body are malformed. Extensions MUST be placed under label `8`.

### 5.2 Full-state rule

Every Identity Record contains the entire current Contact Document. Missing fields mean absent fields. They never mean “copy this field from an earlier record.” Followee v1 defines no delta, patch, predecessor-record hash, or history dependency.

### 5.3 Timestamps

`timestamp_ms` is an unsigned 64-bit Unix timestamp in milliseconds. It is an ordering value constrained by the recipient's clock; it is not evidence of the record's actual creation time.

A signer maintaining the greatest non-premature timestamp `previous` known to it computes:

```text
timestamp_ms = max(now_ms, previous + 1)
```

For a first record, it uses `now_ms`. The addition MUST use checked arithmetic. A signer MUST ignore known records whose timestamps exceed its trusted local time when calculating `previous`; it MUST NOT chase a relay's tolerated future timestamp.

A signer without current local state SHOULD resolve through several relays before signing. Signing software MUST serialize simultaneous signing requests for one DID where practical and SHOULD warn when the proposed timestamp leads its trusted clock. A root-revocation signer MUST perform an explicit clock-sanity check before signing.

### 5.4 Future bound

The v1 constant is:

```text
MAX_FUTURE_SKEW_MS = 300000
```

A record is premature for a recipient when:

```text
record.timestamp_ms > recipient.now_ms + MAX_FUTURE_SKEW_MS
```

The addition MUST use overflow-safe comparison. A premature record is not currently admissible. An Ingress Relay SHOULD reject it rather than retain a future queue. A Relay Resolver MUST repeat the check before serving a full record. Every DID Resolver MUST repeat the check during candidate selection.

If a Relay Resolver retains a Full record that has become premature under its current clock—for example after a backwards clock correction—it MUST NOT return that record as Full. It MAY return a usable Ref instead; otherwise it returns the Section 12.3 Error result with `premature`. This serving-time classification does not remove the stored record, alter its `lastUpdated`, or assign a relay-local update number. Once the record is no longer premature, it may again be served as Full if it remains the Relay's current entry.

### 5.5 Optional validity horizon

If present, `validUntil_ms` MUST be greater than or equal to `timestamp_ms`. A record becomes stale when `recipient.now_ms > validUntil_ms`.

Staleness does not invalidate the signature, remove the record from same-authority ordering, or reverse a learned root revocation. A resolver MUST expose staleness to the caller. A stale record MUST NOT establish a verified migration link.

### 5.6 Record extensions

The optional record extension map uses URI strings satisfying Section 7.2 as keys. Each key names a public extension specification. Extension values are limited to the CBOR types in Appendix A and remain subject to all aggregate depth, member, string, and byte limits.

Extension integers are limited to the basic CBOR integer range: unsigned values from `0` through `2^64 - 1`, and negative values from `-2^64` through `-1`. Bignum tags are forbidden.

Core implementations MUST ignore unknown well-formed extensions after enforcing their structural limits. An extension MUST NOT alter DID derivation, signature verification, authority precedence, timestamp ordering, size limits, or any other v1 core rule.

## 6. Deterministic CBOR and COSE envelope

### 6.1 CBOR validity and deterministic profile

Authority Descriptors, public-key objects, Identity Record bodies, Contact Documents, and relay-protocol messages use [RFC 8949](https://www.rfc-editor.org/rfc/rfc8949) CBOR. Conforming decoders enforce three successive layers: CBOR well-formedness and basic validity, the Followee deterministic profile, and the applicable Followee schema. The distinctions in this section determine the wire error classification in Section 15.3.

#### 6.1.1 Well-formedness and basic validity

An encoded object MUST contain exactly one well-formed CBOR data item within its enclosing byte boundary. Truncation, reserved additional-information values, incomplete containers, and trailing bytes where exactly one item is required are not well-formed.

Followee requires basic validity checking under RFC 8949 Sections 5.3 and 5.6:

1. every map MUST contain unique keys under the key-equivalence rules applicable to the Followee data model; and
2. every text string MUST contain valid UTF-8 as defined by [RFC 3629](https://www.rfc-editor.org/rfc/rfc3629).

For this rule, two map keys are equivalent when they denote the same value in RFC 8949's generic data model; different serializations of one value do not create distinct keys. For example, unsigned integer `0` encoded as `00` and the same integer encoded non-minimally as `18 00` are equivalent keys. After an item has passed the deterministic-profile checks in Section 6.1.2, an implementation may equivalently compare the received deterministic encodings of permitted keys, because v1 admits only one such encoding for each key value. CBOR values of different generic data-model types, such as unsigned integer `0` and simple value `false`, are not equivalent merely because a host language compares them as equal.

UTF-8 validation MUST reject overlong encodings, surrogate code points U+D800 through U+DFFF, values above U+10FFFF, incomplete code-point sequences, and every other byte sequence excluded by RFC 3629. No Unicode normalization is applied or implied.

Basic-validity checking is recursive through every CBOR array and map, including unknown extension values and relay-protocol messages. It applies even when the recipient does not otherwise interpret a field. A decoder MUST reject the containing CBOR item rather than discard a duplicate entry, replace invalid text, or expose a partially normalized value.

Recursion stops at byte-string boundaries. A byte string's length and encoding are validated, but its contents are opaque to the enclosing CBOR item and MUST NOT be recursively interpreted as CBOR merely because they happen to contain CBOR bytes. Identity Record bytes carried by a relay `Full` result or change entry are validated separately as candidates under Section 8.1. Failure of one such candidate does not invalidate an otherwise conforming relay response.

Input that is not well-formed CBOR, or is well-formed but fails these basic-validity requirements, produces `invalidCbor`.

#### 6.1.2 Followee deterministic profile

Every basically valid CBOR item then MUST satisfy the core deterministic encoding requirements in Section 4.2.1 of RFC 8949, further restricted as follows:

1. all arrays, maps, text strings, and byte strings use definite lengths;
2. integers, lengths, and tags use their shortest permitted encodings;
3. map entries are ordered by bytewise lexicographic order of their deterministic encoded keys;
4. floating-point values, CBOR simple value `undefined`, and CBOR tags are forbidden inside protocol data;
5. the only permitted tag in a complete Identity Record is the required outer COSE Sign1 tag `18`;
6. bignum tags are forbidden; all integers fit the ranges stated by their schema; and
7. a decoder MUST reject, rather than normalize and accept, a non-deterministic or profile-forbidden encoding.

A basically valid item that violates this subsection produces `nonDeterministicCbor`.

CBOR simple values other than `false`, `true`, `null`, and `undefined` are not admitted by any v1 schema in Appendix A. Their shortest encodings are nevertheless well-formed, basically valid, and deterministic. An otherwise conforming protocol item containing such a simple value therefore passes Sections 6.1.1 and 6.1.2 and produces `schemaViolation` under Section 6.1.3. It MUST NOT be classified as `nonDeterministicCbor` merely because the applicable v1 schema assigns it no meaning. Registration of semantics for that simple value outside Followee, whether before or after publication of this specification, does not alter the closed v1 schemas. This does not alter rule 4: the simple value `undefined` remains forbidden by the Followee profile and produces `nonDeterministicCbor`.

Followee does not use generic CBOR tag validity to classify its envelope. Inner tags are forbidden by the Followee profile and therefore produce `nonDeterministicCbor`. The required outer tag `18` and the structure it encloses are validated under the COSE schema in Section 6.2; a violation uses the specifically assigned error from Section 15.3, or `schemaViolation` where no more specific error applies.

#### 6.1.3 Schema and multiple faults

After an item passes Sections 6.1.1 and 6.1.2, implementations apply the applicable Followee schema and verification rules. They return the specific error assigned by the relevant normative rule, such as `unsupportedSuite`, `invalidDid`, `unsupportedHash`, `recordTooLarge`, or `invalidRevocationKey`. `schemaViolation` is the fallback for a schema or limit failure with no more specific assigned error.

When one input independently violates more than one rule, the exact error is unspecified unless this specification or a normative vector assigns precedence. Implementations MAY reorder cheap independent checks under Section 8.1 and remain conforming if they reject the input with an applicable error. Exact error assertions therefore require fault-isolated inputs.

Every non-negative integer map label written numerically in this specification or in Appendix A denotes a CBOR unsigned-integer key of major type `0` with that exact value. CBOR simple values are different data items: in particular, `false` and `true` MUST NOT be accepted as labels `0` and `1`, even if an implementation language compares those values as equal. Implementations MUST enforce the CBOR key type before applying host-language map lookup or set-equality operations.

The bytes received on the wire are the bytes verified. A verifier MUST NOT decode a non-deterministic body and then re-encode it into a different body for signature verification.

### 6.2 COSE Sign1 profile

A complete Identity Record is a tagged COSE Sign1 structure as defined by [RFC 9052](https://www.rfc-editor.org/rfc/rfc9052):

```cbor
18([
  h'a10132',    / protected header bytes: {1: -19} /
  {},           / empty unprotected header map /
  h'...',       / attached deterministic-CBOR record body /
  h'...'        / 64-byte Ed25519 signature /
])
```

The following restrictions are mandatory:

1. CBOR tag `18` MUST be present;
2. the protected header map MUST contain exactly `{1: -19}`;
3. its encoded protected-header byte string MUST therefore equal `a10132` hexadecimal;
4. the unprotected header map MUST be empty;
5. the payload MUST be attached and contain exactly one deterministic `record-body` item;
6. the signature MUST be exactly 64 bytes; and
7. no trailing bytes are permitted after the tagged COSE object.

The external AAD is the exact byte string `Followee/IdentityRecord/v1`. The COSE `Sig_structure` is therefore:

```cbor
[
  "Signature1",
  h'a10132',
  h'466f6c6c6f7765652f4964656e746974795265636f72642f7631',
  recordBodyBytes
]
```

The Ed25519 signature is computed over the deterministic CBOR encoding of that `Sig_structure`.

### 6.3 Body digest

Participants compute:

```text
bodyDigest = SHA-256(recordBodyBytes)
```

The digest is used for duplicate detection, local metadata, version identifiers, and equal-timestamp ordering. It excludes the COSE tag, headers, and signature. The digest is not transmitted inside the signed body and has no authority independent of the body bytes from which it is computed.

### 6.4 Media types

The HTTP profile uses existing generic media types:

| Object | Media type |
| --- | --- |
| Complete tagged Identity Record | `application/cose` |
| Followee relay API CBOR request or response | `application/cbor` |
| DID Core JSON projection | `application/did+json` |
| DID Core JSON-LD projection | `application/did+ld+json` |
| WebFinger response | `application/jrd+json` |

Protocol meaning for generic CBOR and COSE types is established by the endpoint and this specification. Implementations MUST NOT infer that an arbitrary `application/cose` object is a Followee Identity Record without applying the complete profile.

## 7. Contact Document

### 7.1 Contact fields

The Contact Document is one bounded map:

| Label | Name | Type | Maximum |
| ---: | --- | --- | ---: |
| `0` | `displayName` | text | 256 UTF-8 bytes |
| `1` | `summary` | text | 2,048 UTF-8 bytes |
| `2` | `avatar` | URI satisfying Section 7.2 | 2,048 UTF-8 bytes |
| `3` | `alsoKnownAs` | array of URIs satisfying Section 7.2 | 32 entries |
| `4` | `services` | array of service maps | 64 entries |
| `5` | `migration` | migration map | one predecessor and one successor |
| `6` | `extensions` | extension map | aggregate limits apply |

Every field is optional, and an empty Contact Document is valid. The Contact Document is nevertheless always present in an Identity Record. Binary avatars, posts, attachments, feed contents, and other large objects MUST NOT be embedded; they are linked by URI.

`alsoKnownAs` entries are signed claims, not proofs that an external authority assigned a name. Domain-qualified handle claims require Section 10 verification.

### 7.2 URI requirements

Every field described as a URI MUST match the `URI` production in Section 3 of [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986), encoded as a CBOR text string. This production requires a scheme and permits its optional query and fragment components. A `relative-ref`, including a network-path reference, absolute-path reference, relative-path reference, query-only reference, or fragment-only reference, is malformed. For example, `https://example.com/profile#about` and `did:web:example.com#key-1` are valid URI forms, while `/profile`, `?view=full`, and `#about` are not. Scheme comparison and all other component comparison follow the applicable URI specification; Followee performs no general URI canonicalization.

RFC 3986 uses ABNF, whose quoted string literals are case-insensitive under [RFC 5234](https://www.rfc-editor.org/rfc/rfc5234). Consequently, both lowercase `v` and uppercase `V` introduce the `IPvFuture` alternative in an IP-literal host. Implementations MUST NOT reject an otherwise valid `IPvFuture` address merely because that letter is uppercase.

Clients MUST treat dereferenced URI content as untrusted external content. A signature over an avatar or service URI does not sign the bytes later served by that URI.

### 7.3 Service entries

A service entry is:

| Label | Name | Required | Rule |
| ---: | --- | --- | --- |
| `0` | `id` | Yes | 1–256 ASCII `unreserved` characters; unique within the document |
| `1` | `type` | Yes | Initial type token or URI satisfying Section 7.2 |
| `2` | `endpoint` | Yes | URI satisfying Section 7.2 |
| `3` | `mediaType` | No | RFC 6838 type and subtype, maximum 256 ASCII bytes |
| `4` | `label` | No | UTF-8 text, maximum 256 bytes |
| `5` | `language` | No | Well-formed RFC 5646 language tag, maximum 64 ASCII bytes |
| `6` | `rel` | No | RFC 8288 `reg-rel-type` or URI satisfying Section 7.2, maximum 256 bytes |

`mediaType` MUST consist exactly of an RFC 6838 `type-name`, the `/` character, and an RFC 6838 `subtype-name`. Each name MUST satisfy the `restricted-name` grammar in Section 4.2 of that RFC. Media-type parameters are not permitted in this field.

`language` MUST satisfy the `Language-Tag` ABNF in Section 2.1 of RFC 5646, including its fixed grandfathered productions. Verification is case-insensitive as required by that RFC, but the exact signed text is retained. A verifier MUST NOT require subtags to appear in the IANA Language Subtag Registry, replace deprecated subtags with preferred values, or otherwise canonicalize the field.

The token form of `rel` MUST satisfy RFC 8288 `reg-rel-type` exactly: one lowercase ASCII letter followed by zero or more lowercase ASCII letters, digits, `.`, or `-`. Any other relation value MUST be a URI satisfying Section 7.2. A verifier MUST NOT require a token to appear in the IANA Link Relations registry.

These fields are verified against fixed syntax only. Media-type, language-subtag, and link-relation registry contents are not inputs to Identity Record validity; a registry update MUST NOT change whether existing signed bytes verify.

The initial case-sensitive service-type tokens are:

```text
Website
Feed
Profile
ActivityPub
Messaging
Repository
Payment
Other
```

A type outside this list MUST be a URI satisfying Section 7.2 and naming its specification. Service array order is presentation order; a client may reorder or filter it.

### 7.4 Reciprocal migration fields

The migration map may contain:

| Label | Name | Meaning |
| ---: | --- | --- |
| `0` | `predecessor` | The one Followee DID from which this DID claims to continue |
| `1` | `successor` | The one Followee DID to which this DID invites followers to move |

Each value MUST be a canonical Followee DID different from the containing record's DID. Lists are forbidden. Both fields may appear when the DID is one link in a longer chain.

If the migration map is present, it MUST contain at least one of these fields and MUST contain no other core labels.

Given DIDs A and B, A → B is a verified migration link only if:

1. A's winning fresh record contains `successor = B`;
2. B's winning fresh record contains `predecessor = A`; and
3. both records pass descriptor binding, strict signature verification, time admission, and the resolver's sticky authority-state rules.

One field alone is an unverified directional self-claim. Relays MUST treat migration fields as opaque Contact Document data. They MUST NOT derive authority state, redirect resolution, or rewrite references from them.

A verified migration link does not transfer authority, merge DIDs, retire either DID, prove civil identity, or replace a following-list entry. Clients MAY offer a deliberate re-follow action and MUST NOT act automatically.

### 7.5 Contact extensions

Contact extensions use the same Section 7.2 URI-keyed extension map as record extensions. Unknown well-formed fields are ignored. Extensions cannot alter the core interpretation of `alsoKnownAs`, `services`, or `migration`.

## 8. Verification, authority state, and ordering

### 8.1 Full-record verification algorithm

Given expected Followee DID `target`, complete envelope bytes `candidate`, recipient time `now_ms`, and local sticky authority state, a Record Verifier MUST perform the following checks. It may reorder cheap independent checks for denial-of-service resistance, but the final result MUST be equivalent.

1. Reject `candidate` if it exceeds 16 KiB.
2. Parse exactly one tagged COSE Sign1 object within the depth and member limits, applying the well-formedness, basic-validity, and deterministic-profile classifications in Section 6.1.
3. Require the exact COSE profile in Section 6.2.
4. Parse the payload as one basically valid, deterministic `record-body`; reject trailing bytes and recursively enforce Section 6.1 even in unknown extension values.
5. Require `protocolVersion = 1` and the exact v1 schema.
6. Parse `target` under Section 3.1, returning `invalidDid` for malformed syntax or encoding and `unsupportedHash` for a structurally well-formed but unsupported hash profile.
7. Require the body `id` to equal `target` byte for byte; otherwise return `identityBindingMismatch`.
8. Validate the Authority Descriptor schema and deterministic encoding.
9. Recompute the descriptor digest and require it to reproduce `target`; otherwise return `identityBindingMismatch`.
10. Enforce the authority-dependent presence or absence of `revocationKey`.
11. For `authority = 0`, select the descriptor root key.
12. For `authority = 1`, recompute the revocation-key commitment, require equality, and select the revealed key.
13. Require the selected key suite to equal the protected COSE algorithm.
14. Perform strict Ed25519 verification over the COSE `Sig_structure`.
15. Validate the Contact Document and every aggregate limit.
16. Require `validUntil_ms >= timestamp_ms` when `validUntil_ms` is present.
17. Classify the record as premature or time-admissible under Section 5.4.
18. Compute the body digest from the received payload bytes.
19. Apply sticky authority-state exclusion and record ordering.
20. Classify the selected result as fresh or stale.

An implementation MUST NOT allow a valid signature to bypass descriptor binding, schema limits, or authority-state rules.

The outer COSE item and attached record-body item have separate CBOR boundaries. The payload byte string is opaque while the outer COSE structure is parsed, then its contents are validated as the record body in step 4. An invalid record body invalidates that candidate; when the candidate was carried in an otherwise valid relay response, it does not retroactively invalidate the relay-response wrapper or neighbouring candidates.

Steps 7 and 9 deliberately use the same error. The complete identity-binding invariant is `body id = target = DID(authorityDescriptor)`; `identityBindingMismatch` reports any failure of that invariant. Consequently, an unchanged internally consistent envelope checked against another target, a re-signed body-`id` mutation checked against the original target, and that same mutation checked against the mutated target all fail with `identityBindingMismatch`, regardless of the permitted ordering of independent checks. The broader name is deliberate: the Authority Descriptor may be correct when only the signed body `id` differs from the requested target.

### 8.2 Authority precedence

The two authority values are:

```text
0 = Root
1 = RootRevoked
```

Any signature-valid, descriptor-bound, non-premature RootRevoked record has absolute precedence over every Root record, regardless of timestamp. Upon observing one, a relay or client MUST persist sticky `RootRevoked` state for that DID and MUST NOT subsequently select, admit as current, or automatically restore a Root record while that state is retained.

A stale RootRevoked record still activates the transition. `validUntil_ms` governs Contact Document freshness, not authority expiry.

The first RootRevoked record is a complete current record. All Root records—past, current, future, seen, or not yet seen—become ineligible. There is no “last good Root record” fallback.

### 8.3 Ordering within one authority state

Within the applicable authority state:

1. the greater `timestamp_ms` wins; then
2. at equal timestamps, the lexicographically lower 32-byte body digest wins.

Digest comparison treats each digest as 32 unsigned bytes from left to right. The signature is excluded. A relay stores only the winner, not a conflict set.

If a lower-digest equal-time candidate replaces the current record, that replacement is a relay-local map change and receives a new relay-local update number.

### 8.4 Duplicate and losing records

An exact body digest match is a duplicate even if envelope bytes differ. Under the strict deterministic Ed25519 profile, conforming envelopes for the same body and key should also be identical, but duplicate detection relies on the body digest.

A valid losing record MUST NOT replace current state and MUST NOT increment the relay-local update number. A Relay MAY discard it immediately.

### 8.5 Sticky-state loss

Sticky RootRevoked state is local knowledge, not a global revocation oracle. A participant that drops the entire DID entry or restores a snapshot predating revocation becomes a fresh observer for omitted state. A malicious relay can withhold a revocation from such a participant.

A client SHOULD retain sticky RootRevoked state independently of cached full-record expiry or eviction. A relay SHOULD preserve RootRevoked entries preferentially under Section 11.3.

## 9. DID method operations and DID Document projection

### 9.1 Create

Creation is the local derivation and first publication process in Section 4.4. There is no privileged registry transaction.

### 9.2 Resolve

A DID Resolver accepts a bare canonical Followee DID and optional resolution policy. It:

1. checks locally cached validated state and sticky authority state;
2. queries one or more configured Relay Resolvers;
3. follows relay references within shared budgets;
4. verifies every full candidate independently;
5. selects the winning record under Section 8;
6. projects the selected record into the requested representation; and
7. returns DID resolution metadata, a DID Document, and DID Document metadata.

Absence from any finite set of relays means only “not found through this resolution operation.” It is not proof that the DID was never created or is unavailable elsewhere.

### 9.3 Update

An update is publication of another complete Identity Record signed by the key applicable to its authority state. A Root update uses `authority = 0`. Activation and subsequent use of the revocation key use `authority = 1`.

Followee defines no patch operation. Relay admission is not part of authority: any party may transport an already signed record to an Ingress Relay.

### 9.4 Root revocation

To revoke the root, the controller creates a complete `authority = 1` record, includes the precommitted revocation public key, signs with the corresponding private key, and publishes it broadly. Once learned, the transition is irreversible.

Root revocation is a restricted update, not DID deactivation and not arbitrary key rotation. The revocation key becomes the permanent active key for the remaining life of the DID.

### 9.5 Deactivation

Followee v1 does not support protocol-level DID deactivation. A controller may publish an empty or explanatory Contact Document, may remove services, and may publish reciprocal migration fields, but none of these changes deactivates the DID or authorises clients to delete a following relationship.

This explicit absence satisfies the DID Core requirement that a method specify how deactivation works or state that it is not possible.

### 9.6 DID Document JSON projection

A resolver producing `application/did+json` MUST construct a JSON object from the winning record. The object contains:

1. `id`, equal to the canonical Followee DID;
2. one `verificationMethod` for the applicable root or revealed revocation key;
3. `alsoKnownAs`, if non-empty;
4. `service`, if non-empty; and
5. `followeeContact`, preserving the complete Followee-native Contact Document in the JSON mapping below.

The verification method is:

```json
{
  "id": "did:flw:...#active",
  "type": "JsonWebKey2020",
  "controller": "did:flw:...",
  "publicKeyJwk": {
    "kty": "OKP",
    "crv": "Ed25519",
    "x": "<unpadded base64url of the 32 public-key bytes>"
  }
}
```

The projection MUST NOT include private JWK members or an `alg` value. The active key is exposed as verification material, but Followee does not assign DID Core authentication, assertion, key-agreement, capability-invocation, or capability-delegation relationships to it.

Each native service projects to:

```json
{
  "id": "<did>#service-<native-service-id>",
  "type": "<projected-service-type>",
  "serviceEndpoint": "<native-endpoint>"
}
```

An initial native type token projects to `https://w3id.org/followee/service/` followed by that exact token; for example, `Feed` projects to `https://w3id.org/followee/service/Feed`. A native absolute-URI service type projects unchanged. This prevents Followee's convenient native tokens from colliding with unrelated DID Core service-type names.

The `followeeContact` object uses the text field names in Section 7, preserves service metadata, uses arrays in native order, encodes extension CBOR byte strings as unpadded base64url objects of the form `{"bytes":"..."}`, and represents extension integer map keys as decimal strings prefixed with `#`. This object is a derived representation, not separately signed JSON.

For example, the native Contact Document in Appendix B projects in part as:

```json
"followeeContact": {
  "displayName": "Alice Example",
  "summary": "Writer",
  "alsoKnownAs": ["acct:alice@example.com"],
  "services": [{
    "id": "feed",
    "type": "Feed",
    "endpoint": "https://alice.example/feed.xml",
    "mediaType": "application/atom+xml",
    "label": "Writing"
  }]
}
```

Migration MUST appear only inside `followeeContact.migration`, with `predecessor` and `successor` retaining their directional meanings. A resolver MUST NOT project migration values into `alsoKnownAs`, `canonicalId`, or `equivalentId`.

For `application/did+ld+json`, the resolver additionally includes:

```json
"@context": [
  "https://www.w3.org/ns/did/v1",
  "https://w3id.org/security/suites/jws-2020/v1",
  "https://w3id.org/followee/v1"
]
```

The proposed protected Followee context MUST define `followeeContact` and its nested terms before JSON-LD conformance is claimed. Until that context is published at its persistent URI and registered where required, implementations MUST advertise `application/did+json` and MUST NOT claim conforming `application/did+ld+json` output.

### 9.7 DID resolution metadata

On success, resolution metadata SHOULD include:

```json
{
  "contentType": "application/did+json",
  "followee": {
    "authority": "root",
    "timestampMs": 1785589200123,
    "bodyDigest": "<unpadded base64url>",
    "stale": false,
    "relaysConsulted": 3
  }
}
```

`authority` is `root` or `rootRevoked`. `timestampMs` is an ordering value and MUST NOT be relabelled as a creation time. `relaysConsulted` is local diagnostic metadata, not an assurance level.

DID Document metadata SHOULD include a `versionId` formed as:

```text
<authority-integer>:<decimal-timestamp-ms>:<lowercase-body-digest-hex>
```

It MUST omit `created` and `updated`, because the record timestamp does not prove either fact. It MUST omit `deactivated`, because Followee has no deactivation operation.

## 10. Human-readable handle discovery

### 10.1 Handle form

The v1 user-facing handle form is:

```text
local@domain
```

For interoperable v1 lookup:

1. `local` contains 1–64 ASCII characters from `ALPHA`, `DIGIT`, `.`, `_`, or `-`;
2. `local` is case-sensitive at the protocol layer;
3. `domain` is a valid DNS domain transformed to its lowercase ASCII IDNA form under [IDNA2008](https://www.rfc-editor.org/rfc/rfc5890); and
4. the canonical WebFinger resource is `acct:local@domain`.

A handle authority may offer aliases or case-insensitive user interfaces, but each returned mapping is verified for the exact canonical resource requested. A handle authority SHOULD NOT assign ASCII-case variants of one local part under one domain to different Followee DIDs. It SHOULD either reject the later variant or map every accepted variant as an alias of the same DID. Lookup remains exact: each successful response still names the exact canonical `acct:` resource requested. Handles that require a broader email local-part syntax may be supported by a later profile.

### 10.2 WebFinger mapping

The handle authority is the HTTPS origin of `domain`. A client requests:

```http
GET /.well-known/webfinger?resource=acct%3Aalice%40example.com HTTP/1.1
Host: example.com
Accept: application/jrd+json
```

The response follows [RFC 7033](https://www.rfc-editor.org/rfc/rfc7033). The proposed Followee relation URI is:

```text
https://w3id.org/followee/rel/did
```

Example:

```json
{
  "subject": "acct:alice@example.com",
  "links": [{
    "rel": "https://w3id.org/followee/rel/did",
    "href": "did:flw:zQm..."
  }]
}
```

A successful mapping requires:

1. a valid HTTPS connection for the requested domain;
2. a successful WebFinger response of type `application/jrd+json`;
3. `subject` exactly equal to the requested canonical `acct:` URI;
4. exactly one link with the Followee DID relation; and
5. a canonical v1 Followee DID in `href`.

Zero or multiple matching links are not a verified mapping. Redirects MUST remain HTTPS and MUST comply with the client's WebFinger security policy. Ordinary public WebFinger endpoints SHOULD return `Access-Control-Allow-Origin: *` for browser clients.

### 10.3 Optional current-record bootstrap

A WebFinger response MAY additionally include:

```text
rel  = https://w3id.org/followee/rel/record
type = application/cose
href = an HTTPS URL
```

The URL returns one complete Identity Record for the mapped DID. This is a bootstrap publisher, not trusted verification. The client MUST fetch within ordinary byte and deadline budgets and MUST perform full local verification. A direct record endpoint does not provide DID-only availability after the domain disappears.

### 10.4 Inverse handle verification

An `acct:` URI inside `alsoKnownAs` is only a claim until the named domain's current WebFinger response maps that exact resource back to the same Followee DID. Relays MUST NOT transmit or derive a `verified` flag. Clients SHOULD verify claimed handles lazily when displaying or relying upon them and cache the result only for a bounded, domain-policy TTL.

Existing followers retain the Followee DID when a handle disappears or changes. The former handle authority need not redirect indefinitely.

## 11. Relay data model

### 11.1 Partial current map

A Relay maintains a bounded partial map conceptually equivalent to:

```text
Followee DID -> {
  entry: Full(IdentityRecord) | Ref(RelayIndex, DirectoryGeneration),
  authorityState: Unknown | Root | RootRevoked,
  lastUpdated: RelayLocalUpdateNumber
}
```

A Relay is not required to store every DID. Admission, sponsorship, payment, quotas, and eviction are local operator policy.

`RootRevoked` may be established only by locally verifying a full RootRevoked record. A received reference never establishes authority state. Converting a full record to a reference MUST preserve already learned RootRevoked state.

### 11.2 Full and reference tiers

A Relay may maintain separate full-record and reference capacities. A reference contains routing information only. It MUST NOT contain or imply a remote validity assertion, remote authority state, verified-handle status, or proof of completeness.

When a reference-only entry later receives a full candidate, the Relay validates it normally. If the Relay retained ordering metadata from its former full record, it SHOULD use that metadata to prevent a same-authority rollback. If it did not retain such metadata, it treats the full candidate as newly observed while still enforcing any retained RootRevoked state.

### 11.3 Eviction

Within its own quotas, a Relay SHOULD prefer:

1. converting a RootRevoked full entry to a usable reference;
2. retaining the entry's sticky RootRevoked bit; and
3. dropping the entire RootRevoked entry only after less security-sensitive candidates have been considered.

This is a retention preference, not an unbounded storage obligation. Dropping the entire entry drops its local sticky state; later re-admission begins as a fresh observation.

### 11.4 Relay directory

Each Relay publishes a bounded directory assigning unsigned integer indices to known relays. An index is meaningful only with the publishing Relay's current 16-byte `directoryGeneration`.

Indices SHOULD remain stable within a generation and MUST NOT be silently reused for another endpoint within the same generation. A mapping change that reuses or changes existing indices requires a freshly generated cryptographically random generation value. Generations are opaque equality tokens and have no ordering semantics.

### 11.5 Lazy path compression

If Relay A asks Relay B for a DID and B returns a reference to Relay C, A MAY store a direct reference to C after resolving B's directory entry. A need not fetch a full record merely to compress the path. If C later refers to D, clients or relays may continue within their traversal budgets.

Misdirection can reduce availability but cannot make an invalid record pass local verification.

## 12. Mandatory HTTP/CBOR relay profile

### 12.1 Base URI and transport

A Relay advertises an HTTPS base URI ending in `/`. The v1 operation paths are relative to that base:

| Operation | Method and relative path | Request | Response |
| --- | --- | --- | --- |
| Relay information | `GET v1/info` | none | `application/cbor` |
| Batch resolve | `POST v1/resolve` | `application/cbor` | `application/cbor` |
| Relay directory | `GET v1/directory` | none | `application/cbor` |
| Publish | `POST v1/publish` | `application/cose` | `application/cbor` |
| Current-state changes | `POST v1/changes` | `application/cbor` | `application/cbor` |

Public read operations MUST be usable without ambient authentication and SHOULD return `Access-Control-Allow-Origin: *`. Ingress publication may require authentication, payment, or another local policy. HTTPS authenticates the endpoint, not the identity record; every full record still requires cryptographic verification.

Equivalent transports MAY be implemented, but an implementation claiming the v1 HTTP profile MUST expose the operations required by its role at these paths.

All API CBOR messages MUST satisfy Section 6.1. A v1 request parser MUST reject unknown top-level integer labels rather than guess their semantics. A response parser MUST ignore unknown labels only when a negotiated later protocol version defines them; under protocol version `1`, unknown core labels are a schema violation.

CBOR well-formedness, basic validity, and deterministic-profile validation applies to each outer relay request and response as a complete item. Byte strings within that wrapper remain opaque under Section 6.1.1. In particular, a candidate Identity Record carried as a Full byte string is not part of wrapper validity and is verified separately under Section 8.1.

A CBOR-layer fault in an outer request means that protocol item processing did not begin. The Relay MUST reject the complete request with HTTP `400` and MUST NOT return per-item results. By contrast, a valid batch request containing an invalid DID is protocol-level input: the Relay returns HTTP `200` and an aligned per-DID Error result under Section 12.3.

A client receiving an outer response that is not well-formed, basically valid, deterministic, or schema-conforming MUST reject that complete relay response. It MUST NOT interpret rejection as Absent for any requested DID. Opaque Full candidates inside an accepted response are handled independently and do not affect wrapper acceptance.

### 12.2 Relay information

`GET v1/info` returns one `relay-info` object containing:

| Label | Meaning |
| ---: | --- |
| `0` | Protocol version, `1` |
| `1` | Stable 16-byte relay instance identifier |
| `2` | Capability bit mask |
| `3` | Supported protocol versions |
| `4` | Supported signature suites |
| `5` | Advertised limits map |
| `6` | Current 16-byte cursor generation |
| `7` | Current 16-byte directory generation |
| `8` | Canonical HTTPS base URI |

Capability bits are:

```text
0x01 Relay Resolver
0x02 current-state synchronization
0x04 ingress publication
0x08 optional history
```

Unknown capability bits MUST be ignored. Every Relay Resolver sets `0x01`; every Relay additionally sets `0x02`.

A v1 implementation MUST include protocol version `1` and signature suite `-19` in their respective arrays. It MAY also advertise later versions or suites that it implements under their own specifications.

The relay instance identifier identifies one relay for cycle detection and cache scoping. It is not a signing key, identity authority, or permanent operator identity.

The advertised limits map is:

| Label | Meaning |
| ---: | --- |
| `0` | Maximum complete Identity Record bytes |
| `1` | Maximum resolve-request DID count |
| `2` | Maximum resolve-response bytes |
| `3` | Maximum `changes` item count |
| `4` | Maximum `changes` response bytes |

### 12.3 Batch resolve

The request is:

```cbor
{
  0: 1,                   / protocol version /
  1: [ "did:flw:..." ]   / one or more DIDs /
}
```

The response is:

```cbor
{
  0: 1,                   / protocol version /
  1: h'...16 bytes...',   / directoryGeneration /
  2: [ result, ... ]      / one result per requested DID, same order /
}
```

Each result is exactly one of:

```cbor
{ 0: 0, 1: h'...' }       / Full: complete application/cose bytes /
{ 0: 1, 1: 42 }           / Ref: relay index in response generation /
{ 0: 2 }                  / Absent /
{ 0: 3, 2: 2 }            / Error: error code /
```

A Full response carries the exact admitted complete envelope bytes as a candidate, not a validity assertion. A Relay MUST NOT edit, annotate, or inject data into those bytes. A Ref result is interpreted only with the response's directory generation. An Absent result is local absence, not global non-existence.

The request DID array MAY contain the same DID more than once. Each occurrence counts separately against the batch limit and has its own position in the response. A Relay MUST NOT deduplicate, reorder, combine, or omit occurrences. The response result array MUST contain exactly as many entries as the request DID array, in the same order. A client MUST reject the complete relay response if the counts differ.

Each result is interpreted against the DID at the same request index. Full-result bytes are opaque during response-wrapper validation and are subsequently verified under Section 8.1 with that indexed DID as `target`. If one Full candidate fails, the client discards only that candidate and continues processing every other result at its original index. It MUST NOT shift later results, invalidate the accepted wrapper, or treat the failed candidate as Absent. A Ref is followed for the DID at its original request index.

An Error result reports a per-DID error from Section 15.3 while preserving batch alignment. In particular, a Relay Resolver that retains a Full record but cannot serve it because its present clock classifies it as premature returns `{ 0: 3, 2: 10 }` unless it returns a usable Ref. It MUST NOT use Absent for that condition. A per-DID Error result is diagnostic information from that Relay, not an assurance that other Relays will report the same condition.

If the Relay's directory generation changes before the client obtains the matching directory, the reference is unusable. The client MUST refetch or repeat resolution; it MUST NOT interpret the same integer index under the newer generation.

A conforming Relay Resolver MUST accept batches of at least 64 DIDs when the request and response remain within 1 MiB. It MAY accept up to the protocol hard maximum of 256 DIDs. It MAY return `responseTooLarge` for a requested batch whose results cannot fit its advertised bound; clients then split the batch.

### 12.4 Directory

`GET v1/directory` returns:

```cbor
{
  0: 1,
  1: h'...16-byte directory generation...',
  2: [
    {
      0: relayIndex,
      1: h'...16-byte relay id...',
      2: "https://relay.example/followee/",
      3: capabilityBits
    }
  ]
}
```

The directory is capped at 4,096 entries and 1 MiB encoded. Directory endpoints are hints. Clients MUST validate HTTPS URIs, reject unsupported schemes, detect relay-ID and endpoint cycles, and apply network policy before connecting.

### 12.5 Publication

An Ingress Relay accepts one complete Identity Record at `POST v1/publish`. It applies the verification and ingress algorithm in Section 13.1 before the record can affect current state.

The response is:

```cbor
{
  0: 1,
  1: status,
  ? 2: errorCode
}
```

Status values are:

```text
0 admitted and current
1 valid but no current-state change
2 rejected
```

“Admitted and current” means current at that Relay only. It makes no propagation, retention, payment, or global-availability promise.

### 12.6 Current-state changes

The request is:

```cbor
{
  0: 1,
  1: cursor-or-null,
  2: itemLimit,
  3: byteLimit
}
```

The response is:

```cbor
{
  0: 1,
  1: status,
  ? 2: [ changeEntry, ... ],
  ? 3: nextCursor,
  ? 4: hasMore,
  ? 5: directoryGeneration,
  ? 6: errorCode
}
```

Status `0` means success, status `1` means `ResetRequired`, and status `2` means another error identified by `errorCode`. On success, entries, `nextCursor`, `hasMore`, and `directoryGeneration` are required and `errorCode` MUST be absent. On reset, entries, `nextCursor`, `hasMore`, `directoryGeneration`, and `errorCode` MUST all be absent; status `1` is the sole v1 wire encoding of `ResetRequired`, and the response therefore contains exactly labels `0` and `1`. On status `2`, `errorCode` is required and entries, `nextCursor`, `hasMore`, and `directoryGeneration` MUST be absent. A change entry is:

```cbor
[
  "did:flw:...",
  { 0: 0, 1: h'...' } / { 0: 1, 1: relayIndex },
  lastUpdated
]
```

The cursor is an opaque byte string of at most 128 bytes. A null cursor requests a bounded initial enumeration. Entries are ordered by increasing `lastUpdated` and include only current tuples whose `lastUpdated` lies after the supplied cursor position. If one DID changed three times, only its current tuple is returned.

`itemLimit` and `byteLimit` MUST both be greater than zero and no greater than the Relay's advertised or protocol hard maximum.

On success, the number of returned entries MUST NOT exceed `itemLimit`. A receiver that obtains more entries MUST reject the complete response and MUST NOT use its `nextCursor`.

`nextCursor` advances through exactly the returned range. If no entry is returned, it represents the supplied position. A Relay MUST NOT advance past omitted eligible entries. If the next single entry cannot fit within `byteLimit`, it returns `responseTooLarge` rather than an unchanged success cursor loop.

`hasMore` reports whether further entries were known when the response was assembled. Concurrent updates may create later work after `hasMore = false`.

### 12.7 Cursor generation and reset

Conceptually, a cursor identifies:

```text
(cursorGeneration, relayLocalUpdateNumber)
```

The encoding is Relay-local and opaque. A Relay chooses a new random 16-byte generation when cursor positions become incompatible, including after an incompatible restore, renumbering, or approaching update-counter exhaustion.

On generation reset, the Relay MUST ensure that an initial null-cursor scan can enumerate every retained current entry. It may preserve compatible per-entry numbers or assign fresh numbers to all current entries. A peer receiving `ResetRequired` discards only that peer cursor and performs a new bounded enumeration; it does not discard independently verified identity state.

## 13. Relay admission and synchronization semantics

### 13.1 Ingress algorithm

For a full candidate, an Ingress Relay:

1. enforces cheap request, quota, and envelope-size limits;
2. performs the full verification algorithm in Section 8.1;
3. rejects or defers a premature record;
4. drops a Root record without state change if local authority state is RootRevoked;
5. persists a newly observed valid RootRevoked transition before acknowledging admission;
6. compares timestamp and body digest within the applicable authority state;
7. returns no-change for a duplicate or losing record; and
8. for a winning record, atomically replaces current state, preserves authority state, and assigns a new relay-local update number.

Signature verification MUST complete before candidate bytes enter the current map, appear in `v1/changes`, or are served as Full. A bounded asynchronous quarantine is permitted, but quarantine is not relay state.

There is no transmitted `verified` flag, validation certificate, or relay assurance field.

### 13.2 Update-number rule

A Relay increments its update number if and only if admitted current identity state changes. These events increment it:

- a greater timestamp replaces current state;
- a lower body digest wins at the current timestamp; or
- a valid RootRevoked record creates the irreversible authority transition.

These events do not increment it:

- invalid input;
- a duplicate;
- a losing record;
- a Root record received after RootRevoked; or
- storage housekeeping that merely converts a Full entry to a Ref.

A Relay may maintain a separate storage-generation mechanism for housekeeping changes. It MUST NOT present storage conversion as a newly signed identity update.

### 13.3 Synchronization receiver

A receiving Relay treats each Full change entry as untrusted candidate bytes and runs its own ingress algorithm. It treats each Ref as an unverified routing hint and MUST NOT import the sender's authority state. A receiver may path-compress a reference after consulting the sender's directory. An unusable Ref is discarded without identity-state or local-update-number change.

After accepting a well-formed, basically valid, deterministic, and schema-conforming success response, the receiver processes each Full candidate independently. Rejection or deferral affects only that candidate. It MUST NOT prevent processing of other entries, alter another DID's stored entry or sticky authority state, or increment the local update number.

The receiver MUST store and use the returned opaque `nextCursor` regardless of how many Full candidates it admitted or Ref hints it retained, including zero. Candidate rejection or an unusable Ref MUST NOT prevent cursor advancement, cause the same range to be requested again, or cause the receiver to derive a replacement cursor from entry contents. This rule does not apply when the outer response itself is rejected, because such a response supplies no trustworthy cursor.

A locally premature candidate also MUST NOT stall the peer cursor. The receiver MAY retain it in a bounded pending area or pull it again later, but v1 imposes no pending-cache or retry obligation. If the sender's current tuple never changes, the candidate may not appear again in that incremental stream after the receiver advances.

Relay histories need not be consulted. Synchronization exchanges current state, not an event chain.

### 13.4 Pull policy

Peer choice, polling frequency, identities of interest, admission economics, and synchronization scope are operator policy. A Relay may synchronize continuously, on demand, only for sponsored identities, only for recently requested identities, or not at all.

The protocol provides a sharing mechanism; it does not require altruism.

### 13.5 Restore behaviour

A backup SHOULD capture each entry's current payload, authority state, and update metadata atomically. After restoring an older snapshot, a Relay MUST reset cursor generation. It SHOULD mark restored Root or Unknown entries for refresh and SHOULD re-resolve them through several peers before serving a restored Root full record.

This reduces accidental resurrection. It cannot prove that no withheld RootRevoked record exists.

## 14. Client resolution and migration presentation

### 14.1 Reference traversal

A following list stores canonical Followee DIDs as its durable keys. It MAY cache display names, handles, avatars, selected records, and service links, but those values are replaceable presentation state and MUST NOT substitute for the DID.

A client begins with configured relays, accepts Full candidates for local verification, and follows Ref results by resolving the corresponding directory entry. It MUST share aggregate limits across the complete user operation.

An Absent or Error result yields neither a Full candidate nor a reference target. It consumes the same applicable contacted-relay, response-byte, concurrency, and deadline budgets as any other response. A client MUST NOT treat either result from one Relay as a conclusive answer for the DID or as a reason to terminate resolution while an unqueried Relay already selected for the operation remains and the shared operation budgets permit contacting it. Neither result changes locally cached identity state or sticky authority state.

An Error result is diagnostic information about the reporting Relay only. In particular, `Error(premature)` reflects that Relay's clock and serving decision. A client MUST NOT import that classification into another candidate, defer a DID because of it, or use it to reject a Full candidate obtained from the same or another Relay. Every Full candidate is verified and classified independently under Sections 5.4 and 8.1 using the client's own `now_ms` and local sticky authority state.

A rejected outer relay response is neither Absent nor Error and yields no candidates or reference targets. It consumes the same applicable contacted-relay, response-byte, concurrency, and deadline budgets as any other attempted response, changes no cached identity state or sticky authority state, and MUST NOT terminate resolution while an unqueried Relay already selected for the operation remains and the shared budgets permit contacting it. When an accepted response contains an invalid opaque Full candidate, only that candidate is discarded; other indexed results remain usable.

Suggested v1 defaults are:

| Budget | Default |
| --- | ---: |
| Initial relays queried | 3 |
| Maximum distinct relays visited | 16 |
| Maximum reference depth | 8 |
| Maximum concurrent requests | 4 |
| Maximum total response bytes | 1 MiB |
| Resolution deadline | 10 seconds |
| Maximum migration hops | 2 |

Cycle detection uses `(relay instance identifier, normalized relay base URI, Followee DID)` for relay traversal and Followee DID for migration traversal. Every newly contacted base URI counts against the distinct-relay budget even if it advertises a previously seen relay identifier. A new relay hop or migration hop MUST NOT reset aggregate relay, byte, concurrency, or deadline budgets.

For this accounting only, clients normalize an HTTPS relay URI by lowercasing scheme and ASCII host, removing the default port `443`, removing dot segments, and normalizing percent-encodings of unreserved characters under RFC 3986. Redirect targets count as contacted base URIs.

A client may return a locally cached valid record with a freshness or availability warning after remote failure. It SHOULD NOT automatically replace a cached same-authority record with an earlier timestamp.

### 14.2 Migration verification states

When checking a claimed migration relation, a client records one of three local states:

| State | Meaning | Ordinary presentation |
| --- | --- | --- |
| **Verified** | Both winning fresh records were obtained and reciprocate under Section 7.4 | May explain the migration and offer deliberate re-follow |
| **Checked but unverified** | A winning fresh counterpart was obtained, but it did not reciprocate | Suppress the relationship; diagnostics may report the failed local test |
| **Not checked** | The reciprocal test did not complete because it was deferred, exhausted its shared budget, timed out, encountered unavailability, or found no admissible counterpart | Do not present the relationship; may offer a separate explicit check |

Only Verified permits migration-oriented presentation. It never permits silent following-list replacement, inherited trust decisions, or automatic deletion of the old DID.

Not checked is not a negative result and MUST NOT be cached or reported as failed reciprocity. A user-requested explicit check is a new operation and receives fresh aggregate budgets. Checked but unverified may later be retried because either controller can publish new state.

### 14.3 Predecessor impersonation defence

Any new DID can self-assert a famous DID as `predecessor`. Until the claimed predecessor's winning fresh record reciprocates, an ordinary client MUST NOT present the claim as “formerly,” “continues from,” provenance, succession, or migration. It SHOULD suppress the claim entirely.

When the state is Not checked, a client MAY offer a generic verification action, but the control MUST NOT imply endorsement by the named predecessor. Developer views may display the raw signed claim if they clearly label it unverified.

### 14.4 Migration decay

A reciprocal migration link is live current state, not a permanent historical certificate. It ceases to verify when either selected record becomes stale, unavailable, superseded, or non-reciprocal.

Controllers who want a bridge to remain useful SHOULD keep the old DID's linking record fresh and published through several relays for as long as they want late-arriving followers to verify it.

## 15. Limits and error codes

### 15.1 Record limits

| Item | Hard maximum |
| --- | ---: |
| Complete tagged COSE Identity Record | 16 KiB |
| Contact Document within the record | 12 KiB |
| Record-body CBOR nesting depth | 8 |
| Total record-body map and array members | 256 |
| Display name | 256 UTF-8 bytes |
| Summary | 2,048 UTF-8 bytes |
| Any URI | 2,048 UTF-8 bytes |
| `alsoKnownAs` entries | 32 |
| Service entries | 64 |
| Migration predecessor entries | 1 |
| Migration successor entries | 1 |
| Service identifier or label | 256 bytes |
| Extension key | 256 UTF-8 bytes |

The aggregate record and Contact Document caps are binding even when individual fields are within their maxima. A parser MUST enforce outer byte limits before allocating from declared inner lengths.

The 64-entry service limit is an independent collection guard, not a promise that 64 services fit within a complete v1 record. Each minimally populated service contributes one array member and three map members. After the required record, Authority Descriptor, public-key, and Contact Document members are counted, the 256-member aggregate permits at most 61 minimal services in a Root record and 60 in a RootRevoked record. Optional fields may lower those effective maxima further. Implementations MUST enforce both the collection limit and the aggregate limit.

### 15.2 Relay-message limits

| Item | Hard maximum |
| --- | ---: |
| Resolve request DIDs | 256 |
| Conforming minimum supported resolve batch | 64 DIDs within 1 MiB |
| Directory entries | 4,096 |
| Directory response | 1 MiB |
| Cursor | 128 bytes |
| `changes` requested items | 1,024 |
| `changes` requested bytes | 4 MiB |
| Any protocol URI | 2,048 bytes |
| Relay API CBOR nesting depth | 8 |

Relay indices are `uint32`. Directory generations, cursor generations, relay instance identifiers, and cursors are opaque byte strings. Relay-local update numbers and all other relay wire integers are `uint64` unless a smaller hard bound is stated.

Operators may impose lower publication quotas, retention limits, or authenticated-service limits. A server claiming the relevant public capability MUST meet the conforming minimums it advertises.

### 15.3 Wire error codes

| Code | Name | Meaning |
| ---: | --- | --- |
| `0` | `invalidDid` | DID syntax, multibase encoding, or multihash structure is malformed |
| `1` | `unsupportedHash` | A structurally well-formed multihash names a hash code or digest length unsupported by this version |
| `2` | `unsupportedSuite` | Signature suite is not supported |
| `3` | `recordTooLarge` | Envelope exceeds the hard or advertised cap |
| `4` | `invalidCbor` | Input is not well-formed CBOR, or is well-formed but not basically valid under RFC 8949, including invalid UTF-8 text strings and duplicate map keys |
| `5` | `nonDeterministicCbor` | Basically valid CBOR violates the deterministic or restricted Followee profile in Section 6.1.2 |
| `6` | `schemaViolation` | Parsed object violates its v1 schema or limits, including use of a well-formed, basically valid, deterministically encoded data-item type that the applicable schema does not admit |
| `7` | `identityBindingMismatch` | Body `id`, target DID, and Authority Descriptor do not bind to the same identifier |
| `8` | `invalidRevocationKey` | Revealed key does not match the commitment or key profile |
| `9` | `invalidSignature` | COSE or Ed25519 verification fails |
| `10` | `premature` | Timestamp exceeds the recipient's future bound |
| `11` | `rootRevoked` | Root candidate is excluded by sticky state |
| `12` | `losingRecord` | Valid candidate loses current ordering |
| `13` | `duplicate` | Body digest is already current |
| `14` | `policyRejected` | Local admission policy rejected the request |
| `15` | `rateLimited` | Local rate or resource limit was reached |
| `16` | `responseTooLarge` | Requested response cannot fit the negotiated bound |
| `17` | `temporarilyUnavailable` | Operation cannot presently complete |
| `18` | `invalidCursor` | Cursor is malformed or unknown for reasons other than reset |
| `19` | `internalError` | Unexpected server failure |

Stale is result metadata, not an error. Absent is a resolve result, not `invalidDid` or proof of non-existence.

### 15.4 HTTP status use

Successful protocol processing, including Absent, per-DID Error results, valid no-change publication, and `ResetRequired`, SHOULD return HTTP `200` with the protocol body. Servers MUST use `400` when the outer request fails Section 6.1 well-formedness, basic validity, deterministic-profile, or top-level schema validation and therefore cannot safely enter per-item processing. Such a response has no normative per-item CBOR body. Servers SHOULD use `413` for an HTTP entity rejected before protocol parsing, `415` for unsupported media type, `429` for transport-level rate limiting, and `500` or `503` for failures that prevent a protocol response.

An invalid item inside an otherwise valid batch request is not an outer-request failure. In particular, a syntactically malformed DID carried as a basically valid UTF-8 text string receives an aligned per-DID `Error(invalidDid)` in an HTTP `200` resolve response. Invalid UTF-8 instead makes the enclosing request basically invalid under Section 6.1.1. A server MUST NOT reject the entire batch merely because one requested DID is syntactically invalid.

Clients MUST inspect the protocol body on HTTP `200` and MUST bound any error response body before parsing or displaying it.

### 15.5 DID resolution errors

A DID Resolver maps failures to the current DID Resolution result vocabulary where possible:

| Condition | DID resolution error |
| --- | --- |
| Invalid `did:flw` syntax | `invalidDid` |
| Requested representation unsupported | `representationNotSupported` |
| No valid record found within the completed operation | `notFound` |
| Budgets exhausted or relevant relays unavailable | `temporarilyUnavailable` |
| Unexpected local failure | `internalError` |

`notFound` is scoped to the completed resolution operation and MUST NOT be represented to users as proof that the DID does not exist anywhere.

## 16. Security considerations

### 16.1 Security properties

Descriptor hashing binds a DID to one root key and one revocation-key commitment. COSE and strict Ed25519 verification protect Identity Record integrity and origin under the applicable key. Recipient-side future checks bound hostile timestamp maxima. Deterministic ordering converges finite equal-time conflicts. Sticky RootRevoked state permanently excludes a compromised root once revocation is learned.

These mechanisms provide authenticity and deterministic local selection. They do not provide global availability, global freshness, or proof that all valid records have been seen.

### 16.2 Eavesdropping and resolution privacy

Identity Records are public, but resolution queries can reveal a user's following graph. HTTPS hides requests from passive observers between endpoints but not from the queried relay. Clients SHOULD cache, distribute queries among independent relays, avoid distinctive all-followings refresh batches, and support personal relays or privacy-preserving transports where appropriate.

### 16.3 Replay and rollback

An old record remains authentic. In the same authority state it loses to a later known timestamp, but a malicious relay may withhold later state. Clients SHOULD retain the greatest locally validated ordering key and warn or refuse before automatic rollback. Once RootRevoked is known, rollback to Root is forbidden.

There is no global proof that a response is the newest record ever signed.

### 16.4 Message insertion and modification

Inserted or modified full records fail descriptor binding, schema validation, or signature verification unless the attacker controls the applicable private key. References and relay metadata are not signed identity content and may be malicious; they are handled only as bounded availability hints.

### 16.5 Deletion and withholding

A relay can delete, omit, or falsely report absence for any record. Query diversity, local caching, handle-hosted bootstrap records, and alternate relays mitigate withholding. No finite query proves global absence.

### 16.6 Man-in-the-middle attacks

HTTPS authenticates WebFinger domains and public HTTP relay endpoints. A compromised or impersonated relay endpoint can return stale records, invalid bytes, or hostile references, but cannot make them pass local Identity Record verification. A WebFinger man-in-the-middle can mis-map a handle if Web PKI authentication is defeated; after a client stores the resulting Followee DID, later Contact Document authenticity is independent of that domain mapping.

### 16.7 Denial of service and amplification

Implementations MUST apply byte, item, nesting, concurrency, hop, and deadline limits before expensive work where possible. Relays MUST verify full records before amplifying them through current-state synchronization. Clients MUST share budgets across reference and migration traversal and detect cycles.

Valid signatures do not entitle an identity to free storage. Admission controls, quotas, sponsorship, payment, eviction, and selective synchronization are legitimate.

### 16.8 Timestamp attacks and clock failure

An authorised or compromised signer can choose a timestamp up to the recipient's tolerated future boundary and can pre-sign later records. A single currently submitted record can delay same-authority correction by approximately the future-skew window, not indefinitely. Root revocation invalidates the entire Root class, including unseen pre-signed Root records.

A relay clock far ahead may admit records healthy participants reject. A relay clock far behind rejects normal records and becomes unhelpful. Clock correctness affects usefulness, not network authority.

### 16.9 Equal-time equivocation

The lower-body-digest rule bounds current storage and converges without treating arrival order as authority. It does not prove intent, punish equivocation, or preserve global conflict evidence. Signers SHOULD still avoid collisions.

### 16.10 Root-key compromise

Anyone holding the root private key can produce indistinguishable Root records until revocation is learned. Temporary access permits pre-signing. The response is total Root revocation, not rejection of selected timestamps.

Followee intentionally defines no per-record blacklist: such a structure grows without bound and cannot establish that every compromised record has been named.

### 16.11 Revocation-key compromise or loss

The revocation key is the final authority. If it is compromised, the attacker may revoke the root and control the DID permanently. If it is lost before use, the DID has no recovery path. If it is lost or compromised after activation, Followee v1 has no further protocol recovery.

A controller still in control may create a fresh DID and publish reciprocal migration links, but clients must re-follow deliberately.

### 16.12 Descriptor and algorithm downgrade

A verifier accepts only the v1 descriptor version, full SHA-256 multihash profile, and fully specified Ed25519 COSE algorithm `-19`. The creator cannot select a weaker hash or the deprecated polymorphic `-8` algorithm.

If SHA-256 or Ed25519 is later deprecated for creation, existing DIDs are not silently reinterpreted. A future specification must distinguish refusing to create new identifiers from refusing to verify old ones. Migration to a new DID remains explicit.

### 16.13 Endpoint and external-content risk

Contact URIs may lead to malicious, enormous, mutable, or privacy-invasive content. Clients MUST apply ordinary URL, origin, content-type, download-size, and sandboxing policy. Service inclusion is not an endorsement by a relay or resolver.

### 16.14 Uniqueness

Global DID uniqueness derives probabilistically from independently generated keys and the full SHA-256 descriptor commitment. Two identical Authority Descriptors intentionally produce the same DID. Controllers MUST generate independent keys and MUST NOT reuse test keys.

### 16.15 Residual implementation risk

The most dangerous implementation failures include checking only the signed `id` without descriptor binding, accepting non-deterministic CBOR after re-encoding, trusting relay validation, accepting Root after learned revocation, treating stale migration as current, accepting non-strict Ed25519 encodings, and allowing traversal hops to reset budgets.

Conformance tests MUST exercise each of these failures.

### 16.16 Incremental synchronization convergence

Cursor synchronization alone does not guarantee that a Relay eventually acquires every temporarily inadmissible record. A receiver that rejects a locally premature Full candidate still advances the valid response's peer cursor under Section 13.3. If the sender's current tuple for that DID never changes, the same record may not appear again in that incremental stream.

Recovery may occur through later pull under Section 13.4, a new bounded full enumeration, another Relay, or a subsequent source update. None is guaranteed by cursor synchronization itself. This liveness trade prevents one bad or premature candidate from permanently stalling synchronization of every later identity from that peer.

## 17. Privacy considerations

Followee records are public and stable DIDs are correlatable. Controllers SHOULD publish links rather than secrets or unnecessary personal data. Separate personas SHOULD use separate DIDs when correlation would be harmful.

The Authority Descriptor exposes the root public key and a hash commitment, not the unrevealed revocation public key. After Root revocation, the revocation public key becomes public. Neither public key should be assumed to identify a legal person.

Handles are federated discovery aids. Their domains observe lookups and can reassign names under their own authority. A Contact Document's handle claim does not itself prove domain control.

Relays may log IP addresses, query batches, publication attempts, and timing. Operators SHOULD publish retention policies, minimize logs, and support privacy-preserving access where practical. Clients SHOULD avoid sending an entire following list to one relay in one uniquely identifying batch.

## 18. Optional remote-signer interface

This section defines an OPTIONAL application interface. It does not add delegation or another valid Identity Record form.

A remote signer may accept an authenticated request containing exact deterministic `recordBodyBytes` and return the complete COSE Identity Record. The minimal CBOR request is:

```cbor
{
  0: 1,
  1: h'...recordBodyBytes...'
}
```

The success response is:

```cbor
{
  0: 1,
  1: h'...complete tagged COSE Identity Record...'
}
```

Before signing, the signer MUST:

1. parse and validate the deterministic record body;
2. reproduce the DID from the Authority Descriptor;
3. ensure it controls the key applicable to the requested authority state;
4. enforce the signer timestamp algorithm and clock checks;
5. ensure the Contact Document is complete rather than a delta; and
6. apply its own user-presence, authentication, display, rate, and policy controls.

Transport authentication, user authorisation, multi-device access policy, audit logging, and vault custody are application concerns. A returned envelope is an ordinary Followee Identity Record and carries no remote-signer or delegation marker.

## 19. Optional relay history

History is not required for DID creation, record verification, resolution, update, root revocation, relay synchronization, or convergence.

A Relay MAY expose its own append-only admitted history through a separate specification. Such a history:

- records only what that Relay chose to admit;
- may begin late and contain gaps relative to other relays;
- is never a network-wide chain;
- does not decide canonical state; and
- is not consulted by the v1 verification algorithm.

## 20. Conformance and test requirements

### 20.1 Record Verifier tests

A conforming Record Verifier MUST pass published positive and negative vectors covering:

- DID decoding and exact multihash profile;
- distinct `invalidDid` and `unsupportedHash` classification for malformed and unsupported multihashes;
- Authority Descriptor derivation;
- revocation-key commitment;
- CBOR well-formedness, basic validity, deterministic-profile, and schema classifications;
- exact `invalidCbor` rejection of adjacent duplicate keys and invalid RFC 3629 UTF-8, including overlong, surrogate, above-U+10FFFF, and incomplete code-point sequences inside otherwise ignored extension values;
- exact `schemaViolation` rejection of both one-byte and two-byte deterministically encoded CBOR simple values not admitted by the v1 schema, inside otherwise ignored extension values;
- exact COSE protected headers and external AAD;
- strict Ed25519 verification;
- descriptor substitution;
- every target/body/descriptor identity-binding permutation specified in Appendix B.7 item 1;
- root and RootRevoked records;
- valid and invalid `mediaType`, `language`, and `rel` syntax at their exact boundaries;
- URI fields with schemes, queries, and fragments; rejection of every relative-reference form; and both lowercase and uppercase `IPvFuture` introducers;
- exact CBOR unsigned-integer label typing, including rejection of `false` and `true` substituted for labels `0` and `1` in Authority Descriptors and public-key objects;
- future timestamps and stale records;
- equal-time lower-digest ordering; and
- every aggregate record limit.

In particular, a verifier MUST reject a candidate whose signature verifies and whose body `id` equals the target DID, but whose carried Authority Descriptor does not reproduce that DID. Passing the other negative tests while accepting this case indicates that descriptor binding is not implemented.

### 20.2 Relay tests

A conforming Relay MUST additionally pass tests covering:

- current-state admission and no-change outcomes;
- sticky RootRevoked state;
- full-to-reference conversion without authority rollback;
- reference misdirection and cycles;
- batch alignment and response splitting;
- duplicate requested DIDs without deduplication or reordering, exact response cardinality, and rejection of count mismatches;
- HTTP `400` for outer request CBOR faults, including adjacent duplicate keys;
- HTTP `200` with positionally aligned per-DID results when a valid batch request contains a syntactically malformed DID as valid UTF-8;
- complete rejection of a non-deterministically encoded outer response without interpreting it as Absent;
- opaque Full byte-string isolation in resolve and `changes` responses, including preservation of valid entries after an earlier invalid candidate;
- distinction between Absent and a retained Full record that becomes premature under a backwards clock correction;
- coalesced `changes` output;
- synchronization cursor advancement to the exact returned `nextCursor` despite rejected Full candidates, without record, authority-state, `lastUpdated`, or update-number mutation for the rejected DID;
- complete rejection of a `changes` success response containing more entries than the request's `itemLimit`, without processing entries, changing state, or using `nextCursor`;
- every status-dependent required and forbidden `changes` field combination, including the exact two-field status `1` ResetRequired response;
- cursor pagination without gaps;
- cursor-generation reset;
- restore-time behaviour; and
- bounded resource use under invalid and Sybil input.

### 20.3 Client tests

A conforming DID Resolver or Followee client MUST additionally pass tests covering:

- multi-relay candidate selection;
- continuation past Absent and per-DID Error results while an unqueried Relay selected for the operation and sufficient shared budget remain;
- continuation past a rejected outer relay response under the same shared budgets;
- positional isolation of an invalid Full candidate without shifting or discarding later results from an accepted batch response;
- independent local classification of every Full candidate without importing another Relay's `premature` diagnosis;
- withheld and stale records;
- shared traversal budgets;
- handle mapping and inverse verification;
- reciprocal migration verification;
- Verified, Checked but unverified, and Not checked migration states;
- predecessor impersonation suppression; and
- no automatic following-list migration.

### 20.4 Interoperability criterion

At least two independent implementations MUST produce byte-identical Authority Descriptors and record bodies from the same structured input, verify the same envelopes, derive the same DIDs and body digests, select the same winners from candidates delivered in different orders, and exchange state through the HTTP/CBOR profile before v1 is described as interoperable.

The complete conformance suite MUST be rerun after a normative CBOR-classification or relay-wrapper change. Reports SHOULD separately count acceptance/rejection disagreements, symbolic differences permitted by unspecified multi-fault precedence, and genuine unresolved specification ambiguities. A raw symbolic difference under an explicitly unspecified assertion is not itself an interoperability failure, but it MUST remain visible in the report.

## 21. Registration and extension considerations

Before production registration, the specification maintainers SHOULD:

1. confirm that `flw` remains unassigned in the W3C DID Methods registry;
2. publish this specification at a stable, content-addressable release URL;
3. submit `did:flw` to the W3C DID Extensions method registry;
4. publish the protected JSON-LD context at `https://w3id.org/followee/v1` before advertising `application/did+ld+json`;
5. establish persistent redirects for the two Followee WebFinger relation URIs;
6. publish the complete machine-readable CDDL and conformance vectors alongside the specification; and
7. define a transparent process for future descriptor versions, suites, service types, and extensions.

A registry entry is discovery metadata. It does not create DIDs, operate relays, confer authority over records, or make the registry part of Followee resolution.

## 22. Versioning

Followee v1 freezes:

- method name `flw`;
- Authority Descriptor version `1`;
- record protocol version `1`;
- SHA-256 descriptor and revocation commitments;
- base58btc multihash DID encoding;
- Ed25519 COSE algorithm `-19`;
- CBOR labels, basic-validity classification, deterministic profile, and byte-string opacity boundary;
- the one-way Root → RootRevoked authority rule; and
- the v1 relay wire schemas.

A future version may add new descriptor versions or protocol capabilities, but it MUST NOT reinterpret valid version 1 bytes. A relay advertises supported protocol versions. Unsupported versions or suites cannot enter the v1 current map.

---

## Appendix A. Normative CDDL

The following schema uses [RFC 8610](https://www.rfc-editor.org/rfc/rfc8610) CDDL. Textual and aggregate limits from Section 15 remain normative where CDDL cannot express them conveniently.

```cddl
flw-did = tstr
uri = tstr

identity-record = #6.18([
  protected: bstr .cbor protected-map,
  unprotected: {},
  payload: bstr .cbor record-body,
  signature: bstr .size 64
])

protected-map = {
  1: -19
}

public-key = {
  0: -19,
  1: bstr .size 32
}

authority-descriptor = {
  0: 1,
  1: public-key,
  2: bstr .size 32
}

record-body = {
  0: 1,
  1: flw-did,
  2: uint,
  3: 0 / 1,
  4: authority-descriptor,
  ? 5: public-key,
  ? 6: uint,
  7: contact-document,
  ? 8: extension-map
}

contact-document = {
  ? 0: tstr,
  ? 1: tstr,
  ? 2: uri,
  ? 3: [* uri],
  ? 4: [* service-entry],
  ? 5: migration,
  ? 6: extension-map
}

service-entry = {
  0: tstr,
  1: tstr,
  2: uri,
  ? 3: tstr,
  ? 4: tstr,
  ? 5: tstr,
  ? 6: tstr
}

migration = {
  ? 0: flw-did,
  ? 1: flw-did
}

extension-map = {
  * tstr => extension-value
}

extension-value =
    uint
  / nint
  / bstr
  / tstr
  / bool
  / nil
  / [* extension-value]
  / extension-object

extension-object = {
  * extension-inner-key => extension-value
}

extension-inner-key = uint / nint / tstr

relay-info = {
  0: 1,
  1: bstr .size 16,
  2: uint,
  3: [1* uint],
  4: [1* int],
  5: relay-limits,
  6: bstr .size 16,
  7: bstr .size 16,
  8: uri
}

relay-limits = {
  0: uint,  / maximum record bytes /
  1: uint,  / maximum resolve batch /
  2: uint,  / maximum resolve response bytes /
  3: uint,  / maximum changes items /
  4: uint   / maximum changes bytes /
}

resolve-request = {
  0: 1,
  1: [1* flw-did]
}

resolve-response = {
  0: 1,
  1: bstr .size 16,
  2: [* resolve-result]
}

resolve-result =
    { 0: 0, 1: bstr }
  / { 0: 1, 1: uint }
  / { 0: 2 }
  / { 0: 3, 2: uint }

relay-directory = {
  0: 1,
  1: bstr .size 16,
  2: [* directory-entry]
}

directory-entry = {
  0: uint,
  1: bstr .size 16,
  2: uri,
  3: uint
}

publish-response = {
  0: 1,
  1: 0 / 1 / 2,
  ? 2: uint
}

changes-request = {
  0: 1,
  1: bstr / nil,
  2: uint,
  3: uint
}

changes-response = {
  0: 1,
  1: 0 / 1 / 2,
  ? 2: [* change-entry],
  ? 3: bstr,
  ? 4: bool,
  ? 5: bstr .size 16,
  ? 6: uint
}

change-entry = [
  flw-did,
  ({ 0: 0, 1: bstr } / { 0: 1, 1: uint }),
  uint
]

remote-sign-request = {
  0: 1,
  1: bstr
}

remote-sign-response = {
  0: 1,
  1: bstr
}
```

The optional markers in the `changes-response` CDDL express the union of fields used across all statuses; they do not make those fields discretionary within a status. The status-conditional required and forbidden fields in Section 12.6 are normative and MUST be enforced in addition to CDDL acceptance.

The conditional relationship between record-body labels `3` and `5` is normative text in Section 5.1. CDDL acceptance alone is never sufficient record validation.

CDDL does not express the positional relationship between `resolve-request` and `resolve-response`. Duplicate DIDs are permitted in the request array, every occurrence counts separately, and Section 12.3 requires an equal-length result array in the same order.

The `.cbor` control on the Identity Record payload describes its required interpretation once candidate verification begins. It does not override Section 6.1.1's byte-string opacity rule for an enclosing relay message. Full-result and change-entry byte strings are ordinary opaque `bstr` values until separately submitted to Section 8.1.

## Appendix B. Normative test vectors

### B.1 Warning

The following private seeds are public test material. They MUST NOT be used for a real Followee DID.

### B.2 Keys

```text
root seed:
000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f

root public key:
03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8

revocation seed:
202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f

revocation public key:
29acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd7
```

### B.3 Revocation commitment and descriptor

```text
revocation public-key CBOR:
a2003201582029acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd7

revocation commitment:
d123bafb7ae35472d9a73944d98314a38ff8f201d79c32e640f97a27bec880de

Authority Descriptor CBOR:
a3000101a2003201582003a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8025820d123bafb7ae35472d9a73944d98314a38ff8f201d79c32e640f97a27bec880de

descriptor digest:
12dc4b843d10c5ca7313aa2452db61d661afbe3943b3fdbea43405c7028d1eb2

multihash bytes:
122012dc4b843d10c5ca7313aa2452db61d661afbe3943b3fdbea43405c7028d1eb2

Followee DID:
did:flw:zQmPcGstBa7wW9hoYQbS6JZ4UxwZmoKr7YVf9y7qxiyD3Cm
```

### B.4 Root record

The timestamp is `1785589200123`, corresponding to `2026-08-01T13:00:00.123Z`. The Contact Document contains Alice's display name, summary, handle claim, and Atom feed.

```text
record body CBOR:
a600010178376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d021b0000019fbd68f4fb030004a3000101a2003201582003a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8025820d123bafb7ae35472d9a73944d98314a38ff8f201d79c32e640f97a27bec880de07a4006d416c696365204578616d706c650166577269746572038176616363743a616c696365406578616d706c652e636f6d0481a500646665656401644665656402781e68747470733a2f2f616c6963652e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046757726974696e67

COSE `Sig_structure` length:
327

COSE `Sig_structure` bytes:
846a5369676e61747572653143a10132581a466f6c6c6f7765652f4964656e746974795265636f72642f7631590118a600010178376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d021b0000019fbd68f4fb030004a3000101a2003201582003a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8025820d123bafb7ae35472d9a73944d98314a38ff8f201d79c32e640f97a27bec880de07a4006d416c696365204578616d706c650166577269746572038176616363743a616c696365406578616d706c652e636f6d0481a500646665656401644665656402781e68747470733a2f2f616c6963652e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046757726974696e67

body digest:
f8e387942fd568c72d629717f579314a3305f26e03b7197958c7555b2e9573c7

protected header bytes:
a10132

signature:
4db146d7bc6ca7690bac44b0c6ef38bcdd685ff157fdcca15da6b64662a26f94bd95b88f97f3e720246b3756c6eb6b8967103f9346dbef51c053cac381a50204

complete tagged COSE Identity Record:
d28443a10132a0590118a600010178376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d021b0000019fbd68f4fb030004a3000101a2003201582003a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8025820d123bafb7ae35472d9a73944d98314a38ff8f201d79c32e640f97a27bec880de07a4006d416c696365204578616d706c650166577269746572038176616363743a616c696365406578616d706c652e636f6d0481a500646665656401644665656402781e68747470733a2f2f616c6963652e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046757726974696e6758404db146d7bc6ca7690bac44b0c6ef38bcdd685ff157fdcca15da6b64662a26f94bd95b88f97f3e720246b3756c6eb6b8967103f9346dbef51c053cac381a50204
```

### B.5 Root-revoked record

```text
record body CBOR:
a700010178376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d021b0000019fbd68f8e3030104a3000101a2003201582003a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8025820d123bafb7ae35472d9a73944d98314a38ff8f201d79c32e640f97a27bec880de05a2003201582029acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd707a4006d416c696365204578616d706c650166577269746572038176616363743a616c696365406578616d706c652e636f6d0481a500646665656401644665656402781e68747470733a2f2f616c6963652e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046757726974696e67

body digest:
3c617919801d0c19684144f9b46e0f2384243c17c831a2d76531ba6554cb3861

signature:
c874ee1bb01dc4f3972b978455abba78ab0f84755fbd9ee01425a1e6c910abae7cfa8b407aff2092be09e9032e968a23a87e63f9e1e7b2a0d5498bf7df5d6c09

complete tagged COSE Identity Record:
d28443a10132a059013fa700010178376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d021b0000019fbd68f8e3030104a3000101a2003201582003a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8025820d123bafb7ae35472d9a73944d98314a38ff8f201d79c32e640f97a27bec880de05a2003201582029acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd707a4006d416c696365204578616d706c650166577269746572038176616363743a616c696365406578616d706c652e636f6d0481a500646665656401644665656402781e68747470733a2f2f616c6963652e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046757726974696e675840c874ee1bb01dc4f3972b978455abba78ab0f84755fbd9ee01425a1e6c910abae7cfa8b407aff2092be09e9032e968a23a87e63f9e1e7b2a0d5498bf7df5d6c09
```

This record MUST activate RootRevoked state and outrank every Root record for the DID regardless of Root timestamp.

### B.6 Equal-time ordering

Starting from the B.4 body, replace only `contact.displayName` with the values shown:

```text
"Alice A" body digest:
6f347840328b2b2cd74cce2f9a222a313e9d9504305c3ac816987ff2f4b47d97

"Alice B" body digest:
8123f2cdf1a414b34d38eb2e58b39fb7cf37e9f851d999402f64787b3361c162
```

At equal authority and timestamp, `Alice A` wins because `6f` is lexicographically lower than `81`.

### B.7 Required negative mutations

Implementations MUST reject variants of the positive vectors with any one of these mutations. Where this appendix assigns an error, that error is normative:

1. an identity-binding mismatch, exercised in each of these forms:
   - an unchanged, internally consistent envelope verified against a different syntactically valid target DID;
   - a body `id` changed to a different syntactically valid DID and then re-signed by the applicable legitimate key, verified against the original target; and
   - that same re-signed mutation verified against the mutated target.

   All three cases produce `identityBindingMismatch`. The first fails the body-to-target relation, the second also fails that relation without relying on an invalid signature, and the third passes that relation but fails descriptor-to-target binding.
2. a target DID containing:
   - a structurally well-formed multihash code other than `0x12`, with its declared digest length matching the bytes present; or
   - code `0x12` with a structurally well-formed declared digest length other than `0x20`, again matching the bytes present.

   Both cases produce `unsupportedHash`. A separate case with a missing or non-minimal varint, a declared length that disagrees with the bytes present, or trailing bytes produces `invalidDid`. These target-DID cases do not mutate the signed envelope.
3. protected algorithm `-8` instead of `-19`;
4. missing COSE tag `18`;
5. non-empty unprotected headers;
6. detached payload;
7. non-minimal CBOR integer or length encoding;
8. reordered deterministic map keys;
9. duplicate map key;
10. Root record containing label `5`;
11. RootRevoked record missing label `5`;
12. revealed revocation key changed by one bit;
13. signature changed by one bit;
14. `S >= L`, a non-canonical point, or a small-order public key;
15. `validUntil_ms < timestamp_ms`;
16. any aggregate hard limit exceeded;
17. a CBOR simple value `false` or `true` substituted for an unsigned-integer label `0` or `1` in an Authority Descriptor or nested public-key object;
18. an invalid RFC 3629 UTF-8 text string, including an overlong encoding, a surrogate code point, a value above U+10FFFF, or an incomplete code-point sequence; and
19. a deterministically encoded CBOR simple value other than `false`, `true`, `null`, or `undefined`, including both a one-byte encoding and a two-byte encoding, used where the applicable v1 schema admits no such type.

The item 17 suite MUST include an otherwise internally consistent, descriptor-bound, correctly signed record so that rejection demonstrates schema enforcement rather than a coincidental signature or identity-binding failure. Such a record produces `schemaViolation`.

When item 9 is constructed by replacing the required empty COSE unprotected-header map with a map containing duplicate keys, it independently violates both Section 6.1.1 basic validity and Section 6.2 rule 4. Its fault profile is therefore multiple and its exact error is unspecified. Section B.10 provides the fault-isolated adjacent-duplicate case that normatively produces `invalidCbor`.

Every item 18 mutation changes signed body bytes and therefore MUST be re-signed by the applicable legitimate key before it can carry an exact non-signature assertion. The fault-isolated vectors in Section B.10 produce `invalidCbor`.

Every item 19 mutation likewise changes signed body bytes and MUST be re-signed by the applicable legitimate key. The fault-isolated vectors in Section B.12 place the simple value inside an otherwise valid unknown extension and produce `schemaViolation`.

### B.8 Descriptor substitution with a valid signature

This vector uses two additional deterministic attacker seeds. It is the only negative vector in this appendix for which COSE parsing, schema validation, the body `id` check, and strict Ed25519 verification all succeed. It MUST nevertheless be rejected at Section 8.1 step 9 with `identityBindingMismatch`.

The record claims Alice's DID in body label `1`, but carries an attacker's Authority Descriptor and is correctly signed by the attacker's root key. A verifier that checks the body `id` against the requested DID but does not independently hash the carried descriptor would accept it and give the attacker apparent control of Alice's identifier.

#### B.8.1 Attacker keys

```text
attacker root seed:
404142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f

attacker root public key:
2543b92ff1095511476adc8369db6ddc933665a11978dda1404ee1066ca9559d

attacker revocation seed:
606162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f

attacker revocation public key:
174553b456dddfc6908ecab1c101fe6ab21e2baa0617795b7d43a63482993fd5

attacker revocation commitment:
2a35f76c8bcc0c5fc69e99d51656c2a93a1c8e447677d6f78c8c9d729eef3ca6

attacker Authority Descriptor CBOR:
a3000101a200320158202543b92ff1095511476adc8369db6ddc933665a11978dda1404ee1066ca9559d0258202a35f76c8bcc0c5fc69e99d51656c2a93a1c8e447677d6f78c8c9d729eef3ca6

attacker's own legitimate DID, for contrast:
did:flw:zQmPdjR6k8HFgbf4e51P7iMy4aY3buGsxQU49fSHdGhce7s
```

#### B.8.2 Substituted record

This body is identical to the B.4 body except that label `4` contains the attacker's Authority Descriptor. The substituted descriptor has the same encoded length, so the COSE framing is unchanged.

```text
target DID, unchanged in body label 1:
did:flw:zQmPcGstBa7wW9hoYQbS6JZ4UxwZmoKr7YVf9y7qxiyD3Cm

body digest:
1ca53f60b31bec6334d0c0449cd639d5c8b2922549287ba00cf40df018164e68

signature, valid under the attacker's root key:
b8352e21b1168a4c74020f2b7cf10b519fda4fb0c2465a682328f802c08b1873e1b1c137b79cce7f81aa00fc1a5630e34c19500a016b45867c9900108625650e

complete tagged COSE Identity Record:
d28443a10132a0590118a600010178376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d021b0000019fbd68f4fb030004a3000101a200320158202543b92ff1095511476adc8369db6ddc933665a11978dda1404ee1066ca9559d0258202a35f76c8bcc0c5fc69e99d51656c2a93a1c8e447677d6f78c8c9d729eef3ca607a4006d416c696365204578616d706c650166577269746572038176616363743a616c696365406578616d706c652e636f6d0481a500646665656401644665656402781e68747470733a2f2f616c6963652e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046757726974696e675840b8352e21b1168a4c74020f2b7cf10b519fda4fb0c2465a682328f802c08b1873e1b1c137b79cce7f81aa00fc1a5630e34c19500a016b45867c9900108625650e
```

#### B.8.3 Required behaviour

```text
Section 8.1 step 3  (COSE profile)          PASS
Section 8.1 step 5  (v1 schema)             PASS
Section 8.1 step 7  (body id == target)     PASS
Section 8.1 step 8  (descriptor schema)     PASS
Section 8.1 step 9  (descriptor digest)     FAIL -> identityBindingMismatch
Section 8.1 step 14 (strict Ed25519)        would PASS
```

A conforming Record Verifier MUST reject the candidate and MUST NOT admit it, serve it, assign it a relay-local update number, or expose it as a resolution result.

A client receiving these bytes as a `Full` candidate MUST discard that candidate as invalid, MUST NOT display its Contact Document, and MAY continue resolution using other candidates within the existing operation budgets. The invalid candidate is not equivalent to a valid `Absent` relay response. If no valid candidate is found, the operation's final resolution result is determined normally under the result taxonomy in Section 12.3 and the client-resolution rules in Section 14.

### B.9 Independent Bob identity

This second complete identity is normative test material for cross-DID state isolation and relay batches. Migration vectors are intentionally deferred to the additive v0.8.1 vector release.

```text
Bob root seed:
808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f

Bob root public key:
cd14b37f956e953194ff7fb73b3d81dcc561d61a7538094b7c3e1a643ee5f3aa

Bob revocation seed:
a0a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebf

Bob revocation public key:
4fd099ccd47d7893dfe9ec24414ecb0d9b5420232aad30d91c465be33cbe65c4

Bob revocation public-key CBOR:
a200320158204fd099ccd47d7893dfe9ec24414ecb0d9b5420232aad30d91c465be33cbe65c4

Bob revocation commitment:
46ed171c07da81226f954a36b2e61c3be4caee1f7b5d78aa6022eedb69486c41

Bob Authority Descriptor CBOR:
a3000101a20032015820cd14b37f956e953194ff7fb73b3d81dcc561d61a7538094b7c3e1a643ee5f3aa02582046ed171c07da81226f954a36b2e61c3be4caee1f7b5d78aa6022eedb69486c41

Bob descriptor digest:
ddc23bec60a7a9dad831d8c52439b9f3f30e17012da4d948233ece41154817ba

Bob multihash bytes:
1220ddc23bec60a7a9dad831d8c52439b9f3f30e17012da4d948233ece41154817ba

Bob Followee DID:
did:flw:zQmdGJbJu6pBbiyZX9gJHBTFxnUCtBgRa7mZRcKKs1TcFEy
```

Bob's timestamp is `1785589201123`. His Contact Document contains a display name, summary, handle claim, and Atom feed.

```text
Bob record body CBOR:
a600010178376469643a666c773a7a516d64474a624a753670426269795a5839674a48425446786e55437442675261376d5a52634b4b73315463464579021b0000019fbd68f8e3030004a3000101a20032015820cd14b37f956e953194ff7fb73b3d81dcc561d61a7538094b7c3e1a643ee5f3aa02582046ed171c07da81226f954a36b2e61c3be4caee1f7b5d78aa6022eedb69486c4107a4006b426f62204578616d706c650166526561646572038174616363743a626f62406578616d706c652e6e65740481a500646665656401644665656402781c68747470733a2f2f626f622e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046752656164696e67

Bob COSE Sig_structure length:
321

Bob COSE Sig_structure bytes:
846a5369676e61747572653143a10132581a466f6c6c6f7765652f4964656e746974795265636f72642f7631590112a600010178376469643a666c773a7a516d64474a624a753670426269795a5839674a48425446786e55437442675261376d5a52634b4b73315463464579021b0000019fbd68f8e3030004a3000101a20032015820cd14b37f956e953194ff7fb73b3d81dcc561d61a7538094b7c3e1a643ee5f3aa02582046ed171c07da81226f954a36b2e61c3be4caee1f7b5d78aa6022eedb69486c4107a4006b426f62204578616d706c650166526561646572038174616363743a626f62406578616d706c652e6e65740481a500646665656401644665656402781c68747470733a2f2f626f622e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046752656164696e67

Bob body digest:
c7d107d8004c0376b453d7de0eaf187f0597e0b4edccac307a81ddba3b8fcda8

Bob signature:
958a63029defee36e1047c002a8346aa57c832ed8fc27781ee622cc92330bc434c8f075aa89290b2c1021bf19602a92b5681ae6615268ed928bd113f15c60202

Bob complete tagged COSE Identity Record:
d28443a10132a0590112a600010178376469643a666c773a7a516d64474a624a753670426269795a5839674a48425446786e55437442675261376d5a52634b4b73315463464579021b0000019fbd68f8e3030004a3000101a20032015820cd14b37f956e953194ff7fb73b3d81dcc561d61a7538094b7c3e1a643ee5f3aa02582046ed171c07da81226f954a36b2e61c3be4caee1f7b5d78aa6022eedb69486c4107a4006b426f62204578616d706c650166526561646572038174616363743a626f62406578616d706c652e6e65740481a500646665656401644665656402781c68747470733a2f2f626f622e6578616d706c652f666565642e786d6c03746170706c69636174696f6e2f61746f6d2b786d6c046752656164696e675840958a63029defee36e1047c002a8346aa57c832ed8fc27781ee622cc92330bc434c8f075aa89290b2c1021bf19602a92b5681ae6615268ed928bd113f15c60202
```

Alice and Bob have independent sticky authority state. Admitting or revoking one MUST NOT modify the other's current entry, authority state, ordering metadata, or update metadata.

### B.10 Fault-isolated basic-validity records

Each vector in this section starts from the B.4 Alice record body, changes the initial map head from `a6` to `a7`, and appends record label `8` followed by the exact extension-map bytes shown. The extension key is the otherwise valid URI `https://example.com/ext`. The resulting raw body is signed with Alice's legitimate B.2 root seed without decoding or normalizing the invalid value.

The duplicate-key vector uses two adjacent deterministic encodings of integer key `0` inside a nested extension object. Both keys and values are individually allowed, and their equality is not an independent map-order reversal. Duplicate-key basic validity is its only fault.

```text
duplicate-key appended bytes:
08a17768747470733a2f2f6578616d706c652e636f6d2f657874a200000001

body digest:
128fec939e1273f890be281a82f7bfac1134e3bab9bc0651022f3a6000698dd2

COSE Sig_structure length:
358

signature:
afba8e1577abd9c6383b8df9a5c05913df217b3f1c4dc0c4c0027f9a44629d1a397dd4ad36f6e01028a3060a8481690cc589e2f9525e597f0a6a0cf60c9cb404

expected result:
invalidCbor
```

The four UTF-8 vectors place an invalid text-string value—not a key—inside the same unknown extension. The extension namespace is otherwise well-formed and unknown core extensions are ignored after structural validation, so invalid UTF-8 is the only fault.

```text
overlong U+002E appended bytes:
08a17768747470733a2f2f6578616d706c652e636f6d2f65787462c0ae

body digest:
4b8cc526c781c6b9ba707b6393f392f1132b0e5d18a7e7611a583d1013278f70

COSE Sig_structure length:
356

signature:
738365f103b6f943311c4f339bcd4889e405129e2643d57f2fd3698adc50d8da8df529b886252b62727233a828769dabcac7c0add28f442e72c325905844a50e

expected result:
invalidCbor

lone U+D800 surrogate appended bytes:
08a17768747470733a2f2f6578616d706c652e636f6d2f65787463eda080

body digest:
fd9cbe63338d1a3a1791c596db9a3824376070a7126aab2064d90bd62333afe8

COSE Sig_structure length:
357

signature:
7fcefa0e654da023a71dc8ed5e2cb988ac4111a9b3a75e88c5757e2b59d792e965ff004eae3c26c13e29fe56c7addec04fad04e4f18e5ba375a827c02028e103

expected result:
invalidCbor

U+110000 above the RFC 3629 maximum appended bytes:
08a17768747470733a2f2f6578616d706c652e636f6d2f65787464f4908080

body digest:
95bfb5eb8a921a0b7ceeff63a81ccd6404cf7e64945d9d888805f208b49e4204

COSE Sig_structure length:
358

signature:
28ecb7c9e471940d077cd3d24f1e348aaac855be352523ae9867ef2839bbdf6d8794f110e0d4a79055009dd803afdd259729c16c70746acab0ad620d190e0607

expected result:
invalidCbor

incomplete three-byte code point in a complete two-byte text string appended bytes:
08a17768747470733a2f2f6578616d706c652e636f6d2f65787462e282

body digest:
60e93b06213c6038ab697b796f8264cc854dc12442efbf15f2abd35eae165e09

COSE Sig_structure length:
356

signature:
e7cd9850280f108e8caf550cdff381765c957dc53993b28a57d8f4b362f5e624105d83ffe12b22df2d3ca8d54c833030f1fa1617cd1e4b8697f670aa41d7c601

expected result:
invalidCbor
```

For the final case, the text-string head is deliberately `62`, declaring exactly the two bytes `e2 82`. The containing CBOR body is complete and well-formed; only the UTF-8 code point is incomplete. Using head `63` without a third byte would instead test truncated CBOR well-formedness.

For every vector, the complete envelope is constructed exactly as in Section 6.2 from the mutated raw body and listed signature. A verifier MUST reject it before exposing decoded extension content. A verifier that reports `invalidSignature` has failed to use the listed re-signature or has altered the received body bytes.

### B.11 Relay-wrapper and candidate-isolation vectors

The relay vectors use directory generation `000102030405060708090a0b0c0d0e0f`. Complete Full byte strings are the exact B.4, B.8, and B.9 envelopes. Wrapper validators MUST treat those byte strings as opaque; candidate verification occurs only after the wrapper is accepted.

#### B.11.1 Invalid outer request

This otherwise structured resolve request contains adjacent duplicate top-level label `1` entries. Its exact bytes are:

```text
a30001018178376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d018178376469643a666c773a7a516d64474a624a753670426269795a5839674a48425446786e55437442675261376d5a52634b4b73315463464579

length:
121

SHA-256:
0f3aa1e98de0c1d63a2dd740e04542be326e550e75a133ade1ac045694bfb790
```

The Relay MUST reject the complete request with HTTP `400`. It MUST NOT choose either duplicate value, combine the arrays, or return per-DID results.

#### B.11.2 Invalid outer response

This resolve response is otherwise equivalent to `{ 0: 1, 1: h'000102030405060708090a0b0c0d0e0f', 2: [{ 0: 2 }] }`, but protocol version `1` is non-minimally encoded as `18 01`:

```text
a30018010150000102030405060708090a0b0c0d0e0f0281a10002

length:
27

SHA-256:
251497e0a44248c6099c5851e0c6668c0731d2b7f1f610f28c6f3c42254475cf
```

A client MUST reject the complete response as `nonDeterministicCbor`, obtain no candidate or Absent result from it, change no cached or sticky identity state, consume the ordinary operation budgets, and continue with another already-selected Relay when Section 14.1 permits.

#### B.11.3 Resolve candidate isolation

The request is `{ 0: 1, 1: [Alice-DID, Bob-DID] }`:

```text
a20001018278376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d78376469643a666c773a7a516d64474a624a753670426269795a5839674a48425446786e55437442675261376d5a52634b4b73315463464579

length:
119

SHA-256:
a2d1d1944182db0f42468bdcaeb086d1987ee3570b892811a378f0ec3bbbca78
```

The response is the deterministic encoding of:

```cbor
{
  0: 1,
  1: h'000102030405060708090a0b0c0d0e0f',
  2: [
    { 0: 0, 1: h'B.8 complete envelope bytes' },
    { 0: 0, 1: h'B.9 complete envelope bytes' }
  ]
}
```

Its encoded length is `743` and its SHA-256 digest is:

```text
62246877adbd56be2996ea37d05475d88c0e7932ff9b042f8ddbb9a809f8f4ca
```

The client MUST accept the response wrapper, process results positionally, discard the B.8 candidate at index `0`, and retain the valid Bob candidate at index `1`. Index `0` receives no candidate from this Relay; that is not a final Absent result and later results MUST NOT shift left.

#### B.11.4 Duplicate requested DIDs and cardinality

This canonical request contains `[Alice-DID, Alice-DID, Bob-DID]`:

```text
a20001018378376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d78376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d78376469643a666c773a7a516d64474a624a753670426269795a5839674a48425446786e55437442675261376d5a52634b4b73315463464579

length:
176

SHA-256:
ea2c9422529945ce78406f486c80ad633a1e90726cd493dedfa4347df373cf73
```

The conforming response contains `[Full(B.4), Full(B.4), Full(B.9)]` under the same directory generation. Its encoded length is `1106` and SHA-256 digest is:

```text
203e22e2d913359b08070c289d60889770bcdeee0584187dee25e1c8e05fdfe8
```

A Relay MUST return three results. A client MUST reject a two-result response, even if both returned Full records independently verify. It MUST NOT infer Absent for the omitted occurrence or tail.

#### B.11.5 Changes isolation and cursor progress

Seed the receiving Relay with Alice's exact B.4 envelope as current Root state, Alice `lastUpdated = 41`, and local update counter `41`. Bob is absent. Use recipient time `now_ms = 1785589201123`.

The request uses opaque cursor `v08-0000`, `itemLimit = 2`, and `byteLimit = 1048576`:

```text
a4000101487630382d303030300202031a00100000

length:
21

SHA-256:
e65ad99bab6cd0eefba501a8e65ecfb30ad8ad453da9e554346e2becaab339df
```

The response is the deterministic encoding of:

```cbor
{
  0: 1,
  1: 0,
  2: [
    [ Alice-DID, { 0: 0, 1: h'B.8 complete envelope bytes' }, 1001 ],
    [ Bob-DID,   { 0: 0, 1: h'B.9 complete envelope bytes' }, 1002 ]
  ],
  3: h'7630382d30303032',  / "v08-0002" /
  4: false,
  5: h'000102030405060708090a0b0c0d0e0f'
}
```

Its encoded length is `879` and SHA-256 digest is:

```text
3337aa0be1d6b8cbf856a31657490398a4b778de586e0b292da68c5c26c200f2
```

After processing the accepted wrapper:

1. Alice's complete local entry MUST remain byte-for-byte and field-for-field unchanged: B.4 envelope bytes, Root authority state, `lastUpdated = 41`, and all local update metadata;
2. Bob's B.9 record MUST be admitted as current Root state and receive the sole new local update number, `42`;
3. the local update counter MUST equal `42`;
4. the stored peer cursor MUST equal the exact returned bytes `7630382d30303032`; and
5. the B.8 rejection MUST NOT cause the range to be requested again or alter either Alice's or Bob's state beyond the successful Bob admission.

Sender `lastUpdated` values `1001` and `1002` are not receiver update numbers and MUST NOT be copied into local entry metadata.

#### B.11.6 Malformed DID inside a valid batch

Seed the Relay with Alice's B.4 record and Bob's B.9 record. This deterministic request contains Alice's DID, the syntactically malformed but valid-UTF-8 string `did:flw:not-a-multibase`, and Bob's DID, in that order:

```text
a20001018378376469643a666c773a7a516d5063477374426137775739686f59516253364a5a345578775a6d6f4b7237595666397937717869794433436d776469643a666c773a6e6f742d612d6d756c74696261736578376469643a666c773a7a516d64474a624a753670426269795a5839674a48425446786e55437442675261376d5a52634b4b73315463464579

length:
143

SHA-256:
8276648c9938dcc57a004695414bc7bd6776186b8df1626210667abf1c9ccf38
```

The Relay returns HTTP `200` and the deterministic response `{ 0: 1, 1: directory-generation, 2: [Full(B.4), Error(invalidDid), Full(B.9)] }`, where `directory-generation` is `000102030405060708090a0b0c0d0e0f`. Its encoded length is `748` and SHA-256 digest is:

```text
d8a36364ed62a8fabb905f6c20c04304fe1803df10fa1680840c5c7cd1af96fa
```

The malformed middle DID MUST NOT cause HTTP `400`, terminate the batch, shift either neighbouring result, or suppress Bob's result. The client receives exactly three positionally aligned results and independently verifies the Full candidates at indices `0` and `2` against Alice's and Bob's requested DIDs.

#### B.11.7 `changes` item-limit overflow

Reuse the B.11.5 request and initial receiver state, including `itemLimit = 2`, peer cursor `v08-0000`, Alice's exact B.4 entry at local update `41`, and Bob absent. Assume directory generation `000102030405060708090a0b0c0d0e0f` contains a usable Relay at index `0`.

The invalid response is the deterministic encoding of:

```cbor
{
  0: 1,
  1: 0,
  2: [
    [ Alice-DID,    { 0: 0, 1: h'B.8 complete envelope bytes' }, 1001 ],
    [ Bob-DID,      { 0: 0, 1: h'B.9 complete envelope bytes' }, 1002 ],
    [ Attacker-DID, { 0: 1, 1: 0 },                              1003 ]
  ],
  3: h'7630382d30303033',  / "v08-0003" /
  4: false,
  5: h'000102030405060708090a0b0c0d0e0f'
}
```

`Attacker-DID` is the attacker's own legitimate DID from Section B.8.1. The response is otherwise well-formed, basically valid, deterministic, and schema-conforming, but contains three entries when the request permitted two. Its encoded length is `945` and SHA-256 digest is:

```text
334740ea2ce15b4b70dfcdd88f4cfc7f31bfd53f1b7615aa08df1c4137f4d795
```

The receiver MUST reject the complete response before processing any entry. Alice's full local entry and update metadata remain unchanged, Bob remains absent, the local update counter remains `41`, and the stored peer cursor remains the exact request cursor `7630382d30303030`. The receiver MUST NOT store or use `v08-0003`, even though it is a plausible cursor and the first two entries would fit the requested count if the third were silently ignored.

### B.12 Fault-isolated schema-disallowed-simple-value records

Each vector in this section starts from the B.4 Alice record body, changes the initial map head from `a6` to `a7`, and appends record label `8` followed by an extension map whose key is the valid URI `https://example.com/ext`. The extension value is a deterministically encoded CBOR simple value not admitted by the v1 extension-value schema. Unknown core extensions are otherwise ignored after structural validation.

Both values are well-formed and basically valid. `f0` is the shortest one-byte encoding of simple value 16; `f8 20` is the shortest two-byte encoding of simple value 32. Neither is forbidden by Section 6.1.2, but neither is admitted by `extension-value` in Appendix A. Schema type is therefore the only fault.

```text
simple value 16 appended bytes:
08a17768747470733a2f2f6578616d706c652e636f6d2f657874f0

body digest:
0f08c916dbe92d5bebe06804f4e3bf5a1e23c7f32360638cd7d10a9b15cca1cf

COSE Sig_structure length:
354

signature:
6984d30e32b516e59450cd22c14b7bb6c93b83dad2ce9850e70691a4b76363bfd9823f60151c1c77dfe41f476e4183e28f4e676bbff536d558b96abc2c8e8c0d

expected result:
schemaViolation

simple value 32 appended bytes:
08a17768747470733a2f2f6578616d706c652e636f6d2f657874f820

body digest:
2687c33152622b00dad17f6389a6d781d6065fe3a19e5bf98575d15440e3ff49

COSE Sig_structure length:
355

signature:
1a30f8094723a03835429225a43c500c6cf7b68bbee3fb4e98145215fef849e680e091bae1fec9f07288c7d4ef9c1f235a5272f25260a0e49425036215a4cc06

expected result:
schemaViolation
```

For each vector, the complete envelope is constructed exactly as in Section 6.2 from the mutated raw body and listed signature. The signature is produced with Alice's legitimate B.2 root seed over the exact received body bytes. A verifier that reports `invalidSignature` has failed to use the listed re-signature or has altered those bytes. A verifier that reports `nonDeterministicCbor` has incorrectly treated a schema-disallowed simple value as a Followee profile violation rather than applying the v1 schema.

## Appendix C. References

1. W3C, [Decentralized Identifiers (DIDs) v1.0](https://www.w3.org/TR/did-core/).
2. W3C, [Decentralized Identifier Resolution](https://w3c.github.io/did-resolution/).
3. W3C, [DID Methods](https://www.w3.org/TR/did-extensions-methods/) and [Decentralized Identifier Extensions](https://www.w3.org/TR/did-extensions/).
4. IETF, [RFC 8949: Concise Binary Object Representation](https://www.rfc-editor.org/rfc/rfc8949).
5. IETF, [RFC 8610: Concise Data Definition Language](https://www.rfc-editor.org/rfc/rfc8610).
6. IETF, [RFC 9052: COSE Structures and Process](https://www.rfc-editor.org/rfc/rfc9052).
7. IETF, [RFC 9864: Fully-Specified Algorithms for JOSE and COSE](https://www.rfc-editor.org/rfc/rfc9864).
8. IETF, [RFC 8032: Edwards-Curve Digital Signature Algorithm](https://www.rfc-editor.org/rfc/rfc8032).
9. IETF, [RFC 6234: US Secure Hash Algorithms](https://www.rfc-editor.org/rfc/rfc6234).
10. IETF, [RFC 7033: WebFinger](https://www.rfc-editor.org/rfc/rfc7033).
11. IETF, [RFC 7565: The `acct` URI Scheme](https://www.rfc-editor.org/rfc/rfc7565).
12. IETF, [RFC 3986: Uniform Resource Identifier Syntax](https://www.rfc-editor.org/rfc/rfc3986).
13. IETF, [RFC 7517: JSON Web Key](https://www.rfc-editor.org/rfc/rfc7517).
14. IETF, [RFC 4648: Base Encodings](https://www.rfc-editor.org/rfc/rfc4648).
15. IETF, [RFC 5646: Tags for Identifying Languages](https://www.rfc-editor.org/rfc/rfc5646) (BCP 47).
16. Multiformats, [multibase registry](https://github.com/multiformats/multibase) and [multicodec table](https://github.com/multiformats/multicodec/blob/master/table.csv).
17. IETF, [RFC 5890: Internationalized Domain Names for Applications](https://www.rfc-editor.org/rfc/rfc5890).
18. IETF, [RFC 6838: Media Type Specifications and Registration Procedures](https://www.rfc-editor.org/rfc/rfc6838).
19. IETF, [RFC 8288: Web Linking](https://www.rfc-editor.org/rfc/rfc8288).
20. IETF, [RFC 5234: Augmented BNF for Syntax Specifications](https://www.rfc-editor.org/rfc/rfc5234).
21. IETF, [RFC 3629: UTF-8, a transformation format of ISO 10646](https://www.rfc-editor.org/rfc/rfc3629).

---

## Acknowledgements

Development of this specification benefited from iterative drafting, analysis, and adversarial review using OpenAI's ChatGPT and Anthropic's Claude. These systems are acknowledged as tools rather than authors.

## Licence and disclaimer

Copyright © 2026 Mats Helander.

This specification is licensed under the [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/). It may be shared and adapted, including commercially, provided appropriate attribution is given, a link to the licence is supplied, and changes are indicated.

To the extent permitted by applicable law, this work is provided **as is**, without warranties or conditions of any kind. No author or contributor accepts liability for loss arising from its use or implementation. Implementers are responsible for their own security analysis, testing, legal review, and deployment decisions.

Software implementations are separate works and are intended to be released under the [MIT License](https://opensource.org/license/mit). The `LICENSE` file distributed with each implementation is authoritative for that software.
