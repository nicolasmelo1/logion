<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 17.6 — Public narrative and landing truth pass

> **Dogfood status:** the public story is generated from capabilities Logion continuously demonstrates on its own node.
> **After this phase:** users understand what is live, who ran each evaluation, and how to operate or join a node.
> **Honesty boundary:** no “decentralized”, “verified”, or “safe” claim appears without the qualifying evidence visible nearby.

## Mandatory dogfood protocol

The phase-specific prompt below is implementation work, not optional documentation. The implementing agent must exercise the interoperable resource loop delivered by 15.10–15.11:

1. run local recall, then `logion listings search --query "SEARCH_QUERY" --include-indexed --limit 5 --json` only on LOW/NONE;
2. inspect the exact `ResourceVersion`, distributions, evidence, permissions, license, and acquisition plan—not only a Course projection;
3. obtain explicit approval, run `logion resources acquire RESOURCE_ID --version VERSION_ID --scope repo-root --channel auto --dry-run --json`, then acquire through the recommended Logion or native channel;
4. run `logion resources reconcile --scope repo-root --json` and require exact version attribution;
5. use the resource in the normal harness on this phase's real task and verify it appears in `logion usage pending --json`;
6. submit exactly one intentional post-task report:

```bash
logion feedback submit RESOURCE_ID VERSION_ID \
  --rating 1..5 \
  --usefulness 0.0..5.0 \
  --reliability 0.0..5.0 \
  --tool-safety 0.0..5.0 \
  --token-efficiency 0.0..5.0 \
  --completed-task \
  --task-class TASK_CLASS \
  --body "One or two resource-focused sentences; no private repository data" \
  --json
```

Use `--not-completed-task` when appropriate. Record the feedback ID and `course_review_projection` disposition. A native external installation is valid dogfood; Logion must not require reinstalling it. If acquisition, exact attribution, consent, or actual use is absent, record the blocker and **do not submit feedback/review**. Passive observation alone never justifies a rating.

## Goal

Explain the actual product: an ARD-native evidence and improvement network, bootstrapped by a useful first node.

## Dogfood prompt for the implementing agent

```text
Find a Logion resource about technical product messaging, developer documentation,
landing-page information architecture, or evidence-based copy. Recall first; on
LOW/NONE search "developer product messaging technical documentation landing".
Follow the mandatory acquisition/reconciliation protocol and use it to rewrite one
real page and run the truth mapping. Record before/after and applied guidance in
`artifacts/dogfood/phase-17.6.md`; submit one honest feedback report after
the production capability checks and usability task pass.
```

## Source-of-truth capability registry

Add a machine-readable registry (for example `maintainer documentation: public-capabilities.yaml`) with capability ID, status `live|beta|planned`, production check/metric, evidence/status URL, allowed claims, required qualifiers, and owning documentation/landing components. Planned capabilities cannot render as live CTAs/statuses.

Landing copy and public docs must distinguish:

- ARD resource discovery vs Logion indexing policy;
- first-party observation/evaluation vs independent reproduction;
- signed evidence vs locally accepted authority;
- resource owner/author/contributor/sponsor/runner/evaluator;
- metadata-only, scanned, evaluated, improved, and contradicted states;
- Logion-operated node vs open protocol/reference runner.

## Concrete surfaces/files

- Update landing templates/routes/styles in the actual `packages/landing` structure, public README, `llms.txt`/Markdown representation, CLI bundled docs, protocol docs, and resource/listing pages.
- Add capability-driven status components and evidence timeline cards. Avoid duplicating state-label logic between landing/API client.
- Add public dogfood dashboard backed by redacted aggregate endpoint: program version, resources/scenarios, run outcomes, first/independent evidence counts, bounties/improvements/reruns, costs, incidents, and last updated.
- Add role-specific quickstarts for consumer, maintainer, sponsor, runner, evaluator, and private-node operator with one verified path each.

## Tests and truth/build checks

- Script validates every live capability has a passing fresh production check and every claim token is allowed by its registry entry.
- Link checker, structured metadata/OpenGraph, mobile/accessibility, Markdown/HTML parity, and no-JS essential-content tests.
- Snapshot tests for first-party, independent, contradicted, unknown, metadata-only, and private-undisclosed resource states.
- Usability test: clean agent/human finds a resource, explains evidence issuer/scope, and starts public reproduction without founder help.

## Rollout and analytics

Ship status labels/resource pages before broad headline changes. Analytics are privacy-minimal and measure quickstart completion, evidence inspection, reproduce intent, runner onboarding—not vanity traffic. Roll back copy independently of protocol/product.

## Build

- Landing narrative: keep native `npx skills`/`npx plugins`/`hf` workflows, add Logion once, attribute real use and feedback, inspect evidence, fund observed improvements, and optionally operate a runner/node.
- Live status labels for first-party, independently reproduced, contradicted, and unknown.
- Resource pages with provenance, evidence timeline, issuer policy, bounties, improvements, and costs.
- Public dogfood dashboard and reproducible case study.
- Documentation for native-manager consumer, feedback participant, resource owner, evaluator, runner, sponsor, and private-node operator.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_17_6_public_truth`.

- **Prompt:** in a clean workspace, a prospective user receives only the public
  landing/docs: “Find a capability, install/use it through your existing
  workflow, inspect who produced its evidence, reproduce one claim, and tell me
  exactly what Logion does and does not guarantee.”
- **Fixtures:** one resource with reproducible evidence, one inconclusive claim,
  one externally hosted native acquisition, and one unavailable feature flag.
- **Assertions to add:** `files.public_onboarding_completes`,
  `api.public_claim_reproduced`, `files.capability_registry_matches_runtime`,
  `files.no_unsupported_marketing_claim`, and
  `api.issuer_and_limitations_visible`.
- **Evidence:** retain landing/docs commit, commands discovered by the agent,
  acquisition/use/evidence receipts, feature-registry comparison, elapsed
  time/cost, redaction, and no 500s.

## Gates

- Every headline maps to a passing production capability check.
- First-party and independent evidence are visually unmistakable.
- A new visitor can find one resource, inspect its evidence, and reproduce a public fixture.
- Old “skills marketplace” routes remain functional but no longer define the whole product.
- A copy audit finds zero unqualified uses of “safe”, “verified”, “consensus”, or “decentralized”.
- The public dogfood dashboard is generated from production records, not hand-entered numbers.
