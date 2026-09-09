<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Release 0.2 — the loop has to work

> **The single acceptance test for 0.2:** a person who is not Logion installs
> the CLI, acquires a skill from anywhere, uses it in their own harness, and
> that use becomes attributed evidence a publisher can be shown. Everything
> below exists to make that sentence true. A phase merging is not the gate.

Exit condition: every box in "Gate checklist for cutting 0.2" below is checked
on real evidence, and the release is published (0.2 on PyPI and npm) with the
landing page's durability language matching what the gate actually proved.

Current published state: `logion-cli` / `logion-client` (PyPI) and
`@logionsh/cli` (npm) are at **0.1.15, published 2026-07-19**. Everything from
15.10, 15.10.1, and 15.11 is unreleased. 0.2 is the next publish and there is
no publish before it.

The version is deliberate. 15.10 (acquisition), 15.11 + 15.11.1 (observation),
15.12 (catalog/discovery), and 16.1/16.2 (evaluation) are one product story.
Shipping them as 0.1.16 … 0.1.21 spends the announcement on fragments and
leaves every intermediate version describing a product that cannot yet do the
thing it is for.

## The loops

Four loops define the product. Loops A, B, and D ship in 0.2. Loop C does not —
see its section for why, and do not pull it forward.

### Loop A — usage (the core loop, 0.2)

```text
1. user installs Logion
2. user acquires a skill — from Logion, skills.sh, ClawHub, LobeHub, hf,
   npx skills, npx plugins, dsh, or a bare git clone
3. the harness emits usage signal on real work
4. that signal accumulates into an attributed usage + review base
```

Non-negotiables in this loop:

- **Step 2 must not require reacquisition through Logion.** A skill the user
  already has, installed by any native manager, is in scope. Logion attributes;
  it does not replace the installer. This is the difference between an
  observability layer and a competing store.
- **Step 3 carries two signal classes, and they must never be merged.**

| Class | What it is | Who produces it | Endpoint | Rating? |
| --- | --- | --- | --- | --- |
| **Deterministic** | Machine fact: the resource was invoked, it completed or failed, duration bucket, harness, exact version, scope kind | The harness hook, mechanically | `POST /resources/{id}/versions/{vid}/usage-receipts` | Never |
| **Non-deterministic** | The agent's own judgement: did this help, what broke, usefulness / reliability / tool-safety / token-efficiency, prose | The agent, deliberately, after the task | `POST /resources/{id}/versions/{vid}/feedback` | Yes |

  Both are already implemented in `api/resource_feedback/`. The distinction is
  not new — it is the existing receipt-vs-feedback split, and this is the
  vocabulary to use for it publicly. **An observation is not a rating.** A
  deterministic receipt says something ran; only the agent's deliberate report
  says whether it was any good.

- **Step 4 is what gets shown to publishers**, and it publishes `n`. See
  `../maintainer documentation: measurement-publication-playbook.md`.

Harness coverage required for 0.2 — each declares capability honestly and fails
closed rather than inferring use:

| Harness | Deterministic receipt | Non-deterministic feedback |
| --- | --- | --- |
| Claude Code | hook in `settings.json` | agent-invoked |
| Codex | hook in `.codex/hooks.json` | agent-invoked |
| DeepSeek Harness (dsh) | via 15.10.1 plugin channel | agent-invoked |
| pi.dev | scope discovery only today → `inventory_only_observation_unsupported` | agent-invoked |
| Hermes | scope discovery only today → `inventory_only_observation_unsupported` | agent-invoked |

A harness without a trustworthy tool-use hook reports
`inventory_only_observation_unsupported`. It never fabricates an event, and
install is never counted as use.

### Loop B — the question (0.2)

```text
before:  "does this skill work?"          → nobody can answer
after:   "/logion does this skill work?    → Logion answers
          what do other agents say?"
```

