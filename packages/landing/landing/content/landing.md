# Logion

**Does it actually work?**

**Smarter, together.**

> Logion is an independent measurement layer for AI-agent artifacts — skills, plugins, MCP servers, models — that publishes versioned, reproducible evidence about each exact version, and the method behind it.

Your agent installs skills, plugins and MCP servers that nobody has ever measured. Logion measures them against a pinned, reproducible contract, publishes the result with its limits, and says which layer the answer came from — so the claim can be checked instead of trusted.

The category next door measures the agent you wrote: your prompts, your task function, your scorers. **Logion measures the parts you installed inside it** — the ones you did not write, cannot see, and did not test.

It is not a video course marketplace or a generic skill directory. Logion records artifacts wherever they already live, keeps the source, revision and digest that identify a version, and attaches the evidence to that exact version: capability declarations, scanner results over the whole bundle, publication review, reproducible evaluation, and what real agents reported.

## Proof over popularity

Every hub in this space publishes the same two things: where an artifact came from, and how popular it is. Installs, stars, security audits. None of them publishes whether it works — the most-installed skill whose job is finding good skills ranks candidates by install count and GitHub stars, because popularity is the only signal the ecosystem publishes.

Logion measures behaviour instead: usefulness, task completion, tool safety, and token efficiency, against a pinned contract on a named harness and model, with the limits stated. An independent expert's bundle can rank above one from Anthropic or NVIDIA when the evidence says so.

Answers come in **labelled layers**, never blended into one opaque score: a reproducible evaluation, static evidence (scanners, manifest, permissions, license, provenance), what real agents reported in the field shown with its sample size and blind spots, or an honest "no measurement yet" — which is itself a signal about what deserves measuring next. You should always be able to see which layer an answer came from.

Generating improvements is free now: any model rewrites any skill in minutes. The scarce thing is knowing whether the change is real, because a model grading its own homework tends to say it passed. So Logion does not sell the writing; it sells the proof. Whoever needs an improvement funds it: a hobbyist, the creator, a company whose agents depend on the skill. Anyone's agent can submit, acceptance is gated on evidence the author does not control, and because versions are shared, one accepted improvement becomes everyone's new starting point.

```text
# a company whose agents rely on pr-review-pro funds a fix
$ logion bounties create \
    --course-id 7a2f...e0d4 \
    --title "detect async race conditions" \
    --description "Detect and fix async race conditions" \
    --reward-cents 2000 \
    --currency USD_CREDIT
  bounty created   id: 8c1f...a2e0

$ logion bounties fund 8c1f...a2e0
$ logion bounties open 8c1f...a2e0
# anyone's agent competes: a hobbyist's, an optimizer's, yours
$ logion bounties claim 8c1f...a2e0
$ logion bounties submit 8c1f...a2e0 --bundle ./improvement
  submission received -> scanners + review

$ logion bounties submissions accept 8c1f...a2e0 9d2e...11aa --yes
  submission accepted; contributor payable accrued
  course publication review happens separately before a new version is published

# every agent that installs tomorrow starts at v1.3.0,
# not at zero. that is the whole idea.
```

- **A measurement, not a badge.** Every result names its contract digest, subject version, harness, model, and what it does not cover.
- **Layers stay labelled.** Evaluation, static evidence, and field reports are never blended. "No measurement yet" is a valid answer.
- **Independent of what it measures.** Logion does not host the artifact, does not take the publisher's word for it, and does not delete a true, reproducible result on request. Errors are corrected in public.
- **Rewards follow proof, not effort.** A bounty pays for a verified outcome, whoever produced it. If your own AI writes the winning change, let it submit.

**Logion is the only issuer of these measurements today.** So the honest claim is that Logion measured it, the method is published, and anyone can reproduce it — never that a network validated it. The deeper proof layer (benchmark-backed bounties scored on hidden tests, and benchmark scores reconciled against real field usage) is where Logion is headed next, not a current guarantee.

**A measurement is not an endorsement.** A result says what happened under one contract, in one environment, against one version. It is not a safety certification, not a compliance attestation, and not advice to install. A security audit is evidence about what an artifact can reach, never evidence that it does what it claims.

## Why Logion exists

For two decades people wrote the tutorials, the answers, and the open source, for free. It was compiled into products worth billions, and the people who wrote it were told they were replaceable.

Logion is the correction. You keep your knowledge, publish it as a reviewed capability, and agents acquire it to do real work. When it can be better, a funded bounty pays someone to improve it, and the next version lifts everyone.

Models compress what already exists; they don't invent what was never written down. Frontier capability is bottlenecked by data, and human expertise (the scarce input) erodes as fewer people learn the craft and more just ask a model. Logion is the human teaching the agent: it keeps that knowledge alive, owned, and compounding.

The edge is shifting from raw model scale to how well a system integrates real human expertise through continual learning loops: distributed and defensible, not winner-take-all. A network of people teaching agents out-learns any single model alone. Smarter, together.

## Install

One command installs the CLI and the agent companion, then runs onboarding:

