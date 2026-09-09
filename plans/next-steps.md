<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Logion — Next Steps

The execution order. Short on purpose: this is the file to reread weekly.
Everything that is context, contract, or policy moved out on 2026-08-17.

| Read when | File |
| --- | --- |
| Cutting the next release; defining what "done" means | [`release-0.2.md`](release-0.2.md) |
| Writing public copy, arguing positioning, touching protocols | [`positioning-and-independence.md`](positioning-and-independence.md) |
| Touching the landing, the report page, or any public answer | [`public-answer-surface.md`](public-answer-surface.md) |
| Implementing identity, acquisition, reconciliation, observation | [`normative-carry-overs.md`](normative-carry-overs.md) |
| Instructing counsel, forming the entity | [`legal-and-entity.md`](legal-and-entity.md) |
| Publishing a measurement about someone else's artifact | [`../maintainer documentation: measurement-publication-playbook.md`](../maintainer documentation: measurement-publication-playbook.md) |

**Current position (2026-09-07):** step 5a — the plan cadence
(`16.1.1`–`16.1.3`). Step 5 sealed on 2026-09-07: `16.1` carries a passing gate
with no caveats, so a portable eval contract runs through the reference runner.
It cost seven pull requests and 14,443 inserted lines across three
repositories, which is what step 5a exists to stop repeating. Nothing has been
published since 0.1.15 on 2026-07-19.

**The one-sentence goal:** *evaluation is the entry, observation is the upsell.*
A controlled eval needs nobody's permission and works at N=1; consented field
observation needs users and is what gets sold after an eval report opens the
door.

