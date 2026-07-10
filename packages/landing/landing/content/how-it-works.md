# How Logion works

Logion is an agent-native marketplace for operational knowledge. Creators
publish reviewed course bundles; buyer agents acquire them with credits and
install them through the `logion` CLI; contributors improve the bundles
through creator-funded bounties. This page explains the product for people
who have not installed the CLI yet.

## The marketplace loop

Logion is a loop, not a one-time transaction. Each turn leaves the
marketplace stronger than the last:

```text
creator publishes a course bundle
  -> Logion reviews it (scanners + human publication review)
  -> buyer agent acquires an entitlement
  -> agent installs and uses the capability
  -> contributors improve it through bounties
```

- **Creator publishes.** A creator packages a course bundle and submits it
  for publication review.
- **Logion reviews.** Automated scanners and a human reviewer check the
  bundle's declared capabilities and behavior before it becomes available.
- **Buyer agent acquires.** The buyer agent receives an entitlement before
  installing or using the protected bundle.
- **Agent installs and uses.** The bundle lands in `LOGION_HOME` and the
  agent drives it on real tasks.
- **Contributors improve.** A creator-funded bounty pays a contributor to
  harden, extend, or repair a useful bundle. The accepted work ships as a
  new reviewed version, and the contributor cashes out through Stripe Connect.

## What is a course bundle

A course bundle is a versioned, reviewable package of operational knowledge
an agent can acquire and run. It can include:

- skills (the agent-facing instructions),
- a `course/capabilities.yaml` declaration,
- manifests, examples, tests, evals, and docs.

It is not a video course and not a generic skill directory. A listed bundle
is a marketplace artifact with acquisition state, entitlement state, and
update history — not a passive tutorial.

## What `SKILL.md` and capability declarations do

`SKILL.md` is the entry point a harness reads to use the bundle. The
`course/capabilities.yaml` file declares what the bundle needs and does:

- which tools and permissions it expects,
- what behavior reviewers and buyer agents can evaluate before granting access,
- what the bundle will not do.

Capability declarations are the core of trust and review. They make a
bundle's behavior visible to scanners, human reviewers, and buyer agents,
and they keep the published version accountable after acquisition.

## First steps by audience

### Buyer / user

You want an agent to do a job using a reviewed capability.

```bash
logion listings search --query "database migrations" --category data
logion courses get 7a2f...e0d4
logion credits balance
logion courses purchase 7a2f...e0d4 --yes
logion skills install \
  --course-id 7a2f...e0d4 \
  --version-id 3f9b...c1a8 \
  --source ./migration-safety-review \
  --install-source logion-marketplace
```

Free courses cost zero credits. Paid courses spend credits without a Stripe
redirect per purchase. Credits top up at 100 credits per US dollar.

### Creator

You want to publish what you know as a reviewed, versioned capability.

```bash
logion courses capabilities validate --bundle-dir ./migration-playbook
logion courses publication request 9c1d...ab21
```

Publication review runs automated scanners plus human review before the
bundle is available. Creators keep 85% of paid course revenue; the platform
fee is 15%.

### Contributor

You want to improve an existing bundle and earn from a bounty.

```bash
logion bounties create --course-id 7a2f...e0d4 \
  --title "detect async race conditions" --reward 800
```

Bounties are funded in credits. A contributor submits an improvement; on
acceptance the work ships as a new reviewed version and the contributor
cashes out through Stripe Connect.

### Reviewer / operator

You evaluate bundles before they reach buyers. Review uses the bundle's
capability declarations, scanner results, and human judgment. Published
versions are immutable, so a buyer can reason about exactly what their agent
installed, and reports, takedowns, and access revocation protect the
marketplace after publication.

## Install

One command installs the CLI and the agent companion, then runs onboarding:

```bash
curl -fsSL https://logion.sh/install.sh | sh
```

pipx and npx are alternate entrypoints that run the same onboarding:

```bash
pipx install logion-cli && logion onboarding
npx @logionsh/cli onboarding
```

Point your agent — Claude, Codex, OpenCode, or Hermes — at Logion and it
drives the marketplace for you.

## Trust model

Every published bundle is reviewable before acquisition and accountable
after publication:

- immutable published versions,
- `course/capabilities.yaml` capability declarations,
- automated scanners,
- human publication review,
- buyer-safe capability summaries,
- reports, takedowns, and access revocation.

Runtime sandbox enforcement is future runtime work and is not claimed as
solved on this page.
