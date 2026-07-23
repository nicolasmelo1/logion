<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Logion — Next Steps

We plan in cycles, but the post-15.8 architecture now has one strict dependency spine:

`public planning → generic resources → native scope contract → acquisition/use feedback → ARD discovery → portable evidence → local multi-agent node → independent verification → improvement liquidity`.

Each `phase-*.md` is an implementation contract. A subphase should fit one focused PR or one explicit operator rollout; umbrellas define gates, not parallel implementation tickets.

## Current release cycle

1. [`cycle-0-contract-e2e-hardening.md`](cycle-0-contract-e2e-hardening.md)
   is the immediate gate: repair API/public-contract drift, enforce additive
   `/v1` compatibility, and prove supported CLI/API pairs.
2. `cycles/cycle-1-to-release.md` ships the
   MVP after Cycle 0 is green. Phases 13.x and 14.x still gate first users.

The additional focused plans
[`cli-api-compatibility-matrix.md`](cli-api-compatibility-matrix.md) and
[`indexer-run-progress-observability.md`](indexer-run-progress-observability.md)
belong to those current hardening/release cycles; they do not alter the strict
post-15.8 product sequence below.

## Completed foundation for the new direction

Phases 15.1–15.7 provide GitHub identity, publishing, PR delivery, external skill indexing, observation scanning, and honest discovery tiers.

[`phase-15.8-platform-funded-bounties-on-indexed-listings.md`](phase-15.8-platform-funded-bounties-on-indexed-listings.md) is the pivot point: Logion can sponsor improvements on ownerless indexed resources before network liquidity exists.

## Phase 15 — first useful node

Umbrella: [`phase-15-native-resource-loop-and-first-ard-node.md`](phase-15-native-resource-loop-and-first-ard-node.md).

| Phase | Outcome | Dogfood level |
| --- | --- | --- |
| [`15.8.1`](phase-15.8.1-public-roadmap-sync.md) | Publish the canonical planning projection and accept public planning contributions | Governance prerequisite |
| [`15.9`](phase-15.9-generic-resource-model-and-index-backfill.md) | Generic resource/version/source identity with compatible Course and listing projections | Bootstrap only |
| [`15.9.1`](phase-15.9.1-harness-resource-scope-and-observation-contract.md) | Native Codex/Claude/Hermes/Pi locations, precedence, installation receipts, and observation contract | Scope detection |
| [`15.10`](phase-15.10-native-acquisition-artifact-delivery-and-inventory.md) | Hosted artifact downloads plus `npx skills`, `npx plugins`, and `hf` acquisition/reconciliation | Level 1: acquisition |
| [`15.11`](phase-15.11-native-use-observation-linked-feedback-and-reviews.md) | Observe native usage and submit generic feedback linked to the exact resource/Course | Level 2: real feedback |
| [`15.12`](phase-15.12-ard-catalog-ingestion-and-self-publication.md) | ARD ingestion, self-publication, and zero-duplicate self-crawl | Level 3: discovery |
| [`15.13`](phase-15.13-portable-scan-evidence.md) | Signed portable evidence from current scanners | Level 4: evidence |
| [`15.14`](phase-15.14-feedback-driven-platform-bounties.md) | Choose platform-funded improvements from attributed usage and friction | Level 5: demand → improvement |
| [`15.14.1`](phase-15.14.1-local-multi-agent-first-node-foundation.md) | Isolated founder-operated roles on one MacBook | Level 5.5: local roles |
| [`15.15`](phase-15.15-isolated-first-runner-node.md) | First isolated CPU runner using the proving ground | Level 6: execution |
| [`15.16`](phase-15.16-first-party-resource-dogfood-loop.md) | Recurring acquire → use → feedback/evidence → bounty → improvement → rerun loop | Level 7: full product |
| [`15.17`](phase-15.17-aktp-evidence-and-improvement-feed-v0.md) | AKTP v0 as an ARD-linked evidence/improvement feed | Level 8: protocol |

**Phase 15 exit:** a resource installed through Logion or a native manager is exactly attributed, used, receives linked feedback, is discovered through ARD, scanned, exercised, improved through a feedback-driven bounty, and rerun by the Logion-operated first node.

## Phase 16 — independent verification

Umbrella: [`phase-16-distributed-evaluation-and-independent-verification.md`](phase-16-distributed-evaluation-and-independent-verification.md).

