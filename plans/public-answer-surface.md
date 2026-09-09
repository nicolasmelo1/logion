<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# The public answer surface

> **Why this file exists:** as of 2026-08-27 no plan describes a way to get an
> answer out of Logion without installing the CLI. The only public web surfaces
> planned anywhere are the landing and one evidence report page
> ([`17.6`](phase-17.6-public-narrative-and-landing-truth-pass.md),
> [`release-0.2.md`](release-0.2.md)). Loop B's answer is already designed to
> need nobody — this is the surface that exposes it.
> **Honesty boundary:** this surface answers with evidence that already exists.
> It never issues a new verdict about a third party on demand.

## The split it enforces

The axis is not *site versus CLI*. It is **consuming the answer versus producing
the evidence**.

| | Consuming the answer | Producing field evidence |
| --- | --- | --- |
| Surface | public URL, no account | the CLI |
| Install required | none | yes |
| Question it answers | "does this artifact work?" | "which of *my* installed artifacts do I actually use?" |
| Analogue | Google | Analytics / Dependabot |

`release-0.2.md` already decided that Loop B's launch answer is **controlled
evaluation, which "needs nobody" and works at N=1**. That means the answer never
depended on the asker having installed anything. The product is ready to be
zero-install; only the surface is missing.

The two surfaces do not compete. The public box is acquisition; the CLI is
retention.

## The category problem this fixes first

A business-side reader who follows MCP/eval/RAG discourse read `logion.sh` on
2026-08-26 and reported understanding roughly 30% of it, seeing neither the
problem nor the mechanism. The diagnostic detail is which product he reached for
to fill the empty category: **Braintrust** — eval and observability for a team
shipping *its own* LLM app (its unit is your dataset, your task function, your
scorers).

Once a reader assigns that category, nothing else on the page can land. A
Braintrust-shaped reader needs no index, no cross-hub reconciliation, no issuer,
no attestation. He read 30% because the other 70% answers questions his assumed
category does not ask.

An empty category is occupied by borrowing the full one next to it — the same
move [`positioning-and-independence.md`](positioning-and-independence.md)
already prescribes for Apify vocabulary, applied to the category rather than the
metric:

> **Braintrust evaluates the agent you wrote. Logion evaluates the parts you
> installed inside it — the ones you did not write.**

The rendered output disambiguates the category better than any tagline: when the
subject on screen is a third party's artifact, nobody confuses it with
first-party observability.

## The surface

```text
                         L O G I O N

        ┌──────────────────────────────────────────────┐
        │ paste a skill, plugin, MCP server or model   │
        └──────────────────────────────────────────────┘

                        [ Does it work? ]

        ────────────────  recent findings  ────────────────
        (results render immediately below, on first load)
```

The box stays empty, as Google's does. What makes an empty box legible is that
the output shape is visible below it without asking — Google can omit that
because everyone already knows what a search result looks like, and nobody knows
what a Logion result looks like.

### Rule 1 — the scroll renders findings, not inventory

This is the difference between the product and a marketplace listing, and it is
a rendering decision, not a copy decision.

```text
INVENTORY (rebuilds the marketplace)   FINDING (renders the product)
┌──────────────┐ ┌──────────────┐      ┌────────────────────────────────┐
│ pdf-tools    │ │ web-scraper  │      │ pdf-tools  v2.1.0              │
│ ★ 4.8  12k   │ │ ★ 4.6  8k    │      │ fails 40% of extract-table     │
└──────────────┘ └──────────────┘      │ 200 runs · method published    │
                                       └────────────────────────────────┘
```

A grid of artifacts with names and counters is the landing
`../maintainer documentation: landing-page.md` is being rewritten to stop being. The object on
screen must be the verdict, not the item.

### Rule 2 — the box never returns an empty screen

An honest system will answer "nobody has measured this yet" for most of the
index at launch. If a visitor's first three attempts return nothing, the box
teaches that the answer is nothing, and it becomes a liability.

So the layered answer `release-0.2.md` already defines becomes the box's
response ladder, and the **free layer has to cover the tail**: cross-hub
presence and version coverage, install counts from the hubs that publish them,
scanner results, permissions, license, provenance, freshness, and edges between
artifacts. That layer costs zero inference and spans the whole index, which is
what makes the box survivable before the evaluated head is large.

`"no measurement yet"` is a valid terminal answer, but it always carries a
request-a-measurement action, and those requests are the demand queue that
selects what to evaluate next.

### Rule 2.1 — write for the person who already gave up

