<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# ASM–Logion collaboration and protocol-convergence gate

> **Status:** cross-cutting architecture and collaboration gate; this document
> authorizes outreach and a bounded interoperability experiment, not adoption of
> ASM or a new Logion protocol.
> **Applies before:** Phase 15.12 design freeze, Phase 15.17 wire-format freeze,
> and any public selection/receipt contract in Phases 16.7 or 16.9.
> **Honesty boundary:** public activity by both projects indicates possible fit,
> not partnership, endorsement, adoption, or shared governance.

## Goal

Explore a collaboration with Yi Guo (`YE-YI7`), creator of
[ASM — Agent Service Manifest](https://github.com/YE-YI7/asm-spec), before
Logion and ASM independently freeze overlapping selection, operational-metadata,
declared-versus-observed, or receipt contracts.

The desired result is fewer protocols and one explicit seam. Logion must not
become a translation chain that carries the same claim through AI Catalog,
ARD, ASM, Logion-private objects, and AKTP under different names.

## Why this gate exists

ASM publicly positions itself as the selection layer between discovery and
settlement. It covers declared invocability, eligibility, pricing, SLA,
quality, operational constraints, a reference selector, and execution/cost
receipts. Logion plans local evidence-aware ranking, usage/eval receipts,
declared-versus-observed reconciliation, and an AKTP evidence/improvement feed.

The overlap is material:

| Concern | ASM direction | Logion plan at risk of duplication |
| --- | --- | --- |
| selection inputs | invocation, eligibility, pricing, SLA, quality, risk | generic resource metadata and Phase 16.7 ranking inputs |
| selection function | gated selector and reference scoring | Phase 16.7 ranking profiles |
| observed mismatch | Trust Delta and probe/receipt discussion | Phases 15.13, 16.8, and 16.9 |
| invocation/cost receipt | ASM receipt envelope | local usage/runner receipts and possible AKTP references |
| settlement handoff | x402/AP2/ACP integration | node-local Stripe/x402 adapters and entitlements |

This is potential collaboration, not evidence that ASM should be adopted.
ASM is young, fast-moving, independently maintained, and candid that external
production selection traffic is not yet established. Logion must respect Yi's
authorship and autonomy while protecting both projects from accidental
competition and maintainer dependency.

## Fixed protocol boundaries

The collaboration cannot redefine the pinned upstream contracts:

- AI Catalog remains the typed artifact/catalog representation.
- ARD remains discovery and relevance-oriented registry interaction. Its score
  is never a trust, safety, quality, or universal selection score.
- Native protocols/managers remain responsible for invocation or acquisition.
- Settlement remains node-local and pluggable.
- Logion remains the resource-use, issuer-aware evidence, independent
  reproduction, and improvement-liquidity operator.

ASM is a candidate for the one open contract for provider/aggregator-declared
selection inputs and, subject to review, one invocation/cost receipt. AKTP is a
candidate only for the portable evidence/improvement event stream that remains
after overlaps are removed.

## Non-Frankenstein invariants

Any joint design or fallback implementation MUST preserve all of these:

1. **One canonical subject.** AI Catalog identifier plus immutable artifact or
   manifest digest anchors every claim. ASM `service_id`, native package
   coordinates, and Logion IDs are source aliases, not competing global IDs.
2. **One selection descriptor.** Logion will not publish a second open schema
   for pricing, SLA, invocability, operational constraints, or selection facts
   while ASM convergence is viable.
3. **One invocation receipt.** The same invocation/cost observation is never
   emitted as both an ASM receipt and a structurally different AKTP/Logion
   receipt. A portable event may reference the original signed receipt by
   digest and issuer.
4. **Declared is not observed.** Publisher claims, aggregator-derived claims,
   Logion observations, controlled evals, and local policy decisions retain
   distinct issuers, timestamps, digests, and authority.
5. **No universal score.** A reference selector may be open, but final ordering
   is a versioned local policy with reproducible explanation.
6. **No schema relay.** Internal services normalize once into the Logion domain
   model. Wire adapters remain at boundaries; they do not make every service
   speak every protocol.
7. **No partnership claim without consent.** Until both projects publish an
   agreed statement, documentation says “exploring interoperability.”

## When to approach Yi

### T0 — exploratory outreach after this plan is shareable

Contact Yi as soon as this plan is accepted and available through the public
planning mirror. Do not wait for Phase 15.12 implementation: early contact is
specifically meant to avoid two independently frozen designs.

The first contact is low-commitment. It asks to compare roadmaps and identify
overlap; it does not ask Yi to join Logion, transfer ASM, accept Logion fields,
or promise compatibility.

Create an initial Logion-authored overlap/ownership matrix at T0. Mark disputed
or unanswered cells `unresolved`; do not attribute those positions to Yi. This
local record lets artifact-agnostic Phase 15.12 proceed even if scheduling takes
time, while still blocking ASM-specific contracts until T1 resolves them or a
documented independent outcome is selected.

### T1 — concrete co-design after Phase 15.11

After Phase 15.11 passes its real-agent gate, Logion can bring concrete,
redacted artifacts: immutable `ResourceVersion` identity, acquisition receipt,
usage receipt, feedback boundary, and issuer/consent rules. Before Phase 15.17
freezes any wire format, hold a focused design review covering:

- canonical subject and version binding;
- provider-declared versus aggregator-derived versus observed claims;
- selection descriptor ownership;
- selector/policy boundary;
- invocation/cost receipt ownership;
- how AKTP references rather than duplicates a receipt;
- governance, releases, compatibility, and maintainer continuity.

### T2 — one joint proof during Phases 15.12–15.13

Only after a written T1 boundary decision, run one bounded public fixture:

```text
AI Catalog publishes one resource
  → ARD discovers it
  → the agreed selection descriptor supplies declared eligibility/value
  → Logion applies a local explainable policy
  → a safe fixture invocation emits one receipt
  → Logion records separate observed evidence
  → an evidence/improvement event references original objects by digest
```

The experiment fails if it needs duplicate identities, dual receipts, lossy
field translation, or an unverifiable merged score.

### T3 — upstream and durable governance in Phase 17.1

After real dogfood and at least one independent consumer, publish conformance
results and propose only the smallest upstream changes. Durable collaboration
may then include shared fixtures, coordinated releases, co-maintainership, or a
neutral home, but none is assumed by this plan.

## How to approach Yi

Prefer a short direct introduction or a dedicated public ASM issue/discussion,
depending on Yi's stated preference. Do not append a Logion architecture pitch
to an unrelated issue such as
[ASM #6](https://github.com/YE-YI7/asm-spec/issues/6). Keep the first message
short, specific, and reciprocal:

```text
Hi Yi — I’m building Logion, an open resource-use → evidence → improvement
network for agent resources. Your work on ASM, AI Catalog #83, and the
declared-vs-observed seam overlaps several things we had planned: selection
inputs, explainable ranking, and receipts.

We do not want to create a competing schema or bolt ASM onto Logion as another
translation layer. We would like to compare roadmaps early and see whether
there is one clean division: ASM as the open selection/operational contract and
reference selector; Logion as a real operator for consented field evidence,
independent evals, and verified improvement — with one subject and one receipt.

We can offer a public dogfood/conformance environment and are prepared to
remove or narrow overlapping Logion protocol work if the joint boundary is
better. No adoption or partnership claim is implied. Would you be open to a
short architecture call or a dedicated public design issue?

Context: <public plan URL>
Proposed single fixture: discovery → declared selection inputs → local policy
→ one receipt → observed evidence → improvement.
```

Interaction rules:

- lead with the overlap and the willingness to delete Logion duplication;
- acknowledge ASM authorship and cite Yi for concepts/fixtures used;
- ask what Yi wants ASM to own, not only how Logion can consume it;
- offer concrete engineering capacity: fixtures, threat modeling, conformance,
  real-agent dogfood, and upstream PRs;
- separate project collaboration from employment, investment, acquisition, or
  governance discussions;
- keep architectural conclusions public and attributable unless security or
  privacy requires a private channel.

## Required decision record

Before T2, add a public decision record with:

- ASM commit/release and Logion plan revisions reviewed;
- concern-by-concern ownership matrix;
- canonical identity and digest rules;
- exact receipt decision;
- exact selection-policy decision;
- AKTP scope retained, removed, or deferred;
- compatibility and unknown-field behavior;
- governance/continuity risks and fallback;
- explicit statements from each project that may be quoted publicly.

Accepted outcomes:

1. **Converge:** ASM owns the open selection descriptor/reference selector;
   Logion removes overlapping public schemas and operates evidence/improvement.
2. **Share primitives:** projects keep distinct scopes but share one subject,
   receipt, fixtures, and compatibility contract.
3. **Remain independent:** no adoption; Logion keeps the boundary generic and
   does not market ASM interoperability or create a competing public selection
   protocol without a later evidence-backed decision.

Silence, scheduling difficulty, or disagreement is outcome 3, not permission to
infer partnership.

## Decision record — T1, recorded 2026-08-25

Source: [`nicolasmelo1/logion#262`](https://github.com/nicolasmelo1/logion/issues/262).
T0 and T1 are complete. This section is the public decision record the section
above requires before T2; an implementer must not re-derive these from the issue
thread.

**Reviewed versions.** ASM: `asm-protocol==0.5.2`, draft head `9cde81a`,
[`YE-YI7/asm-spec#12`](https://github.com/YE-YI7/asm-spec/pull/12). Logion:
public `main@55e34fe`. Both sides independently confirmed the same upstream
pins — AI Catalog `28825483143ce9f3b344ed01dc2771d4adf02d01` and ARD
`5fa2f5aef790b478319f6a3b43adf4661b0ed0e0` — which match
`protocol-specs/UPSTREAM.lock.json`.

**Canonical identity and digest rules.** Settled:

1. AI Catalog `identifier` maps to a stable Logion `Resource` through an
   explicit source mapping.
2. The referenced artifact's immutable content digest anchors the
   `ResourceVersion`. AI Catalog `version` and source revision are provenance
   for that version, not its identity.
3. ASM `service_id` is a source alias only. It never becomes a second global
   identity.
4. ASM `manifest_digest` pins the exact selection descriptor the selector
   consulted. It must not define the `ResourceVersion`, because pricing, SLA and
   risk can change while the artifact does not.

The load-bearing consequence, and the one the fixture must prove: **a
manifest-only change changes the selection-evidence digest and must not create a
new `ResourceVersion`.**

**Receipt decision.** The upstream `{kind, digest, issuer}` reference does *not*
belong on the usage receipt. It belongs on a later evidence/AKTP artifact. This
is no longer a preference — it is a contract fact:
`SubmitUsageReceiptRequest` is published with `additionalProperties: false` in
`contracts/openapi/v1.json` and enforced as `extra="forbid"` at
`packages/api/api/resource_feedback/controllers/submit_usage_receipt.py`, so the
privacy-minimized observation cannot quietly grow an evidence reference.

**Selection-policy decision.** ASM owns the selection descriptor and the
Selection Receipt. Logion creates no selection manifest and copies no selection,
execution, payment or authorization fact into an observation.

**Unsigned boundary.** Selection Receipt v0.1 is intentionally unsigned. Any
reference must carry a machine-readable `"verification_status": "unsigned"` and
must not present `selector.name` as a verified issuer.

**AKTP scope.** Deferred. Catalog publication, ARD discovery and the evidence
feed where the reference is meant to live are all unbuilt, so the fixture is an
interoperability and design artifact and must not be read as freezing the wire
format of something unbuilt.

**Ownership matrix.**

| Concern | Owner |
| --- | --- |
| Canonical ASM manifest, Selection Receipt, `asm-protocol==0.5.2` validator behaviour | ASM |
| Shared fixture, offline deterministic checks, current-shape usage observation, non-adoption and unsigned statements | Logion public PR |
| Backend `Resource`/`ResourceVersion` mapping, fixture seeding, real devrig verification | Logion |
| Sanitized conformance results, published after both sides pass | Both |

**Open item.** ASM observed that public `main` generates
`SubmitUsageReceiptRequest` with `extra="allow"` in
`packages/client/src/logion/v1/_types/generated/v1.py`. Confirmed: the published
contract and the API both close the boundary; the *generated client* does not
mirror `additionalProperties: false`. Until that is reconciled, neither side may
cite the generated client as evidence of the closed boundary — cite the contract
or the API.

**Outcome.** Not yet decided. This is exploration under the standing rule that
"remain independent" (outcome 3) is a valid result. Nothing here is adoption,
partnership, endorsement, or shared governance.

## Acceptance gates

- Exit condition: the gate is finished when the T1 decision record has a
  recorded ASM response (accept, decline, or no response after the stated
  window) and either the T2 fixture proves one subject and one receipt move
  without lossy translation, or the outreach closes with the overlap matrix
  filed as the durable artifact and the collaboration explicitly parked.
- Initial outreach links a shareable plan and makes no adoption claim.
- A written overlap/ownership matrix exists before Phase 15.12 adds any
  ASM-specific production adapter.
- Phase 15.17 freezes no invocation/cost receipt that duplicates ASM.
- Phase 16.7 publishes no competing universal selection manifest or global
  score.
- The T2 fixture uses one subject and one receipt without lossy translation.
- Roadmap and public narrative are updated only after an attributable decision.