1. [`16.1 — Eval contract and reference runner`](phase-16.1-eval-contract-and-reference-runner.md)
2. [`16.2 — Typed evaluators and skill reference evaluator`](phase-16.2-typed-evaluators-and-skill-reference-evaluator.md)
3. [`16.3 — Runner registry and network jobs`](phase-16.3-runner-registry-and-network-jobs.md)
4. [`16.4 — Deterministic replication and agreement`](phase-16.4-deterministic-replication-and-agreement.md)
5. [`16.5 — Eval attestations and cross-node authority`](phase-16.5-eval-attestations-and-cross-node-authority.md)
6. [`16.6 — Benchmark-backed bounties`](phase-16.6-benchmark-backed-bounties.md)
7. [`16.7 — Evidence search and issuer-aware ranking`](phase-16.7-evidence-search-and-issuer-aware-ranking.md)
8. [`16.8 — Portable field evidence and aggregation`](phase-16.8-portable-field-evidence-and-aggregation.md)
9. [`16.9 — Benchmark/field reconciliation`](phase-16.9-benchmark-field-reconciliation.md)
10. [`16.10 — External runner onboarding and conformance`](phase-16.10-external-runner-onboarding-and-conformance.md)
11. [`16.11 — MCP registry adapter and safe probes`](phase-16.11-mcp-registry-adapter-and-safe-probes.md)
12. [`16.12 — Hugging Face metadata and constrained model evaluation`](phase-16.12-hugging-face-metadata-and-constrained-model-evaluation.md)

**Phase 16 exit:** at least one independent operator reproduces a bounded evaluation and issues a verifiable attestation without Logion-owned compute or credentials.

## Phase 17 — ecosystem and hardening

Umbrella: [`phase-17-open-ecosystem-and-production-hardening.md`](phase-17-open-ecosystem-and-production-hardening.md).

1. [`17.1 — ARD/AKTP conformance and upstream proposals`](phase-17.1-ard-aktp-conformance-and-upstream-proposals.md)
2. [`17.2 — Independent node federation`](phase-17.2-independent-node-federation.md)
3. [`17.3 — Resource claims and commercial rails`](phase-17.3-resource-claims-and-commercial-rails.md)
4. [`17.4 — Private and enterprise nodes`](phase-17.4-private-and-enterprise-nodes.md)
5. [`17.5 — Trust-boundary invariant tests`](phase-17.5-trust-boundary-invariant-tests.md)
6. [`17.6 — Public narrative and landing truth pass`](phase-17.6-public-narrative-and-landing-truth-pass.md)

## Phase 18 — prove it is a network

[`phase-18-network-liquidity-and-independent-operation.md`](phase-18-network-liquidity-and-independent-operation.md) requires useful non-founder supply and demand for three consecutive months. It explicitly rejects a token, fake subsidized volume, a mandatory global payment rail, or an owned GPU fleet.

## Sequencing rules

- Every 15.9+ subphase adds a named builtin scenario and is incomplete until it
  passes [the cheap real-agent proving-ground gate](agent-proving-ground-phase-gate.md)
  against the locally running API. Scripted scenarios validate the harness but
  cannot close a phase.
- ARD owns discovery. AKTP must not recreate a catalog or peer-discovery protocol.
- Logion is open-source first: public planning and contribution surfaces are a
  product invariant, while commercial rails remain optional.
- Repository scope is the default inside a repository. No harness adapter may
  silently install into a user-global directory.
- `Resource` is the protocol identity; `Course`, indexed listing, and skills commands remain compatible product projections.
- Logion runs every path first, including hosted artifact download and native-manager reconciliation, through the same public contracts used by other operators.
- Users keep `npx skills`, `npx plugins`, `hf`, and future native workflows; Logion integrates attribution, evidence, and feedback instead of imposing a replacement installer.
- First-party evidence is valuable but labeled first-party until independently reproduced.
- Skills come first. MCP execution follows strict safe probes. Hugging Face starts metadata-first; larger model evaluation waits for compatible external or sponsor-funded compute.
- No phase may require Logion to own a GPU fleet.
- No public claim can be stronger than its underlying evidence and local authority policy.

## Already shipped

Phases 1–12 are done. The proving ground is also existing infrastructure, not a future Phase 18. Current behavior lives in [`../maintainer documentation: `](../maintainer documentation: ), with recurring release verification in [`../maintainer documentation: release-smoke-checklist.md`](../maintainer documentation: release-smoke-checklist.md).

The older roadmap blocks are historical context only. This file supersedes their future sequencing where they conflict.
