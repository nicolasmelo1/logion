<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# ASM collaboration and protocol convergence

This document records a strategic constraint: Logion must not become a pile of
agent protocols joined by adapters while duplicating identity, selection,
receipts, and trust semantics.

The implementation/contact gate lives in
[`plans/asm-logion-collaboration-and-protocol-convergence-gate.md`](../plans/asm-logion-collaboration-and-protocol-convergence-gate.md).
This document explains the intended long-term shape; it does not claim a
partnership with ASM or its creator.

## Why ASM matters

[ASM — Agent Service Manifest](https://github.com/YE-YI7/asm-spec), created by
Yi Guo, is developing a selection layer between discovery and settlement. Its
public work covers provider/aggregator-declared invocability, pricing, SLA,
quality, operational constraints, reference selection, and invocation/cost
receipts. Yi has also been engaging adjacent upstream work, including
[AI Catalog issue #83](https://github.com/Agent-Card/ai-catalog/issues/83).

That direction is close enough to Logion's future selection, receipts, and
declared-versus-observed plans that passive “integration” would be irresponsible.
The correct first move is collaboration and deletion of overlap, not another
adapter.

## Target architecture

The cleanest candidate division is:

```text
AI Catalog
  publisher-owned typed artifact representation
        ↓
ARD
  discovery and relevance-oriented registry interaction
        ↓
ASM candidate boundary
  declared eligibility/value/operational contract
  + open reference selection mechanism
        ↓
Logion
  consented use evidence, independent evals, local authority,
  declared-vs-observed reconciliation, and improvement liquidity
        ↓
node-local settlement
  Stripe, x402, AP2, or another operator-selected adapter
```

AKTP survives only where it adds a portable evidence/improvement event stream
that the other layers do not provide. It must reference an existing signed
invocation receipt rather than invent a second receipt for the same event.

This is a candidate architecture to discuss with Yi, not a unilateral assignment
of responsibility to ASM.

## Product and protocol ownership

Logion's defensibility does not depend on owning a selection schema or scoring
algorithm. Its potential durable assets remain:

- exact resource/version attribution in native workflows;
- consented longitudinal outcome history;
- issuer-aware evidence and independent reproduction;
- relationships among resource owners, users, sponsors, and operators;
- liquidity that turns observed failures into verified improvements.

Therefore Logion can use or co-maintain an open selection contract without
giving away its product thesis. Conversely, ASM can gain a real evidence and
improvement operator without needing to become a marketplace, eval network, or
bounty system.

## One internal model, adapters only at boundaries

Even when multiple ecosystem protocols are necessary, their wire objects must
not leak through the whole Logion implementation:

- `Resource`/`ResourceVersion` remains the canonical internal subject graph.
- Source identifiers retain provenance and map to that graph explicitly.
- AI Catalog, ARD, a possible ASM contract, native managers, and AKTP are edge
  codecs with independent version pins.
- A claim is normalized once with original issuer, source, timestamp, digest,
  and raw-object reference.
- Policy decisions and rankings reference claims; they never rewrite them.

The test for architectural health is not “how many standards are supported.”
It is whether an operator can remove one boundary adapter without migrating the
core subject/evidence graph.

## Collaboration sequence

1. **Approach early.** Contact Yi once the convergence plan is publicly
   shareable, before Phase 15.12 or any ASM-specific code is frozen.
2. **Bring reality next.** After Phase 15.11, compare actual Logion identity,
   consent, usage receipt, and feedback artifacts with ASM's current schema and
   receipts.
3. **Decide before protocol.** Resolve selection and receipt ownership before
   Phase 15.17 or Phase 16.7 publishes a competing contract.
4. **Prove one seam.** Run one public end-to-end fixture during Phases
   15.12–15.13 with one identity, one receipt, separate declared/observed
   claims, and a reproducible local policy.
5. **Upstream after evidence.** Use Phase 17.1 for conformance, minimal
   proposals, release coordination, and any durable governance arrangement.

## What collaboration should feel like

The approach must be peer-to-peer:

- acknowledge that ASM is Yi's project and preserve attribution;
- state Logion's overlap plainly;
- offer to remove duplicate Logion plans, not merely ask ASM to fit them;
- offer engineering work and real dogfood rather than only schema opinions;
- ask whether Yi wants independent projects, shared primitives, or deeper
  co-maintenance;
- publish only conclusions both parties have agreed may be represented.

No response or no agreement means the projects remain independent. Logion then
keeps its boundary generic and narrow; it does not silently fork ASM or imply
compatibility.

## Kill criteria

Do not adopt or market an ASM relationship when:

- the same fact needs multiple competing identifiers;
- one invocation requires two incompatible receipts;
- Logion must mirror mutable ASM claims without issuer/freshness provenance;
- ASM ranking becomes a global trust score;
- collaboration depends indefinitely on an unreviewed moving branch;
- the integration adds more translation code than customer-visible value;
- either project would need to misstate adoption, traffic, independence, or
  evidence strength.

The desirable outcome is not “Logion supports ASM.” It is that both projects
can point to one coherent operating loop with less duplicated protocol work
than they had before collaborating.
