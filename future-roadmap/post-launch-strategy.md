<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Post-Launch Strategy

> **Historical context, partially superseded.** The current wedge is native
> resource acquisition/reconciliation → attributed use → explicit feedback →
> portable evidence → funded improvement. [The sequenced
> roadmap](sequenced-roadmap.md) wins on ordering and terminology.

This document intentionally starts after the first MVP launch. The short-term
MVP path is already documented in `plans/` and should remain focused.

## Positioning

Logion should position itself as more than a marketplace for skills.

Skill hubs can copy:

- listings
- install commands
- basic ratings
- `SKILL.md` packaging
- simple paid downloads

They are much less likely to quickly copy:

- ledger-backed economic flows
- entitlement-aware acquisition
- Stripe Connect seller settlement
- bounty-funded improvement loops
- publication review and moderation history
- capability declarations and mismatch evidence
- signed provenance and attestations
- runtime policy export
- sandbox-aware install and execution controls
- multi-harness distribution with one execution surface
- private enterprise registries with audit and governance

The moat should therefore be the combination of:

```text
trust + money + provenance + distribution + improvement liquidity
```

## Immediately After Launch

The first post-launch work should not be full federation or a heavy enterprise
rewrite. It should strengthen the current marketplace loop and make the product
harder to dismiss as "just a skill store".

### Eval-backed bounties and improvement evidence

Before Logion leans heavily on bounties as a marketplace growth loop, it should
make improvement work easier for creators and contributors who do not know how
to design evals themselves.

The key direction is:

- keep creator-provided examples and rationale as helpful signals, not the only
  scoring authority
- add benchmark-backed bounty types for tasks where the platform can provide a
  bounded runner and scorecard
- prefer deterministic evaluation first
- add bounded network-evaluator jobs for fuzzy tasks where the platform owns the
  rubric but trusted agents in the marketplace execute the judging work
- use LLM judging only selectively when deterministic checks and network
  evaluators are still not enough
- treat marketplace behavior as a long-term prioritization and ranking signal,
  not as the sole proof that a specific submission improved quality

See [Eval-Backed Bounties And Improvement Evidence](eval-backed-bounties-and-improvement-evidence.md).

### Version diffs and review diffs

Creators will need precise feedback when a course is rejected or when a new
version changes risk.

Add review surfaces for:

- file diffs between course versions
- manifest diffs
- capability diffs
- dependency diffs
- scanner finding diffs
- permission/risk expansion diffs
- reviewer comments anchored to files or evidence blocks
- "create improvement proposal" or "create bounty from this finding"

The goal is to make review actionable, not merely pass/fail.

### Open improvement proposals without automatic money

