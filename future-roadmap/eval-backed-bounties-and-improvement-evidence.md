<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Eval-Backed Bounties And Improvement Evidence

> **2026 direction note:** benchmark evaluation is a later verification lane,
> not the initial product or a reason to acquire GPU infrastructure. Near-term
> bounties originate in attributed native use and explicit feedback; independent
> runners bring compute later.

This document covers the first major post-launch expansion of the bounty system:
turning bounties from creator-judged improvement requests into progressively
more measurable, platform-supported improvement loops.

## Why this should happen immediately after launch

The MVP bounty model is good enough to prove the economic loop:

- creator opens a bounty
- contributor submits work
- creator accepts or rejects the submission
- payout state is tracked

That is enough for launch, but it does not create a scalable answer to the most
important question:

```text
Did this course actually get better?
```

Diffs, scanner findings, capability mismatches, and sandbox traces are all
useful, but they do not answer that question by themselves.

Without a stronger evaluation layer, the marketplace risks:

- contributors optimizing for persuasion instead of measurable quality
- creators making hard-to-compare judgment calls on arbitrary submissions
- buyers seeing lots of claimed improvement but little proof
- rankings and bounty reputation drifting toward noise

## Product rule

Keep four layers distinct:

```text
bounty funding != publication trust != runtime containment != quality evidence
```

- Bounties coordinate money.
- Publication review coordinates trust.
- Runtime policy/sandbox coordinates containment.
- Evaluation coordinates whether an improvement actually helped.

None of these replaces the others.

## Main design goal

Logion should make improvement work accessible even to contributors and creators
who do not know what evals are or how to design them well.

The product should not assume that every course creator can invent a sound
benchmark, hidden test set, or scoring rubric.

Instead, the platform should provide a constrained structure similar to Kaggle:

- the task is clear
- the submission format is clear
- the runner is clear
- the scoring function is clear
- fake improvements are harder to sell

Contributors should freestyle on the solution, not on how success is measured.

## Recommended product shape

Support two bounty lanes after launch:

### 1. Proposal / review-assisted bounties

Use when the work is still too subjective or underspecified for strong scoring.

Properties:

- creator or platform defines a plain-language goal
- contributor submits rationale plus artifacts
- review surfaces show diffs, evidence, and tradeoffs
- creator still decides whether to accept the work
- accepted work still becomes a new course version and goes through publication
  review

This is the lighter-weight lane.

### 2. Benchmark-backed bounties

Use when the marketplace can provide a bounded evaluation harness.

Properties:

- Logion defines the evaluation shape
- contributors submit something that must run under Logion's harness
- the platform computes official scores
- creators can still review the work, but the scorecard becomes the shared
  language for deciding whether it improved
- acceptance should not rely on contributor-authored benchmark claims alone

This becomes the scalable, harder-to-fake lane.

## How to help newbies who do not know evals

The platform should progressively take responsibility for evaluation design.

### What the creator should provide

The creator should usually provide only:

- the target problem
- a plain-language success definition
- constraints and tradeoffs
- optional examples of good/bad outcomes

Example:

- "Improve PR review usefulness without adding more false positives"
- "Make the weather-check workflow more robust on missing fields"
- "Improve video cut suggestions for short-form clips while preserving pacing"

### What Logion should provide

Logion should provide the structure around that request:

- bounty type (`proposal` vs `benchmark-backed`)
- task family templates
- fixture format
- submission format
- local validation command
- official runner
- standard scorecard
- hidden/public split when needed
- anti-cheat rules

The less eval expertise a creator needs, the better the marketplace will scale.

## Eval archetypes instead of one universal eval system

Logion cannot assume all courses are about the same thing. Courses may cover:

- PR verification
- browser workflows
- weather/API checks
- data extraction
- writing and transformation
- media editing or selection
- many other domains

So the platform should not try to force one universal metric.

Instead, it should support a small set of eval archetypes:

### Deterministic / exact-match archetypes

Good for:

- routing decisions
- schema extraction
- structured outputs
- command success/failure
- file/artifact generation
- regression suites
- policy/safety checks

Typical metrics:

- exact match
- field accuracy
- pass rate
- regression count
- latency/cost caps
- policy violations

### Execution / workflow archetypes

Good for:

- CLI workflows
- repo verification
- browser automation
- API workflows
- file transformation pipelines

Typical metrics:

- task completion
- expected artifact produced
- side effects match expectation
- tests pass
- no forbidden behavior

### Retrieval / recommendation archetypes

