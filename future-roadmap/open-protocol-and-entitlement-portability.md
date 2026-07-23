<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Open Protocol And Entitlement Portability

> **Historical thesis, revised by the post-15.8 plan.** AI Catalog owns the
> typed catalog/entry representation; ARD owns intent-oriented resource
> discovery and registry interoperability over those entries. Acquisition remains native to Logion bundles,
> `npx skills`, `npx plugins`, `hf`, and future ecosystem managers; Logion reconciles
> identity/use/feedback instead of replacing them. AKTP is limited to portable evidence,
> work, and improvement events. The live sequence is
> [`plans/next-steps.md`](../plans/next-steps.md); where this document describes
> an AKTP discovery feed or branded-node CLI, the live plan supersedes it.

This document states the network thesis in protocol terms, maps Logion's
roles onto the AT Protocol architecture, and specifies the target model for
the one problem atproto never had to solve: portable paid entitlements.

It complements [Protocol-Ready Architecture](protocol-ready-architecture.md)
(the additive schema path) and revises the framing of its "Open Source
Boundary" section: under this thesis the *destination* is open reference
implementations, and the *route* is spec-first extraction — never opening
the operational monolith as-is.

## Thesis

```text
The CENTRAL idea is that the network exists, and that the product loop
exists. Everything else is nodes talking to nodes.
```

