<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15 — Native resource feedback loop and the first AI Catalog/ARD node

> **Dogfood status:** begins in 15.10 with real artifact acquisition, captures native-workflow feedback in 15.11, and becomes end-to-end in 15.16.
> **After this phase:** Logion adapts to native resource managers, links real
> use/feedback to canonical resources, publishes AI Catalog, discovers through
> ARD, operates an isolated runner, and publishes portable evidence.
> **Honesty boundary:** until independent nodes reproduce results, evidence is explicitly first-party, never “network consensus”.

## Goal

Turn the existing marketplace, indexer, scanners, proving ground, jobs, and
bounty rails into the first useful node of an open resource-improvement network.
AI Catalog owns the typed publication format; ARD supplies pre-invocation
discovery/registry behavior over its entries. AKTP starts narrowly as the
evidence, work, and improvement overlay.

## Umbrella dogfood instruction

This umbrella is not implemented as one PR and must not produce one synthetic
umbrella review. For each active 15.10–15.17 implementation, execute the
phase-specific prompt and its inherited carry-over gates. From 15.10 onward
this means real artifact acquisition through Logion or the recommended native
manager; from 15.11 onward it also means exact reconciliation, observed use,
and one honest generic `feedback submit` report with its Course-review
projection disposition. A resource may be reused only when it genuinely fits
the next task; each phase still needs its own use evidence and feedback
judgment.

## Implementation handoff rule

The subphase file is authoritative for tables, wire contracts, files, migrations, failure cases, tests, rollout, and acceptance gates. A smaller implementing model must not start from this umbrella alone. Phase ordering is strict except that documentation/fixture preparation may overlap; no later phase may fake a dependency behind a mock in production.

## What remains valid

The delivered foundation includes GitHub identity, package maps, publishing,
PR delivery, external indexing, indexed-listing observation scans, discovery
tiers, platform-funded bounties, and generic resource identity/backfill.

## Current lifecycle

The former 15.8.1 planning mirror, 15.9 generic identity/backfill, and shipped
15.9.1 scope/inventory/dry-run/envelope subset are consolidated foundation; the
canonical public mirror retires those three plan files. Missing HMAC identity,
real acquisition, cryptographic signature verification, and harness-integrated
observation are not claimed shipped: their complete contract lives in
`next-steps.md` and is inherited by 15.10/15.11.

1. **15.10:** native acquisition, hosted artifact delivery, and local inventory.
2. **15.11:** native-use observation, generic feedback, and Course-review projection.
3. **15.11.1:** publisher-integrated consented observation.
4. **15.12:** AI Catalog publication/ingestion and ARD discovery.
5. **15.13:** signed portable scanner evidence.
6. **15.14:** feedback-driven platform bounties.
7. **15.14.1:** local multi-agent first-node foundation.
8. **15.15:** isolated first runner node.
9. **15.16:** first-party recurring dogfood loop.
10. **15.17:** AKTP evidence and improvement feed v0.

## Architectural rule

`native managers or Logion acquire → a separate companion or
publisher-integrated projection attributes consented use and feedback → AI
Catalog publishes → ARD discovers → Logion/AKTP coordinates evidence and
improvement → resource owners publish the result`.

Publisher integration is a distribution/runtime concern. It does not add
consent, hooks, or receipt semantics to AI Catalog or ARD. Portable static
Skills remain valid distributions even when their harness exposes no automatic
use-observation lifecycle.

`Course` and the current skill CLI remain supported commercial/editorial projections. `Resource` becomes the protocol identity. No big-bang rename and no custom discovery protocol.

Before 15.12 freezes adjacent selection metadata and before 15.17 freezes a
receipt/event contract, follow
[`asm-logion-collaboration-and-protocol-convergence-gate.md`](asm-logion-collaboration-and-protocol-convergence-gate.md).
ASM is a candidate collaboration boundary, not another mandatory protocol.
Logion adds no competing selection descriptor or duplicate invocation receipt
while convergence remains viable.

## Exit gate

A resource acquired through Logion or a native manager can be reconciled to an immutable version, used in a normal harness, given linked feedback, discovered through ARD, scanned, exercised in an isolated job, connected to a feedback-driven bounty, and rerun after a proposed improvement.

This exit gate is additionally blocked until every active 15.10–15.17 builtin
scenario, including the HMAC/acquisition/observation gates inherited from the
retired files, passes
[the mandatory cheap real-agent proving-ground gate](agent-proving-ground-phase-gate.md)
against the local API. The umbrella has no replacement “happy path” scenario:
`phase_15_16_full_resource_loop` is the composition check, while every narrower
scenario remains required.