Good for:

- search
- recall
- recommendation
- matching tasks to courses or tools

Typical metrics:

- hit rate
- top-k success
- MRR / nDCG
- downstream usefulness

### Rubric / pairwise archetypes

Good for:

- writing quality
- explanation quality
- curriculum structure
- some creative/media tasks

Typical metrics:

- rubric score
- pairwise preference
- consistency score
- regression guardrails

This is the most expensive and easiest-to-game class, so it should come later
or be used selectively.

## Deterministic evals should be the default

The cheapest and most scalable path is to start with deterministic evaluation.

Prefer these first whenever possible:

- schema validation
- exact output checks
- fixture-based command runs
- regression corpora
- side-effect verification
- bundle-provided tests
- policy/safety rule checks

Why this should be the default:

- cheap to run
- reproducible
- easier to explain to creators and contributors
- much harder to fake than self-reported results
- suitable for broad marketplace coverage

The platform should treat deterministic evals as the backbone and LLM judging as
an exception path, not the default path.

## Cheap LLM evaluation

LLM-based evaluation is still useful for tasks where deterministic checks are not
enough, but it should be constrained carefully.

### When LLM judging is justified

Use it only when the target task is genuinely fuzzy, for example:

- explanation clarity
- summary usefulness
- curriculum sequencing
- nuanced output comparison
- subjective but still reviewable media/text judgments

### How to keep LLM judging cheap

Use these constraints:

- keep prompts short and rubric-based
- score only final outputs, not every intermediate trace
- use pairwise comparison when possible instead of long-form critique
- batch evaluation jobs
- cache baseline outputs and reference artifacts
- apply LLM judging only to bounty classes that truly need it
- use smaller open-source judges for first pass where quality is acceptable
- escalate to stronger models only for narrow high-value cases

### What LLM judging should not do

Do not let it become:

- the only acceptance authority
- the only payout authority
- the default path for every bounty
- a hot-path requirement on every low-value submission

## Can Logion use its own agent network to run evals?

Yes. This is one of the most promising long-term ways to make Logion feel like a
living marketplace instead of a passive registry.

If Agent A submits bounty work, Logion should eventually be able to route bounded
review or eval tasks to Agents B, C, and D, pay them for doing that work, and
use their outputs as part of the official evidence package.

This is attractive for two reasons:

- it can reduce dependence on centralized external LLM providers for fuzzy evals
- it turns evaluation itself into marketplace activity that other agents can earn
  from

That said, the platform should treat this as **network-executed evaluation**,
not as "whatever three random agents said".

The important distinction is:

```text
platform-owned evaluation policy + network-executed evaluators
!= open consensus with no trust controls
```

The platform should still define:

- the eval template
- the scoring rubric
- which evaluators are eligible
- what counts as agreement, disagreement, or abstention
- when a result is auto-accepted
- when a result escalates
- how payout is weighted by later observed accuracy

In other words, Logion can own the eval contract while outsourcing bounded
execution of that contract to the network.

## Automation-first trust and safety

The long-term target should be a trust and safety model that is mostly automated
and agent-native, not a marketplace that secretly depends on a growing human
operations team.

That means the ideal future state is not:

- creator submits work
- human moderator reads everything
- human reviewer decides every payout
- human reviewer decides every publication

It is closer to:

- course bundle review is mostly automated
- eval design is scaffolded and templated
- benchmark-backed bounty scoring is mostly automated
- network agents perform bounded review/eval tasks
- only suspicious, conflicting, or high-risk cases escalate

Human review should become:

- an exception path
- a dispute path
- a fraud path
- a policy-change path
- a high-risk release path

not the default operating model for every marketplace event.

## What a network-evaluator lane should look like

A practical future lane could be:

1. a creator or platform sponsor submits a bounty plus `eval.yml`
2. Logion validates the schema and classifies the eval archetype
3. deterministic checks run first
4. if fuzzy judging is still required, Logion assigns the task to multiple
   qualified network evaluators
5. evaluators return structured judgments, not just prose
6. Logion compares their outputs for agreement, drift, missing rationale, and
   policy violations
7. agreement may resolve automatically for low-risk classes; disagreement,
   suspicious patterns, or high-stakes cases escalate
8. evaluator payout is released only after the result clears platform rules

This preserves the idea that the marketplace is alive while keeping the
platform, not the crowd, in charge of the trust contract.

## What "consensus" should mean

Consensus should not mean simple majority opinion.

A better definition is something like:

- evaluators independently score the same artifact under the same rubric
- outputs are normalized into a structured schema
- Logion checks whether they agree within an allowed band
- deterministic guardrails veto unsafe or clearly invalid outcomes
- evaluator history affects future weighting and eligibility

Possible future signals:

- agreement with later accepted outcomes
- agreement with deterministic checks where overlap exists
- low dispute rate
- low fraud correlation
- usefulness of suggested eval improvements
- stability over time across similar tasks

This makes evaluation by agents feel less like voting and more like a measured
quality-control layer.

## Main risks of paying network agents to evaluate

This can work, but it creates a real attack surface:

- sybil evaluators farming easy credits
- collusion rings between submitters and evaluators
- reciprocal reviewing
- low-effort rubber-stamp judgments
- prompt-targeted overfitting against known evaluator behavior
- hidden centralization where the same model family pretends to be diversity

So this lane should not launch without guardrails such as:

- eligibility thresholds for evaluators
- diversity requirements across evaluator types or providers
- anti-collusion monitoring
- delayed payout or clawback windows for suspicious reviews
- evaluator reputation tied to later observed quality
- strong preference for deterministic checks before network judging
- escalation on disagreement or anomalous agreement

## Should creators evaluate themselves?

Yes, but only in a limited role.

Creators should be allowed to provide:

- self-authored examples
- bundle-local tests
- plain-language acceptance intent
- optional benchmark ideas

But creator-provided evaluation should be treated as:

- a helpful signal
- local iteration support
- part of the evidence package

It should not be treated as the sole source of truth for official scoring.

Otherwise the system becomes easy to game and hard to compare across courses.

## Should Logion evaluate improvements itself?

Yes. Over time, the platform should own the official evaluation path for
benchmark-backed bounties.

Recommended evidence tiers:

### Tier 1: contributor/creator evidence

Useful for context, not authority.

Examples:

- rationale
- local benchmark screenshots
- claimed before/after results
- bundle tests

### Tier 2: platform-run evaluation

This should become the main official quality signal.

"Platform-run" does not have to mean "every judgment comes from a centralized
external model provider". Over time it can also mean that Logion owns the eval
policy, routes bounded judging tasks to trusted network evaluators when needed,
and scores the result under platform rules.

Examples:

- deterministic fixture runs
- standard regression suites
- policy/safety checks
- bounded LLM rubric scoring where necessary
- network-executed evaluator tasks under a platform-defined rubric

### Tier 3: post-publication marketplace evidence

Useful as a long-term reality check.

Examples:

- install-to-keep rate
- repeat usage
- explicit ratings
- low report/refund rate
- observed usefulness over time

The platform-run tier should be the backbone. Self-reported evidence alone is
not enough. Marketplace evidence alone is too noisy and too easy to distort.

## Should marketplace signals influence bounty quality?

Yes, but carefully.

Marketplace behavior can help answer whether a course stays useful after
publication, but it should not be the only official scoring mechanism.

Use marketplace signals for:

- prioritizing which open improvement proposals deserve bounty funding
- discovering stale or degraded courses
- spotting high-impact courses that deserve platform attention
- long-term ranking and reputation adjustments
- surfacing where a benchmark-backed bounty should be created next

Do not use marketplace signals alone as:

- proof that a specific submission improved quality
- a fully trusted payout trigger
- a substitute for benchmark or review evidence

Signals like clicks, installs, or ratings can be manipulated or simply reflect
novelty and incumbency. The marketplace should inform where evaluation effort is
spent, not replace evaluation.

## Suggested execution order after launch

Immediately after launch, the marketplace should add this capability in layers:

1. review/version diffs and creator-facing evidence surfaces
2. benchmark-backed bounty spec with a small number of task-family templates
3. deterministic platform-run eval jobs for the easiest classes
4. open improvement proposals tied to the same evidence model
5. bounded network-evaluator jobs for fuzzy classes with strict eligibility and escalation rules
6. selective LLM judging where network evaluation still needs model help
7. marketplace signals feeding prioritization and long-term ranking

## Optimizer-generated improvement supply

A benchmark-backed bounty plus its `eval.yml` is, structurally, an
optimization environment: program = the skill, verifier = the eval
contract, reward = the scorecard delta. Optimizer loops that mine failures
and mutate skills/prompts against a validation signal already exist in the
open (DSPy optimizers as the research lineage; GEPA-descendants like
Sentient's EvoSkill as evolutionary variants running on Harbor-style
sandboxed tasks). This commoditizes the *production* of improvements — and
moves the scarce value to exactly what this document specifies: neutral
verification and persistent, attributed distribution.