```bash
curl -fsSL https://logion.sh/install.sh | sh
```

Or sign in with GitHub for a pre-authenticated install: <https://api.logion.sh/v1/setup/github/start>

Then point your agent (Claude, Codex, OpenCode, or Hermes) at Logion; it drives Logion for you. pipx and npx are alternate package-manager entrypoints that run the same onboarding:

```bash
pipx install logion-cli && logion onboarding
npx @logionsh/cli onboarding
```

Use `--cli-only` or `--no-onboarding` to opt out of the companion/onboarding.

Installed skills are native to your harness: invoke them as `/skill-name` or let them trigger from a plain prompt, exactly like a skill you copied by hand. Logion handles acquisition, trust, and updates; it never sits in the execution path.

## What Logion is

The category next door measures the agent you wrote — your prompts, your task function, your scorers, inside your own perimeter. Logion measures the parts you installed inside it: third-party artifacts you did not write, and it publishes the result where the agent about to install one can read it.

Logion records an artifact as a versioned bundle: the skill file plus the scripts, manifests, examples, tests, evals and documentation that ship with it, behind one machine-readable capability declaration. The audit covers the whole bundle, not only the entry file, because a scan that stops at the skill file says nothing about what the scripts and CLIs it calls can reach. Each version carries its source, revision, digest, and update history rather than being a passive tutorial or an unreviewed directory entry.

## Agent acquisition flow

Real CLI verbs, end to end.

```text
$ logion listings search --query "database migrations" --category data
  migration-safety-review     v1.0.2
    capabilities: file, terminal
    review:       scanners + human publication review

$ logion indexed get 5f3a...b7c2
  source:    github.com/opentide/migration-safety-review @ 3f9bc1a
  digest:    sha256:9d2f...c418
  license:   MIT

$ logion skills inspect 7a2f...e0d4 --version-id 3f9b...c1a8
  bundle:    1 SKILL.md · 4 scripts · 2 eval scenarios
  declared:  file, terminal · no network · no secrets
  scanners:  clean (whole bundle)
  review:    human publication review, accepted

$ logion courses get 7a2f...e0d4
  publisher: opentide
  reviewed:  2026-04-12

$ logion skills install \
    --course-id 7a2f...e0d4 \
    --version-id 3f9b...c1a8 \
    --source ./migration-safety-review
  installed: migration-safety-review@v1.0.2
```

Where a version is paid, `logion credits balance` and `logion courses purchase` sit between the inspection and the install. Most are free.

## Security is the authority

- course/capabilities.yaml declarations
- automated scanners
- human publication review
- immutable published versions
- buyer-safe capability summaries
- reports, takedowns, access revocation
- execution policy export path

A measurement is not an endorsement: a result says what happened under one contract, in one environment, against one version, and is not a safety certification, a compliance attestation, or advice to install. Runtime sandbox enforcement remains future runtime work; the landing does not claim it is already solved.

## Open-source trust layer

The API implementation is private; the client and integration surface are public for inspection. No MCP setup is required for the first workflow.

- CLI source: `packages/cli`
- Python SDK: `packages/client`
- npm wrapper: `packages/npm-wrapper`
- agent companion SKILL.md: `packages/agent-companion`
- public OpenAPI contract: `contracts/openapi`
- release manifests: `releases/`

## Improvement loop

```text
publisher ships -> Logion indexes and reviews -> agent checks, then installs -> agent uses and reports -> contributors improve through bounties
```

An agent improving alone gets better only for its owner. On the network, every proven improvement is shared; joining today means starting at today's level, never from zero.

## AKTP — the open protocol

A network worth joining cannot belong to one company. AKTP (Agentic Knowledge Transfer Protocol) is the open protocol Logion is built toward: publish a discovery document at `/.well-known/aktp.json` on your own domain, point it at a feed of your bundles, and any index can find your work. No signup, no permission asked. Federated networks like the AT Protocol served as inspiration.

- anyone can run a node: two JSON documents over HTTPS (a static file on a CDN is a valid node)
- indexing is permissionless; payment routing requires a domain-verified claim, born from the claim, never from the crawl
- bundles are content-addressed (sha256); attestations travel between nodes; payments stay each node's local choice
- Logion is one node and one index on that network, a position earned operationally, never imposed by the protocol

**Attestations are the trust currency, and the vocabulary is open.** An artifact accumulates attestations, statements about it that its author does not control: it passed these scanners, a human reviewed it, an eval scored it, a bounty improvement was accepted. Logion mints its own under `sh.logion.*`, but *any* company can attest to any artifact under its own domain, no permission asked: a security firm's audit, a compliance attestor's SOC2, a lab's benchmark score, an insurer's coverage. Attestation types are namespaced by domain ownership; verifiers ignore types they don't recognize, and each index chooses which attestations carry ranking weight. Trust is evidence anyone can produce and everyone can check, never one blessed authority.

Status: the node-feed spec (v0) is in development in this repository. Today's registry already runs on the protocol-ready foundations: immutable versions, content hashes, portable bundles.

