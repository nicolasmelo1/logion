<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.12 — AI Catalog publication and ARD discovery

> **Dogfood — Level 3 (discovery):** Logion publishes a conformant AI Catalog,
> exposes/searches it through ARD, consumes both paths with production adapters,
> and verifies zero duplicate resources after acquisition/feedback already work.
> **After this phase:** AI Catalog is the typed publication/index format; ARD is
> the intent-oriented discovery protocol and registry interface built over AI
> Catalog entries. Existing hub crawlers remain ingestion adapters.
> **Honesty boundary:** discovery proves addressability, not quality, safety, or performance.

## Mandatory dogfood protocol

The phase-specific prompt below is implementation work, not optional documentation. The implementing agent must exercise the interoperable resource loop delivered by 15.10–15.11:

1. run local recall, then `logion listings search --query "SEARCH_QUERY" --include-indexed --limit 5 --json` only on LOW/NONE;
2. inspect the exact `ResourceVersion`, distributions, evidence, permissions, license, and acquisition plan—not only a Course projection;
3. obtain explicit approval, run `logion resources acquire RESOURCE_ID --version VERSION_ID --scope repo-root --channel auto --dry-run --json`, then acquire through the recommended Logion or native channel;
4. run `logion resources reconcile --scope repo-root --json` and require exact version attribution;
5. use the resource in the normal harness on this phase's real task and verify it appears in `logion usage pending --json`;
6. submit exactly one intentional post-task report:

```bash
logion feedback submit RESOURCE_ID VERSION_ID \
  --rating 1..5 \
  --usefulness 0.0..5.0 \
  --reliability 0.0..5.0 \
  --tool-safety 0.0..5.0 \
  --token-efficiency 0.0..5.0 \
  --completed-task \
  --task-class TASK_CLASS \
  --body "One or two resource-focused sentences; no private repository data" \
  --json
```

Use `--not-completed-task` when appropriate. Record the feedback ID and `course_review_projection` disposition. A native external installation is valid dogfood; Logion must not require reinstalling it. If acquisition, exact attribution, consent, or actual use is absent, record the blocker and **do not submit feedback/review**. Passive observation alone never justifies a rating.

## Goal

Adopt the AI Catalog data model and ARD discovery protocol instead of extending
AKTP into catalog publication or search.

## Normative layering

```text
AI Catalog
  typed/nestable JSON catalog + entries + host/publisher/trust metadata
  served at /.well-known/ai-catalog.json or another allowed location
             ↓ indexed/consumed by
ARD
  pre-invocation discovery protocol and registry APIs
  asks “what resource is available for this task?”
             ↓ returns AI Catalog entries/references
native protocol
  MCP, A2A, Agent Skills, plugin, OpenAPI, model host, or other runtime

AKTP (Logion proposal)
  optional evidence/improvement events linked to the stable resource identity
```

AI Catalog and ARD are complementary but distinct specifications. The
implementation must not call an AI Catalog document an “ARD schema”, pretend
ARD replaces AI Catalog, or put Logion evidence semantics into either base
specification.

## Dogfood prompt for the implementing agent

```text
Implement Phase 15.12 while using a Logion resource about protocol design, JSON
Schema, catalog/indexer design, or interoperability. Start with
`logion recall search "JSON schema protocol catalog interoperability" --limit 5`.
On LOW/NONE, search the store with
`logion listings search --query "JSON schema protocol interoperability" --include-indexed --limit 5 --json`.
Inspect the best exact resource/version and follow the mandatory native-or-Logion
acquisition/reconciliation protocol.
Use the acquired resource to critique the AI Catalog codec and Trust Manifest,
the ARD search/registry adapter, pagination, unknown-field handling, identity
normalization, and both conformance suites. Record the exact suggestions
used in `artifacts/dogfood/phase-15.12.md`. After the implementation passes its
self-crawl, submit one generic `feedback submit` report for the exact resource/version
actually used and record its Course projection disposition.
```

## Spec sources and independent version pins

- AI Catalog documentation/specification: <https://ai-catalog.io/> and
  <https://ai-catalog.io/specification/>.
- ARD documentation/specification: <https://agenticresourcediscovery.org/>.
- Official client connectors and shared Agent Finder directory:
  <https://github.com/ards-project/ard-connectors> and
  <https://github.com/ards-project/ard-connectors/blob/main/agent-finders.json>.
