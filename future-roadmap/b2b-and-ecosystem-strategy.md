<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# B2B And Ecosystem Strategy

> **2026 direction note:** treat Course/skill below as compatibility examples
> of a generic resource. The wedge is native reconciliation, consented feedback,
> issuer-aware evidence, and private-node policy—not a proprietary installer or
> catalog-only sale. [The sequenced roadmap](sequenced-roadmap.md) governs order.

This document covers Logion's post-MVP route into teams, enterprises, open
source, and harness ecosystems.

## B2C Versus B2B Positioning

For B2C, Logion can be described as:

```text
a marketplace where agents buy and install operational capabilities
```

For B2B, that is too small.

For teams and enterprises, the better positioning is:

```text
a private, auditable registry and trust layer for agent capabilities
```

Enterprises care less about "courses" as a consumer category and more about:

- approved capabilities
- internal distribution
- who installed what
- what permissions were requested
- who reviewed the package
- what version is running
- whether execution is sandboxed
- how to revoke or update
- how to fund internal improvements
- how to prove compliance

## B2B Product Shape

### Teams

Team features:

- organization accounts
- shared billing
- private courses
- private listings
- member roles
- org-level reviewers
- private bounties
- install audit logs
- capability approval policy
- harness integration setup

### Enterprise

Enterprise features:

- SSO/SAML/OIDC
- SCIM or directory sync
- private registry
- VPC/private deployment option later
- policy-as-code for installs
- required sandbox mode
- exportable audit logs
- org-specific scanners or allowlists
- legal/compliance reporting
- admin override and revocation
- SLA/support

### Self-hosted or internal registry

Self-hosting should not be the first enterprise feature, but the architecture
should leave room for it.

The first useful step is:

```text
private hosted registry with protocol-compatible packages
```

Later:

```text
customer-hosted registry node with optional Logion Cloud trust/payment services
```

## Protocol And Payment Split

Separate what can become protocol/open from what should stay hosted initially.

Protocol-compatible:

- course manifests
- bundle hashes
- package signatures
- capability metadata
- review attestations
- sandbox attestations
- public metadata
- mirrors
- external-hosted content

Hosted initially:

- Stripe Billing
- Stripe Connect
- KYC/onboarding
- refunds
- chargebacks
- tax/compliance
- paid entitlements
- bounty escrow
- reward pool
- fraud controls
- disputes

This lets Logion support external hosting and future nodes without giving up the
economic center too early.

## Harness Strategy

Logion should meet users inside existing harnesses instead of forcing a heavy
new UI.

Priority:

1. CLI as stable engine
2. SDK/types as stable contract
3. vendor plugins/wrappers as primary UX
4. web/TUI later where useful for creators/admins

Required CLI properties:

- `--json` for all important commands
- stable exit codes
- clean stdout/stderr separation
- small composable subcommands
- explicit paid actions
- explicit install/update approval
- machine-readable errors

The wrappers should stay thin:

```text
harness command -> wrapper -> logion CLI --json -> render host-native response
```

## Public And Private Repository Boundary

Recommended long-term repo strategy:

- public `logion` repo for CLI, SDK, types, companion, vendor integrations,
  package spec, examples, validators, and mock API
- private API/backend repo for hosted marketplace, payments, ledger, fraud,
  admin/review operations, and private infra
- private workspace repo for shared internal docs, orchestration, and local
  cross-repo development

Avoid using git submodules as the primary workflow. A private workspace with
cloned sibling repos and shared scripts is easier for humans, CI, and agents.

## Public Mock API And Contract Testing

External contributors should not need private backend access.

The public repo should eventually include:

- versioned OpenAPI contract
- generated or shared SDK/types
- mock API/dev server
- fixtures for marketplace flows
- fake auth
- fake course listings
- fake acquisition/entitlement responses
- fake install/update flows
- contract tests

The private API and public mock should both satisfy the same public contract.

This supports:

- public CLI contributions
- vendor plugin development
- docs examples
- CI without private secrets
- compatibility checks

## Open Source Strategy

Open first:

- course package spec
- CLI
- SDK/types
- vendor wrappers
- companion package
- local validators
- basic local scanners
- mock API
- examples/templates

Keep private initially:

- hosted marketplace backend
- payments and ledger internals
- fraud/reward scoring
- proprietary ranking signals
- admin/review operational tooling
- sensitive anti-abuse checks

This is open-core in practice:

- open ecosystem and tooling
- hosted trust/economy as the commercial center

## Listings And Ranking

Listings should eventually support a pluggable ranking architecture.

Open-source:

- base retrieval
- filters
- normalization
- schema
- default ranking
- explainability fields
- BYO ranker interface

Hosted/private controls:

- abuse suppression
- compliance constraints
- paid marketplace policy
- proprietary fraud signals
- marketplace experiments

This lets advanced users customize ranking without forcing Logion to reveal
every anti-abuse signal.

## Local-First And Offline Compatibility

Agents work better when common reads are local and low-friction.

Invest in:

- local installed-course manifest
- local entitlement metadata
- local recall/search
- cached listing metadata
- update checks
- install receipts
- offline inspection
- sync once online

This helps both B2C and enterprise usage.

## Security And Supply Chain As B2B Moat

Generic skill hubs can offer discovery. Logion should offer stronger security:

- signed bundles
- checksums
- provenance
- review history
- capability declarations
- observed mismatch evidence
- execution policy export
- sandbox enforcement
- install receipts
- audit logs
- revocation/update controls

That is the enterprise wedge.

## Narrative

The strongest external narrative is not:

```text
marketplace of courses for agents
```

It is:

```text
the economic network for agent capabilities
```

Expanded:

```text
Logion is a protocol-compatible marketplace where agents discover, buy, install,
verify, improve, and monetize operational capabilities.
```

This connects:

- marketplace
- protocol
- bounties
- reputation
- review/security
- open ecosystem
- enterprise governance
- network effects
