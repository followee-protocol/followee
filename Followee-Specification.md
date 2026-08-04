# Followee

## `did:flw` DID Method and Relay Protocol Specification

**Author: Mats Helander**
**Draft v0.6**
**5 August 2026**
**Licence: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)**

---

## Abstract

Followee resolves a permanent, self-certifying identifier to its controller's current public contact information through an open network of independently operated relays. It is designed to let a person or organisation be followed independently of the websites, feeds, applications, domains, and platforms it currently uses.

This document defines the `did:flw` DID method and the Followee v1 relay protocol. It specifies identifier construction, Authority Descriptors, deterministic CBOR Identity Records, COSE signatures, one-way root revocation, record ordering, Contact Documents, DID Document projection, WebFinger handle discovery, relay resolution and synchronization, client traversal, limits, errors, and conformance requirements.

Followee has no canonical registry, global ledger, shared history, consensus group, token, or mandatory relay. A conforming resolver verifies every full record locally. Relays are availability infrastructure, not identity authorities.

## 1. Status, scope, and requirements language

### 1.1 Status

This is the first implementer's draft of the Followee specification. It is intended to be complete enough for independent proof-of-concept implementations and adversarial interoperability testing. The `flw` method name, relation URIs, media-type usage, extension context, and registries described here remain subject to the relevant registration processes before a production interoperability claim is made.

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

The optional record extension map uses absolute URI strings as keys. Each key names a public extension specification. Extension values are limited to the CBOR types in Appendix A and remain subject to all aggregate depth, member, string, and byte limits.

Extension integers are limited to the basic CBOR integer range: unsigned values from `0` through `2^64 - 1`, and negative values from `-2^64` through `-1`. Bignum tags are forbidden.

Core implementations MUST ignore unknown well-formed extensions after enforcing their structural limits. An extension MUST NOT alter DID derivation, signature verification, authority precedence, timestamp ordering, size limits, or any other v1 core rule.

## 6. Deterministic CBOR and COSE envelope

### 6.1 Deterministic CBOR profile

