# Permitted nondeterminism and opacity

Two conforming implementations must produce byte-identical results for
everything the specification makes deterministic, and must be compared
only semantically for everything the specification leaves to the relay
or transport. This file states which is which for the interoperability
experiment, so that neither side normalizes away a real disagreement or
fails the run over a value that was never required to match.

## Byte-deterministic — compared byte for byte

- Authority Descriptor CBOR, revocation-key commitments, descriptor
  digests, multihashes, DIDs (Sections 3–4).
- Record body CBOR, body digests, COSE `Sig_structure` bytes, Ed25519
  signatures, complete envelopes (Sections 5–6; deterministic CBOR plus
  deterministic RFC 8032 signing).
- Winner selection: winning body digest and resulting authority state
  for a given target, candidate set, `nowMs`, and sticky state
  (Section 8), independent of candidate delivery order.
- The CBOR encoding of every relay request and response wrapper an
  implementation emits for given protocol-level content (Section 6.1
  applies to relay messages).

## Relay-chosen or opaque — never byte-compared, never normalized

These values are semantically real. They are excluded from
byte-comparison because the specification defines them as relay-local
or opaque, not because they are noise. A comparison harness must not
rewrite, sort, or replace them inside a captured message; it compares
the containing message structurally and treats these fields as opaque
equality tokens exactly as a protocol peer would.

| Value | Nature |
| --- | --- |
| Relay instance identifier (info label 1, directory entries) | Stable opaque 16 bytes, relay-chosen |
| Cursor generation (info label 6) | Opaque 16 bytes, regenerated on reset |
| Directory generation (info label 7, resolve/changes label 5) | Opaque 16 bytes; equality token scoping indices |
| Cursors and `nextCursor` | Opaque byte strings up to 128 bytes; only the exact returned bytes may be presented back |
| Relay-local update numbers / `lastUpdated` | Relay-local ordering values; never copied between relays |
| Directory indices | Meaningful only within one directory generation |
| Advertised limits (info label 5) | Relay policy within specification bounds |
| Base URIs, relay set composition, `hasMore` timing | Deployment and timing dependent |

## Transport-layer variation

HTTP header names are case-insensitive, header order is not
significant, and transfer framing (chunking, connection reuse, TLS
details) is not part of the protocol. Captured exchange transcripts
record method, path, status, content type, and exact body bytes; they
deliberately omit other headers. A conforming exchange may differ in
any omitted transport detail.

## The rule against invented stability

Do not invent a normative requirement merely to make a transcript
byte-stable. Where a captured or documented exchange contains an
illustrative relay-chosen value, its provenance is marked
`illustrative-nonnormative`, and a live exchange is correct with any
other specification-conforming value in that position. Conversely, a
mismatch in any byte-deterministic value above is a real
interoperability failure and must be reported, not patched over by
normalization.
