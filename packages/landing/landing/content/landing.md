# Logion

> Logion is an agent-native marketplace where buyer agents acquire reviewed course bundles by spending credits (100 credits = $1), install them via the `lgn` CLI, and improve them through creator-funded bounties.

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

Real CLI verbs, end to end.

```text
$ lgn listings search "database migrations"
  migration-safety-review     900 credits   v1.0.2
    capabilities: file, terminal
    review:       scanners + human publication review

$ lgn courses get 7a2f...e0d4
  price:     900 credits
  publisher: opentide
  reviewed:  2026-04-12

$ lgn credits balance
  1,200 credits

$ lgn courses purchase 7a2f...e0d4 --yes
  spent:        900 credits
  remaining:    300 credits
  entitlement:  granted

$ lgn skills install \
    --course-id 7a2f...e0d4 \
    --version-id 3f9b...c1a8 \
    --source ./migration-safety-review \
    --install-source logion-marketplace
  installed: migration-safety-review@v1.0.2
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

The API implementation is private; the client and integration surface are public for inspection. No MCP setup is required for the first workflow.

- CLI source — `packages/cli`
- Python SDK — `packages/sdk-python`
- npm wrapper — `packages/npm-wrapper`
- agent companion SKILL.md — `packages/agent-companion`
- public OpenAPI contract — `contracts/openapi`
- release manifests — `releases/`

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

## Credits, referrals, and bounties

Credits without packs — credits are a wallet/spending-control mechanism for agents, not packs.

- no platform subscription gate
- buyers top up credits
- 100 credits = $1
- paid course purchases spend credits without a Stripe redirect
- free courses cost zero credits
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
Logion is an agent-native marketplace for operational knowledge, packaged as reviewed, versioned course bundles that buyer agents can acquire, install, and improve. It is not a video course marketplace or a generic skill directory.

**How are courses priced?**
Courses are priced in credits. Credits top up at 100 credits per US dollar. There is no platform subscription gate. Free courses cost zero credits. Paid course purchases spend credits without a Stripe redirect.

**How much do creators keep?**
Creators keep 85% of paid course revenue. The platform fee is 15%. Creator payouts are made through Stripe Connect, not by redeeming buyer credits.

**How are course bundles trusted?**
Every published bundle is reviewable before acquisition and accountable after publication. Trust comes from capability declarations (`course/capabilities.yaml`), automated scanners, human publication review, immutable versions, and reports/takedown paths. Runtime sandbox enforcement is future runtime work and is not claimed as solved.

**How does a buyer agent acquire a course?**
Real CLI flow — `lgn listings search` to find a reviewed course, `lgn courses get` for details, `lgn credits balance` to confirm funds, `lgn courses purchase` to spend credits and receive an entitlement, and `lgn skills install` to install the bundle into `LOGION_HOME`.

**Is MCP required to use Logion?**
No. The first workflow uses the public CLI and SDK directly. MCP can remain a future thin adapter over the same public CLI and API contract.

**What are bounties?**
Bounties are creator-funded improvements to course bundles. Contributors submit improvements and, on acceptance, cash out through Stripe Connect. Bounties are funded in credits.

**Are credits refundable or transferable?**
No. Credits are non-cash, non-transferable, non-redeemable usage rights inside the marketplace. Credits may be reversed for chargebacks, fraud, abuse, or administrative correction. See `/credits-terms` for the full rules.

## Legal

- Terms: /terms
- Privacy: /privacy
- Credits Terms: /credits-terms
- Referral Program Terms: /referrals-terms
- Contact: hello@logion.sh
