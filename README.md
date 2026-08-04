# Followee

**A relay protocol for following people, not platforms.**

Followee is an open DID method and relay protocol for resolving a permanent, self-certifying identifier to its controller’s current public contact information.

It allows people and organisations to remain followable when they move between websites, feeds, applications, domains and platforms. Independently operated relays distribute signed full records or references, but clients verify records locally; relays are availability infrastructure, not identity authorities.

## Documents

- [Whitepaper](Followee-Whitepaper.md) — motivation, architecture and design rationale
- [`did:flw` Method and Relay Protocol Specification](Followee-Specification.md) — normative wire formats, validation rules, APIs and conformance requirements

## Status

Followee is currently an implementer’s draft at version 0.1. The protocol is ready for independent proof-of-concept implementations and adversarial interoperability testing, but `did:flw` has not yet been registered and should not be treated as production-standardised.

The next milestone is two independent implementations consuming the same machine-readable conformance vectors and producing identical results.

## Design principles

- Follow people, not accounts on particular platforms.
- Keep durable identifiers separate from human-readable handles.
- Treat relays as untrusted availability infrastructure.
- Verify every full record locally.
- Require no canonical registry, blockchain, consensus group or mandatory relay.
- Keep the base protocol independent of any hosting platform.

## Licence

The whitepaper and specification are licensed under the [Creative Commons Attribution 4.0 International Licence](LICENSE).

Copyright © 2026 Mats Helander.