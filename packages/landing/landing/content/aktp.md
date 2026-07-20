# AKTP — Agentic Knowledge Transfer Protocol

An open protocol for AI agents to discover, verify, and transfer operational knowledge — skills, evals, environments, datasets — across independent domains. What HTTP did for documents, AKTP does for agent capability: anyone can host, anyone can index, anyone can build on top. Federated networks like the AT Protocol served as inspiration.

The central idea: the network exists, and the improvement loop exists. Everything else is nodes talking to nodes. The network must be able to exist without any one company — anyone may run a node, build a client, or operate a competing index.

## The problem

- Fragmented distribution: every harness has its own directory, format, and channel — no common layer.
- Trust doesn't travel: a security scan, human review, or eval score produced in one place cannot be verified anywhere else.
- Purchases aren't portable: buying access on a marketplace chains the buyer to that marketplace.

## How it works

A node is anything that serves two JSON documents over HTTPS — a Next.js route, a static file on a CDN, or a full backend are equally valid nodes.

1. Publish a discovery document on your domain (owning the domain is owning the identity — no signup, no permission asked).
2. Point it at a feed of your listings; each item declares source, bundle (sha256), license, and purchase mode.
3. Indexes crawl permissionlessly and apply their own policy (scans, review, ranking). Rejection by one index never removes content from your node.
4. Agents discover, verify the hash, and install. Bundles are content-addressed: any mirror serves them, integrity is verifiable offline.

Discovery document — `GET https://{host}/.well-known/aktp.json`:

```json
{
  "aktp_node": 0,
  "name": "AI Hero",
  "operator_url": "https://www.aihero.dev",
  "feed_url": "https://www.aihero.dev/feed.json",
  "contact": "mailto:matt@aihero.dev"
}
```

A feed listing item:

```json
{
  "id": "evalite-basics",
  "title": "Evalite Basics",
  "original_author": "mattpocock",
  "license_spdx": "MIT",
  "source": {"type": "github", "owner": "mattpocock", "repo": "skills", "subpath": "evalite"},
  "bundle": {"url": "https://cdn.example/bundles/evalite-basics-1.2.0.tar.gz", "sha256": "9f2c..."},
  "purchase": {"mode": "free"},
  "content_type": "sh.logion.skill"
}
```

Canonical identity: `gh:owner/repo#subpath` when a repository exists, `node:{host}/{id}` when it doesn't.

Hosting is speech (permissionless): anyone runs a node with any content, any store rules, any payment rails. Indexing is reach (policy): appearing in an index is conditioned on that index's scanners and moderation. The authority rule: **the right to route payment is born from the claim, never from the crawl** — only a domain-verified owner can attach a purchase rail to their own content.

## Attestations — the trust core

An artifact accumulates attestations: signed statements about it that its author does not control — it passed these scanners, a human reviewed it, an eval scored it, a bounty improvement was accepted. The protocol freezes only the envelope (what is signed, how signatures verify). Which kinds of attestation exist is an open, reverse-DNS vocabulary: **any company can attest to any artifact under its own domain, no permission asked** — a security firm's audit, a compliance attestor's SOC2, a lab's benchmark score, an insurer's coverage. Logion mints its own under `sh.logion.*`. Verifiers ignore types they don't recognize; each index chooses which attestations carry ranking weight. Evidence is global, judgment is local, and no single authority is blessed.

## Layering

```text
format + evidence  = protocol   (global, open)
service + money    = node-local (each node, its own rails)
vocabulary         = namespace  (permissionless — owning a domain is owning a namespace)
```

Money never crosses nodes; improvements, evidence, and attestations do. The frozen core is tiny: canonical identity, content addressing, the attestation envelope, and the must-ignore rule (unknown fields ignored; unknown values degrade gracefully; only unknown protocol versions hard-fail, loudly and on purpose).

## Portable entitlements

AKTP sells access, so it defines a signed entitlement credential: the selling node signs (buyer, course, version) with its key; the credential travels with the buyer; any node verifies it offline against the origin node's public key. Refunds emit revocations on the node's event stream. Degradation chain: valid credential → serve; none at hand → ask the origin node; origin dead → verify against its archived key and serve from any hash-matching mirror. The purchase survives node death: buy at any node, install anywhere.

## The self-improving loop

Artifact published at any node → bounty opened (global format, node-local escrow) → anyone's agent contributes, evals prove → accepted and paid, recorded as a portable attestation → the improved version becomes the whole network's new baseline. Whoever joins today starts at today's level, never from zero. Bounties can never be disabled by a node — a creator chooses whether to fund them, never whether the community may open them. Divergence between original and community-improved versions is always disclosed.

## Stages

- v0 — indexed stores: well-known + feed spec, permissionless crawl, domain-verified claims route sales. No credential needed.
- v1 — signed feeds: per-node keys, signed feeds/manifests, node registry, readable attestations.
- v2 — portable entitlements: credentials + revocation + archived keys. Buy at any node, install anywhere.
- v3 — federation: node sync, mirrors, trust levels, cross-node reads. Cross-node payments stay out of the protocol, by design.

Status: the node-feed spec (v0) is in development in this repository. Logion's marketplace already runs on the protocol-ready foundations — immutable versions, content hashes, portable bundles. Logion operates the reference index and the first client; a position earned operationally, never imposed by the protocol.
