<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logion-wordmark.svg">
  <img alt="Logion" src="assets/logion-wordmark-light.svg" width="460">
</picture>

<p><strong>Smarter, together.</strong><br>
<em>λόγιον — what is declared true</em></p>

</div>

---

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/nicolasmelo1/logion?style=flat-square&color=D99A2B&labelColor=0C1E22"></a>
  <a href="https://github.com/nicolasmelo1/logion/actions/workflows/pr-safety.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/nicolasmelo1/logion/pr-safety.yml?branch=main&style=flat-square&label=ci&color=57C9A0&labelColor=0C1E22"></a>
  <a href="https://pypi.org/project/logion-cli/"><img alt="PyPI: logion-cli" src="https://img.shields.io/pypi/v/logion-cli?style=flat-square&label=pypi&color=57C9A0&labelColor=0C1E22"></a>
  <a href="https://www.npmjs.com/package/@logionsh/cli"><img alt="npm: @logionsh/cli" src="https://img.shields.io/npm/v/@logionsh/cli?style=flat-square&label=npm&color=D99A2B&labelColor=0C1E22"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12+-D99A2B?style=flat-square&labelColor=0C1E22">
  <img alt="Status: beta" src="https://img.shields.io/badge/status-beta-9DB0AE?style=flat-square&labelColor=0C1E22">
  <a href="https://api.logion.sh"><img alt="API: live" src="https://img.shields.io/badge/api-live-57C9A0?style=flat-square&labelColor=0C1E22"></a>
  <a href="https://discord.gg/7GfgAzADE"><img alt="Discord" src="https://img.shields.io/badge/discord-join-5865F2?style=flat-square&logo=discord&logoColor=white&labelColor=0C1E22"></a>
  <a href="https://x.com/logionsh"><img alt="X (Twitter)" src="https://img.shields.io/badge/X-@logionsh-D99A2B?style=flat-square&logo=x&logoColor=white&labelColor=0C1E22"></a>
</p>

**Logion is an open protocol and economic network for _verifiable_ agent capability.**

When an agent hits a wall, instead of improvising it acquires a capability
published by someone else — and trusts it not because it's popular, but because
the exact version carries evidence: it was scanned, its declared powers were
reconciled against what it actually does, and, increasingly, it was **proven**
against a benchmark. When a capability isn't good enough, a funded bounty pays
someone to improve it, and the money flows to the people who create and improve
— not to whoever hosts the list.

This repository is the **open-source developer tooling** for that network: the
SDK, CLI, and agent companion you build and integrate against. It is the client
surface — not the platform itself.

## The end goal

A skills index is free everywhere, so discovery is worth ~nothing. The thing
that is worth paying for — and the thing no free index can give you — is
**proof that a capability works, and a loop that makes it better.** Logion is
built to be that layer, and to be it as an open network rather than a walled
store:

- **Proof over popularity.** Stars and install counts say a capability is
  popular. Logion attaches *attestations* instead — scan, eval score, usage
  telemetry, improvement history — each with its producer and trust level shown.
  An unknown author's capability can outrank a famous one because the evidence
  says so.
- **A loop, not a transaction.** Every acquisition, use, and bounty leaves the
  next version better. Money enters from the demand side (teams and labs funding
  bounties and evaluations), work flows in from creators and the network, and
  Logion clears it — the majority to the people who create and improve, a rail
  fee for running the network.
- **Skills are the wedge, not the ceiling.** The same backbone — a versioned
  artifact that accumulates attestations — extends to tools, MCP servers,
  agents, and the evals/environments that judge them.
- **One node among many.** Logion is designed to be a protocol, not a landlord.
  Anyone can run a node on the same spec, index the same capabilities, and
  federate. If someone runs a better node, the protocol won.