- Before coding, pin exact upstream commits/releases and fixtures for **both**
  specifications. Never implement from this plan's paraphrase.
- Put AI Catalog models under
  `logion_indexer/ai_catalog/v1_0/` (or pinned current version) and ARD models
  under `logion_indexer/ard/v0_9/`; their dispatchers, version negotiation,
  errors, and fixture suites remain separate.
- Unknown optional fields follow each specification's must-ignore/extension
  rules. Errors distinguish `ai_catalog_version_unsupported` from
  `ard_version_unsupported`.

## Bootstrap discovery through `ard-connectors`

Implementing ARD codecs without knowing any Agent Finder endpoint produces an
empty discovery product. Logion therefore consumes the upstream
`ards-project/ard-connectors` directory as a versioned **indexer control-plane
source**.

It is not installed into the Logion CLI, companion, customer harness, or
`~/.agentfinder`. Those client connectors are useful upstream reference
implementations, but Logion's scheduled indexer queries Agent Finders
server-side and exposes resulting resources through its existing catalog/search.

### Snapshot contract

Fetch `agent-finders.json` by an immutable GitHub commit, initially validating
the current shape:

```json
{
  "selected": null,
  "finders": [
    {
      "id": "github",
      "name": "GitHub Agent Finder",
      "description": "...",
      "search": "https://agentfinder.github.com/api/v1/search",
      "mcp": "https://agentfinder.github.com/api/v1/mcp"
    }
  ]
}
```

- `selected` is a connector-side user preference and is ignored by the
  indexer. Logion queries every operator-enabled finder; it never silently
  chooses the upstream selected value.
- Store upstream repository, commit SHA, file digest, fetched/activated time,
  schema version, validation result, and last-good snapshot.
- A scheduled refresh compares the newest upstream commit with last-good.
  Added/changed hosts enter `pending_operator_approval`; removed finders stop
  new crawls but retain historical source provenance.
- Malformed or unreachable updates never erase last-good. Surface snapshot age
  and `fresh|stale|rejected` status.
- Do not vendor endpoint credentials. Finder auth, if later supported, uses
  operator-managed secret references outside the snapshot.

### Agent Finder query contract

For each enabled finder, use the upstream canonical request:

```http
POST <finder.search>
Content-Type: application/json

{"query":{"text":"<bounded discovery query>","filter":{"type":["..."]}}}
```

The scheduler starts with explicit query families/resource types rather than an
unbounded crawler. Preserve finder ID, endpoint, snapshot commit/digest, query
text digest, filters, retrieval time, referrals, raw result digest, relevance
score/explanation, and returned AI Catalog entry identity.

Relevance score means match quality only. It never becomes Logion trust,
safety, review, or evaluation evidence.

If a response includes referrals to other Agent Finders, record them as
untrusted candidates. Query only after the same endpoint validation and
operator approval used for directory additions; cap referral depth, fanout,
total requests, entries, and bytes.

## Concrete file plan

### Public repository

- Add `logion_indexer/adapters/ai_catalog.py`,
  `ai_catalog/{codec,conformance}.py`, versioned models, and official fixtures.
- Add `logion_indexer/adapters/ard.py`, `ard/{client,codec,conformance}.py`,
  versioned request/response models, and official ARD fixtures.
- Add `logion_indexer/sources/ard_connectors.py` for immutable snapshot fetch,
  schema validation, diff/approval, and last-good activation.
- Add `logion_indexer/sources/agent_finders.py` for bounded multi-finder
  scheduling, referral candidates, source receipts, and result normalization.
- Extend `adapters/base.py`, `models.py`, `pipeline.py`, `dedup.py`, and `pusher.py` to emit generic resources from 15.9.
- Add CLI `logion-indexer crawl --adapter ai-catalog --entrypoint URL`,
  `validate-ai-catalog FILE|URL`, `search --adapter ard --registry URL`, and
  `validate-ard FILE|URL`.
- Add operator CLI `logion-indexer ard-connectors sync|diff|approve|status`
  and `agent-finders run --finder ID|all --query-family FAMILY --dry-run`.
  These are indexer/operator commands, not customer CLI installation commands.
- Add `logion/packages/client/.../_resources/resources.py` support for source filters if 15.9 did not already include them.

### Private repository

