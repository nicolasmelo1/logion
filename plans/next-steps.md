<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Logion — Next Steps

The execution order. Short on purpose: this is the file to reread weekly.
Everything that is context, contract, or policy moved out on 2026-08-17.

| Read when | File |
| --- | --- |
| Cutting the next release; defining what "done" means | [`release-0.2.md`](release-0.2.md) |
| Writing public copy, arguing positioning, touching protocols | [`positioning-and-independence.md`](positioning-and-independence.md) |
| Implementing identity, acquisition, reconciliation, observation | [`normative-carry-overs.md`](normative-carry-overs.md) |
| Instructing counsel, forming the entity | [`legal-and-entity.md`](legal-and-entity.md) |
| Publishing a measurement about someone else's artifact | [`../maintainer documentation: measurement-publication-playbook.md`](../maintainer documentation: measurement-publication-playbook.md) |

**Current position:** step 3 — phase 15.12 (AI Catalog publication and ARD
discovery) is being implemented on `feat/phase-15.12-ai-catalog-ard`. Nothing
has been published since 0.1.15 on 2026-07-19.

**The one-sentence goal:** *evaluation is the entry, observation is the upsell.*
A controlled eval needs nobody's permission and works at N=1; consented field
observation needs users and is what gets sold after an eval report opens the
door.

## Execution order

Authoritative. A phase not listed here is written, valid, and **off the critical
path** until its precondition exists. Cross-cutting gates that authorize or
constrain phases rather than shipping work of their own sit off the order with
their own exit conditions: [`asm-logion-collaboration-and-protocol-convergence-gate.md`](asm-logion-collaboration-and-protocol-convergence-gate.md)
(precondition: Phase 15.12/15.17 design freezes, which it precedes),
[`legal-and-entity.md`](legal-and-entity.md) (trigger-based, runs in parallel),
[`normative-carry-overs.md`](normative-carry-overs.md) (binding contracts, no
work of its own), and [`positioning-and-independence.md`](positioning-and-independence.md)
(binding language discipline, no work of its own).

| # | Work | Exit condition |
| --- | --- | --- |
| 1 | [`15.11`](phase-15.11-native-use-observation-linked-feedback-and-reviews.md) closeout | The remaining "Still open" items are closed and the observation hook fires **live**, not from a replayed payload. Item 1 and item 2 are also prerequisites of step 2 — see below. |
| 2 | **Cross-hub install reconciliation** | One canonical artifact + version shows where it is listed across every indexed hub, and the install counts of the hubs that publish them, with coverage and blind spots stated. No hub can answer this about another hub. |
| 3 | [`15.12`](phase-15.12-ai-catalog-publication-and-ard-discovery.md) | `logion.sh` serves `/.well-known/ai-catalog.json` and ARD ingestion runs. **ASM contact (T1) fires before this design freeze.** |
| 4 | [`15.14.1`](phase-15.14.1-local-multi-agent-first-node-foundation.md) + [`15.15`](phase-15.15-isolated-first-runner-node.md) | One isolated local node runs jobs in rootless containers. Hard prerequisite of 16.1. |
| 5 | [`16.1`](phase-16.1-eval-contract-and-reference-runner.md) + [`16.2`](phase-16.2-typed-evaluators-and-skill-reference-evaluator.md) | A portable eval contract runs a third-party skill through the reference runner and produces a normalized result. |
| — | **RELEASE 0.2** | Loops A, B, D work end to end. Full gate in [`release-0.2.md`](release-0.2.md). No publish before this. Note that Loop B's primary launch answer is Logion's own controlled evaluation, so measurements exist *before* this line, not after it. What step 6 adds is publishing one as a report about a named third party. |
| 6 | **First public measurement** | One published, reproducible evaluation of a third-party artifact: prose, stated method and limits, the subject version, and the command to reproduce. The real gate — not "16.2 merged", and not the same artifact as the in-product answer that 0.2 already ships. |
| 7 | [`15.17`](phase-15.17-aktp-evidence-and-improvement-feed-v0.md) | AKTP v0, minimal, defined only after real payload exists, and the first `evidence.published` event carries the step 6 measurement. The event cannot be step 6's own exit condition, because the protocol that transports it is built here. |
| 8 | Publisher outreach | Contact carries a finished report. Nobody is asked to install anything first. |
| 9 | [`17.3`](phase-17.3-resource-claims-and-commercial-rails.md) + [`16.3`](phase-16.3-runner-registry-and-network-jobs.md)–[`16.5`](phase-16.5-eval-attestations-and-cross-node-authority.md) | Claims/commerce (Loop C) and federation. 16.3–16.5 are **blocked by definition** until an external operator exists. |
| 10 | **Issuer #2** | The first attestation about a Logion-catalogued subject issued by someone who is not Logion. The thesis milestone. |