Not all of this exists yet. See **[What's live today](#whats-live-today)** and
**[Where it's going](#where-its-going)** below — we try hard to keep the line
between the two honest.

## Why Logion exists

For two decades people wrote the tutorials, the answers, and the open source —
for free. It was compiled into products worth billions, and the people who
wrote it were told they were replaceable.

Logion is the correction. You keep your knowledge, publish it as a reviewed
capability, and agents acquire it to do real work. When it can be better, a
funded bounty pays someone to improve it — and the next version lifts everyone.

Models compress what already exists; they don't invent what was never written
down. Frontier capability is bottlenecked by data, and human expertise — the
scarce input — erodes as fewer people learn the craft and more just ask a
model. **Logion is the human teaching the agent**: it keeps that knowledge
alive, owned, and compounding.

The edge is shifting from raw model scale to how well a system integrates real
human expertise through continual learning loops — distributed and defensible,
not winner-take-all. A network of people teaching agents out-learns any single
model alone.

**Smarter, together.**

## The loop

The heart of the product is a cycle, not a transaction. Everything a capability
accumulates is an **attestation** — a signal with a producer and a trust level,
shown openly. No single blessed score.

```
        ┌──────────────────────────────────────────────────┐
        │                                                    │
   use ─┤  A capability is acquired and run on a real        │
        │  task, in your own harness. Honest usage           │
        │  telemetry becomes evidence.                       │
        │                                                    │
  test ─┤  It is scanned, and — increasingly — scored        │
        │  against a benchmark: reproducible, held-out,      │
        │  reconciled against real-world usage.              │
        │                                                    │
   pay ─┤  A funded bounty pays someone to improve it.       │
        │  The improvement is proven, not argued.            │
        │                                                    │
 prove ─┤  The new, attested version passes the same         │
        │  review — and the money reaches the people who     │
        │  created and improved it.                          │
        │                                                    │
        └────────────────────────────────────────────────────┘
            ↺ a better, attested version → back to use
```

> Spend, install, and permission **always** require human confirmation.
> Money never moves faster than trust.

## What's live today

Logion is a working marketplace, not a whitepaper. Shipped and running against
the live API:

- **Marketplace loop** — publish → automated review → human gate → acquire →
  use → review → bounty → accept, exercised end-to-end by a real autonomous
  agent.
- **Trust pipeline** — every version declares `capabilities.yaml`, runs through
  Trivy · OSV Scanner · agent-safety checks, reconciles observed-vs-declared
  behavior, and passes a human reviewer before publish.
- **Credit economy** — credits as the buyer unit of account, a double-entry
  marketplace ledger, funded bounties, and Stripe-backed top-ups and
  creator/contributor payouts.
- **Client surface** — the public Python SDK, the CLI, and the agent companion
  in this repo.

## Where it's going

The proof layer — the part that makes Logion more than a paid index — is what
we are building next. Honestly labeled as *not yet shipped*:

- **Evals as attestations** — a portable `eval.yml` contract and scorecards, so
  "this version got 20% better" is a reproduced fact, not a claim.
- **Network-executed evaluation** — deterministic evals run by independent
  nodes where agreement is byte-equality of a canonical scorecard, so a result
  can be trusted without trusting the runner.
- **Provenance ≠ authority** — a foreign node's score is shown as an attributed
  claim, never authoritative, until it is reproduced under a trusted baseline.
- **Benchmark ↔ field reconciliation** — a benchmark score that real-world
  usage contradicts is flagged, never trusted blindly.
- **Open node network** — `/.well-known/logion.json` feeds so any index can
  crawl our catalog exactly the way we crawl others', with payment routing born
  from a verified claim, never from a crawl.

## Install

### From source (today)

```bash
git clone https://github.com/nicolasmelo1/logion.git
cd logion
uv sync --all-packages --all-groups
```

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the full dev setup and the local mock
server.

### Public dev rig

You can iterate on the companion directly from this repo without a separate API
checkout. The public `.devrig/` supports two modes:

```bash
make bootstrap
make dev-up MODE=mock               # local Prism mock on 127.0.0.1:4010
make dev-up MODE=prod               # live API with your own Logion account
make doctor AGENT=codex
make dev-logs                       # tail the Prism mock log
make companion AGENT=codex ROLE=seller
make companion AGENT=codex ROLE=buyer
make companion AGENT=codex ROLE=admin
# or launch the harness in this repo with the companion already synced
make start-companion AGENT=codex ROLE=seller
make dev-rebuild-companion AGENT=codex ROLE=seller
```

`MODE=prod` does **not** create throwaway accounts; it points the build at the
live API so you can test with your own user. `ROLE` is a harness persona label,
not proof of a separate backend account; use `seller`, `buyer`, and `admin` to
exercise different product/operator flows from the same local rig. In both
modes the companion is installed from `packages/agent-companion` and exposed to
harnesses as `/logion`.
For public-rig parity, `make devrig-lint`, `make devrig-test`,
`make dev-rebuild`, `make dev-rebuild-cli`, `make dev-rebuild-companion`, and
`make dev-rebuild-npm` wrap the local equivalents that still make sense in the
mocked public setup.

### Package managers

```bash
pipx install logion-cli                       # PyPI
npx @logionsh/cli onboarding                 # npm one-shot
npm install -g @logionsh/cli                 # npm global install
curl -fsSL https://logion.sh/install.sh | sh  # standalone installer
```

The npm package installs the matching Python CLI into a Logion-managed virtual
environment during `postinstall`; npm users do not need to run pip, pipx, or uv.

## Quick verification

```bash
logion --version
logion --help
logion listings search --query "video cuts" --limit 5
logion listings search --category devops --tag terraform   # narrow by category + tag
```

Discovery is structured: `--category` filters by a canonical slug and `--tag`
is repeatable (AND across filters, prefix match — `--tag pr` finds `pr-review`).
With `--sort relevance` results are ranked by how closely they match the query.

## What's in the box

| Package | What it is |
| --- | --- |
| [`packages/client`](packages/client) | **`logion-client`** — Python SDK for the Logion API |
| [`packages/cli`](packages/cli) | **`logion-cli`** — command line for operators, agents, and integrators |
| [`packages/agent-companion`](packages/agent-companion/README.md) | **`logion-agent-companion`** — a compact `SKILL.md` that loads into an agent's harness |
| [`packages/scanners`](packages/scanners) | **`logion-scanners`** — capability safety scanning used by the review pipeline |

## Core concepts

The vocabulary you work with every day. Full reference in
[`docs/marketplace/concepts.md`](docs/marketplace/concepts.md).

- **Course** — the capability bundle: lessons, workflows, code, tests,
  metadata, price, visibility, and publication status.
- **Course version** — an immutable release of a course. The durable unit of
  trust; it never changes after publication.
- **Attestation** — a signal attached to a version (scan, eval score, usage
  telemetry, improvement history), each carrying its producer and trust level.
  Attestations are displayed and weighed; they are evidence, not a single
  blessed number.
- **Entitlement** — the right to access a version. Always a separate concept
  from the order that paid for it — purchased, granted, or free.
- **Bounty** — a funded request to improve a course, with submissions,
  acceptance, expiry, and payout (denominated in credits).
- **Publication review** — the automated + human gate that decides whether a
  version may be published.

## Why trust is the moat

A course can influence terminal commands, files, the network, secrets, and paid
actions. **Capabilities are supply chain, not content** — so trust is treated
as a layered production control, not a cosmetic seal. Every version runs through:

```
declare   capabilities.yaml — what the course may touch
  ↓
scan      Trivy · OSV Scanner · agent-safety checks
  ↓
reconcile observed vs. declared capabilities
  ↓
decide    a reviewer approves or rejects with feedback
  ↓
publish   immutable, hashable version → buyer sees a safe summary
```

Review establishes publication trust. Evals establish that a version is
measurably good. Sandboxing establishes runtime containment. Bounties establish
economic coordination. None substitutes for another. See
[`docs/marketplace/safety.md`](docs/marketplace/safety.md).

## Documentation

- [`docs/marketplace/`](docs/marketplace) — concepts, getting started,
  creating courses, credits & purchases, reviews, bounties, and safety
- [`docs/openapi-sync.md`](docs/openapi-sync.md) — how the API contract is
  synced and how to run a local mock
- [`docs/branding-guide.md`](docs/branding-guide.md) — logo, palette, type,
  voice, and motif; the machine-readable mirror is served at `/design.txt`
- [`packages/agent-companion/README.md`](packages/agent-companion/README.md) —
  the agent companion guide

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup, mock-server usage,
commit conventions, and the PR checklist. Security policy lives in
[SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
