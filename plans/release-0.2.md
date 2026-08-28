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
   day one, needs nobody. This is the primary answer at launch.
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
([`15.11.1`](phase-15.11.1-publisher-integrated-consented-observation.md)) —
which is the upsell, not a gap to paper over.

Remote execution never authorises TLS interception, credential access, probing,
load testing, or provider-side modification.

## Public surface required for 0.2

The agent-first documentation stance was correct when the user was an agent
being asked about Logion. It does not match the buyer any more. The person who
must be convinced is a human at a company deciding whether to trust Logion with
usage data and whether to fund a bounty. That person opens a browser, spends
thirty seconds, and leaves.

Required:

1. **Landing truth pass** — [`17.6`](phase-17.6-public-narrative-and-landing-truth-pass.md),
   pulled forward out of Phase 17. The current landing describes a marketplace
   and shipping 0.2 against it publishes a false description of the product.
2. **A human-readable explanation of the loop** — measure → evidence →
   improvement → re-measure.
3. **One evidence report page.** A permanent URL rendering one measurement
   well: the chart, the method, the eval-contract digest, the subject version,
   the limits, `n` where field data appears, and the command to reproduce.
   yukon.org's benchmark-evolution view is the reference for what "showing the
   number" looks like when evidence is the product.
4. **A version-over-version chart.** The single most valuable visual is the
   same subject measured across versions — it makes improvement visible, which
   is the entire thesis in one image.

Scope discipline: build one page that renders one report beautifully. Generalise
into a dashboard only once there are enough reports to justify it. When the
product is evidence the visualization is the deliverable — that is an argument
for making one excellent, not for building a charting framework around a single
data point.

## Gate checklist for cutting 0.2

Ordered. Everything must be true simultaneously.

- [ ] **Loop A end to end on a machine that is not the founder's**, with a
      harness hook firing **live** — not a replayed payload. The current
      `phase-15.11` gate evidence is a replay and does not satisfy this.
- [ ] The seven "Still open" items in
      [`15.11`](phase-15.11-native-use-observation-linked-feedback-and-reviews.md)
      are closed, including a **pseudonymous identity tier** — `identity_tier`
      is always `account` today, so feedback still requires an account, which
      contradicts the local-first pitch on the first screen.
- [ ] **One envelope, not two.** The live `UsageObservation` spool schema and
      the richer `cli/_observation.py` envelope cannot both stay normative.
      Adopt one, delete the other.
- [ ] `logion.sh` serves `/.well-known/ai-catalog.json` (today: 404).
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
- [ ] `16.1`/`16.2` produce a normalized result for a third-party skill through
      the reference runner on the local node.
- [ ] Cycle 0 invariants green: additive `/v1`, contract-audit authoritative,
      supported CLI/API pairs proven. See
      [`cycle-0-contract-e2e-hardening.md`](cycle-0-contract-e2e-hardening.md)
      and [`cli-api-compatibility-matrix.md`](cli-api-compatibility-matrix.md).
- [ ] Landing truth pass done; report page live; version chart renders.
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
