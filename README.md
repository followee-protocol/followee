# Followee

**A relay protocol for following people, not platforms.**

Followee is an open DID method and relay protocol for resolving a permanent, self-certifying identifier to its controller’s current public contact information.

It allows people and organisations to remain followable when they move between websites, feeds, applications, domains and platforms. Independently operated relays distribute signed full records or references, but clients verify records locally; relays are availability infrastructure, not identity authorities.

## Documents

- [Whitepaper](Followee-Whitepaper.md) — motivation, architecture and design rationale
- [`did:flw` Method and Relay Protocol Specification](Followee-Specification.md) — normative wire formats, validation rules, APIs and conformance requirements
- [Interoperability campaign 1](interop/campaign-1/CAMPAIGN.md) — independent Rust ↔ Motoko convergence evidence (v0.9.1)
- [Interoperability campaign 2](interop/campaign-2/CAMPAIGN.md) — maintained Rust ↔ Motoko interoperability evidence (v0.9.2)
- [Operational-readiness plan](OPERATIONAL-READINESS.md) — the next milestone: predeclared gates for the remaining conformance, lifecycle, network, and release work

## Status

The current specification is the **v0.9.2 implementer’s draft**.

Two proof-of-concept implementations exist, in Rust and Motoko. Campaign 1 preserves the independent-convergence evidence between them at its historical scope (v0.9.1, frozen at tag `v0.9.1-interop-campaign-1`). Campaign 2 demonstrates maintained Rust–Motoko interoperability under the v0.9.2 authoring-revision-2 contract for its documented tested scope, with zero unexplained disagreements; its coverage boundary is recorded in the campaign record and does not extend to multi-relay traversal, WebFinger handles, concurrency behaviour, or public (non-loopback) deployment.

The `did:flw` method and the proposed Followee WebFinger relation URIs are **not yet registered**, and Followee must not yet be presented as production-ready or as a finalized standard. Interoperability at Campaign 2’s scope is not a production-readiness claim, and registry inclusion, when it happens, will be discovery metadata rather than standardization in itself.

The next milestone is the operational-readiness program defined in [`OPERATIONAL-READINESS.md`](OPERATIONAL-READINESS.md). Formal GitHub release-candidate publication remains deferred until the pre-release gates designated in that plan pass.

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