### Why 15.11.1 moved off the critical path

`15.11.1` is written and valid. It is off the critical path because it answers a
question that is not the bottleneck, at a cost the bottleneck does not require.

What it uniquely buys is observation of *use* by people who never install
Logion. That is client-side observation, so it needs consent — legally (ePrivacy
Art. 5(3) covers storing or accessing information on terminal equipment, and
applies even to anonymous data) and practically (Go shipped telemetry opt-in
after backlash, Homebrew added a first-run prompt, and the .NET SDK's opt-out is
patched out downstream by the distributors that carry it). Consent is the right
answer, and it is a real ask to put in front of a publisher's users.

The problem publishers actually have is that install counts are fragmented per
store. The same skill can hold three million installs split across skills.sh,
ClawHub and browse.sh, and none of them can see the others. Counting installs
from Logion's own store would only add a fourth fragment.

De-fragmentation needs no consent and no client-side code, and the hard half is
already built: `packages/indexer/` crawls the hubs, resolves each skill to its
GitHub identity, and dedups across them, recording a `DiscoveryChannel` per hub
per skill. Step 2 is the metric layer on top of that identity layer.

**Verified 2026-08-25, hub by hub** — the promise has to match what is actually
published:

| Hub | Per-skill install count public? | Where |
| --- | --- | --- |
| skills.sh | yes | rendered in the page, with a trend series; `/api/v1/skills` exists but returns 401 |
| browse.sh | yes | `installCount` in embedded JSON |
| ClawHub | **no** | `/v1/feeds/skills` returns 861 entries whose only numeric field is `featuredAt`; not on the site either |
| LobeHub | unconfirmed | a single `installCount` that reads as a schema example, not data |
| skillsmp, smithery | not found | homepage only; detail pages not checked |

So "sum the downloads across stores" is **not** deliverable as stated: the hub
with the largest catalog does not publish counts. What is deliverable is
cross-hub *presence and version coverage* per canonical artifact — which nobody
offers — plus a partial install sum over the hubs that do publish, labelled with
its coverage and its blind spots. That is the same discipline `15.11.1` already
requires of aggregation, applied to a cheaper signal.

One constraint to carry forward when `15.11.1` returns: its consent must reuse
the existing `~/.logion/integrations.json` store — the four modes, the separate
review scope, the `DO_NOT_TRACK` handling — rather than the parallel
per-projection `consent.json` the closed attempt introduced. Two consent stores
that do not read each other is a privacy defect, not a layout preference: a user
who set `off` in one was not honoured by the other.

Step 1 remains a prerequisite of nothing in step 2. Its own exit condition still
stands on its own terms.

### Why 16.3–16.5 cannot be pulled forward

Definitional, not a priority call. `16.4`: *"two processes under one operator are
not independent nodes."* Phase 16 exit: *"at least one independent operator …
without Logion-owned compute or credentials."* With zero external operators the
code can be written and cannot pass its own gate. `16.1`/`16.2` have no such
dependency — they run at N=1 on Logion's own node, which is why they are the
entry point.

## Sequencing rules

- **A phase closes on its externally visible effect, not on its merge.** Step 6
  is the clearest case.
