<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Positioning, protocols, and independence

Why Logion is not a marketplace, why it is not Apify, where ARD / AI Catalog /
AKTP sit, and what independence actually means before the network exists.

Split out of `next-steps.md` on 2026-08-17. Read before writing public copy,
before positioning arguments, and before any decision that moves commerce
earlier in the sequence.

Exit condition: the language-discipline rules below are wired into public-copy
review (no "the network validates" before issuer #2, no "Google of tools", no
pulled-forward commerce), and the issuer-#2 milestone entry records its first
real entry when one exists.

## Naming: stop calling it a marketplace

"Marketplace" forces a two-sided cold start with no N=1 solution, and that
framing is what produced abundant supply with no demand.

On the critical path the product is:

```text
published measurement  →  the CLI that produces field evidence  →  publisher observability
   (acquisition)              (retention)                            (monetisation)
```

Each stage works alone, in order, with one person, and the first one works with
**zero** — a controlled evaluation needs nobody's permission and runs at N=1.
The shipped commerce rails (credits, entitlements, Stripe Connect, bounties,
ledger) remain built and remain the *later* monetisation of a trust layer. They
are not the wedge.

> Local skill hygiene used to sit in the first box. It is retention, not
> acquisition — see [The wedge](#the-wedge).

The monetisation sentence:

> **We don't earn when you buy it. We earn when it gets fixed.**

Bounty revenue is remediation revenue, not sales commission. The incentive is
aligned with the measurement being honest, which is the opposite of a store
rating its own inventory.

## The wedge

> **Corrected 2026-09-01.** This section used to say the wedge was local mode —
> *"which of my installed skills did I actually use?"* — and called it "the
> end-user wedge". [`public-answer-surface.md`](public-answer-surface.md), written
> ten days later, already contradicted it: **"the public box is acquisition; the
> CLI is retention."** The newer file was right and this one was binding on public
> copy, so the stale version was shaping the pitch. What follows replaces it.

### Acquisition is a rendered finding, not an install

The wedge is **one published measurement of a popular artifact, readable with no
account and no install.** Everything else — the CLI, local mode, consent, the
cohort — is what happens after someone already believes the number.

```text
acquisition   a rendered finding on a public URL      (no install, no account)
retention     "which of mine do I actually use?"      (the CLI)
monetisation  cohort evidence a publisher cannot get  (the publisher)
```

The order matters because the middle rung cannot carry the first. That was the
error being corrected.

### The individual local-mode pain is real, and its carrier is an org

The pain is not imaginary: `anthropics/claude-code#35319` — 183 skills in one
org, up from 67 in four weeks, no visibility, context budget unjustifiable —
filed and closed with no maintainer response. The mistake was assigning it to an
*individual* as a reason to install.

Field check, 2026-08-31, an informal thread of six working senior engineers
(n=6, self-selected, not a study — recorded because it is the only direct
evidence available and it points one way):

- three report using **zero** skills, one of them after trying roughly a hundred;
- one uses only skills he wrote himself and does not revisit them;
- none reported an inventory-hygiene problem;
- none could state what Logion does after reading the landing page.

An individual with four skills does not have a hygiene problem. **The 183-skill
inventory belongs to an organisation**, and an org is reached through a person
who already trusts the measurement. So local mode is retention and expansion
inside an account, not the thing that opens one.

`local-only` consent is still not a privacy concession — it is the default
product, nothing leaves the machine, and `logion usage pending` shows exactly
what exists locally. That property sells the CLI to someone already convinced.
It does not convince anyone.

### The buyer is the person who already gave up

The same thread produced the strongest demand signal in the file, from its most
hostile participant: *"of about a hundred skills I tested, not one was actually
useful."* That is the workspace's unverified *~67% of skills fail in practice*
restated harder, first-hand, by someone with no stake in it.

It reframes the question the product answers. The copy currently addresses an
enthusiast choosing among 300 candidates. The reachable audience is the engineer
who **already stopped**, and their question is not *"which one is best?"* but
*"is it worth trying again?"* Those are different first screens: a ranking
answers the first, a finding answers the second.

Corollary for [Step 0 selection](../maintainer documentation: measurement-publication-playbook.md):
a subject that provokes public *disagreement* outranks one that is merely
popular. Observed on `caveman` in the same thread — *"it is not consensus that
caveman is good; a lot of people dislike its output"* — which fires trigger 1
(a falsifiable published number), trigger 2 (demand) and trigger 3 (reach) at
once. That is why it stays the preferred first subject in
[`next-steps.md`](next-steps.md#the-shape-of-step-6).

### Reproduction is the substitute for reputation

The objection that has no answer in this file yet, stated plainly in the same
thread: *"if you were somebody, people would believe the number."* It is
correct, and independence does not answer it — independence is about conflict of
interest, notoriety is about whether anyone reads you at all.

The only asset an unknown issuer has is that its result can be **re-run by
someone else**. That converts reputation from something Logion must accumulate
into something a stranger can verify in one command. But it is only real when
somebody actually does it, so it has to be an exit condition rather than an
affordance:

> **One external reproduction of the first public measurement is worth more than
> any install count**, and it is the cheapest partial down-payment on
> [issuer #2](#issuer-2--the-milestone-that-makes-the-thesis-true) available
> before federation exists.

Tracked as part of [step 6](next-steps.md#execution-order).

### The two standing objections

- *"It will eat my tokens."* The observation path is a subprocess hook, not a
  model call — zero tokens. Anything that does cost tokens stays separable.
- *"It will send my company's data."* Default `local-only`; the spool rejects
  prompts, paths, arguments and content **by schema, not by policy**; the user
  can read, export and delete it; `DO_NOT_TRACK` forces `off`.

### Distribution consequence

The publisher is the channel for end-user installs, not the reverse. A publisher
who wants cohort data asks their own community to install the companion. Logion
supplies the instrument; the publisher supplies the audience. This is still the
Snyk/Dependabot shape — the user installs for their own benefit and ecosystem
data is the by-product — but the *first contact* is the report, not the tool.

### Naming discipline that follows from all of this

"Google of tools" tested badly and must not be used. In the 2026-08-31 thread it
produced, in order: *"isn't that just a README"*, *"a hub of skills?"*, *"a
marketplace of markdown"*, and *"HuggingFace for skills"* — every one of them the
marketplace category this document exists to leave. Google is an *index*, and an
index is the commodity half of the product.

Lead with the verb instead: **nobody proves that a skill works; Logion does.**
In the same thread that sentence is what moved the hardest sceptic from "what is
the appeal" to "what is the methodology", which is the question the product is
built to answer.

## Why Logion is not Apify

Apify is the closest structural analogue: ~42,700 Actors from ~2,148 publishers,
80% revenue share, pay-per-event, an MCP server and agent-facing surfaces, and a
full trust layer — star ratings, review counts, run counts, **success rate**, and
an Actor quality score of 0–100 that feeds store ranking.

The difference that explains everything: **Apify runs the code.** Observability
is a by-product of owning the runtime. No consent, no harness adapters, no
installation identity, no protocol needed.

Owning execution solves four problems at once — observability, quality,
metered monetisation, and trust. Logion refuses the runtime by design and
therefore has to solve all four by hand. That is the price of the position and
it should be known rather than discovered.

But the refusal buys the thing Apify can never have: **nobody who owns a runtime
can measure across runtimes.** Apify knows nothing about a skill running in
Claude Code.

The hybrid Logion actually runs is stronger than either pure position:

| | Runtime owner | Consent needed | Coverage |
| --- | --- | --- | --- |
| Controlled evaluation (16.1/16.2) | **Logion** (own sandbox) | none | anything catalogued |
| Field observation (15.11/15.11.1) | the user | yes | what consents |

Apify only has the first half, and only inside its own store.

### The validation Apify hands over for free

Even with ratings, reviews, success rates, a quality score and automated QA,
third-party auditors sprang up *inside* Apify — `audit-tools.ai` ("Evaluate Any
Apify Actor Before You Spend"), an `Actor Reliability Monitor`, and
`apifystats.com` measuring the store daily. Same pattern as `skill-history.com`
over skills.sh, and as skills.sh **purchasing** three independent audits
(Gen Agent Trust Hub, Socket, Snyk) rather than issuing its own score.

Nobody fully trusts the number published by the owner of the store about the
products in that store. That is the market Logion is in.

### Is Apify a competitor?

Not today, for economic rather than technical reasons: Apify's revenue is margin
on compute, and measuring artifacts that run elsewhere produces no billable run.
Every incentive points inward.

It becomes a competitor if they decide "tool store for AI" is worth more than
"scraping platform" and start cataloguing artifacts that do not run on them —
arriving with 42k artifacts, 2k publishers and mature payment rails.

Two practical consequences:

1. **Borrow their vocabulary.** *Success rate* and *quality score* are terms the
   market already understands in an exactly analogous context. Do not invent new
   nomenclature for published measurements.
2. **Pay-per-event is the direction of travel.** Apify is retiring rental for
   metered usage in 2026. That supports
   `future-roadmap/smart-payments-and-metered-capabilities.md` and argues
   against binding the model to one-time course purchase.

## What the hubs actually publish, checked 2026-08-27

The differentiation argument should rest on what the pages render, not on a
characterisation of them.

| Hub | What a skill page shows | Behavioural evidence |
| --- | --- | --- |
| skills.sh | installs, GitHub stars, first-seen date, three security audits (Gen Agent Trust Hub, Socket, Snyk) | **none** — no test results, no reviews, no ratings, no version history |
| ClawHub | downloads, installs, stars, lineage, ownership, docs, package integrity, audits | none found |
| LobeHub | catalogue and discovery | none found |

Every one of them measures **provenance and popularity**. None measures
**behaviour**. That is the whole gap, and it restates the standing rule: install
counts are commodity; only use and outcome differentiate.

### The self-demonstrating case

`skills.sh/vercel-labs/skills/find-skills` — 3.1M installs, 29.7K stars — states
in its own description that the quality criteria it applies when recommending
other skills are **installs above 1K, source reputation, and GitHub star count**.

The most-installed skill whose job is finding good skills ranks by popularity,
because popularity is the only signal the ecosystem publishes. The argument for
Logion does not need to be made in prose; it is already written by the ecosystem
into its most-installed artifact.

The same page carries **Snyk `Warn` alongside two passing audits**, and nothing
reconciles them — because a security audit is not evidence of function, and the
market has nowhere to put that difference.

Note also that `find-skills` exists on both skills.sh and ClawHub under the same
name. Neither hub can tell a user what the other holds. That is step 2 of
[`next-steps.md`](next-steps.md) appearing unprompted in the first example
anyone picks.

## The garden without walls

Apify measures what it hosts. Logion measures what exists — including artifacts
in no store, unclaimed, or whose author never asked. Permissionless evaluation
is a different primitive, and the lineage is old: Moody's rates bonds it does not
issue, Nielsen measures channels it does not operate, Consumer Reports buys at
retail and refuses advertising. In software the direct analogue is Snyk/Socket:
scanning packages they do not host, paid by enterprises rather than by the
registry.

**But "different from Apify" is not "safe."** Unoccupied and safe are opposites
in a new market. What exists already:

- `effectorHQ/skill-eval` — "measure whether AI agent skills actually work",
  scoring 0.0 (broken) to 1.0 (production-ready);
- SkillCompass — measurement tool, early traction;
- Skill Reviewer — audits `SKILL.md` for quality, correctness, effectiveness.

Small, free, open-source, and already at the same address. What none of them
have: controlled evaluation with a published reproducible contract, field
observation, and — decisively — **the improvement loop**. Auditing a skill's
text is not measuring its behaviour, and neither one fixes anything.

Nothing structural stops skills.sh (≈670k skills, three audits already
integrated, and the distribution) from adding an efficacy score. The defence is
not the position. It is being first with a published method, owning the
improvement loop, and being independent of what is measured.

Reported market context worth confirming before public use: **~67% of skills
fail in practice**, and ClawHub went from 13,729 registered skills to 3,286 after
a security purge.

## Where the protocols sit

ARD explicitly excludes quality signals, evaluations, reviews, and usage
telemetry, and states that its relevance score *"MUST NOT be interpreted by
orchestrators as a cryptographic trust, compliance, or safety rating"*, leaving
quality to *"consuming systems and external evaluation mechanisms"*.

**The gap AKTP fills is one the ARD authors declared, not one Logion invented.**

```text
AI Catalog       typed catalog and entry representation
ARD              pre-invocation search/discovery over those entries
native protocol  execution/acquisition (MCP, A2A, Skills, hf, dsh)
16.1/16.2        the plant that produces the evidence
AKTP             the envelope that transports it between nodes
```

A protocol for evidence with no evidence to carry is an empty envelope. That is
why AKTP v0 comes *after* a real measurement exists, never before.

See [`../protocol-specs/README.md`](../protocol-specs/README.md) for the pinned
normative sources; upstream at the locked commit always wins over any summary
here.

### Adoption reality, probed 2026-08-17

ARD was announced by Google and Microsoft on 2026-06-17, Apache 2.0, on the AI
Catalog data model. Backers include Google, Microsoft, GoDaddy, Hugging Face,
Nvidia, Salesforce, ServiceNow, Databricks, Snowflake, GitHub, Cisco.

Everyone built the **consumer** side — GitHub Copilot Agent Finder, Google Cloud
Agent Registry, Hugging Face Discover Tool. Almost nobody serves a catalog.

Of eleven announced backers plus nine adjacent vendors probed directly, **only
`huggingface.co` serves `/.well-known/ai-catalog.json`**. The rest return
404/403 — as does `logion.sh`. And the Hugging Face catalog, the reference
implementation, contains **two entries with six fields each** (`identifier`,
`displayName`, `type`, `url`, `description`, `tags`): no version, no digest, no
evidence.

Three consequences:

- Publishing a catalog is cheap and puts Logion in a very short list. Treat it
  as credibility and conformance — **ARD will not deliver a user in 2026**. If
  any plan says "we will be discovered via ARD", strike it.
- **Logion cannot run "entirely on top of" AI Catalog as it exists.** `Resource`
  is keyed by `(resource_type, canonical_uri)` with content-digest versions; the
  catalog entry carries neither. Identity and address come from upstream;
  version, digest, evidence and improvement are Logion's.
- The strategic risk is not AKTP being copied — it is **ARD absorbing an evidence
  layer in a later version**. That outcome is *consistent* with the thesis
  (protocol over company). The defence is to own the evidence corpus, not the
  schema, which is a direct argument for AKTP v0 being minimal and late.

## Independence: methodological now, structural later

The structural defence against the conflict that produces third-party auditors
around walled gardens is real and built as invariants rather than promises:

- [`17.3`](phase-17.3-resource-claims-and-commercial-rails.md): an active claim
  "does not change Resource ID/version/source/evidence/attribution"; commercial
  terms live on the Course/listing projection and "never masquerad[e] as base AI
  Catalog, ARD relevance metadata, or AKTP evidence"; a successful claim creates
  "zero new Resource rows and zero rewritten evidence rows", asserted by
  `api.commercial_projection_does_not_change_identity`.
- [`16.5`](phase-16.5-eval-attestations-and-cross-node-authority.md): "AKTP
  carries evidence; authority is local, issuer-aware, and policy-versioned" —
  consumers compute their own verdict, so **the network is the auditor**, not an
  outside party who shows up because nobody trusts the house.
- `../maintainer documentation: community-improvements-and-funded-bounties.md`: "Acceptance of
  an improvement is not publication trust. A payout is not publication trust
  either," with paid and unpaid outcomes carried as *different attestations*.

**That defence is structural only once other issuers exist.** Until then Logion
is the only node and independence is *methodological*: published method,
reproducible results, stated limits, and not selling what it measures yet.

Language discipline, binding on public copy:

- Before issuer #2, **do not say "the network validates this."** Say what is
  true: Logion measured it, the method is published, anyone can reproduce it.
  Claiming network validation while operating the only node violates the
  standing rule that no public claim may be stronger than its evidence.
- **Do not pull claim → commercial listing forward** in the execution order.
  The invariants make the separation defensible; plural issuers make it
  unarguable. `17.3` sits late for this reason.
- Every network reward names an **external** payer. A network paying itself to
  validate itself is, by the workspace's own coalition-wealth test,
  indistinguishable from a collusion ring. Cf.
  `future-roadmap/economic-network-and-rewards.md`.
- **Never describe Logion with an index metaphor** — "Google of tools", "hub",
  "catalog of skills". Tested 2026-08-31 and it routes every listener straight
  back into the marketplace category. Lead with the verb: *nobody proves that a
  skill works; Logion does.*
- **A measurement is never an endorsement, and it must say so where it is
  rendered.** A published finding about an artifact is scoped to one contract,
  one environment, one subject version. It is not a safety certification, not a
  compliance attestation, and not a recommendation to install. That disclaimer
  currently lives only in internal docs; it belongs next to the finding, because
  the first artifact Logion measures that later turns out to be malicious will
  be read as *"Logion approved it"* unless the page already said otherwise.

## Issuer #2 — the milestone that makes the thesis true

The first attestation about a Logion-catalogued subject, issued by someone who
is not Logion, verified under a consumer's local policy.

> **An attestation format that only one entity ever issues is a proprietary log
> with extra steps.** Portability becomes real at issuer #2, not at spec v1.

The survival mechanics of an attestation differ from those of a plain file, and
the difference is easy to talk past:

- A Markdown note survives its editor because **the file is the value** — self
  contained, opens anywhere. The Obsidian property.
- An attestation's value lives entirely in **who signed it and whether anyone
  trusts that signer**. If the sole issuer disappears, the signed bytes survive
  and the trust anchor does not.

So the closer model is **Git, not Obsidian**: a repository outlives GitHub
because the object graph is self-contained *and replicated*, every clone a full
replica. `community-improvements-and-funded-bounties.md` already states the
relationship — "AKTP adds portable capability, evidence, lineage and incentive
context without replacing Git" — and the consequence is that **plural issuers
are a survival condition, not a long-term nicety**.

Track it as a first-class milestone: date, issuer identity, subject, and the
consumer policy under which it verified.

## Competitive notes

- **yukon.org** ships sandbox-verified benchmarking with leaderboards today,
  with Stanford/Berkeley/Princeton/Ethereum participating. It validates the
  *market* for verified results (16.1/16.2). It does not validate building
  federation before having nodes — Yukon solved recruitment alongside, not
  after, and led with one verifiable result (ECDSA.fail, 50.3% over the Google
  Quantum AI baseline in 8 hours) rather than an architecture.
- **trajectory.ai** runs the same instrument → signal → improve → deploy loop,
  but inside one customer's product, backed by Fei-Fei Li and Jeff Dean.
  Competing head-on loses. The defensible difference: they measure one product
  in a perimeter the customer controls; Logion measures one artifact across
  thousands of installations nobody controls. Only a third party can do that.
- **skills.sh** already ships install telemetry, weekly installs per skill,
  per-agent-platform breakdown, and all-time/24h leaderboards. **Install counts
  are commodity.** Only use and outcome differentiate.
- **Warp** is the closest thing to a direct competitor that exists, and it is
  worth reading precisely rather than dismissing. Warp Factories orchestrates
  **third-party harnesses by name** — `claude code`, `codex`, `cursor`, "any
  MCP-capable coding agent" — and advertises evals, custom scoring for spec
  adherence and defects caused, ROI metrics, an Agent Kits gallery, benchmark
  comparisons **across models and harnesses**, and a self-improvement loop where
  "agents study patterns across runs and open PRs against your factory config".
  That is Braintrust plus Apify plus an improvement loop, and it disproves the
  earlier claim that nobody ranks model-harness pairs.
  **The boundary is the subject, and their own page draws it:** those benchmarks
  measure *"your factory's agents executing your specific workflows, **not
  third-party artifact quality**"*. Four consequences follow — the subject is
  your agents rather than someone else's artifact; results stay private to the
  customer instead of being publicly addressable by an agent about to install
  something; it requires adopting Warp; and benchmarking harnesses while selling
  the orchestration platform next to an artifact gallery is the house rating
  inventory adjacent to its own store, which is the structure that produced
  `audit-tools.ai` inside Apify. Asked publicly what outcome cost telemetry
  changes, the founder's answer was to pivot to "benchmark models on your own
  code" — deeper into the first-party perimeter, not out of it.
  **Read them as the best available candidate for issuer #2**, not as a threat:
  they already produce per-run, per-model, per-harness, per-cost evidence with
  pass rates, and AKTP is the envelope an operator would emit it through.
- **Braintrust** ($80M Series B, Feb 2026) is not a competitor but is the
  category a reader defaults to, which makes it a positioning problem rather
  than a competitive one. It is eval and observability for the LLM app *you*
  wrote — your dataset, your task function, your scorers, your traces. Same
  structural boundary already stated for trajectory.ai, now with a reference the
  market recognises. Use it, do not invent vocabulary: **Braintrust evaluates
  the agent you wrote; Logion evaluates the parts you installed inside it — the
  ones you did not write.** A business-side reader who follows the space
  understood ~30% of the current landing precisely because he assigned Logion to
  the Braintrust category and then found nothing on the page answering that
  category's questions.
