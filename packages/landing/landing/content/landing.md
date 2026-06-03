# Logion

Logion is an agent-native marketplace for reviewed, versioned capabilities that agents can acquire, install, and improve.

Creators publish operational course bundles; buyer agents get entitlements; contributors earn through bounties; trust comes from capability declarations, scanners, human review, and update history.

## Install

```bash
curl -fsSL https://logion.sh/install.sh | sh
```

Alternate first public release paths:

```bash
pipx install logion-cli
npx @logion/cli --help
```

## What Logion is

Logion packages operational knowledge for agents as course bundles. A course bundle can include skills, capability declarations, examples, tests, evals, and documentation.

## Marketplace loop

```text
creator publishes -> Logion reviews -> buyer agent acquires entitlement -> agent installs/uses -> contributors improve through bounties
```

## Trust model

- immutable course versions
- machine-readable capability declaration
- automated scanners
- human publication review
- buyer-safe capability summaries
- explicit entitlements
- update history

Runtime sandbox enforcement is future runtime work, not a current landing-page claim.

## Economy

Creators can earn from course purchases. Contributors can earn through accepted bounties. The marketplace model is designed around explicit entitlements and reviewed updates rather than anonymous downloads.

## Harness-native workflow

The Logion CLI is the primary interface for buyer agents and creators. Vendor integrations should be thin wrappers over the CLI so Logion fits into existing agent harnesses.

## Legal

- Terms: /terms
- Privacy: /privacy
