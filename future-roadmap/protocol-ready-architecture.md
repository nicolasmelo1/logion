<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Protocol-Ready Architecture

> **2026 direction note:** this path remains because current plans reference it,
> but the architecture now centers generic `Resource`. ARD is discovery; AKTP
> extends evidence and improvement. Native managers keep third-party delivery.
> No universal package format, compute fleet, or global authority is implied.

This document describes how Logion can evolve toward a protocol-compatible
architecture without rewriting the current marketplace or breaking the MVP.

## Principle

Do not attempt full federation immediately.

Instead, make the existing centralized marketplace protocol-ready:

- portable package format
- deterministic manifests
- content-addressed bundles
- optional creator signatures
- canonical URIs
- external-hosted bundles
- signed review attestations
- central payments and entitlements at first

This gives Logion a protocol path while preserving current product velocity.

## What The Current Architecture Already Gets Right

### Versioned courses

Course versions are the right foundation. Protocol objects must be immutable or
the trust model becomes ambiguous.

### Content hashes

Hashes can become the basis for:

- bundle verification
- tamper detection
- reproducible review
- mirror validation
- signed attestations

### S3 assets can be abstracted later

Current S3-backed assets are fine for MVP. They do not block future support for
external URLs or other storage providers if the model evolves additively.

### Entitlements are separate from orders

This is essential. In the future, Logion can grant entitlements to resources
whose content is hosted outside Logion.

### Ledger exists

The append-only ledger is important for:

- seller settlement
- bounty escrow/release/refund
- future reward pools
- audit trails
- reconciliation

### Bounties are separate

Bounties are economic coordination, not course ownership or publication trust.
That separation is necessary for sponsor-funded and platform-funded improvement
lanes later.

### Review pipeline is separate

Publication review can later produce signed attestations without changing the
core course model.

### Agent-scoped marketplace

Agents are already first-class actors. That aligns with a future where agents
resolve, install, review, improve, and purchase capabilities.

## Non-Breaking Protocol-Ready Additions

These additions should be optional/nullable at first.

### Courses

Potential future fields:

```text
canonical_uri
source_node_id
external_home_url
license
protocol_visibility
```

Purpose:

- identify a course outside the local database
- link to a source node or external homepage
- expose licensing
- control whether a course is local-only, public, mirrored, or federated

### Course versions

Potential future fields:

```text
manifest_url
manifest_hash
bundle_hash
signature
signature_algorithm
storage_provider
external_bundle_url
protocol_version
```

Purpose:

- verify externally hosted manifests/bundles
- preserve current S3 storage while enabling external storage
- support signed course packages
- allow future protocol evolution without changing old versions

### Nodes

Potential future table:

```text
nodes
- id
- node_id
- did
- base_url
- public_key
- status
- trust_level
- created_at
- updated_at
```

Purpose:

- identify external registries or mirrors
- store trust status
- verify signatures from known nodes
- support later federation

### Course attestations

Potential future table:

```text
course_attestations
- id
- course_id
- version_id
- issuer_node_id
- issuer_agent_id
- attestation_type
- payload_json
- signature
- signature_algorithm
- created_at
```

`attestation_type` is an **open reverse-DNS namespace**, not a closed enum
(see the extensibility model in
[Open Protocol And Entitlement Portability](open-protocol-and-entitlement-portability.md)):
Logion mints under `sh.logion.*`; third parties mint under their own
domains (`com.vanta.soc2`, insurance coverage, eval scores) without
permission. Verifiers ignore types they do not recognize; each index
chooses which types carry ranking/policy weight.

Logion's own initial types (`sh.logion.*`):

- `creator_signature`
- `automated_security_review`
- `human_publication_review`
- `capability_mismatch_report`
- `sandbox_verification`
- `bounty_acceptance`
- `logion_publication`

### Protocol events

Potential future table:

```text
protocol_events
- id
- event_type
- actor_agent_id
- object_type
- object_id
- payload_json
- signature
- created_at
```

Purpose:

- create an append-only product event stream
- support mirrors or sync later
- preserve a path toward node-to-node replication

### External course sources

Potential future table:

```text
external_course_sources
- id
- course_id
- node_id
- canonical_url
- sync_status
- last_seen_at
- last_error
- created_at
- updated_at
```

Purpose:

- index external-hosted courses
- track sync health
- separate local course identity from source location

## What Would Be Breaking Too Early

Avoid these changes until the protocol is mature:

- replacing local `course.id` with global URIs
- replacing local `owner_agent_id` with mandatory federated identity
- requiring all entitlements to be cross-node
- making all storage abstract instead of adding optional external storage
- assuming orders always involve remote sellers
- assuming the review pipeline always works on remote bundles only
- making checkout work across independent nodes
- making bounties target remote creators by default
- replacing local API keys/auth with protocol identity

Those changes would force a rewrite before PMF.

## Recommended Phases

### Phase 2A: Protocol-ready packaging

Goal: current centralized courses become portable.

Deliverables:

- public AKTP course manifest spec
- deterministic manifest generation
- deterministic bundle hashing
- local package validation
- local scanner execution
- optional creator signatures
- CLI support for package/validate/hash/test

### Phase 2B: External-hosted courses, central payment

Goal: creators can host bundles outside Logion while Logion keeps monetization
and trust.

Deliverables:

- `storage_provider = logion_s3 | external_url`
- `external_bundle_url`
- manifest and bundle hash validation
- review pipeline can fetch external bundle
- purchase still uses Logion Checkout
- entitlement still issued by Logion
- payout still uses Stripe Connect

### Phase 2C: Attestations and trust layer

Goal: review and provenance become portable trust objects.

Deliverables:

- automated scanner attestation
- human review attestation
- creator signature attestation
- Logion publication attestation
- bounty acceptance attestation
- public read surface for approved attestations

### Phase 2D: Network rewards

Goal: contributions can earn beyond direct course sales and creator-funded
bounties.

Deliverables:

- ledger accounts for network pool
- contribution scoring
- reward eligibility
- payout thresholds
- delayed settlement windows
- anti-fraud review

This should happen after packages, external hosting, and attestations are real.

### Phase 2E: Federation and multiple nodes

Goal: other nodes can index, mirror, publish, or attest.

Deliverables:

- node registry
- sync protocol
- mirror validation
- trust levels
- protocol events
- portable identities
- cross-node reads

Cross-node payments should remain a later problem.

## Hybrid External Hosting Model

The first useful protocol-compatible model is:

```text
creator-hosted bundle
  -> Logion indexes manifest + hash
  -> Logion reviews bundle
  -> buyer purchases through Logion
  -> Logion grants entitlement
  -> client downloads from external host after entitlement check
```

This preserves:

- monetization
- review
- moderation
- disputes
- seller settlement
- entitlement control

while reducing:

- Logion storage cost
- Logion bandwidth cost
- creator lock-in

## Open Source Boundary

Open first:

- course format / manifest spec
- CLI
- SDK/types
- local validators
- basic local scanners
- examples/templates
- protocol docs once real

Keep closed or source-available initially:

- hosted marketplace backend
- payment and ledger internals
- fraud/reward scoring
- admin/review operational tooling
- proprietary ranking signals

This keeps the ecosystem open while protecting the operational and economic
engine before PMF.
