<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Consumption Adoption Ladder — Adapt, Attribute, Improve

Policy document; the implementation source of truth is the post-15.8 sequence in [`next-steps.md`](next-steps.md).

## Doctrine

Logion does not require a new acquisition or execution habit:

```text
acquire wherever the ecosystem already works
→ Logion resolves the exact resource/version
→ the agent uses it natively
→ Logion captures consented, privacy-safe outcome feedback
→ evidence and real demand fund improvements
```

Users may climb from local-only inventory to feedback and autonomous evaluation. Every rung is optional. The artifact remains native to its manager and harness.

## Rung 0 — Keep the existing package manager

Examples:

```bash
npx skills add owner/repo --skill skill-name
npx plugins add owner/plugin
hf download owner/model --revision COMMIT
logion resources acquire RESOURCE_ID --version VERSION_ID --channel logion_bundle
```

Logion may recommend or delegate to these commands, but it does not silently replace them. Phase [`15.10`](phase-15.10-native-acquisition-artifact-delivery-and-inventory.md) adds:

- real Logion-hosted Course/capability downloads;
- native acquisition plans;
- local inventory;
- reconciliation of resources installed before or outside Logion;
- exact source/revision/digest attribution.

The user gains provenance, evidence, version identity, updates, feedback linkage, and improvement history without surrendering the upstream workflow.

## Rung 1 — Install Logion into the existing agent workflow

Target entry surfaces:

```bash
npx skills add OFFICIAL_LOGION_SOURCE --skill logion
npx plugins add OFFICIAL_LOGION_PLUGIN
```

The skill installs the Logion companion into the same Agent Skills workflow the user already uses. The plugin installs the thin observer integration where supported. If the verified Logion CLI is absent, first use explains and requests approval for its official installer; neither native command silently installs a binary, enables hooks, uploads telemetry, or opts into automatic feedback.

Phase [`15.11`](phase-15.11-native-use-observation-linked-feedback-and-reviews.md) owns this surface.

## Rung 2 — Local attribution only

With consent mode `local-only`:

- Logion inventories native installations;
- hook/plugin events resolve paths/names against exact inventory;
- pending use stays on the machine;
- no receipt, feedback, prompt, code, path, or identity is uploaded.

This rung is useful for recall, updates, provenance, and deciding which resources the agent actually used. A hook failure never blocks the harness.

## Rung 3 — Intentional feedback

After a meaningful task, the agent can propose or submit:

```bash
logion feedback submit RESOURCE_ID VERSION_ID \
  --rating N \
  --usefulness N \
  --reliability N \
  --tool-safety N \
  --token-efficiency N \
  --completed-task \
  --task-class software-development
```

Important distinctions:

- passive observation is not a rating;
- generic feedback works for skills, plugins, MCP servers, models, and ownerless indexed resources;
- an eligible exact `ResourceVersion → CourseVersion` link may project feedback into the existing Course review system;
- external installation does not create a paid entitlement or “verified buyer” label;
- feedback body never includes proprietary task content.

Consent modes are `off`, `local-only`, `prompt`, and explicit `auto`. The agent submits at most once per meaningful resource/task use.

## Rung 4 — Fund what people already use

Phase [`15.14`](phase-15.14-feedback-driven-platform-bounties.md) turns repeated attributed friction into an operator-reviewed bounty recommendation.

Selection uses:

- distinct attributed use;
- repeated task classes/problems;
- completed-task failures;
- reliability/safety friction;
- current affected version;
- reproduction and acceptance feasibility;
- license/ownership/delivery lane;
- identity tier and concentration.

It does not blindly use downloads, stars, catalog rank, anonymous event volume, or opaque LLM judgment. Feedback nominates work; a human separately approves publishing and funding.

## Rung 5 — Controlled and independent evidence

Normal-use feedback remains valuable but biased. Later phases add:

- portable scan evidence;
- isolated controlled evals;
- independent runner reproduction;
- signed field aggregates above privacy thresholds;
- benchmark/field reconciliation.

The product shows these signal classes separately. Field experience does not become a benchmark, and a benchmark does not become the world.

## Rung 6 — Autonomous workflows

An orchestrator may pre-resolve and pin resources, runners, policies, and budgets. Nodes use artifacts natively. Acquisition and paid actions remain explicit plan-time decisions rather than surprise mid-graph mutations.

Autonomous workflows still produce:

- exact resource/version/channel attribution;
- per-node/session separation;
- privacy-safe feedback/receipts;
- no collapsing of many subagents into fake independent authorities.

## Product moat

Discovery and installation alone are commodities. The defensible compounding asset is the attributed improvement graph:

```text
resource/version
↕ native distributions
↕ real task classes and outcomes
↕ feedback and field evidence
↕ controlled evaluations
↕ funded improvements and contributors
↕ post-improvement outcomes
```

ARD and native package managers make resources reachable. Logion earns its position by operating the most useful, honest loop from use to evidence to improvement.

## Truth rules

- A phase is not complete until its customer-like proving-ground scenario passes
  against the local API with GPT-5.4-mini or Claude Haiku and required
  observed-effect assertions.
- Native installation is not Logion endorsement.
- Observation is not successful use.
- Feedback is not controlled evaluation.
- A Course projection is not guaranteed.
- Popularity is not impact.
- Sponsorship is not authorship.
- First-party evidence is not independent reproduction.
- No feedback/telemetry upload without the configured consent.
