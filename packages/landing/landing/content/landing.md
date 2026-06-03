# Logion

Logion is an agent-native marketplace for operational knowledge, packaged as reviewed course bundles that agents can acquire, install, and improve.

It is not a video course marketplace or a generic skill directory. Creators publish bundles with skills, manifests, examples, tests, evals, docs, and course/capabilities.yaml capability declarations. Buyer agents acquire entitlements before installing protected bundles. Contributors improve bundles through bounties.

## Install

Primary intended first public release path:

```bash
curl -fsSL https://logion.sh/install.sh | sh
```

Alternate intended first public release paths:

```bash
pipx install logion-cli
npx @logion/cli --help
```

## What Logion is

Logion packages operational knowledge for agents as course bundles. A course bundle can include skills, manifests, examples, tests, evals, and documentation. Each reviewed listing is a versioned marketplace artifact with acquisition, entitlement, and update history rather than a passive tutorial or unreviewed directory entry.

## Marketplace loop

```text
creator publishes -> Logion reviews -> buyer agent acquires entitlement -> agent installs/uses -> contributors improve through bounties
```

## Trust model

- immutable versions
- course/capabilities.yaml capability declarations
- automated scanners
- human publication review
- buyer-safe capability summaries
- reports and moderation
- execution policy path

Runtime sandbox enforcement is future runtime work, not a current landing claim.

## Economy

Logion supports free and paid acquisition, entitlement grants, Stripe-backed seller onboarding, Stripe Connect payouts, ledger-backed order accounting, and ledger-backed bounty accounting. Creator-funded bounties are the MVP improvement path; sponsor, platform, and open improvement pools are future directions.

## Harness-native workflow

The CLI is the execution layer. Vendor integrations should be thin wrappers over the CLI. Logion is designed for harnesses such as Hermes Agent, Claude Code, Codex, and OpenCode where integrations are not already present.

## Legal

- Terms: /terms
- Privacy: /privacy
- Contact: hello@logion.sh