- Add `api/ai_catalog/controllers/get_catalog.py`,
  `services/build_catalog.py`, response types, and router registration.
- Serve `/.well-known/ai-catalog.json` and any separately pinned conformance
  discovery mechanisms. Build entries from `Resource`/`ResourceVersion`; never
  serialize `IndexedListing` directly.
- Add the ARD registry/search surface under `api/ard/` only from the pinned ARD
  spec. Do not conflate its search responses with the AI Catalog document.
- Persist source snapshot/run metadata and expose admin/operator status without
  leaking secrets or allowing arbitrary public URLs.
- Add settings for public origin, page size (hard max 100), enabled resource types, evidence-link feature flag, and cache TTL.
- ETag is a stable digest of the canonical response page. Honor `If-None-Match`; cache must never mix origins or cursors.
- Add an operator self-crawl job handler in `api/jobs/handlers/` only if it fits the existing job runner; otherwise keep it in the indexer deployment. Do not make API requests recursively from request handlers.

## Identity and ingestion algorithm

```text
fetch AI Catalog with HTTPS, timeout, size limit, redirects <= 3
validate AI Catalog media type/specVersion and conformance level
for each catalog page:
  verify cursor loop has not occurred
  parse entries without executing or downloading weights
  normalize type and canonical URI
  resolve version digest; quarantine entries without required immutable identity
  upsert Resource + Source + Version through the 15.9 service
  record source attribution and import outcome
stop at configured page/resource/byte budgets

optionally query an approved ARD registry:
  validate ARD request/response version and scores as registry-supplied metadata
  extract returned AI Catalog entries/references
  feed them through the same AI Catalog identity/validation path
```

The first scheduled run queries the GitHub Agent Finder and Hugging Face
Discover entries supplied by the pinned `agent-finders.json`, subject to
operator approval and health checks. A resource returned by both becomes one
canonical resource with two discovery-source edges, not duplicate listings.

SSRF policy: reject private, loopback, link-local, metadata-service, non-HTTP(S), credential-bearing URLs, DNS rebinding, and cross-host redirects unless the host is explicitly allowlisted for the self-crawl test. Reuse any existing safe URL helper; do not create a weaker second implementation.

## API/CLI outputs

- AI Catalog entries preserve `identifier`, media `type`, `url|data`, host,
  publisher, versions/tags, nesting, and Trust Manifest according to the pinned
  schema. Never invent an “ARD ID” when the identity is an AI Catalog entry
  identifier such as a domain-anchored `urn:air:` value.
- ARD results preserve registry origin, query, filters, returned entry,
  registry-supplied relevance score/explanation, and referral metadata. A
  relevance score is not trust or Logion evidence.
- Import report exposes `seen`, `created`, `matched`, `new_versions`, `quarantined`, `errors_by_code`, cursor, source, and duration.
- CLI exits 0 only when the document is conformant; partial import with quarantines is a nonzero documented exit unless `--allow-quarantine` is explicit.

## Tests and fixtures

- Separate golden encode/decode against pinned AI Catalog and ARD examples.
- Recorded `ard-connectors` fixtures for current shape, unknown fields,
  duplicate IDs, invalid/search host change, removal, last-good rollback, stale
  snapshot, and operator approval.
- Recorded Agent Finder request/response fixtures for GitHub and Hugging Face;
  exact POST body, pagination/referral behavior, relevance-only labeling,
  timeout/rate-limit/5xx, malformed entry, and cross-finder deduplication.
- Prove no connector files, Agent Finder preference, or `~/.agentfinder` state
  are written by the Logion client/companion.
- AI Catalog Minimal/Discoverable/Trusted conformance, nested catalogs,
  `url`/inline `data` exclusivity, media types, Trust Manifest verification,
  poisoning/typosquatting cases, and version compatibility.
- ARD request/search/explore/browse behavior required by the pinned revision,
  registry referrals/federation limits, and conversion through AI Catalog
  entries without identity loss.
- Unknown-field preservation, unsupported major, malformed cursor, cursor loop, duplicate ID, changed digest, missing digest, oversized page, timeout, redirect, and SSRF fixtures.
- Self-publication integration: start local API, fetch/crawl its real AI Catalog
  twice, then discover the same entry through its real local ARD service; assert
  one canonical resource/version and zero duplicate creation.
