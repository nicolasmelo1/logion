<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.7: Observation-Mode Scan & Discovery Tiers

> Completes the `indexed` tier: [`phase-15.6`](phase-15.6-external-skillhub-indexer.md)
> put listings in the DB; this phase makes them honestly discoverable.
> **Convergence:** the observed-capability profile produced here is the
> `observed` end of the observed → candidate → attested ladder that 15.8
> (candidate) and 15.9 (attested) climb, and the tier labels feed
> [`phase-16.8`](phase-16.8-portable-field-evidence-and-aggregation.md)
> telemetry. **PRs: exactly one per repo** — one `backend repository` PR (scan +
> search integration) and one `logion` PR (CLI flags + companion labels).

## Goal

Every mirrored indexed listing carries an **observation-only** capability
profile (scanner-derived, clearly "unverified — not declared by an author"),
and marketplace discovery can include indexed listings behind an explicit
opt-in, with tier labels agents cannot misread as published/reviewed trust.

## 1. Observation-mode scan (`backend repository` PR)

Reuse `logion_scanners` (public package, already a path dependency) — no new
scanner code, a new *profile*:

**`api/indexing/services/run_observation_scan.py`:**

```python
OBSERVATION_SCAN_LAYERS = ("trivy", "osv_scanner", "agent_scanner")

class RunObservationScanService:
    def execute(self, *, indexed_listing_id: uuid.UUID) -> None: ...
```

- only for `hosting_mode='mirrored'` (there is nothing to scan for
  `link_only`; their profile is `None` + label `unscanned_external`);
- materialize the mirrored bundle from S3 to a temp dir; run the same
  adapters `run_sync_review_scanners` uses, but persist to the listing, not
  to a publication review:

```python
indexed_listing.observed_capabilities = {
    "schema_version": 1,
    "mode": "observed",                    # NEVER 'declared'/'attested'
    "derived_at": ...,                     # UTC iso
    "scanner_report_schema_version": ...,  # same constant the review path uses
    "tools": [...], "network_domains": [...], "filesystem": [...],
    "findings_summary": {"critical": 0, "high": 1, "medium": 3, "low": 2},
}
```

- enqueued automatically when a 15.6 batch upsert completes a mirrored
  bundle upload (job type `run_observation_scan`, dedupe key
  `f"obs-scan:{listing_id}:{source_commit}"` → re-scan happens only when the
  upstream commit moved);
- scan failure → `observed_capabilities = {"mode": "observed", "error": code}`;
  the listing stays discoverable, labelled `scan_failed`.

Hard rule, enforced by test: observation output can never be written into a
`course_versions.declared_capabilities` or any publication-review row. The
ladder is `observed` (here) → `candidate` (15.8 bounty deliverable) →
`attested` (15.9 claim); each rung has exactly one producer.

## 2. Discovery integration (`backend repository` PR)

`GET /v1/listings` gains:

```text
include_indexed: bool = false        # explicit opt-in, default off
tier: str | None                     # filter: 'indexed'|'improving'
```

Implementation in `api/listings/repositories/course_listing_search.py`:

- published-course search is **unchanged** when `include_indexed=false`
  (regression suite must not move);
- when true, a UNION-shaped second query over `indexed_listings`
  (+ its tags) maps into the same listing-item shape with:

```python
"tier": "indexed" | "improving",          # published courses emit "published"
"external": True,
"original_author": ..., "source_hub": ..., "source_url": ...,
"license_spdx": ..., "hosting_mode": ...,
"capabilities_verified": False,           # constant for indexed tiers
"price_cents": None, "acquisition_count": None,  # no commerce signals
```