This is the daily-use surface and the reason an individual keeps Logion
installed. Acquisition after the answer happens through Logion **or outside
it** — the answer is the product, not the checkout.

**Design consequence that must be respected at launch.** On day one the field
cohort is empty, and the feedback summary correctly suppresses everything below
the minimum cohort threshold. If Loop B answers "not enough data" for every
query, the first experience is worthless.

So the answer to Loop B is layered, and the layers must be visibly labelled:

1. **Controlled evaluation** (16.2) — Logion's own measurement. Available on
   day one, needs nobody. This is the primary answer at launch. It measures
   **isolated task performance**, which is a weaker claim than sustained use
   across a session, and the layer label must say so — see
   [The sustained-use boundary](#the-sustained-use-boundary).
2. **Static evidence** — scanner results, capability manifest, permissions,
   license, freshness, source provenance.
3. **Field cohort** — deterministic receipts and agent feedback, shown only
   above the cohort threshold, always with `n`, version coverage, harness
   coverage, and known blind spots.
4. **Cited external measurement** — somebody else already measured this
   artifact and published a method. Carries the issuer, the date, the subject
   revision where it is determinable, the URL, and whether anyone has
   reproduced it. Never authoritative, never a badge, always ranked below a
   controlled evaluation, and marked **superseded** the moment the subject
   ships a newer version than the one measured.
5. **Nothing** — say so plainly. "No measurement yet" is a valid, honest
   answer and it is also a demand signal for what to evaluate next.

Never blend the layers into a single opaque score. The whole product is that
the user can see which layer an answer came from.

**Why layer 4 exists.** Published third-party measurements of agent artifacts
already exist and are accumulating — a design-MCP comparison, an independent
retest of a viral skill's token claim, a contributor's critique that made a
skill's author correct their own benchmark. Every one of them is a blog post
with a date. Nothing re-runs when the subject ships a new revision, nothing is
addressable by the agent about to install it, and nothing survives the
publisher losing interest. Indexing them is the cheapest way to stop Loop B
saying "nothing" on day one, and it costs no inference and needs nobody's
permission.

**The cheapest first specimen is a published benchmark about a `model`.** A
benchmark that names a model version and the harness it ran in already carries
every field this layer requires — issuer, date, a determinable subject revision,
a stated method, a public URL — and it exercises `superseded` naturally, because
models ship new versions faster than skills do.
[arXiv:2603.13428](https://arxiv.org/abs/2603.13428) is one such specimen: it
reports a named model in a named harness at 38.03%. Proving the layer against a
benchmark is a cheaper first test of the same storage class than hunting a blog
post about a skill, and `model` is already in scope for the answer surface.

It is also the layer that has no storage class today. The capability-profile
ladder is `observed` / `candidate` / `attested`, each with exactly one
producer, and an unsigned external study is none of the three: Logion's
scanner did not produce it, no bounty delivered it, and no author took it
through publication review. Adding it is a fourth mode with its own producer,
governed by
[`TB-CLAIM-NOT-ENDORSEMENT`](phase-17.5-trust-boundary-invariant-tests.md) —
the invariant already exists; the storage does not.

Design it so the predicate can be emitted **by the party who ran the study,
without Logion in the loop.** A citation Logion has to transcribe is an index;
a predicate an outside issuer can sign about their own work is the first step
to issuer #2, which is the actual thesis milestone.

#### The sustained-use boundary

Layer 1 is the launch answer, and a controlled evaluation is an isolated-task
measurement by construction — that is exactly what makes it reproducible and
what lets another runner replicate it. It is not evidence about behaviour
sustained across a working session, and 0.2 must not let the rendering imply
otherwise.

Two independent published results bound this, from different groups, months
apart:

- [arXiv:2603.13428](https://arxiv.org/abs/2603.13428) holds agent, model,
  repository and verification constant and varies only whether tasks are
  independent or dependency-chained: top scores fall from 80–90% on isolated
  tasks to a maximum of 38.03% under continuous evolution, with a milestone
  resolve rate of 13.37%, and roughly 57% of root causes attributed to failures
  inherited from earlier steps rather than generated locally.
- [arXiv:2608.27454](https://arxiv.org/abs/2608.27454) states the same gap from
  the other side, declaring very long-horizon tasks — hundreds of environment
  actions, multiple hours — outside its evaluated scope.

The consequence for this release is a blind spot, not a feature: the
deterministic receipt is a per-invocation record, so a failure carried in from
an earlier step is invisible to the unit Logion records. Say that, in the layer
label and in the disclaimer. Under
[`../maintainer documentation: measurement-publication-playbook.md`](../maintainer documentation: measurement-publication-playbook.md)
a stated blind spot is also a demand signal for what to measure next.

Do not try to close it in 0.2. The archetype that would measure across a
sequence is deferred — see
[What 0.2 explicitly does not include](#what-02-explicitly-does-not-include).

### Loop C — claim, sell, improve (NOT 0.2 — target 0.3)

```text
1. publisher claims an indexed skill
2. sells it, or does not, on their own terms
3. wants it improved → funds a bounty
4. Logion users list open bounties and submit improvements
5. winner takes all (for now)
6. the improvement is a new immutable hash
```

**This loop does not ship in 0.2, and pulling it forward would damage the
thing 0.2 is built to establish.** Two reasons:

- Step 1 requires [`17.3`](phase-17.3-resource-claims-and-commercial-rails.md)
  (claim challenges, ownership proof, transfer/revocation/dispute). That is
  deliberately late in the execution order.
- Until issuer #2 exists, Logion's independence from what it measures is
  *methodological*, not structural. Selling the artifacts it rates before then
  invites exactly the conflict that produces third-party auditors around walled
  gardens. See
  [`positioning-and-independence.md`](positioning-and-independence.md).

What already exists and can be exercised meanwhile: platform-funded bounties on
ownerless indexed listings, and creator-funded bounties on Courses.

Decisions to record now so 0.3 does not relitigate them:

- **Winner takes all is a deliberate v0.3 simplification, not the end state.**
  It is the opposite of the bucket-brigade payout chaining the workspace README
  names as part of the moat. Ship single-winner first because dispute surface
  and payout complexity kill the first loop; revisit once bounties actually
  clear.
- **The improvement is a new immutable hash.** Resource versions are keyed by
  content digest, so this is already the model. The new version does not
  overwrite, and prior evidence stays bound to the version it measured.
- Ownership rules are already settled in
  `../maintainer documentation: community-improvements-and-funded-bounties.md` and must not be
  re-invented: a funder never gets ownership, release authority, or maintainer
  status; a contributor keeps immutable attribution; only the owner of the
  immediate upstream artifact may authorize a derivative.
- An unfunded item is **"Community improvement — no reward"**, never called a
  bounty without the no-reward disclosure.

### Loop D — coverage boundary (0.2)

What can be tracked, honestly, at 0.2. This table is a public artifact — it is
the disclaimer, and it must fail closed when a harness release drifts.

| Subject | Deterministic receipt | Exact version attribution | Notes |
| --- | --- | --- | --- |
| Agent skill, installed locally | yes, via harness hook | yes — native receipt/lock plus digest | Full loop |
| Plugin, installed locally | yes | yes | Full loop |
| **Remote MCP server** | **yes, client-side** | **no** | See below |
| Local/stdio MCP server | yes | yes, when a lockfile or digest exists | |
| Model (hf) | metadata-first | version yes, use no | Larger evaluation waits for compute |

**The remote MCP correction.** The intuition that "MCP lives on a server so we
get no usage data" is not quite right, and the precise version matters because
it is what goes in the disclaimer:

- The harness **does** see MCP tool calls client-side. A `PostToolUse` hook
  observes `mcp__<server>__<tool>` invocations like any other tool. So
  deterministic receipts for remote MCP are obtainable, and the agent can still
  file non-deterministic feedback.
- What is genuinely missing is **exact version attribution**. A remote endpoint
  has no native receipt, no lockfile, no immutable revision, and no content
  digest. Under the standing reconciliation order that resolves to `unlinked`
  or `ambiguous` — never to a specific `ResourceVersion`. Name similarity is
  never identity.
- Also missing: server-side ground truth. Origin latency, errors that never
  reached the client, and behaviour for other clients are invisible.

So the honest public statement is: *for a remote MCP server, Logion can report
that an endpoint was used and how the agent judged it, but cannot bind that to
an exact immutable version, and reports only what the client saw.* Server-side
truth requires the operator to instrument
(designed, not built — see
[`normative-carry-overs.md`](normative-carry-overs.md#publisher-integrated-observation--designed-not-built)) —
which is the upsell, not a gap to paper over.

Remote execution never authorises TLS interception, credential access, probing,
load testing, or provider-side modification.

**This table bounds what can be attributed, not what a measurement means.** The
second boundary is [The sustained-use boundary](#the-sustained-use-boundary)
under Loop B, and the public disclaimer needs both: one says which subjects
Logion can bind to an exact version, the other says what a passing evaluation
of that version does and does not claim.

## Public surface required for 0.2

The agent-first documentation stance was correct when the user was an agent
being asked about Logion. It does not match the buyer any more. The person who
must be convinced is a human at a company deciding whether to trust Logion with
usage data and whether to fund a bounty. That person opens a browser, spends
thirty seconds, and leaves.

Required, and they are **one** deliverable, not four —
[`public-answer-surface.md`](public-answer-surface.md) owns the whole of it:

1. **A public answer with no account and no install.** One URL where pasting a
   skill, plugin, MCP server or model returns what is known about it. This is
   the surface Loop B was always designed for: its launch answer is controlled
   evaluation, which "needs nobody" and works at N=1, so the answer never
   depended on the asker having installed the CLI. Until now no plan described
   a way to get an answer out of Logion without installing it.
2. **Landing truth pass** — [`17.6`](phase-17.6-public-narrative-and-landing-truth-pass.md),
   pulled forward out of Phase 17. The current landing describes a marketplace
   and shipping 0.2 against it publishes a false description of the product.
   It is executed *through* item 1: the landing **is** the answer surface.
3. **One evidence report page.** A permanent URL rendering one measurement
   well: the chart, the method, the eval-contract digest, the subject version,
   the limits, `n` where field data appears, and the command to reproduce.
   yukon.org's benchmark-evolution view is the reference for what "showing the
   number" looks like when evidence is the product. Built **first**, because the
   landing renders it rather than linking to it.
4. **A version-over-version chart.** The single most valuable visual is the
   same subject measured across versions — it makes improvement visible, which
   is the entire thesis in one image. It must refuse to plot two points whose
   harness/model pair differs without saying so on the chart — otherwise a
   harness upgrade renders as an artifact improvement.
5. **A human-readable explanation of the loop** — measure → evidence →
   improvement → re-measure — placed *below* a rendered result, never above it.

Scope discipline: build one page that renders one report beautifully. Generalise
into a dashboard only once there are enough reports to justify it. When the
product is evidence the visualization is the deliverable — that is an argument
for making one excellent, not for building a charting framework around a single
data point.

**Do not put ecosystem statistics in the hero.** Aggregate problem statistics are
what a page shows when it cannot show the output. A rendered finding — "this
skill fails 40% of task class X" — is a stronger argument than any market-level
number, and the stats belong in the report body, the call, and the launch post.

**Category discipline.** A business-side reader who follows the space read the
current landing and understood ~30% of it, seeing neither the problem nor the
mechanism, because he filled the empty category with Braintrust — first-party
eval and observability for the app *you* wrote. The correction is to borrow the
adjacent full category rather than invent vocabulary: *Braintrust evaluates the
agent you wrote; Logion evaluates the parts you installed inside it.*

The engineer-side failure mode is different and was measured separately on
2026-08-31: six working senior engineers read the pitch and landed on "isn't
that just a README", "a hub of skills", "a marketplace of markdown". The shared
cause is that **every index metaphor re-imports the marketplace category this
release exists to leave.** Lead with the verb — *nobody proves that a skill
works; Logion does* — and let the rendered finding carry the rest.

### The first rendered finding is first-party

Decided 2026-09-02. The subject of the measurement rendered on the public
surface at 0.2 is Logion's own work — the `logion` skill and
`software-factory` — and not a famous skill from a hub. The third-party
measurement stays where it was, at
[step 6](next-steps.md#execution-order), after the release.

**This resolves a contradiction, it is not a preference.** Three rules in this
workspace currently cannot all hold:

1. this release's gate requires the public surface to render at least one real
   finding **on first load**;
2. [`next-steps.md`](next-steps.md#execution-order) puts the first public
   measurement of a third party at step 6, *after* the publish;
3. [the publication playbook](../maintainer documentation: measurement-publication-playbook.md)
   forbids publishing about a third party before author contact, a 7-day
   response window, a published takedown policy, and the
   [legal items](legal-and-entity.md) whose trigger is "before the first
   public measurement".

Rendering a third-party finding at 0.2 either drags step 6 across the release
line or breaks the playbook. A first-party finding satisfies (1) while
leaving (2) and (3) intact, and it is the only subject that does.

**It is also the only subject that can carry the release's most valuable
visual.** [Item 4 of the public surface](#public-surface-required-for-02) is
the version-over-version chart, and a third-party skill measured once is one
point. `software-factory` has a version history Logion owns, so the same
subject can be measured across its own versions and the chart shows an
artifact improving. That is the entire thesis in one image, and nothing else
available at 0.2 can produce it.

Three conditions, all binding:

- **A closed `first_party` field on the result, not a sentence.** 15.16
  already requires honesty labels for first-party / inconclusive / failed on
  the public view; this is that field, decided here because 0.2 renders before
  15.16 ships.
- **Publish the unflattering one.** A first finding that says Logion's own
  skill scores well is worth nothing as evidence and confirms the reading six
  engineers already gave the landing page — a demo. Under
  [audience discipline](#public-surface-required-for-02) a negative finding is
  the credential. `software-factory` is opinionated enough to plausibly lose
  on a task class, which makes it the better of the two subjects.
- **It does not relax the independence rule.** What
  [`positioning-and-independence.md`](positioning-and-independence.md#independence-methodological-now-structural-later)
  forbids before issuer #2 is *selling what Logion measures*, not measuring
  Logion's own work. Measuring itself and saying so is inside the rule;
  measuring itself and rendering it unlabelled is not.

**The task environment is a real repository, and that is the dogfood loop.**
`nicolasmelo1/itl` (public, Python, under active development) is the candidate:
measuring whether a skill helps on invented fixture tasks measures the fixture.
Two constraints follow. The eval contract pins a **commit**, because a repo
still being written is not a stable subject and a result that cannot name the
tree it ran against is not reproducible. And the loop has to close: a finding
about `software-factory` becomes an improvement to `software-factory`, which
is re-measured as a new version and lands as the second point on the chart —
that is [15.16](phase-15.16-first-party-resource-dogfood-loop.md)'s canonical
loop run for real rather than described. `nicolas-portfolio` is out: finished
work generates no ongoing tasks to measure against.

**Audience discipline.** The reachable reader is the engineer who already tried
a pile of skills, concluded none worked, and stopped. They ask "is it worth
trying again?", not "which one is best?" — so a negative finding is the
credential, not a downer. See
[`public-answer-surface.md`](public-answer-surface.md) Rule 2.1.

## Gate checklist for cutting 0.2

Ordered. Everything must be true simultaneously.

- [ ] **Loop A end to end on a machine that is not the founder's**, with a
      harness hook firing **live** — not a replayed payload. Corrected
      2026-09-02: the live-hook half is already done and the replay claim was
      misattributed. `files.observation_from_live_hook` passed in the sealed
      `phase-15.11` report for `native_use_observation_and_feedback`, with 12
      hook invocations; the caveat on that gate is about
      `remote_private_mcp_feedback`, where the agent emits the observation
      itself through `usage observe --stdin` because no harness delivers a
      payload to a differently-driven session. What is still open here is
      only the machine: every run to date is the founder's, against a local
      devrig, with seeded fixtures and role API keys.
- [ ] The seven "Still open" items in
      `15.11`
      are closed, including a **pseudonymous identity tier** — `identity_tier`
      is always `account` today, so feedback still requires an account, which
      contradicts the local-first pitch on the first screen.
- [x] **One envelope, not two.** Settled 2026-08-27: `cli/usage/observations.py`
      is the single normative envelope and `cli/_observation.py` is deleted.
- [x] `logion.sh` serves `/.well-known/ai-catalog.json`. Verified live
      2026-08-27: 308 to `www.logion.sh`, then 200 with a valid
      `specVersion: "1.0"` document. Note the apex redirect — `api.logion.sh`
      returns 403 for the same path and is not the serving origin.
- [ ] ASM contact (T1) has fired, before the 15.12 design freeze.
- [ ] Loop B answers with a labelled layer, and answers "no measurement yet"
      honestly when that is the truth.
- [ ] Loop B's **cited external measurement** layer resolves at least one real
      published third-party measurement to the exact artifact it measured, shows
      the issuer and date, and marks it superseded when the subject has moved on.
      (proof: unspecified:no storage class exists for an unsigned external study; the ladder is observed/candidate/attested and this is none of them)
- [ ] **The archive survives Logion.** `logion aktp export` produces a signed,
      self-contained archive that a clean node imports without loss, and a second
      import creates zero rows.
      (proof: unspecified:the self-export/import test is specified in 15.17, which is sequenced after this release)
- [ ] Loop D coverage table is generated from recorded harness fixtures and
      fails closed on drift.
- [ ] `16.1`/`16.2` produce a normalized result for a **third-party** skill
      through the reference runner on the local node. Run, not published — see
      [The first rendered finding is first-party](#the-first-rendered-finding-is-first-party).
      The subject stays third-party here for a technical reason and not a
      narrative one: only an artifact Logion does not control exercises the
      shapes that break a runner in the field — an odd `SKILL.md`, a version
      that will not resolve from an external hub, an absent license, no digest.
      Measuring only what Logion authored means the runner never meets an
      artifact it cannot parse until a stranger's does. `find-skills` is
      already pinned and installed by the 15.11 fixture, so this costs almost
      nothing.
- [ ] **The finding rendered on the public surface is first-party**, carries a
      closed `first_party` field rather than prose, and is a result that is
      *not* flattering to Logion. See
      [The first rendered finding is first-party](#the-first-rendered-finding-is-first-party).
- [ ] Cycle 0 invariants green: additive `/v1`, contract-audit authoritative,
      supported CLI/API pairs proven. See
      [`cycle-0-contract-e2e-hardening.md`](cycle-0-contract-e2e-hardening.md)
      and [`cli-api-compatibility-matrix.md`](cli-api-compatibility-matrix.md).
- [ ] Landing truth pass done; report page live; version chart renders.
- [ ] **The public answer surface answers without an account or an install**,
      renders at least one real finding on first load, never returns an empty
      screen for an indexed subject, and content-negotiates the same URL for a
      browser and for an agent. See
      [`public-answer-surface.md`](public-answer-surface.md).
- [ ] **Every rendered finding carries its own scope boundary on the same
      screen** — contract digest, harness/model pair, **the task class it
      measured**, and an explicit "not a safety review, not a certification, not
      advice to install, and not a claim about sustained use". A measurement
      published without it reads as an endorsement, and the first measured
      artifact that turns out to be malicious then reads as Logion's failure.
      Task class is on this list because the same artifact under the same model
      can be strongly positive on one class of task and strongly negative on
      another — measured across benchmarks in
      [arXiv:2608.27454](https://arxiv.org/abs/2608.27454) — so a finding
      rendered without its task class is the easiest thing a publisher can
      correctly refute, at the moment the
      [playbook](../maintainer documentation: measurement-publication-playbook.md) says
      exposure is highest. At 0.2 this is a **rendering** requirement satisfied
      by the contract's own declared subject; the closed field and the queryable
      filter are deferred.
      See [`public-answer-surface.md`](public-answer-surface.md) Rule 5.
- [ ] **No public copy uses an index metaphor** ("Google of tools", "hub",
      "catalog of skills") and none claims network validation. Enforced by a
      landing content test, not by review discipline. See
      [`positioning-and-independence.md`](positioning-and-independence.md).
- [ ] The observation envelope carries the **harness version**, and a **model
      slug from a closed allowlist** where the adapter can declare it honestly.
      Adding fields after publish invalidates every installed hook, because the
      spool rejects a mismatched `integration_version` — so this is a
      before-publish item for schema reasons. It is now also a product
      requirement rather than schema hygiene, which matters because that is what
      decides whether it survives a scope cut: evolved-skill value measured
      across models spans a large gain to a large regression on the *same*
      benchmark — [arXiv:2608.27454](https://arxiv.org/abs/2608.27454) reports
      one model lifted from 24.3% to 50.5% while, on that same benchmark,
      another model was driven from 50.5% down to 18.1%. Field
      evidence that does not name the model is therefore not interpretable
      evidence, and evidence recorded at 0.2 is permanent. Contract in
      [`normative-carry-overs.md`](normative-carry-overs.md#envelope-fields--decided-2026-08-27-unbuilt);
      it has no phase owner because 15.11 closed, so it attaches to whichever
      phase next touches the envelope.
- [ ] An eval result names its **full harness stack (outermost orchestrator
      first, each layer id+version), model id+version, and iteration budget as
      closed fields**, and `logion eval compare` fails closed when any of the
      three differs between base and candidate. A pair is not enough: an outer
      orchestration loop over an unchanged harness and model lifts the same
      subject from 44% to 71% at three iterations and 72.67% at ten
      ([arXiv:2609.01481](https://arxiv.org/abs/2609.01481)), so a result that
      records only the innermost harness attributes the orchestrator's gain to
      the artifact. Owner:
      [`16.1`](phase-16.1-eval-contract-and-reference-runner.md#a-pair-is-not-always-a-pair).
- [ ] Legal items whose trigger is "before step 2 reaches an external
      publisher" and "before the first public measurement" are done. See
      [`legal-and-entity.md`](legal-and-entity.md).
- [ ] Token cost of the observation path is zero and separable — a hook is a
      subprocess, not a model call, and anything that does spend tokens stays
      outside it.
- [ ] An unconfigured harness is `off` — not `local-only`, which is what this
      line used to claim while `effective_mode` returned `off`. `DO_NOT_TRACK`
      forces `off` regardless. The user can read, export, and delete the spool.
      (proof: test:packages/cli/tests/test_usage_upload.py::test_off_never_uploads)
- [ ] Receipt consent and review consent are separate scopes. A zero-token
      machine fact and an agent writing prose about the user's repository are
      not one question, and one switch loses the easy consent to pay for the
      hard one.
      (proof: test:packages/cli/tests/test_integrations_commands.py::test_status_keeps_receipt_and_review_scopes_separate)

### Why the durability item is on this list

Everything else on this checklist is about whether the product works. That one
is about whether the thesis is true. "An attestation lives forever" and "if
Google dies its index dies with it, ours does not" are claims about durability,
and durability is the only property in this release with no check behind it: one
node, one issuer, evidence in one object store.

The mechanism is already written —
[`15.17`](phase-15.17-aktp-evidence-and-improvement-feed-v0.md) requires that a
self-export imports losslessly into a clean database and that a second import
creates zero rows. It needs no external operator, which is why it can be pulled
forward: [`16.4`](phase-16.4-deterministic-replication-and-agreement.md) is right
that a self-import proves nothing about independence, but losslessness is a
different property and a self-import is a valid way to prove it.

15.17 is step 7. As sequenced, the property that is the reason the project exists
lands *after* the release that advertises it. Either the export slice moves into
this gate, or the durability language comes off the 0.2 landing page — the
[measurement publication playbook](../maintainer documentation: measurement-publication-playbook.md)
and [`positioning-and-independence.md`](positioning-and-independence.md) already
forbid claiming more than the evidence supports, and that applies inward too.

## What 0.2 explicitly does not include

Claims and commercial listings (Loop C), independent runners, cross-node
attestation authority, bucket-brigade payouts, a dashboard product, GPU-backed
model evaluation, and any public statement that "the network validates" while
Logion is the only issuer.

Three measurement-scope items are deliberately deferred rather than absent.
Recorded here so 0.3 does not relitigate them, and so nothing pulls them forward
on the strength of "the cheapest moment to change a versioned schema is now" —
that argument is true of the observation envelope and false of all three of
these. None of them is yet written into the phase named as its owner.

- **A sequential eval archetype** — a contract whose result is a per-step
  assertion vector plus a degradation slope across a dependency-chained
  sequence, rather than one vector for one run. Owner:
  [`16.2`](phase-16.2-typed-evaluators-and-skill-reference-evaluator.md). It
  cannot land in [`16.1`](phase-16.1-eval-contract-and-reference-runner.md),
  because a sequential run has compounding variance: "reproduce" would have to
  become "reproduce the slope within an interval", which either weakens 16.1's
  determinism guarantee or gets cut on the way in. 0.2 discloses the boundary
  rather than measuring across it. Note that this is the shape required to
  measure a token-reduction claim honestly — the crossover between accumulated
  per-turn input overhead and accumulated output saving is a sequence property,
  not a single-shot one — so it is owed to the first public measurement even
  though it is not owed to this release.
- **Task class as a closed field on the eval contract, and as a filter on
  evidence search.** Owners: `16.2` for the field,
  [`16.7`](phase-16.7-evidence-search-and-issuer-aware-ranking.md) for the
  filter — it is absent from that phase's typed filter list today, so as
  specified evidence search cannot answer "does this work for *my* kind of
  work". 0.2 needs the label on the screen, not the index, and 0.2 authors a
  handful of contracts under one operator, so mapping them to task classes later
  is cheap. The field is already first-class on the *field* side —
  `resource_usage_receipts.task_class`, and `resource_feedback` is unique on
  `(reporter_subject_key, resource_version_id, task_class)`, so one reporter
  deliberately holds different judgements of one version across task classes.
  The asymmetry is that the eval side carries no equivalent, which is also what
  [`16.9`](phase-16.9-benchmark-field-reconciliation.md) needs in order to
  compare a benchmark against a matching field population rather than a mixed
  one.
- **Source-model provenance on a resource version** — which model produced or
  optimised a skill. It predicts outcomes and is not monotonic in the source
  model's capability — skills evolved by another model can outperform
  self-evolved skills, and a stronger source model does not necessarily produce
  better skills ([arXiv:2608.27454](https://arxiv.org/abs/2608.27454)). It stays out of 0.2
  because it is server-side and additive, so it carries none of the envelope's
  before-publish urgency, and because almost nothing in the catalogue can
  declare it honestly today. When it lands it is an optional closed-enum field
  on `ResourceVersion`, never a required one, and never prose.