Authority Descriptors, public-key objects, Identity Record bodies, Contact Documents, and relay-protocol messages use [RFC 8949](https://www.rfc-editor.org/rfc/rfc8949) CBOR with the core deterministic encoding requirements in Section 4.2.1 of that RFC, further restricted as follows:

1. all arrays, maps, text strings, and byte strings use definite lengths;
2. integers, lengths, and tags use their shortest permitted encodings;
3. map entries are ordered by bytewise lexicographic order of their deterministic encoded keys;
4. duplicate map keys are forbidden;
5. floating-point values, CBOR simple value `undefined`, and CBOR tags are forbidden inside protocol data;
6. the only permitted tag in a complete Identity Record is the required outer COSE Sign1 tag `18`;
7. bignum tags are forbidden; all integers fit the ranges stated by their schema;
8. text strings MUST be valid UTF-8; no Unicode normalization is applied or implied; and
9. a decoder MUST reject, rather than normalize and accept, a non-deterministic encoding.

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
| `2` | `avatar` | absolute URI | 2,048 UTF-8 bytes |
| `3` | `alsoKnownAs` | array of absolute URIs | 32 entries |
| `4` | `services` | array of service maps | 64 entries |
| `5` | `migration` | migration map | one predecessor and one successor |
| `6` | `extensions` | extension map | aggregate limits apply |

Every field is optional, and an empty Contact Document is valid. The Contact Document is nevertheless always present in an Identity Record. Binary avatars, posts, attachments, feed contents, and other large objects MUST NOT be embedded; they are linked by URI.

`alsoKnownAs` entries are signed claims, not proofs that an external authority assigned a name. Domain-qualified handle claims require Section 10 verification.

### 7.2 URI requirements

Every field described as a URI MUST be an absolute URI under [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986), encoded as a CBOR text string. Relative references are malformed. Scheme comparison follows the applicable URI specification; Followee performs no general URI canonicalization.

Clients MUST treat dereferenced URI content as untrusted external content. A signature over an avatar or service URI does not sign the bytes later served by that URI.

### 7.3 Service entries

A service entry is:

| Label | Name | Required | Rule |
| ---: | --- | --- | --- |
| `0` | `id` | Yes | 1–256 ASCII `unreserved` characters; unique within the document |
| `1` | `type` | Yes | Initial type token or absolute URI |
| `2` | `endpoint` | Yes | Absolute URI |
| `3` | `mediaType` | No | RFC 6838 type and subtype, maximum 256 ASCII bytes |
| `4` | `label` | No | UTF-8 text, maximum 256 bytes |
| `5` | `language` | No | Well-formed RFC 5646 language tag, maximum 64 ASCII bytes |
| `6` | `rel` | No | RFC 8288 `reg-rel-type` or absolute URI, maximum 256 bytes |

`mediaType` MUST consist exactly of an RFC 6838 `type-name`, the `/` character, and an RFC 6838 `subtype-name`. Each name MUST satisfy the `restricted-name` grammar in Section 4.2 of that RFC. Media-type parameters are not permitted in this field.

`language` MUST satisfy the `Language-Tag` ABNF in Section 2.1 of RFC 5646, including its fixed grandfathered productions. Verification is case-insensitive as required by that RFC, but the exact signed text is retained. A verifier MUST NOT require subtags to appear in the IANA Language Subtag Registry, replace deprecated subtags with preferred values, or otherwise canonicalize the field.

The token form of `rel` MUST satisfy RFC 8288 `reg-rel-type` exactly: one lowercase ASCII letter followed by zero or more lowercase ASCII letters, digits, `.`, or `-`. Any other relation value MUST be an absolute URI under Section 7.2. A verifier MUST NOT require a token to appear in the IANA Link Relations registry.

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

A type outside this list MUST be an absolute URI naming its specification. Service array order is presentation order; a client may reorder or filter it.

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

Contact extensions use the same absolute-URI-keyed extension map as record extensions. Unknown well-formed fields are ignored. Extensions cannot alter the core interpretation of `alsoKnownAs`, `services`, or `migration`.

## 8. Verification, authority state, and ordering

### 8.1 Full-record verification algorithm

Given expected Followee DID `target`, complete envelope bytes `candidate`, recipient time `now_ms`, and local sticky authority state, a Record Verifier MUST perform the following checks. It may reorder cheap independent checks for denial-of-service resistance, but the final result MUST be equivalent.

1. Reject `candidate` if it exceeds 16 KiB.
2. Parse exactly one tagged COSE Sign1 object within the depth and member limits.
3. Require the exact COSE profile in Section 6.2.
4. Parse the payload as one deterministic `record-body`; reject trailing bytes.
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

A receiving Relay treats each Full change entry as untrusted candidate bytes and runs its own ingress algorithm. It treats each Ref as an unverified routing hint and MUST NOT import the sender's authority state. A receiver may path-compress a reference after consulting the sender's directory.

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
| `4` | `invalidCbor` | CBOR cannot be parsed safely |
| `5` | `nonDeterministicCbor` | Encoding violates Section 6.1 |
| `6` | `schemaViolation` | Parsed object violates its v1 schema or limits |
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

Successful protocol processing, including Absent, per-DID Error results, valid no-change publication, and `ResetRequired`, SHOULD return HTTP `200` with the protocol body. Servers SHOULD use `400` for malformed outer requests, `413` for an HTTP entity rejected before protocol parsing, `415` for unsupported media type, `429` for transport-level rate limiting, and `500` or `503` for failures that prevent a protocol response.

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
- deterministic and non-deterministic CBOR encodings;
- exact COSE protected headers and external AAD;
- strict Ed25519 verification;
- descriptor substitution;
- every target/body/descriptor identity-binding permutation specified in Appendix B.7 item 1;
- root and RootRevoked records;
- valid and invalid `mediaType`, `language`, and `rel` syntax at their exact boundaries;
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
- distinction between Absent and a retained Full record that becomes premature under a backwards clock correction;
- coalesced `changes` output;
- every status-dependent required and forbidden `changes` field combination, including the exact two-field status `1` ResetRequired response;
- cursor pagination without gaps;
- cursor-generation reset;
- restore-time behaviour; and
- bounded resource use under invalid and Sybil input.

### 20.3 Client tests

A conforming DID Resolver or Followee client MUST additionally pass tests covering:

- multi-relay candidate selection;
- continuation past Absent and per-DID Error results while an unqueried Relay selected for the operation and sufficient shared budget remain;
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
- CBOR labels and deterministic profile;
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
15. `validUntil_ms < timestamp_ms`; and
16. any aggregate hard limit exceeded.

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

---

## Acknowledgements

Development of this specification benefited from iterative drafting, analysis, and adversarial review using OpenAI's ChatGPT and Anthropic's Claude. These systems are acknowledged as tools rather than authors.

## Licence and disclaimer

Copyright © 2026 Mats Helander.

This specification is licensed under the [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/). It may be shared and adapted, including commercially, provided appropriate attribution is given, a link to the licence is supplied, and changes are indicated.

To the extent permitted by applicable law, this work is provided **as is**, without warranties or conditions of any kind. No author or contributor accepts liability for loss arising from its use or implementation. Implementers are responsible for their own security analysis, testing, legal review, and deployment decisions.

Software implementations are separate works and are intended to be released under the [MIT License](https://opensource.org/license/mit). The `LICENSE` file distributed with each implementation is authoritative for that software.