The response ladder decides *what* is shown. This decides *who it is written
for*, and it is the correction recorded in
[`positioning-and-independence.md`](positioning-and-independence.md#the-buyer-is-the-person-who-already-gave-up).

The reachable reader is not an enthusiast comparing 300 candidates. It is an
engineer who tried a pile of skills, concluded none of them worked, and stopped
— *"of about a hundred skills I tested, not one was actually useful"* (field
thread, 2026-08-31). Their question is **"is it worth trying again?"**, not
"which is best?".

Consequences for this surface:

- A ranked list answers the enthusiast's question and bounces this reader. A
  single rendered verdict answers theirs. This is why Rule 1 is a rendering
  decision and not a taste preference.
- A negative finding is not a downer, it is the credential. It is the proof that
  the page will tell them the truth next time, which is the only thing that
  restores a burned reader.
- Do not open with ecosystem enthusiasm. This reader has already priced in that
  most of it does not work; agreeing with them is the fastest way to be
  believed.

### Rule 3 — the CTA after a result is a different question, never a paywall

"Install the CLI to see more" puts a paywall on the answer and destroys the
property the box just bought. The install prompt offers something the web cannot
answer:

> You looked up one skill. Which of the ones you already have installed do you
> never actually use?

That is the pain in `anthropics/claude-code#35319` and the local-mode wedge
already stated in `positioning-and-independence.md`. The public answer stays
free permanently.

### Rule 4 — one URL, two readers

Every indexed subject gets a stable URL that content-negotiates: HTML for a
browser, JSON/Markdown for an agent. `packages/landing/` already does this for
`landing.md`, `llms.txt`, `llms-full.txt` and `/design.txt`; the result page
inherits the same mechanism, plus an MCP endpoint.

This is the distribution answer to "no harness will bundle Logion." No harness
bundled Google either — it was a URL you could paste. An agent that can check an
artifact *before* installing it is the actual buyer, and it reaches this surface
with nobody installing anything.

## What this collapses

The landing rewrite ([`17.6`](phase-17.6-public-narrative-and-landing-truth-pass.md))
and the "one evidence report page" required by `release-0.2.md` are the **same
deliverable**, and the order inverts: the report page is built first and the
landing is it. This reduces 0.2 scope rather than adding to it.

Do not build a dashboard or a charting framework. One rendered result, done
well, plus the version-over-version chart already required.

### Rule 5 — every finding renders its own scope boundary

Not in a footer, not in a terms page: **next to the result, on the same screen.**

```text
┌────────────────────────────────────────────────────────────┐
│ pdf-tools  v2.1.0                                          │
│ fails 40% of extract-table · 200 runs · method published   │
│                                                            │
│ measured under contract <digest>, harness X vY, model Z vW │
│ not a safety review · not a certification · not advice     │
│ to install                                                 │
└────────────────────────────────────────────────────────────┘
```

Two reasons, and the second is the one that has no owner anywhere else in the
plans:

1. The layered answer is worthless if the reader cannot tell which layer they
   are looking at, and a limit rendered elsewhere is a limit nobody reads.
2. **Publishing a number about an artifact is read as blessing the artifact.**
   The moment something Logion measured turns out to be malicious — and at
   ecosystem scale that is when, not if — the default public reading is
   *"Logion approved it"*. The only defence that works is the one that was
   already on the page before the incident, in the same visual weight as the
   verdict. `measurement-publication-playbook.md` already says a measurement is
   *"not a ranking, not a leaderboard, not a safety certification, not a
   compliance attestation, and not a recommendation to buy"* — that sentence is
   currently internal-facing only, and this rule is what makes it public.

Scanner results may appear as static evidence with their own issuer named. They
never graduate into a safety verdict, because a security audit is not evidence
of function and Logion does not run the artifact on the reader's machine.

## What this surface must not do

- **It never issues a new verdict on demand.** An arbitrary paste returns
  existing evidence; it does not trigger an evaluation whose result is published
  about a named third party without the author contact step in
  [`../maintainer documentation: measurement-publication-playbook.md`](../maintainer documentation: measurement-publication-playbook.md).
  The findings in the scroll are deliberately published measurements that
  already cleared that process.
- It never blends layers into one opaque score, and never renders a badge.
- It never claims network validation while Logion is the only issuer.
- **It never implies a measured artifact is safe, endorsed, or recommended.**
  See Rule 5.

## Preconditions

**Exit condition:** one public URL answers "does this artifact work?" with no
account and no install, renders at least one real retained finding on first
load, and content-negotiates a machine-readable answer for an agent. When
that URL is live and the retained finding it renders is one produced by a
real sealed run, this plan is finished — not at the merge of any PR.

| Needs | From |
| --- | --- |
| Free layer covering the tail | step 2, cross-hub install reconciliation |
| At least one rendered finding | step 5 (`16.1`/`16.2`) — one measured artifact |
| Subject types beyond skills | `model` already exists; `eval_contract` added by [`16.1`](phase-16.1-eval-contract-and-reference-runner.md) |

Models and eval contracts matter here for a specific reason: they carry rich
public metadata on day one and skills do not, so adding them is the fastest path
to Rule 2 holding.