- Deterministic E2E uses a local conformant Agent Finder fixture derived from
  the upstream contract. An opt-in staging smoke queries at least one live
  upstream-listed finder and records availability/schema drift without making
  external uptime a deterministic CI dependency.
- Projection regression: old listing/skills search results do not disappear.
- OpenAPI and client generation checks.

## Rollout/observability

- Feature flags: `ai_catalog_public`, `ai_catalog_ingestion`,
  `ard_discovery`, `ard_connectors_sync`, and per-finder/query-family allowlists.
- Metrics: fetch latency/status, entries/page, quarantines by code, identity conflicts, duplicate rate, self-crawl drift.
- Metrics additionally include snapshot age/diff status, enabled finders,
  finder query success/rate limits, referrals pending approval, results and
  exact/ambiguous deduplication. Never include user prompts.
- Start with Logion self-crawl and one manually approved external catalog; expand only after seven clean scheduled runs.
- Activate the pinned GitHub/Hugging Face Agent Finders only after a reviewed
  dry-run. Expand connectors only from reviewed snapshot diffs.

## Build

- Implement the current AI Catalog schema/Trust Manifest and ARD protocol behind
  independently versioned codecs.
- Publish Logion's AI Catalog at `/.well-known/ai-catalog.json`.
- Add AI Catalog ingestion plus an ARD discovery adapter using the existing
  discover/enrich/validate/mirror/upsert pipeline.
- Synchronize and pin `ard-connectors/agent-finders.json`; query enabled Agent
  Finders from the indexer and preserve per-finder discovery provenance.
- Translate Smithery, GitHub skill sources, MCP registries, and Hugging Face metadata into the generic resource model while preserving source attribution.
- Add official conformance fixtures from both specs and a self-crawl/search test
  against the locally served Logion catalog and ARD service.
- Expose `logion resources search|get` and SDK equivalents; existing `skills search` remains a filtered projection.

## Operational dogfood

Run a scheduled self-crawl in staging. Fail the job on duplicate identity, digest drift without a new version, invalid ARD output, or projection disagreement.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_12_ai_catalog_ard_self_crawl`.

- **Actors/seed:** `node_operator` and clean `consumer`.
  `make proving-ground-seed SCENARIO=phase_15_12` publishes one resource absent
  from the consumer index and serves the real local AI Catalog plus ARD
  service; a local conformant Agent Finder plus pinned `agent-finders.json`
  fixture returns one valid, one duplicate-from-two-finders, one referral, and
  one malformed record.
- **Operator prompt:** “Publish this node's AI Catalog, add it as a catalog
  source, synchronize the official Agent Finder directory, approve the fixture
  endpoints, query all enabled finders, crawl twice, then expose/search the same
  entries through ARD. Report accepted/rejected entries without touching the
  database or installing connectors in the client.”
- **Consumer prompt:** “Find Fixture Linter through ARD, identify the registry
  and original AI Catalog publisher/entry, and inspect its canonical source.”
- **Assertions to implement:** `api.ai_catalog_document_valid`,
  `api.ai_catalog_conformance_level_valid`,
  `api.ard_search_response_valid`,
  `api.ard_connectors_snapshot_pinned`,
  `api.agent_finders_queried`,
  `api.agent_finder_result_provenance_visible`,
  `files.client_has_no_ard_connector_install`,
  `api.catalog_crawl_completed`, `api.ard_resource_ingested`,
  `api.ard_record_rejected`, `api.self_crawl_no_duplicate`, and
  `api.resource_source_provenance_visible`.
- **Negative/evidence:** malformed input is quarantined with a stable reason;
  crawl two and ARD discovery add zero duplicates. Retain both spec
  versions/commits, AI Catalog document, ARD request/response, crawl counters,
  canonical identifier/source, fixture digests, and no-500 proof.

## Acceptance gates

- A clean client can consume the staging AI Catalog directly and discover the
  same resource through the staging ARD service.
- The indexer synchronizes a pinned upstream `agent-finders.json`, queries every
  enabled approved finder, and makes at least one resulting resource searchable.
- No ARD connector package or finder preference is installed into customer
  clients/harnesses.
- Cross-finder duplicate results converge on one canonical resource while
  preserving all discovery-source edges.
- Self-crawl is idempotent and emits an auditable import report.
- AI Catalog and ARD failures have separate stable error codes and quarantine.
- Search can filter by resource type and source.
- No AKTP endpoint is required to discover a resource.
