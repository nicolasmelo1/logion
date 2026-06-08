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

## Agent acquisition flow

Target CLI flow. Exact CLI verbs may change before the first public release.

```text
> Find a reviewed course that helps write safer database migrations
lgn listings search "database migration safety"

FOUND migration-safety-review
price: 900 credits
version: immutable after publish
review: scanners + human publication review
capabilities: file, terminal

Install? yes
lgn courses acquire migration-safety-review
lgn courses install migration-safety-review

entitlement granted
course bundle installed
```

## Security is the authority

- course/capabilities.yaml declarations
- automated scanners
- human publication review
- immutable published versions
- buyer-safe capability summaries
- reports, takedowns, access revocation
- execution policy export path

Runtime sandbox enforcement remains future runtime work; the landing does not claim it is already solved.

## Open-source trust layer

The API implementation is private; the client and integration surface are public for inspection.

- CLI source
- Python SDK source
- npm wrapper source
- agent companion SKILL.md
- public OpenAPI contract
- release manifests
- CI and installer smoke tests

## Agent-readable web surface

- `Accept: text/markdown` on `/`
- `/llms.txt`
- `/robots.txt`
- `/sitemap.xml`
- public GitHub repo

No MCP setup is required for the first workflow; MCP can remain a future thin adapter over the public CLI and API contract.

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

## Credits without packs

Credits are a wallet/spending-control mechanism for agents, not packs.

- minimum top-up exists to avoid Stripe fee damage
- custom amount is the core model
- preset amounts may be UI shortcuts, not packs
- credits are non-cash, non-transferable, and non-redeemable

## Economy, referrals, and bounties

- no platform subscription gate
- buyers top up credits
- 100 credits = $1
- paid course purchases spend credits without a Stripe redirect
- free courses cost zero credits
- creators keep 85% and the platform fee is 15%
- referrers can earn credits through the referral program
- bounty funders fund with credits; bounty contributors cash out through Stripe Connect after acceptance

## Harness-native workflow

The CLI is the execution layer. Vendor integrations should be thin wrappers over the CLI. Logion is designed for harnesses such as Hermes Agent, Claude Code, Codex, and OpenCode where integrations are not already present.

## Legal

- Terms: /terms
- Privacy: /privacy
- Credits Terms: /credits-terms
- Referral Program Terms: /referrals-terms
- Contact: hello@logion.sh
