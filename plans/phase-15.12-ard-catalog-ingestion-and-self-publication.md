<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.12 — ARD catalog ingestion and self-publication

> **Dogfood — Level 3 (discovery):** Logion publishes its own ARD catalog, consumes it with the same adapter used for third parties, and verifies zero duplicate resources after real acquisition/feedback already work.
> **After this phase:** ARD is the discovery plane for Logion resources; existing hub crawlers are ingestion adapters, not a competing protocol.
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

Adopt ARD instead of extending AKTP into discovery.

## Dogfood prompt for the implementing agent

```text
Implement Phase 15.12 while using a Logion resource about protocol design, JSON
Schema, catalog/indexer design, or interoperability. Start with
`logion recall search "JSON schema protocol catalog interoperability" --limit 5`.
On LOW/NONE, search the store with
`logion listings search --query "JSON schema protocol interoperability" --include-indexed --limit 5 --json`.
Inspect the best exact resource/version and follow the mandatory native-or-Logion
acquisition/reconciliation protocol.
Use the acquired resource to critique the ARD codec, pagination, unknown-field handling,
identity normalization, and conformance fixtures. Record the exact suggestions
used in `artifacts/dogfood/phase-15.12.md`. After the implementation passes its
self-crawl, submit one generic `feedback submit` report for the exact resource/version
actually used and record its Course projection disposition.
```

## Spec source and version pin

- Before coding, link the exact upstream ARD specification revision and fixtures in this file/PR. Never implement from this plan's paraphrase alone.
- Put version-specific wire models under `logion/packages/indexer/logion_indexer/ard/v0_9/` (or the actual current version) and a small dispatcher in `ard/codec.py`.
- Unknown optional fields must round-trip in an `extensions` mapping; unsupported major versions fail with `ard_version_unsupported`.

## Concrete file plan

### Public repository

- Add `logion_indexer/adapters/ard.py`, `ard/codec.py`, versioned schemas/models, `ard/conformance.py`, and fixture documents under `packages/indexer/tests/fixtures/ard/`.
- Extend `adapters/base.py`, `models.py`, `pipeline.py`, `dedup.py`, and `pusher.py` to emit generic resources from 15.9.
- Add CLI `logion-indexer crawl --adapter ard --entrypoint URL` and `validate-ard FILE|URL` with machine-readable diagnostics.
- Add `logion/packages/client/.../_resources/resources.py` support for source filters if 15.9 did not already include them.

### Private repository

- Add `api/ard/controllers/catalog.py`, `services/build_catalog.py`, `responses.py`, and router registration in `api/main.py`.
- Serve the spec-mandated well-known path plus catalog pages. Build entries exclusively from `Resource`/`ResourceVersion` rows; never serialize `IndexedListing` directly.
- Add settings for public origin, page size (hard max 100), enabled resource types, evidence-link feature flag, and cache TTL.
- ETag is a stable digest of the canonical response page. Honor `If-None-Match`; cache must never mix origins or cursors.
- Add an operator self-crawl job handler in `api/jobs/handlers/` only if it fits the existing job runner; otherwise keep it in the indexer deployment. Do not make API requests recursively from request handlers.

## Identity and ingestion algorithm

```text
fetch well-known with HTTPS, timeout, size limit, redirects <= 3
validate content type + ARD major version
for each catalog page:
  verify cursor loop has not occurred
  parse entries without executing or downloading weights
  normalize type and canonical URI
  resolve version digest; quarantine entries without required immutable identity
  upsert Resource + Source + Version through the 15.9 service
  record source attribution and import outcome
stop at configured page/resource/byte budgets
```

SSRF policy: reject private, loopback, link-local, metadata-service, non-HTTP(S), credential-bearing URLs, DNS rebinding, and cross-host redirects unless the host is explicitly allowlisted for the self-crawl test. Reuse any existing safe URL helper; do not create a weaker second implementation.

## API/CLI outputs

- Catalog entries expose ARD ID, type, canonical URI, version/digest, media type, title/description, source/provenance links, and optional evidence endpoint relation.
- Import report exposes `seen`, `created`, `matched`, `new_versions`, `quarantined`, `errors_by_code`, cursor, source, and duration.
- CLI exits 0 only when the document is conformant; partial import with quarantines is a nonzero documented exit unless `--allow-quarantine` is explicit.

## Tests and fixtures

- Golden encode/decode against the pinned upstream examples.
- Unknown-field preservation, unsupported major, malformed cursor, cursor loop, duplicate ID, changed digest, missing digest, oversized page, timeout, redirect, and SSRF fixtures.
- Self-publication integration: start local API, crawl its ARD endpoint twice, assert first expected matches/backfill and second zero creates/zero new versions.
- Projection regression: old listing/skills search results do not disappear.
- OpenAPI and client generation checks.

## Rollout/observability

- Feature flags: `ard_catalog_public`, `ard_ingestion`, and per-source allowlist.
- Metrics: fetch latency/status, entries/page, quarantines by code, identity conflicts, duplicate rate, self-crawl drift.
- Start with Logion self-crawl and one manually approved external catalog; expand only after seven clean scheduled runs.

## Build

- Implement the current ARD catalog document and resource descriptor shapes behind versioned codecs.
- Publish Logion's catalog at the ARD well-known endpoint with pagination, stable IDs, types, canonical URIs, version digests, and optional trust/evidence links.
- Add an ARD indexer adapter using the existing discover/enrich/validate/mirror/upsert pipeline.
- Translate Smithery, GitHub skill sources, MCP registries, and Hugging Face metadata into the generic resource model while preserving source attribution.
- Add conformance fixtures from the ARD spec and a self-crawl test against a locally served Logion catalog.
- Expose `logion resources search|get` and SDK equivalents; existing `skills search` remains a filtered projection.

## Operational dogfood

Run a scheduled self-crawl in staging. Fail the job on duplicate identity, digest drift without a new version, invalid ARD output, or projection disagreement.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_12_ard_self_crawl`.

- **Actors/seed:** `node_operator` and clean `consumer`.
  `make proving-ground-seed SCENARIO=phase_15_12` publishes one resource absent
  from the consumer index and serves the real local ARD endpoint; a static
  second source contains one valid and one malformed record.
- **Operator prompt:** “Publish this node's catalog through ARD, add it as a
  catalog source, crawl it twice, and report accepted/rejected entries without
  touching the database.”
- **Consumer prompt:** “Find Fixture Linter, explain which ARD node advertised
  it, and inspect its canonical source.”
- **Assertions to implement:** `api.ard_document_valid`,
  `api.catalog_crawl_completed`, `api.ard_resource_ingested`,
  `api.ard_record_rejected`, `api.self_crawl_no_duplicate`, and
  `api.resource_source_provenance_visible`.
- **Negative/evidence:** malformed input is quarantined with a stable reason;
  crawl two adds zero records. Retain ARD documents/version, crawl counters,
  canonical ID/source, fixture digests, and no-500 proof.

## Acceptance gates

- A clean node can discover the staging catalog using only its ARD entry point.
- Self-crawl is idempotent and emits an auditable import report.
- ARD validation failures are quarantined, not silently normalized.
- Search can filter by resource type and source.
- No AKTP endpoint is required to discover a resource.