**Name.** The protocol is **AKTP — Agentic Knowledge Transfer Protocol**
(decided 2026-07-20). It is deliberately not named after Logion: a
federated protocol carrying one node's name would contradict everything
below — HTTP is not called "Netscape protocol". Logion is the company
operating the reference index/node; `sh.logion.*` namespaces, the
`logion` CLI, and the Logion node's payment rails are that node's own
identifiers and keep their names. Resource publication uses
[AI Catalog](https://ai-catalog.io/) and discovery uses ARD
([`plans/phase-15.12`](../plans/phase-15.12-ai-catalog-publication-and-ard-discovery.md));
an optional catalog entry relation/discovery extension advertises the AKTP evidence/improvement feed
([`plans/phase-15.17`](../plans/phase-15.17-aktp-evidence-and-improvement-feed-v0.md)).

- The network must be able to exist without Logion-the-company. Anyone may
  run a node, anyone may build a client, anyone may build a competitor.
- `api.logion.sh` is one node — the reference index. Its position is earned
  operationally (best crawler, best scanners, most complete view), not
  structurally enforced.
- When a user chooses the `logion` CLI / agent-companion, they choose the
  full-network view. When a creator runs their own store, their users see
  their store's view. Both are valid clients of the same network.
- Money flows to the index the way it flows to a search engine: as a
  consequence of being the best-operated view of everything, not as a toll
  the protocol imposes. Payment rails are a per-node choice (Stripe on the
  Logion node; Pix/AbacatePay/anything on someone else's).

Precedent: Bluesky open-sourced the PDS, the relay, the AppView, and even
its moderation tooling (Ozone), and still operates the dominant
infrastructure. Code openness did not dissolve the network position;
operating the index is the position.

## Role Mapping: ATProto → Logion

| ATProto | Logion equivalent | Status today |
| --- | --- | --- |
| PDS (self-hosted user data server, permissionless) | Resource/evidence node | AI Catalog publication + ARD discovery in [`plans/phase-15.12`](../plans/phase-15.12-ai-catalog-publication-and-ard-discovery.md), AKTP events in [`plans/phase-15.17`](../plans/phase-15.17-aktp-evidence-and-improvement-feed-v0.md) |
| Relay (crawls all PDSs, aggregates) | The `logion-indexer` crawler feeding `api.logion.sh` | Shipped shape in phase 15.6 |
| AppView (indexes, serves the app view, applies moderation) | `api.logion.sh` listings/search + the scanner pipeline as reach policy | Exists (centralized) |
| Client (Graysky, deer.social, …) | `logion` CLI, agent-companion, third-party clients via the public wire contract | Resource CLI is additive in [`plans/phase-15.9`](../plans/phase-15.9-generic-resource-model-and-index-backfill.md); white-label bins were dropped |
| Lexicons (schemas) | Manifest spec, package maps, capability manifests, node feed spec | Partially written; consolidate before any code opens |
| Payments | **Out of protocol.** Node-local checkout choice | Stripe = the Logion node's adapter, not a protocol rule |

## Speech Versus Reach

Adopt atproto's moderation split verbatim:

- **Hosting is permissionless (speech).** Anyone runs a node with any
  content, any store rules, any payment rails, any curation policy. A
  creator's own approval/rejection gate for submissions to *their* store is
  their node's policy. A node may disable third-party submissions entirely
  and only list its own content.
- **Indexing is policy (reach).** Appearing in the `api.logion.sh` view is
  conditioned on Logion's scanners and moderation. Safety trust is always
  the indexer's own (phase 15.6/15.7 rule: no external verification signal
  ever weakens or skips the observation scan). Other indexes may apply
  other policies.

The two never conflict: rejection from the Logion index does not remove the
course from the creator's node; it only removes reach in the Logion view.

Three Logion-specific rules sit on top of the atproto split:

- **Payment routing is born from the claim, never from the crawl.** The
  index crawls anything permissionlessly (attributed, unowned, never
  sellable), but only a claimed owner — logged in, domain-verified — may
  attach their store as the purchase rail for their content. An anonymous
  feed can never route payments for work it does not own.
- **Bounties are never disabled.** The constant-improvement loop is the
  point of the network — without it Logion is just a decentralized
  marketplace. A creator chooses whether to *fund* bounties (credits today;
  revenue-share pools per
  [Economic Network And Rewards](economic-network-and-rewards.md) later,
  including a node-side pledge for creators who sell through their own
  gateway) but can never turn off the community's ability to open them.
  When a community-improved version and a node's original diverge, every
  surface discloses which one the buyer is getting.
- **A claim decides canon, never compensation — and never destroys paid
  work.** Bounty payouts are final at acceptance. If the original creator
  claims their work and rejects the community-improved version, the
  improvement persists as a pending improvement proposal on their course
  (the dormant `improvement_proposals` substrate), authored by its
  contributor, acceptable later. The network's investment in improvement
  outlives any single claim decision.

### Improvement rights, pinned as Q&A

The invariant set every surface (index, node, client) must satisfy —
settled 2026-07-20:

| Question | Answer |
| --- | --- |
| Can anyone improve someone else's artifact? | **Yes, always.** The improvement loop is the point of the network; bounties can never be disabled by a node or a creator (fund-or-not is their only choice). |
| Can anyone sell someone else's artifact? | **No, never.** Payment routing is born from the claim. An index lists, attributes, and links out; it never sells what carries no verified claim. |
| Can anyone sell an *improvement* of someone else's artifact? | **No, unless its immediate owner authorizes a derivative and names the new owner.** A free contribution or funded bounty never grants the funder/contributor sale rights. A contributor/funder cannot silently turn a PR into an independently sellable artifact. |
| Does the improvement flow upstream to the original creator? | **It is offered upstream first, at the immediate owner's discretion.** The outcome is `merge_upstream` or owner-authorized `create_derivative`. The derivative preserves immutable upstream/version/proposal lineage, contributor attribution, named owner and access disclosure. It is then an ordinary artifact owned by that named owner; no special derivative authority model exists. Rejected or unclaimed work persists as disclosed community evidence and can be accepted later. |

The four answers are restatements of the three rules above plus the
never-mirror-paid rule; they are pinned here as Q&A because this is the
form the question always arrives in.

## Node Discoverability

The well-known document answers "given a domain, where is the feed?" — it
never answers "which domains exist?". Discovery is a ladder of mechanisms,
every rung governed by one invariant: **discovery is promiscuous, reach is
policy.** Being found costs an index exactly one validated fetch; being
listed still passes that index's scanners; ranking still requires
attestations. Sybil economics follow directly: spinning up a thousand
nodes is cheap and harmless — none gains reach without evidence, and
evidence is what the coalition analysis in
[Economic Network And Rewards](economic-network-and-rewards.md) watches.

1. **v0 — self-announce.** `POST /v1/nodes/announce {host}` on the index
   + `logion node announce` in the CLI (the requestCrawl pattern; spec and
   abuse bounds were superseded by ARD ingestion in [`plans/phase-15.12`](../plans/phase-15.12-ai-catalog-publication-and-ard-discovery.md)
   §2.6). An announce buys one validated well-known fetch, never a
   listing. Seed yaml remains as bootstrap, never as gate.
2. **v1 — peer exchange.** Optional `known_nodes: []` (array of ≤64
   hosts) on the well-known document: nodes point at nodes they know, and
   any index crawls the network transitively from any entry point — the
   hyperlink model; the network becomes self-describing and no index
   depends on anyone's seed list. Additive and must-ignore for v0
   crawlers. Ships alongside signed feeds because transitive discovery
   needs validation-at-scale (depth caps, per-host budgets, the same
   per-node verdicts) before it is safe.
3. **Ongoing — passive discovery.** Existing crawls surface node
   domains for free: a repo README naming its store, and any attestation
   referencing a `node:{host}/...` canonical URI, is a candidate probe.
   Discovery as a byproduct of operating.
4. **Ongoing — clients as sensors.** `node add HOST` in clients (use a
   node the index doesn't know) with an opt-in report back to the index —
   users teach the indexes.

Anti-patterns, pinned: no mandatory central registry (node directories
are just nodes serving feeds of nodes, competing like any node); no
CT-log/DNS scanning as a strategy (expensive, slow, unnecessary once
rungs 1–2 exist); no blockchain registry (a heavy dependency solving a
problem the ladder already solves).

## Update Propagation

How a change at one node reaches everyone who cares — settled 2026-07-20.
The primitive is **not** crawl and **not** websockets: it is the
**append-only, cursorable event log**. Everything else is transport.

Golden rules, both pinned:

1. **No propagation mechanism may require a node to be a process.** A
   static-JSON-on-a-CDN node must be able to participate in every layer.
2. **No producer ever needs to know its consumers.** Consumers subscribe
   and keep their own cursor (the Kafka-offset / atproto-firehose shape);
   producers never maintain consumer registries, retries, or delivery
   state. Push-to-consumer-lists is webhook hell and is rejected.

The layers, cheapest floor to premium tail:

| Layer | Mechanism | Latency | Serverless node? |
| --- | --- | --- | --- |
| v0 floor | periodic crawl + ETag/Last-Modified (15.12 §1.5) | crawl interval | yes |
| v0 hint | announce/ping on deploy (a `curl` in CI; 15.12 §2.6 revalidation) | seconds | yes |
| v1 | `events_url`: append-only paginated log per node, monotonic cursor, **immutable pages** (CDN-cacheable forever; only the head page changes) | incremental | yes — static files appended by CI |
| v1+ | SSE/WS firehose of the same log, offered by operators that run processes (indexes; the Logion node) | realtime tail | optional by construction |
| v2 | revocation streams (the one thing the entitlement model says is worth realtime) | realtime | index-hosted |

Consequences that answer the scale objections directly:

- **Sync cost is O(changed nodes), never O(catalog).** A ping triggers a
  conditional refetch of *one node's feed* (already capped at 5000
  listings); with `events_url` it triggers a cursor read of *that node's
  delta*. An index with billions of listings is never "recrawled" — a
  consumer reads its event log from its own cursor.
- **Bootstrap at scale** = snapshot + cursor (the CT-log / DB-replication
  shape): a new consumer of a large index fetches an exported snapshot
  once, then follows the log. Full crawls happen zero or one times per
  consumer lifetime.
- **Fan-out inversion:** a node with a million consumers serves them as
  static cache hits on immutable log pages; a consumer that wants
  realtime subscribes to an *index's* firehose rather than to a thousand
  nodes. Index-consuming-index firehoses are the v3 federation path.
- Same events, same cursors, two transports: a consumer may drop off the
  websocket and resume over plain HTTP from the same cursor — the log is
  the truth, the socket is a convenience.

## The Disanalogy: Paid Access

ATProto keeps payments out of protocol because every record is public.
Logion sells *access*, so the protocol needs one object atproto never
defined: a portable proof of purchase that any node/client can verify.

### Target model (destination, not v0)

Correctness anchor: the **signed entitlement credential**, held by the
buyer. Everything else is distribution.

1. **Issuance.** The selling node signs an entitlement credential binding
   `(buyer identity, course canonical_uri, version or version-range,
   issued_at)` with the node's private key. The credential is handed to the
   buyer (their client stores it; in a future repo-model it lives in the
   buyer's own data repo). Fits `course_attestations` with
   `attestation_type = 'entitlement_grant'`.
2. **Verification.** Any node/client verifies offline: resolve the course's
   canonical origin node → fetch/lookup that node's public key (from the
   `nodes` registry) → check signature → check that the credential issuer
   *is* the course's canonical origin (issuer-authority rule below).
3. **Revocation.** Refunds emit `entitlement_revoked` counter-attestations
   on the node's event stream (`protocol_events`). Verifiers check
   revocation with an accepted staleness window. Revocations are the thing
   worth pushing in realtime — buyers never present their own revocations.
   Broadcast of *grants* is optional cache-warming, never required for
   correctness, and should be privacy-weighed (a public purchase graph is
   not acceptable by default; grants travel with the buyer, not the
   firehose).
4. **Fallback chain** (degradation order):
   1. buyer presents a valid, unrevoked credential → serve;
   2. no credential at hand → query the origin node for the entitlement;
   3. origin node dead → verify the credential against the origin node's
      **archived public key** (indexers must retain keys of dead nodes) and
      serve the **content-addressed bundle** from any mirror whose hash
      matches;
   4. no credential, origin dead, and the course does not exist on the
      current node → treat as not-Logion content. This last rule is the
      floor, not the second step — steps 1–3 make purchases survive node
      death.

### Prerequisites the spec must fix first

- **Portable buyer identity.** The credential must bind to an identity
  resolvable at any node (DID-like). v0 pragmatic stand-in: the verified
  GitHub identity from phase 15.1 (`github_identities`), i.e. the
  credential binds a GitHub account id; a real DID method can supersede it
  additively.
- **Issuer authority.** `canonical_uri` must encode the origin node so a
  verifier can reject credentials for course X issued by node Y. Without
  this check, any node can mint entitlements for anyone's courses.
- **Key registry with archival.** The `nodes` table from
  [Protocol-Ready Architecture](protocol-ready-architecture.md) gains the
  operational rule: public keys are never deleted, only superseded; dead
  nodes' keys remain resolvable for credential verification.

## Phasing

| Stage | What ships | Entitlement story | Plan/roadmap anchor |
| --- | --- | --- | --- |
| v0 — indexed resources | AI Catalog publisher/consumer + ARD Agent Finder indexer + optional AKTP evidence/improvement link | **None needed.** Discovery is open; settlement remains node-local | [`plans/phase-15.12`](../plans/phase-15.12-ai-catalog-publication-and-ard-discovery.md), [`plans/phase-15.17`](../plans/phase-15.17-aktp-evidence-and-improvement-feed-v0.md) |
| v1 — signed feeds | Node keypairs, signed feed/manifests, `nodes` registry, `known_nodes` peer exchange, attestation read surface | Still link-out; signatures make mirroring/tamper-evidence real | Protocol-Ready 2A–2C |
| v2 — portable entitlements | Entitlement credentials + revocation events + archived keys + CLI verification | The target model above; buy at a node with Pix, install anywhere | New spec work (this doc) |
| v3 — federation | Node registry, sync, mirrors, trust levels, cross-node reads | Cross-node *payments* remain out of protocol even here | Protocol-Ready 2E |

The v0 cut is deliberate: it makes the "your store, your rules, your
payment gateway, indexed in the network" pitch true today, without the
protocol's hardest object. Do not let v2 block v0.

### x402 settlement (v2 seed — explicitly not v0/v1)

Decision recorded 2026-07: x402 does **not** enter v1. v1 ships the
original idea (credits + Stripe on the Logion node; link-out for other
nodes). This section exists so the door stays open without anyone
mistaking it for current scope.

Context that changed in 2025–2026: x402 (HTTP 402 + stablecoin settlement)
was formalized under the Linux Foundation in April 2026, with Stripe,
Visa, Mastercard, Google, AWS, Amex, and Shopify among the founding
members; Cloudflare and AWS run it at their edges. It is becoming neutral
agent-native payment infrastructure — the MCP trajectory, not a token
play.

Why the protocol is already ready for it, at zero cost today:

- `purchase.mode` is an open namespace with must-ignore (15.12 §1.3 names
  x402 as the worked example): a node can advertise an x402 rail tomorrow
  and v0 crawlers keep working, link-only;
- payments are node-local by layering rule — x402 would be **one more
  settlement adapter beside Stripe**, never a protocol requirement.

What v2 would actually add, in order of value:

1. **Cross-node settlement without Stripe.** A federated node anywhere
   can sell without a Stripe relationship: AKTP carries
   discovery + evidence + entitlement; x402 carries the money leg. This is
   the strongest argument — it removes the last first-party dependency
   from the "anyone can run a node" claim.
2. **402-shaped acquisition.** Agent requests a paid bundle → `402` with
   price → pays → entitlement credential issued. Our atomic no-redirect
   purchase, as an internet standard instead of a proprietary flow.
   Depends on the v2 entitlement credential above (the 402 response is
   just the handshake; the credential is still the object that matters).
3. **Distribution via agent service directories** (Circle Agent
   Marketplace, Agent.market): exposing metered Logion endpoints
   (e.g. paid recall/scorecard reads) where x402-funded agents already
   browse. Cheap post-launch experiment; belongs to
   [Post-Launch Strategy](post-launch-strategy.md) sequencing, listed here
   because the rail is what makes it possible.

Denomination guard, unchanged: credits remain the only user-facing unit;
x402/USDC is a settlement boundary exactly like Stripe today — it never
surfaces on creator or buyer UX.

## Extensibility Model: Closed Core, Open Vocabulary

Good protocols are closed for modification and open for extension. HTTP
never defined HTML, JSON, or WebSocket — it defined an envelope (opaque
payloads with negotiable content types), a must-ignore rule for unknown
headers, an open naming space, and an upgrade path. Google, Meta,
Cloudflare, and Amazon are entirely different businesses built on those
same four mechanisms. AKTP adopts them explicitly, because
a network whose thesis is continuous self-improvement cannot have a
protocol that only its author may improve.

### The frozen core (closed for modification)

Kept tiny on purpose — extensibility only works over a stable floor:

- canonical identity (`gh:` / `node:` URI forms);
- content addressing (sha256 of bundles and manifests is the unit of
  truth);
- the attestation **envelope** — what is signed and how signatures verify —
  never *which types* of attestation exist;
- the must-ignore rule: unknown fields, unknown attestation types, and
  unknown extension namespaces are ignored or gracefully degraded, never
  errors. (Protocol version numbers are the deliberate exception: an
  unknown version hard-fails loudly.)

### The open namespaces (permissionless extension)

Reverse-DNS names, atproto-lexicon style: owning a domain is owning a
namespace. Nobody asks Logion for permission.

| Surface | Logion's own entries | Anyone else's |
| --- | --- | --- |
| `content_type` / `bundle_kind` (the payload is opaque — SKILL.md is our HTML, the first payload, not the only one) | `sh.logion.skill`, `sh.logion.rl-env` | `com.acme.dataset`, model weights, formats not yet invented |
| `attestation_type` (the trust vocabulary itself is extensible) | `sh.logion.scan.observed`, `sh.logion.review.human` | `com.vanta.soc2`, `com.acme.insurance.covered`, eval scores |
| `purchase.mode` | `free`, `external` | x402, subscriptions, streaming money |
| `ext` object on protocol objects | — | `dev.aihero.*` metadata of any shape |

Graceful degradation is how the future enters without breaking the
present: unknown purchase mode → the listing is kept, link-only; unknown
content type → link-only with an honest "unscanned format" label; unknown
attestation type → stored and displayed as unrecognized, ranking weight
zero. Each index chooses which vocabulary it *consumes*; the protocol only
guarantees the vocabulary can *exist*.

### Attestation size discipline — claims inline, evidence by reference

Settled 2026-07-20. An attestation is a **claim, never a dataset** — an
unbounded `payload_json` would let one issuer make every index in the
network pay to store and parse gigabytes. Three rules:

1. **Hard payload cap, pinned in schema**: `payload_json ≤ 16 KiB` (same
   family as the well-known/`ext` caps in 15.12). Over the cap →
   *invalid*, dropped with a reason, never truncated, never crashes a
   consumer; drops are logged (no-silent-caps).
2. **Large evidence travels by reference, content-addressed** — the same
   `{url, sha256, size_bytes, media_type}` shape the feed's `bundle`
   field already uses. The signature covers the *hash*, so the blob is
   tamper-evident without being inline; it can live on any node/CDN/
   mirror, be fetched lazily (only auditors pay the bandwidth), and even
   be access-controlled while the claim stays public. This is the
   in-toto/SLSA shape (small statement + subject digests) and slots into
   native or explicitly chosen artifact storage with no new protocol
   mechanism. Consequence: indexes store **claims +
   hashes**, so operating an index scales with artifact count, never
   with evidence volume.
3. **Collections are paginated streams, never one growing file.** An
   artifact's attestation set is read through the same paginated shape
   as the node feed (page caps, `next`), append-only, with **supersede**
   semantics: the newest record per `(type, issuer)` wins by `issued_at`;
   the active set stays tiny, history stays addressable.

### Worked example: `sh.logion.reviews.summary`

The pattern for turning private index data into portable trust —
Logion's usage reviews as the first case:

- Raw reviews (reviewer identity, text, timing, telemetry) **never leave
  the index** — privacy by schema, the 17.1 construction: the attestation
  format cannot represent per-reviewer data.
- Periodically (per window or when `n` crosses a threshold — never
  per-review, which would leak reviewer timing and flood the stream),
  the index mints a derived summary bound to the version:
  `{canonical_uri, version_hash, usefulness_avg, sample_size, window,
  method}` — sample-size-honest by construction (a 4.8 with n=3 says so).
- Newer summaries supersede older ones; the raw data behind the claim is
  the issuer's own (its signature and track record are what a consumer
  trusts — provenance ≠ authority, per 16.12).