The normative lifecycle, language, paid/unpaid outcome distinction, lineage,
and AKTP attestation boundary live in
[`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md).

Add an `improvement_proposals` domain before expanding bounties.

Initial proposals should be:

- attached to a course or course version
- unfunded by default
- visible to the creator
- optionally visible publicly
- convertible into creator-, sponsor-, or platform-funded bounties later
- unable to bypass publication review

An unfunded proposal may accept a free PR/submission and produce an unpaid
accepted-improvement attestation; it is not merely a waiting room for funding.

This lets buyers and agents express demand without turning every suggestion into
an adversarial economic event.

### Explicit bounty/trust boundary

Make the product rule clear:

```text
bounty acceptance is not publication trust
```

Accepted bounty work should still become a new course version and flow through:

- upload/finalization
- capability validation
- scanner review
- human review
- publication decision

Bounties coordinate money. Publication review coordinates trust.

### Harness integrations as primary UX

The CLI should remain the stable execution layer.

The preferred architecture remains:

```text
vendor harness -> vendor plugin/wrapper -> Logion CLI -> Logion API
```

Prioritize:

- Hermes Agent first
- Claude Code
- Codex
- OpenCode
- OpenClaw
- other harnesses only after the wrapper contract is stable

Do not build separate business logic per vendor.

### Marketplace Companion dogfooding

Publish the first-party Logion Marketplace Companion through Logion itself.

That proves:

- a real course bundle can be packaged
- review can inspect it
- acquisition grants entitlement
- install/update works from the marketplace
- Logion can distribute its own core capability through the same path external
  creators use

## Medium-Term Strategy

Medium-term work should turn Logion from a centralized marketplace into a
protocol-compatible marketplace.

The right intermediate target is:

```text
Logion-hosted marketplace with portable, signed, content-addressed course packages.
```

### Protocol-ready packaging

Define a public course package format that is bigger than `SKILL.md`.

The package should include:

```text
course/
  manifest.md
  course/capabilities.yaml
  skills/
  lessons/
  examples/
  tests/
  evals/
  policies/
  install/
  changelog.md
```

The manifest/spec should support:

- package format version
- creator identity
- course metadata
- files and deterministic hashes
- required tools
- declared permissions
- tests/evals
- dependency metadata
- license
- compatibility targets
- optional creator signature

The public CLI should be able to:

- scaffold packages
- validate manifests
- compute hashes
- produce deterministic bundles
- run local scanners
- test packages locally
- publish packages to Logion

### External-hosted bundles with central payment

Allow creators to host bundles outside Logion while keeping:

- Logion discovery
- Logion review
- Logion checkout
- Logion entitlement
- Logion settlement
- Logion dispute and moderation controls

That turns Logion into:

- registry
- trust layer
- payment layer
- entitlement layer
- review layer
- discovery layer
- settlement layer

The creator can host content on their own S3/R2/IPFS/mirror without forcing
Logion to pay every storage/bandwidth cost.

### Attestations

Turn review evidence into portable signed objects over time.

Examples:

- creator signature
- Logion publication attestation
- automated scanner attestation
- human review attestation
- capability mismatch attestation
- bounty acceptance attestation
- sandbox verification attestation

These attestations become the bridge from centralized review to protocol trust.

### B2B private catalogs

Offer Logion Teams/Enterprise as private capability registries.

Important B2B features:

- organization-owned private courses
- org reviewers
- org policies for install/execute
- audit logs
- private bounties
- private improvement proposals
- centralized billing
- approved harness allowlists
- exportable execution policies
- sandbox requirements by org policy

The B2B buyer is not primarily buying "courses". They are buying controlled,
auditable capability distribution for agents.

## Long-Term Strategy

Long-term, Logion can become a protocol and network for agent capabilities.

### Federation and nodes

Only after the hosted marketplace and package format are strong should Logion
move toward multiple nodes.

Possible future node roles:

- public marketplace node
- private enterprise node
- creator-hosted registry
- mirror node
- review/attestation node
- sandbox execution node

Do not start here. This is the direction, not the next implementation step.

### Cross-node discovery

Eventually, clients could resolve courses through canonical URIs such as:

```text
logion://course/<course_id>/versions/<version_id>
logion://did:logion:<creator>/courses/<slug>@<version>
```

Those URIs should point to:

- metadata
- manifest URL
- bundle hash
- attestations
- entitlement requirements
- compatible harnesses
- sandbox/execution policy

### Cross-node entitlements and payments

Cross-node payments should be treated as a late-stage problem.

Early protocol work can decentralize:

- manifests
- packages
- metadata
- discovery
- review attestations
- mirrors

Payment should remain hosted/centralized until the product has enough demand
and operational maturity to handle:

- fraud
- chargebacks
- refunds
- tax
- KYC
- AML
- disputes
- payout failures
- entitlement portability
- multi-node abuse

### Reviewer marketplace

A paid reviewer market is valuable but should come after reputation and
anti-abuse foundations.

Future reviewer flow:

- automated review produces evidence
- multiple qualified reviewers inspect evidence
- disagreement escalates
- reviewer quality is scored over time
- reviewers can earn for useful, accurate work
- organizations can require internal and external review

This should not replace owner/publication controls. It should strengthen them.

### Network reward pool

A contribution-based reward pool can make Logion feel like a living economic
network, but it is adversarial by default.

Do not launch it until there are:

- durable contribution records
- anti-sybil controls
- anti-collusion signals
- delayed payout windows
- admin review
- appeal/dispute controls
- fraud monitoring

Reward systems should begin small and bounded.

## What Not To Do

Avoid these traps after launch:

- trying to become full atproto too early
- decentralizing payment before content
- treating bounty submissions as trusted artifacts
- letting agent voting automatically publish or pay without review
- building heavy TUI before CLI/plugin distribution is strong
- opening fraud/reward internals too early
- creating six vendor-specific products instead of one CLI-first integration
  layer

## Strategic Summary

The strongest path is:

1. launch the hosted marketplace
2. improve trust/review/diffs
3. add open proposals
4. make packages portable and signed
5. support external-hosted content with central payment
6. turn review into attestations
7. add private enterprise registries
8. add sandbox enforcement
9. add reward pools and reviewer markets carefully
10. federate only after the core network has demand
