<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 17 — Open ecosystem and production hardening

> **Dogfood status:** permanent; Logion remains a normal node that uses public protocols and conformance paths.
> **After this phase:** the system is useful beyond Logion, supports private deployments, and has a defensible attributed use/feedback/evidence/improvement graph rather than a proprietary discovery or installer moat.
> **Honesty boundary:** defensibility comes from real workflow adoption, outcome history, issuer relationships, and improvement liquidity—not ownership of ARD, native package managers, or unverifiable “network intelligence”.

## Goal

Harden the protocol and product only after the first independent verification loop works.

## Umbrella dogfood instruction

Each 17.x phase has a mandatory store-search/use/review prompt. Run it independently for the real task; do not claim the earlier phase's review as dogfood for a later phase. The review is submitted through `logion courses report-usage`, not written only in the PR, and is forbidden when the Course was not installed and used.

## Implementation handoff rule

Phase 17 cannot compensate for missing Phase 16 exit gates. Federation, claims, private nodes, copy, and conformance ship behind separate flags and rollback paths. The concrete subphase specs—not this umbrella—define files, security cases, tests, and rollout.

Phase 17.1 carries forward the attributable outcome of
[`asm-logion-collaboration-and-protocol-convergence-gate.md`](asm-logion-collaboration-and-protocol-convergence-gate.md).
It may publish joint conformance or contribute upstream only with agreed wording;
it must not retroactively describe exploratory contact as adoption or partnership.

## Sequence

1. 17.1 AI Catalog/ARD/AKTP conformance and upstream proposals.
2. 17.2 federation between independently operated nodes.
3. 17.3 resource claims and commercial rails.
4. 17.4 enterprise/private nodes.
5. 17.5 trust-boundary invariant tests.
6. 17.6 public narrative and landing truth pass.

## Exit gate

Two independently operated nodes exchange and verify evidence, retain distinct authority policies, complete one improvement workflow, and survive protocol upgrade, key rotation, and node outage without a central truth dependency.

Every 17.1–17.6 scenario in the subphase specs must pass
[the mandatory proving-ground gate](agent-proving-ground-phase-gate.md) against
locally running APIs with a cheap real agent. Multi-node scenarios may run two
local dev rigs, but must keep databases, issuer keys, homes, and role
credentials independent.