- Any other index may consume it and rank on the same evidence — which
  is the point: the more indexes consume `sh.logion.*` summaries, the
  more the Logion index's operational work (the reviews only it has)
  becomes the trust product the assurance inflow pays for.

### The layering rule

```text
format + evidence  = protocol   (global, open)
service + money    = node-local (each node, its own rails)
vocabulary         = namespace  (permissionless)
```

Applications, settling questions the older roadmap docs left open:

- **Bounties.** The bounty *format* and its *discovery* are global — a
  bounty may be announced network-wide against any canonical URI, wherever
  the artifact lives. Escrow, funding, and payout are always services of
  the node where the bounty was opened, in that node's rails (Logion
  credits on the Logion node; whatever a creator's node chooses on
  theirs). Money never crosses nodes; improvements, evidence, and
  attestations do. Acceptance becomes a portable attestation
  (`sh.logion.bounty.accepted`).
- **Rewards and reputation.** There is no protocol tax — a network that
  taxed its nodes would depend on its owner, which contradicts the thesis.
  Reward pools are node policy funded by node surplus. Reputation is
  computed *per index* from the *global* attestation graph: global
  evidence, local weighting (the PageRank pattern — the graph is public,
  the ranking is each index's own).
- **Enterprise.** A company is a private node running the reference
  implementation behind its firewall; compliance attestors (SOC2,
  insurance, audit) are third-party namespace owners selling trust
  vocabulary; scan/review services are node services anyone can buy from
  the Logion node — including for artifacts that never touch the public
  index.
- **Metered execution, RL rollouts, smart payments.** Node services on
  protocol-shaped artifacts: the environment/eval *formats* travel, the
  per-use metering and royalty splits settle at whichever node hosts the
  execution surface.
- **Eval contracts.** `eval.yml`, archetypes, and scorecards are protocol
  formats so any node can run the same ruler; results are attestations
  (`sh.logion.eval.scored`); network-executed evaluation is a node
  service.

### Spec governance: absorb, never invent

The spec lives in the public repo and evolves the IETF way — rough
consensus and running code. An extension is promoted into the core only
with:

1. **executable conformance tests** — the deterministic eval of a protocol
   change; a spec change without a runnable harness is not promotable;
2. **a backward-compatibility suite** proving must-ignore holds — existing
   nodes, indexes, and clients keep working unmodified;
3. **adoption evidence** — N independent nodes/clients serving the
   extension in production, measurable by crawl (Tier 3 evidence in the
   eval-backed-bounties sense).

Human rubric judgment applies only to what remains: prose clarity and
overlap with existing extensions. Because proposals are PRs with a
deterministic harness attached, the network's own improvement loop —
bounties included — applies to the protocol itself.

## Open Source Boundary, Revised

Destination: open reference implementations of every protocol role (node,
indexer, index/AppView), per the Bluesky precedent. Route:

1. **Spec first.** Node feed (15.12), manifest/package-map, capability
   manifest, attestation formats, entitlement credential. Specs live in the
   public `logion` repo. The spec — not any codebase — is what makes
   multi-language nodes (Node, Elixir, Rust, C, …) possible: nobody ported
   Apache to build nginx; they implemented HTTP.
2. **Conformance suite with the spec.** A language-neutral test suite
   (fixtures + a runner that exercises any implementation over the wire)
   is the real multi-language deliverable and the certificate of "this is
   a valid AKTP node" — the same suite the governance rule requires for
   promoting extensions. The private `backend repository/api` becomes simply
   the first implementation required to pass it: honest dogfooding, full
   internal freedom, public proof the spec is implementable.
3. **Contract, mock, generated clients.** The versioned OpenAPI contract +
   public mock API already planned in
   [B2B And Ecosystem Strategy](b2b-and-ecosystem-strategy.md); per-language
   client SDKs are *generated* from the contract, never hand-maintained.
   The only hand-written multi-language code worth shipping is thin
   crypto helpers (attestation signing, canonical hashing) — the
   libsodium/JWT-libs pattern, because hand-rolled crypto is how nodes get
   hurt.
4. **Reference node next.** A minimal open `logion-node` (host bundles +
   serve the feed + pluggable payment adapter; Stripe is just the Logion
   node's adapter). Small and new by design — it teaches the spec, it does
   not carry the Logion node's economy. A static-JSON store must remain a
   valid node.
5. **Economy stays node-local implementation.** Stripe Connect, credits,
   ledger, fraud, admin tooling are the Logion node's operational layer —
   they are not protocol and their openness is a separate, later decision.
6. **Never open `backend repository/packages/api` as-is.** It interleaves node,
   index, and Logion-node economy concerns; opening the monolith would
   consecrate Stripe/credits as protocol, which is the opposite of the
   thesis. (Technically the split is clean — `api/` has zero import
   coupling to `infra/` — the objection is shape, not feasibility.)

## Guiding Rule

Same as the roadmap-wide rule: protocol-readiness is direction, not a PMF
substitute. The v0 stage exists precisely because it is cheap, honest, and
sellable to a real creator today; v1–v3 activate as the network proves
demand.