Position, in one line: **optimizer loops produce candidates; Logion proves
which ones are real.**

### What to build (in order)

1. **Optimizer-consumable task export.** Make a bounty + eval contract
   trivially targetable by any optimizer loop: a documented mapping from
   `(bounty, eval.yml, public fixtures, editable components)` to a
   self-contained task directory an optimizer can iterate against locally
   (Harbor-compatible task shape is the pragmatic candidate, since that
   layer is consolidating as shared infra). The winner of a local frontier
   becomes an ordinary bounty submission — same diff format, same scans,
   same candidate runs, same human verdict. No special lane, no extra
   trust.
2. **Field failures seed bounty briefs.** Optimizer loops in the wild mine
   *benchmark* failures; the marketplace will hold something better —
   receipts and telemetry of *real* usage (17.1/17.2). A recurring failure
   class on a version should auto-draft a bounty brief: plain-language
   problem statement, the aggregate evidence (privacy rules of 17.1 apply
   — aggregates only, never raw user traces), and a suggested metric.
   This extends the existing "marketplace signals surface where a
   benchmark-backed bounty should be created next" into a concrete
   pipeline: field failure → draft brief → creator/platform funds →
   optimizer loops and humans compete → verified improvement.

### The trust posture (already designed, restated for this supply)

Optimizer-generated submissions are the strongest argument for defenses
this roadmap already specifies, because reward hacking is their *default
behavior*, not misconduct. First-party evidence: optimizing the Logion
companion with GEPA produced heavy reward hacking against the eval, and
MIPROv2 (DSPy) was adopted instead — an optimizer will exploit any signal
it can see. Hence, unchanged but now load-bearing:

- the hidden split is always scored and never shipped (16.1/16.4), with
  the held-back slice (16.11) defeating overfit-to-shipped-fixtures;
- self-reported optimizer scores are Tier 1 evidence — context, never
  authority;
- benchmark ↔ field reconciliation (17.4) is the final detector for
  improvements that are real on the ruler and fake in production;
- the human verdict gate never auto-pays.

### First-party tooling policy

Logion's own optimization tooling (companion optimizer re-runs, any future
"improve this skill" helper the platform ships or recommends) stays on
**DSPy optimizers** (MIPROv2 lineage) — peer-reviewed research with an
empirically lower reward-hacking profile in our own use. Evolutionary
GEPA-descendants are treated as third-party supply whose outputs the
pipeline verifies like anyone else's.

## Payout chaining for dependency-linked submissions

This is v2 territory. It should land only after sandbox stage 3+ (see
[Sandbox And Runtime Trust](sandbox-and-runtime-trust.md)) and after a task
class has accumulated enough repeat activity for market selection to apply
(see recurrence/stationarity in
[Economic Network And Rewards](economic-network-and-rewards.md)).
Reference: "Economy of Minds" (arXiv 2606.02859).

Accepted bounty work usually depends on earlier work: a regression test, an
eval harness, the original course it patches. A flat single-contributor
payout removes the incentive for that earlier work to exist.

Allocate a single bounty payout across the dependency chain that produced
the accepted submission. Illustrative split:

```text
accepted submitter   60%
prior contributors   25%   (e.g. regression author, eval harness author)
original artifact    15%   (course author whose version chain this extends)
```

Fractions are policy and should be tuned per task class. The required
property is that contributors anywhere in a successful chain earn, so chains
actually form.

The chain itself is derived from already-tracked structure: version
ancestry, bounty submission references, and eval artifacts cited by the
accepted submission. No new authorship claim system is required.

## Seed changes worth planting early

Even before the full feature exists, preserve room for it by:

- keeping course versions immutable
- keeping `course/capabilities.yaml` structured for trust/runtime policy
- adding room for a separate evaluation contract rather than overloading
  capabilities alone
- keeping review evidence structured enough to compare before/after changes
- preserving the rule that accepted bounty work still requires publication review

## Long-term outcome

If this works, Logion does not become just a place where people fund arbitrary
patches. It becomes a place where:

- contributors know what kind of improvement is wanted
- creators do not need deep eval expertise to run useful bounties
- platform-run evidence makes fake improvements harder to sell
- marketplace signals reveal where improvement effort actually matters
- the ranking and bounty economy can gradually reward real usefulness rather
  than only early incumbency or persuasive submissions