**Corollary, recorded 2026-09-01:** the published measurement is the *acquisition*
surface and the CLI is *retention*. Local skill hygiene is not the wedge — the
pain is real but its carrier is an organisation, and an org is reached through
someone who already believes a number. See
[`positioning-and-independence.md` §The wedge](positioning-and-independence.md#the-wedge).

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

**Steps 1–5d are before the publish. Steps 6–10 are after it.** Everything before
the line exists to make one sentence true — a person who is not Logion acquires
something, uses it, and that use becomes evidence a publisher can be shown.
Everything after the line is about that evidence being believed by someone else.

| # | Work | Exit condition |
| --- | --- | --- |
| 1 | `15.11` closeout | **Done.** Sealed gate `artifacts/phase-gates/phase-15.11.json`. Plan retired 2026-08-27; shipped shape in [`../maintainer documentation: native-use-observation-and-feedback.md`](../maintainer documentation: native-use-observation-and-feedback.md). Residual debt (unpublished companion/observer, cross-driver live hook) is in [`normative-carry-overs.md`](normative-carry-overs.md). |
| 2 | **Cross-hub install reconciliation** | One canonical artifact + version shows where it is listed across every indexed hub, and the install counts of the hubs that publish them, with coverage and blind spots stated. No hub can answer this about another hub. |
| 3 | `15.12` | **Done.** Sealed gate `artifacts/phase-gates/phase-15.12.json`, and `logion.sh` serves a valid `/.well-known/ai-catalog.json` as of 2026-08-27. Plan retired; shipped shape in [`../maintainer documentation: ai-catalog-and-ard-discovery.md`](../maintainer documentation: ai-catalog-and-ard-discovery.md). |
| 4 | [`15.14.1`](phase-15.14.1-local-multi-agent-first-node-foundation.md) + [`15.15`](phase-15.15-isolated-first-runner-node.md) | **Done 2026-09-01.** Sealed gates `artifacts/phase-gates/phase-15.14.1.json` and `phase-15.15.json`, both `passed` with no caveats. One isolated local node runs signed jobs in rootless containers; the hard prerequisite of 16.1 is met. Plans are **not** retired — they carry the live evidence contracts the 16.1 receipt path inherits. Residual debt: three 15.15 criteria have no check designed (see `DEFERRED.md`), 15.14.1's verdict is not recomputed from typed facts until the freeze lifts 2026-09-30, and the 15.15 dogfood protocol was not completed. |
| 5 | [`16.1`](phase-16.1-eval-contract-and-reference-runner.md) | A portable eval contract runs a third-party skill through the reference runner and produces a normalized result. Gate sealed 2026-09-07 (`artifacts/phase-gates/phase-16.1.json`, `passed`, no caveats). Two criteria still have no check designed (see `DEFERRED.md`) and step 5d reseals it from a run where the actor performs the flow. |
| 5a | [`16.1.1`](phase-16.1.1-a-gate-outlives-its-plan.md) + [`16.1.2`](phase-16.1.2-a-plan-is-one-pull-request.md) + [`16.1.3`](phase-16.1.3-the-documentation-is-read-out-of-the-code.md) | The plan cadence, before the next phase uses it. A delivered plan retires into `maintainer documentation: phases/` under its own number and `docs_integrity` holds it there; a plan promises something checkable or `sf check` is red; the indexes and command lists in the three READMEs are read out of the repositories instead of retyped. Sits between 16.1 and 16.2 on purpose — 16.1 is the phase that measured what a nine-assertion gate costs, and 16.2 is the first that can be built in numbered children instead. |
| 5b | [`16.2`](phase-16.2-typed-evaluators-and-skill-reference-evaluator.md) | Typed evaluators, entered as numbered children under the 16.1.2 ceiling rather than as one entry. |
| 5c | [`public-answer-surface.md`](public-answer-surface.md) | One URL answers "does this artifact work?" with no account and no install, renders at least one real finding on first load, and content-negotiates for an agent. Absorbs [`17.6`](phase-17.6-public-narrative-and-landing-truth-pass.md) and the report page — it is **less** 0.2 scope, not more. |
| 5d | [`driven-actor-performs-the-measured-flow.md`](driven-actor-performs-the-measured-flow.md) | The `node_operator` in `isolated_runner_node` and `eval_contract_reference_runner` carries a real goal and performs the flow its assertions measure, with `15.15` and `16.1` resealed from runs where that is true. Not a product step: it removes a reward-hacking shape from two already sealed gates. The driven-actor rule in `logion#317` is its exit criterion, which is why landing that rule before this work is what blocks a merge. |
| — | **RELEASE 0.2** | Loops A, B, D work end to end. Full gate in [`release-0.2.md`](release-0.2.md). No publish before this. Note that Loop B's primary launch answer is Logion's own controlled evaluation, so measurements exist *before* this line, not after it. What step 6 adds is publishing one as a report about a named third party. |
| 6 | **First public measurement** | One published, reproducible evaluation of a third-party artifact: prose, stated method and limits, the subject version, and the command to reproduce — **and one reproduction of it by somebody who is not Logion**. The real gate — not "16.2 merged", and not the same artifact as the in-product answer that 0.2 already ships. Chosen shape recorded [below](#the-shape-of-step-6); why the reproduction is part of the exit condition rather than a nice-to-have is in [`positioning-and-independence.md`](positioning-and-independence.md#reproduction-is-the-substitute-for-reputation). |
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

### Why the envelope fields land before the publish

Two fields are still owed to the observation envelope: the **harness version**,
and a **model slug drawn from a closed allowlist**. The contract is in
[`normative-carry-overs.md`](normative-carry-overs.md#envelope-fields--decided-2026-08-27-unbuilt)
rather than in a phase file, because `15.11` is closed and its plan is being
retired — the decision has to outlive it. It attaches to whichever phase next
touches the envelope.

The sequencing argument is about schema, not product. The spool rejects any
record whose `integration_version` does not match, so adding a field later is a
version bump that invalidates every installed hook. **The cheapest moment to
change a strictly-versioned envelope is while the installed base is approximately
zero**, which is now and will not be true after 0.2. Nothing else about these
fields is urgent; the schema discipline is what makes them urgent.

Measured token counts are **not** added. The harness does not expose per-resource
token attribution in a hook payload, so any number there would be inferred, and
an inferred number is what this whole document forbids. Token measurement belongs
to `16.2`, where the runner controls the loop. The existing `token_efficiency`
score stays what it is: a declared opinion, not a measurement.

### The shape of step 6

Step 6 is one published measurement. Its cheapest high-signal shape is an
**aggregate over a bounded top-N of one hub** — "we ran a published eval contract
over the N most-installed skills on <hub>; X% do not do what they claim" — rather
than a single artifact in isolation.

Three reasons this shape is preferred:

1. It costs one bounded run, not a fleet, which is the binding constraint while
   the founder funds compute personally.
2. It is the number this workspace already carries as unverified: the reported
   *~67% of skills fail in practice* in
   [`positioning-and-independence.md`](positioning-and-independence.md) is marked
   "confirm before public use". Confirming it **is** the launch.
3. It satisfies both the publication rule and the outreach step at once:
   **publish the aggregate, send each individual finding to its author
   privately.** The aggregate is the public artifact; the individual reports are
   step 8's outreach, which then arrives with a finished report as required.

The observed pattern in this niche supports the shape — `skill-history.com` over
skills.sh, `apifystats.com` and `audit-tools.ai` over Apify. What travels is a
third party measuring the popular thing and publishing an uncomfortable number.
Yukon launched on one verifiable result, not an architecture.

**One external reproduction is part of step 6, not a follow-up.** An unknown
issuer has no reputation to lend the number, and the answer to that is not to
accumulate reputation first — it is that a stranger can re-run the result in one
command. That property is only real once somebody has actually done it, so the
step does not close on publication. What counts: a person who is not Logion runs
the published command against the pinned subject version and reports the
result — agreeing *or* disagreeing. A disagreement that surfaces a real method
error is a better outcome than silence, and it is handled by Step 3 of
[the publication playbook](../maintainer documentation: measurement-publication-playbook.md).
Cheap, and it is the only down-payment on
[issuer #2](positioning-and-independence.md#issuer-2--the-milestone-that-makes-the-thesis-true)
available before federation exists.

**Preferred first subject: a token-reduction skill.** This class carries a
*quantitative, falsifiable, publisher-declared* claim, which makes it the
cheapest thing to measure and the most shareable thing to publish. Two live
candidates, both checked 2026-08-27:

- **`caveman`** — 51,690 GitHub stars within two weeks of release, advertising a
  65% token cut (75–80% in ultra mode). It also carries live public
  *disagreement* — *"it is not consensus that caveman is good; a lot of people
  dislike its output"* (field thread, 2026-08-31) — which fires selection
  triggers 1, 2 and 3 simultaneously and makes it the strongest available
  subject rather than merely the most popular one. Its own documentation concedes the claim
  covers **output tokens only** — input and reasoning are untouched — and that
  the skill adds roughly 1–1.5k input tokens per turn. Nobody has measured the
  crossover, so on short-output, many-turn workloads it may *increase* total
  spend. That boundary is an unclaimed, highly shareable finding.
- **`ponytail`** — advertised −54% code, −22% tokens, −20% cost, −27% time. A
  JetBrains benchmark measured −15% code, −10.3% cost, −11% time: a quarter to a
  half of the claim, with the bootstrap interval on the median just touching
  zero, and savings concentrated on large tasks (−31% on 300+ line work, near
  zero on minimal ones). A published prior measurement to build on or contest,
  and a textbook demonstration of why a result belongs to a task class and a
  model-harness pair rather than to a single headline percentage.

This is also the answer to "the next model makes measurement irrelevant": a
better model does not fix a broken artifact it was instructed to trust, and a
declared percentage that holds only above 300 lines is a fact about the artifact,
not about the model.

**Alternative first subject:** `find-skills` (Vercel Labs), 3.1M installs and 29.7K
stars on skills.sh, whose own description states that its quality criteria for
recommending other skills are install count above 1K, source reputation, and
GitHub stars. The most-installed skill whose job is finding good skills ranks by
popularity. It also carries a Snyk *Warn* alongside two passing audits, which
nothing in the ecosystem reconciles, because a security audit is not evidence of
function. Selection still runs through
[`../maintainer documentation: measurement-publication-playbook.md`](../maintainer documentation: measurement-publication-playbook.md),
including author contact before publication.

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
- **Closing a phase is not retiring its plan, and from 15.15 on it usually must
  not be.** Phases 15.10–15.12 were retired because their gate assertions sit in
  `_CONTRACT_FREEZE` and declare no evidence contract, so deleting the plan cost
  nothing. That stopped being true at 15.15. A plan with a declared evidence
  contract is load-bearing: `phase_integrity.py` requires `phase["plan"]` to
  exist, `evidence_contract.validate()` rejects an `evidence_contracts` block
  whose phase has no entry, and the mutation suite indexes the shipped policy by
  phase id. Deleting such a plan therefore deletes the contract, the mutation
  tests that prove the auditor fires, and — because
  `server_authoritative_request_fields` is only checked for *activated* phases —
  the guard on live code that nobody is going to re-add. Retire a plan only when
  its phase entry can be removed without removing a check. Otherwise mark the
  criteria `- [x]` with a dated settlement note and say **Done** here.
  [`16.1.1`](phase-16.1.1-a-gate-outlives-its-plan.md) replaces this rule with
  a mechanism — the plan moves to `maintainer documentation: phases/` under its own number,
  whatever guarded live code is re-homed as a standing entry first, and
  `docs_integrity` refuses a retirement that is only half done. Until it lands,
  this rule stands.
- **A phase entry demands at most five assertions.** Above that it splits into
  numbered children that seal independently. `16.1` cost seven pull requests
  and 14,443 inserted lines because nine assertions in one gate cannot be
  landed in pieces; the argument and the review date are in
  [`16.1.2`](phase-16.1.2-a-plan-is-one-pull-request.md).
- **A number is spent once**, whether or not it ever carried a gate, and a
  retired number keeps a document in `maintainer documentation: phases/` where a check can
  see it. The pre-Phase-15 blocks were deleted on 2026-08-18 precisely because
  `15`, `16` and `17` had been reused for phases meaning something else.
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
- **The answer is free and install-free; the CLI answers a different question.**
  Never gate a public answer behind installing the CLI. The CLI's pitch is the
  user's own inventory, not more of the public answer. See
  [`public-answer-surface.md`](public-answer-surface.md).
- **Rank by disclosed properties, never by an aggregate quality score.** This
  binds hardest where Logion measures evaluators: a single "eval quality score"
  makes Logion the terminal authority, which contradicts `16.5` ("authority is
  local, issuer-aware, and policy-versioned"). Publish whether an eval has a
  control, a statistical test, a held-out set, a contamination check, and whether
  its reference solution passes its own benchmark — and let the consumer weigh.
- **A published result belongs to a model-harness pair, not to a model.** Record
  harness id+version and model id+version as closed fields, and never compare two
  results across differing pairs without saying so.
- **No public claim can be stronger than its underlying evidence and local
  authority policy.**

## Phase index

`#` maps to the execution order; `—` means written but off the critical path.

### Phase 15 — first useful node
[umbrella](phase-15-native-resource-loop-and-first-ai-catalog-ard-node.md)

| Phase | # | Outcome |
| --- | --- | --- |
| `15.10` | done | Hosted artifact downloads plus `npx skills`, `npx plugins`, `hf` acquisition/reconciliation. Plan retired 2026-08-27; shipped shape in [`../maintainer documentation: native-acquisition-and-inventory.md`](../maintainer documentation: native-acquisition-and-inventory.md) |
| `15.10.1` | — | DeepSeek Harness plugins: built and dogfooded against real `dsh`, plugin **unpublished**. **Distribution experiment**, run after step 6. Plan retired 2026-08-27; shipped shape in [`../maintainer documentation: native-acquisition-and-inventory.md`](../maintainer documentation: native-acquisition-and-inventory.md) |
| `15.11` | done | Observe native usage; feedback linked to the exact resource. Plan retired 2026-08-27; see [`../maintainer documentation: native-use-observation-and-feedback.md`](../maintainer documentation: native-use-observation-and-feedback.md) |
| `15.11.1` | — | Publisher-shipped consented projections; **never built, not now**. The Analytics role it was meant to fill is step 2, which needs no consent and no client-side code. Revisit only on the trigger in [`normative-carry-overs.md`](normative-carry-overs.md#publisher-integrated-observation--designed-not-built). Plan retired 2026-08-27; full design in git history |
| `15.12` | done | AI Catalog publication + ARD discovery. Plan retired 2026-08-27; see [`../maintainer documentation: ai-catalog-and-ard-discovery.md`](../maintainer documentation: ai-catalog-and-ard-discovery.md) |
| [`15.13`](phase-15.13-portable-scan-evidence.md) | — | Signed portable evidence from current scanners |
| [`15.14`](phase-15.14-feedback-driven-platform-bounties.md) | — | Platform-funded improvements from attributed usage |
| [`15.14.1`](phase-15.14.1-local-multi-agent-first-node-foundation.md) | done | Isolated founder-operated roles on one MacBook. Sealed gate `artifacts/phase-gates/phase-15.14.1.json`. Plan kept: it is the canonical plan its policy entry binds to |
| [`15.15`](phase-15.15-isolated-first-runner-node.md) | done | First isolated CPU runner. Sealed gate `artifacts/phase-gates/phase-15.15.json`. Plan kept: it is the canonical plan behind the runner receipt/sandbox evidence contract |
| [`15.16`](phase-15.16-first-party-resource-dogfood-loop.md) | — | Recurring acquire → use → evidence → bounty → rerun loop |
| [`15.17`](phase-15.17-aktp-evidence-and-improvement-feed-v0.md) | 7 | AKTP v0 as an ARD-linked evidence/improvement feed |

### Phase 16 — verification
[umbrella](phase-16-distributed-evaluation-and-independent-verification.md)

**Step 5:** [`16.1`](phase-16.1-eval-contract-and-reference-runner.md).
**Step 5a:** [`16.1.1`](phase-16.1.1-a-gate-outlives-its-plan.md),
[`16.1.2`](phase-16.1.2-a-plan-is-one-pull-request.md),
[`16.1.3`](phase-16.1.3-the-documentation-is-read-out-of-the-code.md) — the
plan cadence, numbered but deliberately ungated: they change policy and
generators, have no customer effect to seal, and prove themselves with `test:`
markers.

**Parked, off the critical path, both written 2026-09-08 out of one
measurement:** [`16.1.4`](phase-16.1.4-a-published-entry-resolves.md) — a third
of our own AI Catalog is a dead pointer, the exported contract declares no
security scheme, and ten money-moving POSTs have no idempotency key. No
precondition; it is a defect plan and every finding in it is reproducible from
a terminal today. [`16.1.5`](phase-16.1.5-what-is-installed-here-has-a-version.md)
— one of the fourteen skills installed on the operator's machine carries a
version, it is Logion's own, and it is stale. No technical precondition either:
it is the N=1 the thesis claims, run on the machines the work actually happens
on, and what it competes with is time, not a dependency. Neither is required
for 0.2.

**Step 5b:**
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
marketplace. `17.6` is now executed *through*
[`public-answer-surface.md`](public-answer-surface.md) at step 5c: the landing
rewrite and the evidence report page are one deliverable, built report-first.

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
