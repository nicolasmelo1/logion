<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Positioning, protocols, and independence

Why Logion is not a marketplace, why it is not Apify, where ARD / AI Catalog /
AKTP sit, and what independence actually means before the network exists.

Split out of `next-steps.md` on 2026-08-17. Read before writing public copy,
before positioning arguments, and before any decision that moves commerce
earlier in the sequence.

Exit condition: the language-discipline rules below are wired into public-copy
review (no "the network validates" before issuer #2, no pulled-forward
commerce), and the issuer-#2 milestone entry records its first real entry when
one exists.

## Naming: stop calling it a marketplace

"Marketplace" forces a two-sided cold start with no N=1 solution, and that
framing is what produced abundant supply with no demand.

On the critical path the product is:

```text
local skill-hygiene tool  →  measurement service  →  publisher observability
```

Each stage works alone, in order, with one person. The shipped commerce rails
(credits, entitlements, Stripe Connect, bounties, ledger) remain built and
remain the *later* monetisation of a trust layer. They are not the wedge.

The monetisation sentence:

> **We don't earn when you buy it. We earn when it gets fixed.**

Bounty revenue is remediation revenue, not sales commission. The incentive is
aligned with the measurement being honest, which is the opposite of a store
rating its own inventory.

## The end-user wedge

Publisher-side value — evidence about your own artifact across installations you
do not control — is settled. The unsolved side is why an individual installs
Logion at all, and without that side the publisher pitch has no cohort behind it.

The answer is not "join a marketplace". It is that local mode is selfishly
useful with zero network participation:

- *Which of my installed skills did I actually use? Which never fire and only
  cost context? Which are duplicates or stale?* This is the pain in
  `anthropics/claude-code#35319` — 183 skills in one org, up from 67 in four
  weeks, no visibility, context budget unjustifiable — filed and closed with no
  maintainer response.
- `local-only` consent is not a privacy concession. **It is the default
  product.** Nothing leaves the machine; `logion usage pending` shows exactly
  what exists locally.

This is the Snyk/Dependabot pattern: the user installs for their own benefit and
ecosystem data is the by-product. Nobody installs Dependabot to help GitHub map
vulnerabilities.

Network participation is a **separate, later step** whose incentive is
comparison: your own numbers mean nothing without a cohort. Same trade offered
to the publisher.

Two objections, each answerable in one sentence:

- *"It will eat my tokens."* The observation path is a subprocess hook, not a
  model call — zero tokens. Anything that does cost tokens stays separable.
- *"It will send my company's data."* Default `local-only`; the spool rejects
  prompts, paths, arguments and content **by schema, not by policy**; the user
  can read, export and delete it; `DO_NOT_TRACK` forces `off`.

**Distribution consequence:** the publisher is the channel for end-user installs,
not the reverse. A publisher who wants cohort data asks their own community to
install the companion. Logion supplies the instrument; the publisher supplies
the audience.

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