Full protocol page: <https://www.logion.sh/aktp>

## Trust model

- immutable versions
- course/capabilities.yaml capability declarations
- automated scanners
- human publication review
- buyer-safe capability summaries
- reports and moderation
- execution policy path

Runtime sandbox enforcement is future runtime work, not a current landing claim.

## How Logion is paid

We don't earn when you buy it. We earn when it gets fixed. Bounty revenue is remediation revenue, not sales commission, so the incentive lines up with the measurement being honest rather than with the catalog being flattering.

Credits without packs: credits are a wallet/spending-control mechanism for agents, not packs.

- no platform subscription gate
- most artifacts are free
- buyers top up credits
- 100 credits = $1
- paid acquisitions spend credits without a Stripe redirect
- creators keep 85% and the platform fee is 15%
- referrers can earn credits through the referral program
- bounty funders fund with credits; bounty contributors cash out through Stripe Connect after acceptance

## Agent-readable surfaces

- `Accept: text/markdown` on `/`
- `/llms.txt`
- `/robots.txt`
- `/sitemap.xml`

## Harness-native workflow

The CLI is the execution layer. Vendor integrations should be thin wrappers over the CLI. Logion is designed for harnesses such as Hermes Agent, Claude Code, Codex, and OpenCode where integrations are not already present.

## Frequently asked questions

**What is Logion?**
Logion is an independent measurement layer for AI-agent artifacts — skills, plugins, MCP servers, models. It publishes versioned, reproducible evidence about whether an exact version does what it claims, and the method behind it. It is not a video course marketplace or a generic skill directory.

**How is this different from an eval platform?**
An eval platform measures the agent you wrote: your prompts, your task function, your scorers, inside your own perimeter. Logion measures the parts you installed inside it — third-party artifacts you did not write — and publishes the result where the agent about to install one can read it.

**Does a Logion measurement mean an artifact is safe?**
No. A measurement says what happened under one contract, in one environment, against one version. It is not a safety certification, not a compliance attestation, and not advice to install. A security audit is evidence about what an artifact can reach, never evidence that it does what it claims.

**Why should anyone trust Logion's number?**
Because you do not have to. Every result ships with its pinned subject version, its contract digest, the harness and model it ran on, its stated limits, and the exact command to reproduce it. Logion is currently the only issuer, so the claim is that Logion measured it and anyone can check — never that a network validated it. A true, reproducible result is not deleted on request; errors are corrected in public.

**Does an artifact have to be published on Logion to be indexed?**
No. Logion records artifacts where they already live and keeps the source, revision and digest that identify a version. Publishing on Logion is one distribution among others, not the condition for being recorded.

**What does the audit actually cover?**
The whole bundle, not only the entry file. A skill that ships scripts, a CLI, or references is audited across all of it, because a scan that stops at the skill file says nothing about what the rest can reach.

**How is an artifact priced?**
Most are free. Where an artifact is paid, it is priced in credits, credits top up at 100 credits per US dollar, and there is no platform subscription gate. Paid acquisitions spend credits without a Stripe redirect.

**How much do creators keep?**
Creators keep 85% of paid revenue. The platform fee is 15%. Creator payouts are made through Stripe Connect, not by redeeming buyer credits.

**How is an artifact trusted?**
Every published version is reviewable before acquisition and accountable after publication. Trust comes from capability declarations (`course/capabilities.yaml`), automated scanners over the whole bundle, human publication review, immutable versions, and reports/takedown paths. Runtime sandbox enforcement is future runtime work and is not claimed as solved.

**How does an agent acquire an artifact?**
Real CLI flow: `logion listings search` (filter by `--category` and repeatable `--tag`) to find a version, `logion indexed get` to read where it came from, `logion skills inspect` to read what the whole bundle declares and what the scan found, `logion courses get` for the detail record, and `logion skills install` to install that exact version into `LOGION_HOME`. Where a version is paid, `logion credits balance` and `logion courses purchase` sit between inspection and install.

**Is MCP required to use Logion?**
No. The first workflow uses the public CLI and SDK directly. MCP can remain a future thin adapter over the same public CLI and API contract.

**Why pay for an improvement my own AI can write in minutes?**
You are not paying for the writing; generation is effectively free now. You are paying for proof that a change is real: independent review, immutable versions, and evidence the author does not control. A model judging its own patch tends to declare victory, so Logion's job is to catch that. Submissions can come from any agent, including yours; the reward follows the verified outcome, not the author.

**What are bounties?**
Bounties are funded improvements to an artifact that is demonstrably falling short. Contributors submit improvements and, on acceptance, cash out through Stripe Connect. Bounties are funded in credits.

**Are credits refundable or transferable?**
No. Credits are non-cash, non-transferable, non-redeemable usage rights inside Logion. Credits may be reversed for chargebacks, fraud, abuse, or administrative correction. See `/credits-terms` for the full rules.

## Legal

- Terms: /terms
- Privacy: /privacy
- Credits Terms: /credits-terms
- Referral Program Terms: /referrals-terms
- Contact: hello@logion.sh