- Every critical-path subphase adds a named builtin scenario and is incomplete
  until it passes [the real-agent proving-ground gate](agent-proving-ground-phase-gate.md)
  against the locally running API. **A replayed payload is not a live run** —
  record which one the evidence represents.
- The identity, acquisition/reconciliation, and observation contracts in
  [`normative-carry-overs.md`](normative-carry-overs.md) are inherited, not
  waived by any resequencing.
- AI Catalog owns the typed catalog/entry model; ARD owns discovery over those
  entries. AKTP recreates neither, and is not frozen before it has real payload.
- Selection/value metadata and invocation receipts have exactly one public
  owner. Follow the ASM gate before adding a Logion equivalent.
- Logion is open-source first; commercial rails stay optional.
- Repository scope is the default inside a repository. No harness adapter
  silently installs into a user-global directory.
- `Resource` is the protocol identity; `Course`, indexed listing, and skills
  commands are compatible projections.
- Logion runs every path first through the same public contracts other operators
  use.
- Users keep `npx skills`, `npx plugins`, `hf`, and native workflows. Logion
  integrates attribution, evidence, and feedback rather than imposing a
  replacement installer.
- **Field evidence is sampled, not censused.** Always publish `n`, version
  coverage, consent mode, harness coverage, concentration, and blind spots.
- First-party evidence is labelled first-party until independently reproduced.
- **Independence is methodological until issuer #2, structural after.** While
  Logion is the only issuer, public copy claims a published, reproducible
  method — never network validation.
- **A single-issuer attestation format is a proprietary log.** Portability is
  proven by the first non-Logion issuer, not by publishing a spec version.
- **Every network reward names an external payer.** A network paying itself to
  validate itself fails the coalition-wealth test.
- Skills first. MCP follows strict safe probes. Hugging Face is metadata-first.
- No phase may require Logion to own a GPU fleet.
- **No public claim can be stronger than its underlying evidence and local
  authority policy.**

## Phase index

`#` maps to the execution order; `—` means written but off the critical path.

### Phase 15 — first useful node
[umbrella](phase-15-native-resource-loop-and-first-ai-catalog-ard-node.md)

| Phase | # | Outcome |
| --- | --- | --- |
| [`15.10`](phase-15.10-native-acquisition-artifact-delivery-and-inventory.md) | done | Hosted artifact downloads plus `npx skills`, `npx plugins`, `hf` acquisition/reconciliation |
| [`15.10.1`](phase-15.10.1-deepseek-harness-adapter-and-logion-dsh-plugin.md) | — | DeepSeek Harness plugins; **distribution experiment**, run after step 6 |
| [`15.11`](phase-15.11-native-use-observation-linked-feedback-and-reviews.md) | 1 | Observe native usage; feedback linked to the exact resource |
| [`15.11.1`](phase-15.11.1-publisher-integrated-consented-observation.md) | — | Publisher-shipped consented projections; **deferred**, see above |
| [`15.12`](phase-15.12-ai-catalog-publication-and-ard-discovery.md) | 3 | AI Catalog publication + ARD discovery — **in progress** on `feat/phase-15.12-ai-catalog-ard` |
| [`15.13`](phase-15.13-portable-scan-evidence.md) | — | Signed portable evidence from current scanners |
| [`15.14`](phase-15.14-feedback-driven-platform-bounties.md) | — | Platform-funded improvements from attributed usage |
| [`15.14.1`](phase-15.14.1-local-multi-agent-first-node-foundation.md) | 4 | Isolated founder-operated roles on one MacBook |
| [`15.15`](phase-15.15-isolated-first-runner-node.md) | 4 | First isolated CPU runner |
| [`15.16`](phase-15.16-first-party-resource-dogfood-loop.md) | — | Recurring acquire → use → evidence → bounty → rerun loop |
| [`15.17`](phase-15.17-aktp-evidence-and-improvement-feed-v0.md) | 7 | AKTP v0 as an ARD-linked evidence/improvement feed |

### Phase 16 — verification
[umbrella](phase-16-distributed-evaluation-and-independent-verification.md)