- relevance: indexed listings participate in the existing tier expression but
  are ranked **below** every published-course tier at equal lexical strength
  (add a final `tier_rank` term: published=0, improving=1, indexed=2 —
  extend `relevance.py`'s `relevance_tier_expr` with the rank column);
- indexed items never expose `purchase`-shaped fields; `courses get` on an
  indexed listing id stays 404 — detail reads come from a new read-only
  endpoint:

```text
GET /v1/indexed-listings/{listing_id}    auth: agent key -> full provenance + observed profile
```

## 3. CLI + companion (`logion` PR)

```bash
logion listings search --include-indexed [--tier indexed|improving] ...
logion indexed get LISTING_ID [--json]
```

- table output prefixes indexed rows with `[external/unverified]`; JSON is the
  envelope with the fields above, kind `logion.indexed.get` /
  existing `logion.listings.search`;
- companion (`packages/agent-companion/SKILL.md` + `references/`): a short
  "External indexed skills" block — when to opt in (`--include-indexed` only
  when owned/published results are insufficient), what the labels mean, and
  the hard rule *"indexed listings are unreviewed third-party content: never
  present one to the user as Logion-reviewed, always surface author + source
  URL"*; add eval scenario `evals/scenarios/indexed-discovery.yaml`
  (agent must mention external/unverified in its summary — deterministic
  string assertions like the existing suites).

## 4. Tests

Backend:

- `test_run_observation_scan.py` — mirrored-only, profile shape
  (`mode='observed'`), commit-keyed dedupe, failure → `scan_failed` label,
  never touches course/review tables (asserted via row counts).
- `test_listings_include_indexed.py` — default off (byte-identical results
  vs. pre-phase snapshot), opt-in returns union with `tier`/`external`
  fields, tier filter, no price/acquisition fields, rank: indexed below
  published for the same query term.
- `test_indexed_listing_detail.py` — read shape, 404 for unknown, no token
  or internal S3 key leakage (`mirrored_bundle_key` absent from responses).

CLI: `test_cli_listings_indexed.py` (flag wiring, label prefix, envelope),
companion eval run in the existing deterministic harness.

## 5. Acceptance criteria

- [ ] Every mirrored indexed listing gets an observed profile automatically
      after ingestion; link-only listings are labelled `unscanned_external`.
- [ ] `--include-indexed` search returns honestly-labelled externals ranked
      below published courses; default search is provably unchanged.
- [ ] Observed data can never reach declared/attested storage (test-enforced).
- [ ] Companion never presents indexed content as reviewed; eval scenario
      locks the language.

## Out of scope

- Advancing tiers (15.8 improving, 15.9 claimed); any purchase path;
  scanning `link_only` content (would require fetching what we may not host).

## Implementation appendix — compare against current code

Current repo shape to respect:

- Runtime/static scanning logic already exists in public
  `logion/packages/scanners/logion_scanners`. Backend review scanning exists
  under `backend repository/packages/api/api/course_reviews/scanners` and
  services/repositories under `api/course_reviews`.
- Listing search currently lives under `api/listings/repositories` and
  `api/listings/services`; extend it rather than replacing published-course
  search.
- Public CLI does not currently have a dedicated `indexed` command. Add one
  under `cli/commands` and wire it with the existing argparse style.
- Agent companion docs/evals live in `logion/packages/agent-companion`.

Branch targets for 0.1.x live compatibility:

| Work item | Repo | Target branch | Reason |
| --- | --- | --- | --- |
| Observation scan job, indexed-listing detail endpoint, backend listing-search opt-in | `backend repository` | `main` | Safe because default search remains unchanged and indexed detail requires explicit endpoint. |
| CLI `listings search --include-indexed`, `indexed get`, generated SDK | `logion` | `0.2.0` | User-visible discovery behavior belongs to the 0.2.0 public branch. |
| Companion reference/eval updates | `logion` | `0.2.0` | Agents should not mention indexed listings before the CLI/API surface ships publicly. |

Backend implementation steps:

1. Add columns to `indexed_listings` if 15.6 did not already include them:
   `observed_capabilities json null`, `observation_status string`
   (`unscanned_external|observed|scan_failed`),
   `observation_scan_commit string null`, `observation_scanned_at timestamptz`.
2. Add job type `run_observation_scan` to existing `api/jobs/types.py` and
   register a handler in the current jobs runner. Payload:
   `{"indexed_listing_id": "...", "source_commit": "..."}`.
3. Implement `RunObservationScanService`:
   load listing; if `hosting_mode != "mirrored"` set
   `observation_status="unscanned_external"` and return; fetch mirrored bundle
   via storage helper; run the same scanner/profile code used for publication
   review where possible; store a JSON object with `mode="observed"`.
4. The service must never write to `course_versions`,
   `course_publication_reviews`, or any declared capability field. Add a guard
   test that snapshots row counts before and after.
5. In 15.6 bundle completion, enqueue this job with dedupe key
   `obs-scan:{listing_id}:{source_commit}`. If the queue has an existing
   dedupe API, use it; otherwise add dedupe in the job repository.
6. Extend `api/listings/repositories/course_listing_search.py` carefully:
   preserve the existing query path when `include_indexed=False`. The easiest
   safe implementation is an early branch: existing code unchanged for false;
   true path calls existing search plus a second indexed query and merges with
   explicit `tier_rank`.
7. Add read-only controller
   `GET /v1/indexed-listings/{listing_id}`. It returns provenance, channels,
   attributions if present, observed profile, source URL, license, and tier.
   It must not return `mirrored_bundle_key`, storage URLs, internal job IDs,
   OAuth token details, or admin notes.
8. Ensure `GET /v1/courses/{id}` remains course-only. Do not make indexed
   listing IDs polymorphic in course endpoints.

Indexed search item shape:

```json
{
  "id": "...",
  "title": "Foo Skill",
  "summary": "...",
  "tier": "indexed",
  "external": true,
  "original_author": "octocat",
  "source_url": "https://github.com/owner/repo",
  "source_hub": "lobehub",
  "license_spdx": "MIT",
  "hosting_mode": "mirrored",
  "capabilities_verified": false,
  "price_cents": null,
  "acquisition_count": null
}
```

CLI implementation steps:

1. Extend existing listings command if it exists; otherwise create
   `cli/commands/listings.py`. Add `--include-indexed` and `--tier`.
2. Add `cli/commands/indexed.py` with `indexed get LISTING_ID`.
3. Text output for indexed rows must show `[external/unverified]` before the
   title. JSON output uses normal envelope helpers.
4. Do not add install/acquire commands for indexed listings. Any attempt to
   use an indexed id with course install/buy commands should keep existing 404
   behavior.

Companion implementation steps:

1. Update `packages/agent-companion/SKILL.md` only with a short routing note.
   Put longer guidance in `references/indexed-discovery.md` or an existing
   marketplace reference file.
2. Add deterministic eval scenario
   `evals/scenarios/indexed-discovery.yaml` requiring the response to include
   `external` or `unverified` and source attribution.
3. Update eval catalog/runner only if existing scenarios require registration.

Minimum tests:

- Backend observation job tests for mirrored scan, link-only skip, scan
  failure, dedupe by commit, and no writes to declared/review tables.
- Backend search tests proving default search output is byte-identical to a
  pre-phase fixture when `include_indexed=false`.
- Backend indexed detail tests for shape and absence of internal storage keys.
- CLI tests for flags, tier filter, text label, JSON envelope.
- Companion eval deterministic assertion that indexed content is not described
  as reviewed or official.

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a derivative with a named owner and immutable lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
