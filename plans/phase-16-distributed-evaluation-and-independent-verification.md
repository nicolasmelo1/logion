<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16 — Distributed evaluation and independent verification

> **Dogfood status:** continuous; every subphase must run first on Logion's own node before external exposure.
> **After this phase:** independent runners can reproduce bounded evaluations and issue their own attestations without trusting Logion infrastructure.
> **Honesty boundary:** disagreement is recorded, not averaged away or mislabeled as consensus.

## Goal

Move from one useful operator to a credible network: portable eval contracts, runner-supplied compute, deterministic replication, issuer-aware authority, and bounties settled against evidence.

## Umbrella dogfood instruction

Do not create an umbrella-level review. Every 16.x subphase begins with a concrete Logion prompt naming the marketplace query and how the installed Course must affect that implementation. The implementing agent follows the mandatory protocol in that file and sends a real Course/version usage review only after the named product gate passes. Missing bundles, approval refusal, auth, and indexed-only results are recorded as product failures, never bypassed or reviewed falsely.

## Implementation handoff rule

Each subphase must land as a focused public/private/infra PR set described by
its file. Generated clients follow OpenAPI, shared wire semantics live in public
versioned packages, private services consume them, and protocol/evidence
immutability forbids destructive retrofits. An implementer must read the active
15.10–15.17 plans, the retained 15.9/15.9.1 carry-over in `next-steps.md`, and
the current maintainer-documentation anchors before coding.

Phases 16.7 and 16.9 also inherit
[`asm-logion-collaboration-and-protocol-convergence-gate.md`](asm-logion-collaboration-and-protocol-convergence-gate.md):
local ranking may consume an agreed open selection contract, but Phase 16 does
not publish a competing service-value manifest, global score, or second receipt.

## Sequence

1. 16.1 eval contract and local reference runner.
2. 16.2 typed evaluator interface and skill evaluator.
3. 16.3 runner registry and network jobs.
4. 16.4 deterministic replication and agreement.
5. 16.5 eval attestations and cross-node authority.
6. 16.6 benchmark-backed bounties.
7. 16.7 evidence search and issuer-aware ranking.
8. 16.8 portable field evidence and aggregation.
9. 16.9 benchmark/field reconciliation.
10. 16.10 external runner onboarding and conformance.
11. 16.11 MCP safe probes.
12. 16.12 Hugging Face metadata and constrained model evaluation.

## Exit gate

At least one independently operated runner reproduces a Logion fixture, publishes a verifiable attestation, disagrees safely on a negative fixture, and receives a bounded bounty payout through node-local settlement.

Every 16.1–16.12 scenario in the subphase specs must also pass
[the mandatory proving-ground gate](agent-proving-ground-phase-gate.md) with
GPT-5.4-mini or Claude Haiku against `local-devrig`. Scripted orchestration tests
and one broad distributed-eval demo cannot replace a missing subphase run.