**Step 5:** [`16.1`](phase-16.1-eval-contract-and-reference-runner.md),
[`16.2`](phase-16.2-typed-evaluators-and-skill-reference-evaluator.md).
`16.2` is also what satisfies "must work for more than MCP" — the `Evaluator`
protocol is typed per resource, so skills, plugins, MCP servers and models all
enter through one execution envelope with no hook, no non-standard frontmatter,
and no permission from the author. **Portability across artifact types is solved
in the evaluation layer, not the observation layer.**

**Step 9, blocked on an external operator:**
[`16.3`](phase-16.3-runner-registry-and-network-jobs.md),
[`16.4`](phase-16.4-deterministic-replication-and-agreement.md),
[`16.5`](phase-16.5-eval-attestations-and-cross-node-authority.md).

**Written, unscheduled:** [`16.6`](phase-16.6-benchmark-backed-bounties.md),
[`16.7`](phase-16.7-evidence-search-and-issuer-aware-ranking.md),
[`16.8`](phase-16.8-portable-field-evidence-and-aggregation.md),
[`16.9`](phase-16.9-benchmark-field-reconciliation.md),
[`16.10`](phase-16.10-external-runner-onboarding-and-conformance.md),
[`16.11`](phase-16.11-mcp-registry-adapter-and-safe-probes.md),
[`16.12`](phase-16.12-hugging-face-metadata-and-constrained-model-evaluation.md).

### Phase 17 — ecosystem and hardening
[umbrella](phase-17-open-ecosystem-and-production-hardening.md). Off the critical
path except [`17.3`](phase-17.3-resource-claims-and-commercial-rails.md) at step
9 and [`17.6`](phase-17.6-public-narrative-and-landing-truth-pass.md), **pulled
forward into the 0.2 release gate** because the landing still describes a
marketplace.

Remaining: [`17.1`](phase-17.1-ai-catalog-ard-aktp-conformance-and-upstream-proposals.md),
[`17.2`](phase-17.2-independent-node-federation.md),
[`17.4`](phase-17.4-private-and-enterprise-nodes.md),
[`17.5`](phase-17.5-trust-boundary-invariant-tests.md).

### Phase 18 — prove it is a network
[`phase-18`](phase-18-network-liquidity-and-independent-operation.md) requires
useful non-founder supply and demand for three consecutive months. Explicitly
rejects a token, subsidized volume, a mandatory global payment rail, or an owned
GPU fleet.

## Release cycle plans

[`cycle-0-contract-e2e-hardening.md`](cycle-0-contract-e2e-hardening.md) is
folded into the single 0.2 release gate rather than blocking feature work: its
invariants must be green **before the publish**, not before each phase.
[`cli-api-compatibility-matrix.md`](cli-api-compatibility-matrix.md) and
[`indexer-run-progress-observability.md`](indexer-run-progress-observability.md)
belong to the same gate.
[`consumption-adoption-ladder.md`](consumption-adoption-ladder.md) is the
standing policy behind Loop A's "acquire wherever the ecosystem already works"
non-negotiable; read it before changing any acquisition or attribution surface.

## Already shipped

Phases 1–12 are done, and the proving ground is existing infrastructure. Shipped
behavior lives in [`../maintainer documentation: `](../maintainer documentation: ), with recurring release
verification in
[`../maintainer documentation: release-smoke-checklist.md`](../maintainer documentation: release-smoke-checklist.md).

The delivered slices through the former 15.9.1 plan were consolidated and their
plan files retired; the shipped shape is in `api.md`, `database-schema.md`,
`cli-structure.md`, `review-and-trust-pipeline.md`, `marketplace-economy.md`,
`repository-structure.md`, and `agent-proving-ground.md`. That retirement does
**not** claim that native acquisition, harness-integrated observation, HMAC local
identity, or feedback shipped — see
[`normative-carry-overs.md`](normative-carry-overs.md).

The pre-Phase-15 roadmap blocks and the cycle-1 plan were deleted on
2026-08-18: every phase file they linked was already retired, and they reused
the numbers `15`, `16`, and `17` for phases that mean something else today.
This file is the only sequencing authority.
