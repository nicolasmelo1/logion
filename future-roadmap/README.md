<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Future roadmap

This directory describes Logion after the product-direction correction captured
in Phase 15.9 onward. `plans/` is the implementation source of truth. These
documents may explain later bets, but cannot pull infrastructure-heavy work
ahead of the evidence required by the phase plans.

## Product thesis

Logion is not primarily a store that invents a new way to install skills, a
centralized eval lab, or a GPU provider.

Logion is the resource-use, evidence, and improvement layer that fits the agent
workflow people already have:

```text
existing native acquisition
  → canonical resource/version attribution
  → privacy-controlled use evidence and feedback
  → portable issuer-aware claims
  → funded improvement work
  → independent reproduction
```

The catalog may index skills, plugins, MCP servers, models, Courses, and future
resource types. Native managers remain native: `npx skills`, `npx plugins`, and
`hf` do not need to be replaced. Logion adds reconciliation, evidence,
feedback, and economic coordination around them. Hosted Logion artifacts remain
one supported distribution, not the universal distribution format.

Logion is open-source first. Revenue rails may fund sustainability, but they do
not control the roadmap thesis. The canonical plans are projected into the
public repository, where contributors can propose concrete changes; accepted
changes are ported to the canonical source and re-emitted without losing credit.

[AI Catalog](https://ai-catalog.io/) is the typed, nestable JSON catalog/entry
substrate. [ARD](https://agenticresourcediscovery.org/) is the pre-invocation
discovery protocol and registry layer that searches/returns AI Catalog entries;
it is not the catalog format itself. AKTP is a narrow, optional
evidence/work/outcome overlay linked to those resource identities. Logion must
pin and test AI Catalog and ARD separately and claim ownership of neither.
The first node bootstraps ARD discovery from the official
[`ard-connectors`](https://github.com/ards-project/ard-connectors) Agent Finder
directory on the server/indexer side. It does not install those connectors into
customer clients.

Normative snapshots and machine-readable schemas are pinned in
[`protocol-specs/`](../protocol-specs/README.md). Agents changing these layers
must read those sources first; roadmap prose is not a substitute for either
specification.

## What is defensible if this works

The moat is not the listing page, installer wrapper, model endpoint, or protocol
acronym. Those are reproducible.

Potentially defensible assets are:

- exact attribution from native acquisition and real agent use to immutable
  resources;
- a longitudinal, consented feedback/outcome graph that competitors cannot
  reconstruct from public metadata;
- issuer-aware evidence and reproduction history;
- trusted relationships with resource owners, sponsors, and independent
  operators;
- liquidity that turns observed failure into funded, verified improvement;
- public integration artifacts embedded in existing agent workflows.

None is defensible before adoption. Therefore the roadmap measures completed
customer loops and independent operation, not schema volume or catalog size.

## Capital and infrastructure rule

Logion does not buy a GPU fleet to validate the thesis. The first node runs on a
developer machine or small CPU server and uses bounded third-party model calls.
Later runners advertise and bring their own compute; sponsors fund unusually
expensive jobs explicitly.

No roadmap item may assume:

- owned H100/H200/B200 capacity;
- mirroring arbitrary model weights;
- a proprietary universal runtime;
- cross-node settlement before node-local economics work;
- automatic spending from opaque telemetry;
- “consensus” when only Logion ran the check.

The founder's first node may run entirely on one MacBook: the existing host
Hermes coordinates isolated Docker/Podman role agents with separate homes,
credentials, repository scopes, and cheap hosted-model budgets. This is honest
first-party bootstrap, not independent network participation.

## Product-quality rule

Every implementation phase from 15.9 onward has a named customer-like scenario
in `packages/agent-proving-ground`. Unit tests and scripted agents remain useful
but do not close a phase. The scenario must pass against the locally running
API with GPT-5.4-mini or Claude Haiku, using public product surfaces and
observed-effect assertions.

See:

- [Agent proving-ground and customer fidelity](agent-proving-ground-and-customer-fidelity.md)
- [Mandatory phase gate](../plans/agent-proving-ground-phase-gate.md)

## Current reading order

1. [Sequenced roadmap](sequenced-roadmap.md)
2. [Native resource, feedback, and first-node strategy](native-resource-feedback-and-first-node.md)
3. [Agent proving-ground and customer fidelity](agent-proving-ground-and-customer-fidelity.md)
4. [Protocol-ready architecture](protocol-ready-architecture.md)
5. [Open protocol and entitlement portability](open-protocol-and-entitlement-portability.md)
6. [Eval-backed bounties and improvement evidence](eval-backed-bounties-and-improvement-evidence.md)
7. [Sandbox and runtime trust](sandbox-and-runtime-trust.md)
8. [Economic network and rewards](economic-network-and-rewards.md)
9. [Human dashboard and user policy](human-dashboard-and-user-policy.md)
10. [B2B and ecosystem strategy](b2b-and-ecosystem-strategy.md)

`post-launch-strategy.md` is retained as historical strategic context, but
`sequenced-roadmap.md` wins on ordering and terminology.

## Ideas deliberately removed

The following former standalone roadmap tracks were removed:

- an RL-environment/training marketplace;
- Logion-owned large-artifact/Merkle delivery;
- smart/metered payment machinery;
- generic skill-composition/routing resolution.

They were not all inherently bad. They were bad commitments now: each pulled
Logion toward compute, storage, payment, or orchestration infrastructure before
the native-use feedback loop had demand. A concrete customer problem may
reintroduce a narrow version later, but the old documents must not act as latent
authorization to build them.

## Decision rule for any new roadmap item

Add it only if the answer to all five questions is credible:

1. Which observed customer/resource problem creates it?
2. Can the first version run on the existing node or participant-supplied
   infrastructure?
3. What portable evidence will prove it works?
4. What named real-agent proving-ground scenario closes it?
5. What metric or kill criterion prevents infrastructure theater?
