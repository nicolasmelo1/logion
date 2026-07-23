<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.6: External Skillhub Indexer — Public Crawler App + Dumb Ingestion API

> Builds the `indexed` tier of indexed → improving → claimed (workspace
> `README.md` "Thesis, strategy, and decided boundaries"; protocol hooks in
> [`future-roadmap/protocol-ready-architecture.md`](../future-roadmap/protocol-ready-architecture.md)).
> Depends on 15.1 (GitHub API client conventions) and 15.3's
> `logion/packages/skillmap` (`logion-skillmap`) — skill-root detection and
> map inference are **not reimplemented here**; the indexer consumes
> `logion_skillmap.infer()` and every indexed listing is upserted **with
> its inferred package map attached**.
> **PRs: exactly one per repo** — one `logion` PR (the new **public**
> `packages/indexer` app: adapters, crawling, GitHub resolution, dedup) and
> one `backend repository` PR (schema + dumb batch-upsert ingestion API + audit).

## Architecture decision (the weight is in the client)

Every skill on every hub ultimately links back to a GitHub repository — hubs
(skills.sh, ClawHub, LobeHub, browse.sh) are aggregators, and so are we. So:

```text
logion-indexer (PUBLIC app, operator-run, operator credentials)
  ├─ hub adapters: crawl/parse hub pages & indexes
  ├─ github resolver: hub page -> linked owner/repo[#subpath]
  ├─ canonicalizer + dedup: one skill == one canonical GitHub identity,
  │    N discovery channels; skip what Logion already has
  └─ pusher: batch-upsert to the Logion admin API
        │
        ▼
Logion API (PRIVATE, deliberately DUMB here)
  ├─ validates + persists indexed_listings / discovery channels
  ├─ stores mirrored bundles (license-gated, DB constraint)
  └─ audits ingestion runs; enqueues 15.7 observation scans
```

- **`logion/packages/indexer`** is a new public Python package
  (`logion-indexer` console script). Public on purpose: the adapter framework
  is useful to others; there are no secrets in code — the operator supplies
  credentials via env (`LOGION_INDEXER_GITHUB_TOKEN`,
  `LOGION_INDEXER_API_KEY` = an **admin** agent key, `LOGION_BASE_URL`).
  Public-repo boundary holds: it talks to `api.logion.sh` through the public
  wire contract only, zero `backend repository` references.
- **The backend API is dumb**: no crawling, no hub knowledge, no GitHub
  resolution server-side. It validates payload shape, enforces provenance/
  license invariants (DB constraints), stores, audits. All intelligence and
  all breakage-prone surface (HTML parsing, rate limits) live in the client,
  where a broken adapter is a patch release — not a backend deploy.

## Frontend consequence

Because the canonical source is always the GitHub repo, discovery surfaces
show **GitHub as the source** (`source_url` = the repo/subpath), with hub
badges as secondary "seen on: LobeHub, skills.sh" chips from the discovery
channels. Hubs are never presented as authors.

## Ethical boundary (hard requirements, tested)

Aggregation **with attribution and a source link** — the legitimate model.
Explicitly rejected and structurally prevented: scraping-to-disguise,
paraphrase-to-hide-origin, fake authorship, fake accounts. Every indexed
listing stores non-null: original author (GitHub owner), source URL, license.
No owner agent, no entitlement, never `published`, never purchasable.
Crawl discipline in every adapter: respect `robots.txt`, identified
User-Agent (`logion-indexer/x.y (+https://logion.sh)`), per-host rate limit
(default 1 req/s, `--rps` cap), ETag/Last-Modified cache.

## Trust model: provenance trust ≠ safety trust

- **Provenance trust** ("who wrote this, which license, which commit"):
  GitHub answers natively — commit-addressed content, author = repo owner,
  machine-readable license. That justifies automatic crawl + mirror (license
  permitting): `source_verification='github_native'`. Hub badges (ClawHub
  "verified" etc.) are captured per **discovery channel** as `hub_verified` —
  a displayed signal produced by criteria we do not audit.
- **Safety trust** ("is this safe to run"): **always ours.** No
  `source_verification` value skips or weakens the 15.7 observation scan.
  `anthropics/skills` and an anonymous hub page get the identical scanner
  profile and the identical "unverified" label until claimed and reviewed.
  Verification metadata may influence ranking/display — never gating
  (test-pinned in 15.7).

## 1. Public indexer app (`logion` PR — `packages/indexer/`)

```text
packages/indexer/
├── logion_indexer/
│   ├── __init__.py
│   ├── cli.py                  # argparse: crawl, resolve, push, run, doctor
│   ├── config.py               # env + seed-file loading
│   ├── canonical.py            # CanonicalSkillId + normalization
│   ├── dedup.py                # local + remote dedup decisions
│   ├── github_resolver.py      # hub page/url -> owner/repo[#subpath]
│   ├── github_source.py        # repo metadata, license, HEAD sha, tarball,
│   │                           #   git/trees payload -> logion_skillmap.infer()
│   ├── crawl.py                # robots.txt, rate limiter, ETag cache, UA
│   ├── pusher.py               # batch-upsert client against the Logion API
│   ├── seeds/sources.yaml      # versioned seed list (below)
│   └── adapters/
│       ├── base.py             # HubAdapter protocol
│       ├── github_direct.py    # repo / repo_subpath / owner-enumeration
│       ├── skills_sh.py
│       ├── clawhub.py
│       ├── lobehub.py
│       ├── browse_sh.py
│       ├── hermes_docs.py
│       └── skills_lock.py      # skills-lock.json (vercel-labs `skills` CLI)
├── pyproject.toml              # console script: logion-indexer;
│                               #   deps: stdlib http + logion-skillmap (pinned)
└── tests/
```

**Canonical identity + dedup (`canonical.py`, `dedup.py`) — the core:**

```python
@dataclass(frozen=True, order=True)
class CanonicalSkillId:
    owner: str          # lowercased
    repo: str           # lowercased
    subpath: str = ""   # normalized, no leading/trailing '/'
    # str form: "gh:{owner}/{repo}" or "gh:{owner}/{repo}#{subpath}"

@dataclass(frozen=True)
class DiscoveredSkill:
    canonical: CanonicalSkillId
    title: str                      # skillmap component name (frontmatter)
    summary: str                    # skillmap component summary (frontmatter)
    original_author: str            # github owner login
    license_spdx: str | None
    source_commit: str | None       # HEAD sha at crawl time
    tags: tuple[str, ...]
    channels: tuple[DiscoveryChannel, ...]  # (hub_slug, hub_url, hub_verified)
    inferred_map: dict | None       # per-skill package-map fragment (below)
    map_flags: tuple[str, ...]      # skillmap needs_review codes, verbatim
```

**Skill detection and mapping are delegated, not duplicated.**
`github_source.py` fetches `git/trees/{sha}?recursive=1` (which it already
needs for SKILL.md discovery) and calls `logion_skillmap.infer()` with a
blob-fetcher backed by the contents API. Consequences, all test-pinned:

- the canonical-skill set for a repo == the inference result's canonical
  components: exclusion (`tests/fixtures/deprecated/node_modules`) and
  harness-mirror dedup apply to indexing for free — `affaan-m/ECC`'s
  `.agents/skills/**` tree indexes once, not once per harness mirror;
  `andrewyng/context-hub`'s `cli/test/fixtures/testskills/**` never
  becomes a listing;
- one listing per canonical component (each component root → its own
  `#subpath` id), exactly the existing multi-skill rule, now with a single
  implementation;
- `title`/`summary` come from SKILL.md frontmatter via skillmap — hub page
  text is a fallback only when frontmatter is absent
  (`skillmap_frontmatter_missing`);
- `inferred_map` is the component's map fragment serialized as the 15.3
  schema restricted to that component (`version`, `package.slug` from the
  component name, single `components.capabilities` entry, `runtime.include`
  = the component subtree). All `needs_review` defaults applied;
  unanswered flags travel in `map_flags` — the indexer never prompts;
- inference runs per repo once, cached by `(owner, repo, sha)` for the run
  (a repo listed on four hubs is inferred once).

`HubAdapter.discover()` yields hub items; `github_resolver` extracts the repo
link from each hub page (every adapter must produce a canonical id or the
item is dropped with reason `no_github_source` — hub-only skills without a
repo are **not indexable** in v1). `dedup.merge()` then:

1. groups all discoveries by `CanonicalSkillId` → one `DiscoveredSkill` with
   the union of channels (this is where LobeHub's copy of an openclaw skill
   collapses into the same record as ClawHub's);
2. queries the API (`GET /v1/admin/indexing/known?ids=gh:...,gh:...`) for
   what Logion already knows: existing indexed listings (update, don't
   create), repos already backing owned courses via `course_source_links`
   (**skip**, reason `already_logion_course`), and claimed listings (**skip**,
   `already_claimed`);
3. emits a plan: `create[]`, `update[]` (commit moved or channels changed),
   `skip[]` with reasons — printed before any push; `--dry-run` stops here.

**CLI surface:**

```bash
logion-indexer run   [--seed-file seeds/sources.yaml] [--only lobehub] [--limit N] [--dry-run] [--json]
logion-indexer crawl --adapter lobehub [--limit N]        # discovery only, prints plan
logion-indexer push  --plan plan.json                     # explicit two-step mode
logion-indexer doctor                                     # creds, robots, API reachability
```

`run` = crawl → resolve → dedup → push → print per-adapter stats
(`discovered/resolved/deduped/created/updated/skipped/errors`). Exit 1 when
any adapter hard-fails, 0 with a `partial` marker when individual items fail.

**GitHub adapter modes** (`github_direct.py`): `repo` (whole repo),
`repo_subpath` (e.g. `stripe/ai#skills`), `owner` (enumerate the account's
repos that contain a `SKILL.md`). Multi-skill repos: one listing per
canonical skillmap component (each component root → its own subpath id);
`repo_subpath` mode filters the inference result to components under the
subpath rather than running a scoped scan.

**Seed list v1 (`seeds/sources.yaml`)** — data, not code:

```yaml
version: 1
sources:
  - {adapter: github_direct, mode: repo,         target: anthropics/skills}
  - {adapter: github_direct, mode: repo,         target: openai/skills}
  - {adapter: github_direct, mode: repo,         target: huggingface/skills}
  - {adapter: github_direct, mode: repo,         target: nvidia/skills}
  - {adapter: github_direct, mode: repo_subpath, target: stripe/ai, subpath: skills}
  - {adapter: github_direct, mode: owner,        target: zarazhangrui}
  - {adapter: github_direct, mode: repo,         target: mattpocock/skills}
  - {adapter: github_direct, mode: repo,         target: MiniMax-AI/skills}
  - {adapter: github_direct, mode: repo,         target: andrewyng/context-hub}
  - {adapter: github_direct, mode: repo,         target: uphiago/recon-skills}
  - {adapter: github_direct, mode: repo,         target: affaan-m/ECC}
  - {adapter: github_direct, mode: repo,         target: ComposioHQ/awesome-claude-skills}
  - {adapter: github_direct, mode: repo,         target: garrytan/gstack}
  - {adapter: github_direct, mode: repo,         target: obra/superpowers}
  - {adapter: skills_sh,   target: "https://www.skills.sh/"}
  - {adapter: clawhub,     target: "https://clawhub.ai/"}
  - {adapter: lobehub,     target: "https://lobehub.com/skills"}
  - {adapter: browse_sh,   target: "https://browse.sh/"}
  - {adapter: hermes_docs, target: "https://hermes-agent.nousresearch.com/docs/skills"}
```

Bundle mirroring is client-side too: for permissive licenses the indexer
downloads the repo tarball (25 MB cap), extracts the skill subtree
(**the subtree = the component's `runtime.include` from the inferred
map** — mirroring and mapping can never disagree), and uploads it with the
batch item (the API hands back a presigned PUT via the existing storage
layer; the client PUTs bytes — same mechanics as `courses uploads push`).

Note the seed-list consequence, DB-enforced: `uphiago/recon-skills` and
`ComposioHQ/awesome-claude-skills` carry no license → `license_class=
'unknown'` → link-only listings. Their inferred maps are still computed
and stored — mapping is provenance/scan/claim input, not hosting.

**`skills_lock` adapter** — a `skills-lock.json` (vercel-labs `skills`
CLI de-facto format: `{version: 1, skills: {name: {source: "owner/repo",
sourceType, computedHash}}}`) is a ready-made discovery list. The adapter
takes a raw URL or local path, accepts only `sourceType == "github"`
entries (others dropped, reason `unsupported_source_type`), and maps
`source` → `gh:owner/repo` canonical ids; resolution/inference then
proceeds identically to `github_direct`. The lockfile's `computedHash` is
stored on the discovery channel (`hub_slug='skills-lock'`,
`hub_url`=lockfile location) and compared against our own bundle hash at
HEAD — mismatch is recorded as channel metadata `lock_drift=true`
(display signal; gates nothing, same rule as `hub_verified`). Seed entry:
`{adapter: skills_lock, target: "https://raw.githubusercontent.com/vercel-labs/open-agents/main/skills-lock.json"}`.
Unknown `version` values → adapter hard-fail (surface format churn
loudly; it is a labs format).

## 2. Dumb ingestion API (`backend repository` PR)

**Migration `0034_nodes_and_indexed_listings.py`** — as previously specified
(`external_course_sources`, `indexed_listings` with required provenance +
`license_class`/`hosting_mode` + the DB-level
`ck_indexed_listings_hosting_requires_permissive` gate + `tier` +
`source_verification`, `indexed_listing_tags`, `ingestion_runs`) with two
changes:

- `indexed_listings.slug` derives from the canonical id
  (`gh--{owner}--{repo}[--{subpath-slug}]`); `canonical_url` on
  `external_course_sources` stores the `gh:` canonical string (idempotency
  anchor, UNIQUE);
- new table `listing_discovery_channels`:

```python
op.create_table(
    "listing_discovery_channels",
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("indexed_listing_id", sa.Uuid(),
              sa.ForeignKey("indexed_listings.id"), nullable=False, index=True),
    sa.Column("hub_slug", sa.String(64), nullable=False),   # 'lobehub'|'clawhub'|...|'github'
    sa.Column("hub_url", sa.String(1024), nullable=False),
    sa.Column("hub_verified", sa.Boolean(), nullable=False,
              server_default=sa.text("false")),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    ... timestamps ...,
    sa.UniqueConstraint("indexed_listing_id", "hub_slug",
                        name="uq_discovery_channel_per_hub"),
)
```

`source_verification` on the listing is derived server-side:
`github_native` always (the canonical source is a repo); channel badges live
on the channels. License constants (`PERMISSIVE_SPDX`, `classify_license`)
unchanged from the previous draft; `unknown` == `restricted` == link-only,
enforced by the CheckConstraint.

**Endpoints (all `RequireAdminOnly`, all dumb):**

```text
POST /v1/admin/indexing/runs                    -> 201 {run_id}   (open an audit run)
GET  /v1/admin/indexing/known?ids=gh:a/b,gh:c/d -> {known: {"gh:a/b": {kind: "indexed_listing"|"course"|"claimed", id}}}
POST /v1/admin/indexing/listings:batch-upsert   -> per-item results
     body: {run_id, items: [{canonical, title, summary, original_author,
            license_spdx, source_commit, tags, channels: [...],
            inferred_map: null | {...15.3 schema...}, map_flags: [...],
            bundle: null | {sha256, size_bytes}}]}   (≤100 items/call)
POST /v1/admin/indexing/listings/{id}/bundle-upload   -> presigned PUT (permissive only; 409 otherwise)
PATCH /v1/admin/indexing/runs/{run_id}/completion      -> stats JSON, closes the run
```

Server-side validation only (no fetching): required provenance fields
non-null, `classify_license`, tags through the existing `normalize_tags`,
canonical string format `^gh:[a-z0-9-]+/[a-z0-9._-]+(#.+)?$`, upsert by
`canonical_url` (create/update, never duplicate), channel rows upserted by
`(listing, hub_slug)` with `last_seen_at` bumped. `inferred_map`, when
non-null, is validated with the 15.3 backend package-map parser
(`parse_package_map` — same rules, same error codes; invalid map →
per-item `422 package_map_invalid`, the rest of the batch proceeds) and
stored on the listing: migration adds
`indexed_listings.inferred_package_map JSONB NULL` and
`indexed_listings.map_flags TEXT[] NOT NULL DEFAULT '{}'`. The API never
infers — it only validates and persists what the indexer computed
(inference stays client-side with the rest of the breakage-prone surface).

Downstream contracts pinned here: the 15.7 observation scan reads
`inferred_package_map.components.runtime.include` as its file-set (falls
back to the whole mirrored bundle when null), and the 15.9 claim flow
seeds the claimed course's `logion-package-map.yaml` from
`inferred_package_map` verbatim — claim → publish is one command. Bundle upload completion
verifies the sha256 and flips `hosting_mode='mirrored'` — which the DB
constraint rejects for non-permissive rows. A completed mirrored upsert
enqueues the 15.7 observation scan (job dedupe key
`f"obs-scan:{listing_id}:{source_commit}"`).

The listing-level invariants from the previous draft stand: no owner, never
`published`, never purchasable (`test_indexed_listing_never_purchasable`),
`ingestion_runs` audit who/when/stats.

## 3. Tests

Indexer (`logion/packages/indexer/tests/` — all network faked with recorded
fixtures per hub):

- `test_canonical.py` — normalization (case, trailing `.git`, subpath), str
  round-trip, ordering stability.
- `test_github_resolver.py` — extraction from each hub's page fixture
  (lobehub skill page → repo link), `no_github_source` drop.
- `test_dedup.py` — multi-hub collapse into one skill with unioned channels;
  known-map handling: update vs skip (`already_logion_course`,
  `already_claimed`); plan output shape; `--dry-run` performs zero POSTs
  (asserted via fake transport).
- `test_adapters_{skills_sh,clawhub,lobehub,browse_sh,hermes_docs}.py` —
  fixture-driven parsing; robots.txt disallow honored; rate limiter called.
- `test_adapter_skills_lock.py` — v1 fixture parses to canonical ids;
  non-github `sourceType` dropped with reason; `computedHash` lands on the
  channel; hash mismatch sets `lock_drift`; unknown `version` hard-fails.
- `test_github_direct.py` — repo/subpath/owner modes, multi-skill repo →
  one item per canonical skillmap component (skillmap faked at the
  interface, its own behavior is tested in 15.3's fixture suite),
  per-`(owner,repo,sha)` inference cache (one `infer()` call for a repo on
  N hubs), subpath filtering, license → SPDX, 25 MB cap, mirror subtree ==
  `runtime.include`.
- `test_inferred_map_payload.py` — every pushed item carries
  `inferred_map`/`map_flags`; frontmatter title preferred over hub title;
  fragment validates against the 15.3 schema before push (invalid fragment
  → item dropped with reason `inferred_map_invalid`, run marked partial).
- `test_pusher.py` — batching ≤100, presigned-PUT flow, partial-failure
  accounting, run open/close lifecycle, API key never logged.

Backend (`packages/api/tests/indexing/`):

- `test_batch_upsert.py` — idempotent re-push (created=0/updated=n), channel
  upsert + `last_seen_at`, canonical format rejection, tag normalization,
  100-item cap, non-admin 403; `inferred_map` validated by
  `parse_package_map` (invalid → per-item 422, batch proceeds), persisted
  to `inferred_package_map`/`map_flags`, updated when `source_commit`
  moves.
- `test_indexed_listing_schema.py` / `test_license_gate.py` — constraints as
  previously specified (hosting-requires-permissive at DB level).
- `test_bundle_upload.py` — presigned flow, sha256 mismatch 422, restricted
  license 409, mirrored flip enqueues observation scan.
- `test_known_lookup.py` — the three kinds (indexed/course/claimed) resolved
  from `course_source_links` + `claimed_course_id`.

## 4. Acceptance criteria

- [ ] `logion-indexer run` against the seed file crawls all hubs, resolves
      every skill to its GitHub identity, and produces one listing per
      canonical skill — a skill listed on three hubs yields **one** listing
      with three discovery channels.
- [ ] Every created/updated listing carries a non-null
      `inferred_package_map` validated by the 15.3 backend parser, plus
      verbatim `map_flags`; skill-root detection, exclusion, and
      harness-mirror dedup are provided by `logion_skillmap` (zero
      duplicate scan logic in `packages/indexer` — grep-pinned test).
- [ ] The seven 15.3 fixture repos index end-to-end in a recorded-fixture
      run: `affaan-m/ECC` mirrors collapse to one listing per component,
      `andrewyng/context-hub` test fixtures produce zero listings,
      license-less repos (`uphiago/recon-skills`,
      `ComposioHQ/awesome-claude-skills`) are link-only **with** stored
      inferred maps.
- [ ] Skills whose repos already back a Logion course or a claimed listing
      are skipped with an explicit reason; re-runs are idempotent
      (created=0 on the second pass).
- [ ] The backend performs zero crawling/fetching; a broken hub layout is
      fixed by an indexer patch release, no backend deploy.
- [ ] Restricted/unknown licenses are link-only (DB-enforced); mirrored
      bundles arrive only via the presigned client upload.
- [ ] Hub "verified" badges are stored per channel and displayed; they gate
      nothing — every mirrored listing still gets the 15.7 observation scan.
- [ ] Public-repo hygiene: `packages/indexer` has no `backend repository`
      references and passes `make public-audit`.

## Out of scope

- Observation-mode scanning + discovery surfacing (15.7); bounties (15.8);
  claims (15.9).
- Hub-only skills with no GitHub repo (not indexable in v1).
- Scheduled/cron crawling (operator-run only) and any auto-sync daemon.

## Implementation appendix — compare against current code

Current repo shape to respect:

- There is no `logion/packages/indexer` package today. Create it as a public
  package beside `packages/cli`, `packages/scanners`, and `packages/client`.
- Backend listing/search code already exists in
  `backend repository/packages/api/api/listings`. Put indexed-listing persistence
  and admin ingestion there unless a tiny `api/indexing` domain makes router
  wiring clearer.
- Existing course provenance from 15.3 lives in `course_source_links`; known
  lookup must compare against that table to avoid duplicate external listings.
- Existing storage helpers live in `api/storage`; use them for mirrored bundle
  uploads instead of creating ad hoc S3 code.

Branch targets for 0.1.x live compatibility:

| Work item | Repo | Target branch | Reason |
| --- | --- | --- | --- |
| `indexed_listings`, `indexed_listing_discovery_channels`, `indexing_runs`, bundle-upload backend endpoints | `backend repository` | `main` | Safe because endpoints are admin-only and indexed listings are invisible until 15.7 opt-in search ships. |
| Public `packages/indexer` crawler CLI and tests | `logion` | `0.2.0` | New operator/developer tool for the 0.2.0 indexing program; do not add to 0.1.x public `main`. |
| Docs for running indexer and seed hub list | `logion` / workspace docs | `0.2.0` | User/operator documentation should align with new package availability. |
| Scheduled production crawling | none | out of scope | Operator-run only in this phase. |

Public indexer package plan:

1. Create `logion/packages/indexer/pyproject.toml`, package
   `logion_indexer`, and tests. Follow the Python packaging style used by
   `packages/scanners` and `packages/cli`.
2. Add modules:
   `canonical.py`, `models.py`, `transport.py`, `rate_limit.py`,
   `github_resolver.py`, `pusher.py`, `cli.py`, and `adapters/`.
3. Adapter interface:
   `discover(self) -> Iterable[DiscoveredSkill]` where each skill has
   `hub_slug`, `hub_url`, `hub_verified`, `title`, `summary`,
   `original_author`, `source_url`, `tags`.
4. Implement adapters for `skills_sh`, `clawhub`, `lobehub`, `browse_sh`,
   `hermes_docs`, plus `github_direct`. All network access must pass through
   `transport.py` so tests can fake it.
5. Canonical id format is `gh:owner/repo` or
   `gh:owner/repo#path/to/skill`. Normalize owner/repo to lowercase, strip
   trailing `.git`, strip GitHub URL noise, preserve subpath case only if
   GitHub paths require it. Prefer lowercase subpaths unless tests prove a
   case-sensitive repo fixture.
6. `github_resolver.py` resolves hub pages to GitHub repo/subpath, fetches
   license metadata and latest commit SHA. Skill-root detection is
   `logion_skillmap.infer()` over the `git/trees?recursive=1` payload
   (blob-fetcher backed by the contents API, cached per
   `(owner, repo, sha)`); do not write a second SKILL.md scanner. Drop
   anything without a GitHub source with reason `no_github_source`.
7. CLI commands:
   `logion-indexer run --hub HUB --api-base URL --api-key KEY [--dry-run]`,
   `logion-indexer plan --hub HUB --out plan.json`,
   `logion-indexer push --plan plan.json --api-base URL --api-key KEY`.
   `run` is `plan` then `push`.
8. Never log API keys or GitHub tokens. Redact values named `token`, `key`,
   `authorization`, and raw bearer strings in error output.

Backend implementation steps:

1. Create migration after the latest private API revision. Tables:
   `indexing_runs`, `indexed_listings`,
   `indexed_listing_discovery_channels`. Add all constraints described above,
   plus `tier indexed|improving|claimed`, `hosting_mode link_only|mirrored`,
   `license_class permissive|restricted|unknown`, `mirrored_bundle_key null`,
   `claimed_course_id null fk courses.id`,
   `inferred_package_map JSONB null`,
   `map_flags TEXT[] not null default '{}'`.
2. Add models to `api/models.py`; keep relationships simple and avoid eager
   loading defaults.
3. Add repositories:
   `api/listings/repositories/indexed_listings.py`,
   `indexed_listing_channels.py`, `indexing_runs.py`.
4. Add services:
   `OpenIndexingRunService`, `KnownIndexedSourcesService`,
   `BatchUpsertIndexedListingsService`, `CreateIndexedBundleUploadService`,
   `CompleteIndexedBundleUploadService`, `CompleteIndexingRunService`.
5. Admin auth: use the existing admin dependency already used by admin
   controllers. If admin controllers are under `api/admin/controllers`, either
   put ingestion endpoints there or import the same dependency into listings.
6. Batch upsert must be dumb: validate and persist only. Do not fetch GitHub,
   crawl hubs, infer missing licenses, infer maps server-side, or mutate
   courses. `inferred_map` validation reuses 15.3's `parse_package_map` —
   no second map parser in the ingestion path.
7. `known` lookup returns:
   `course` if canonical repo/subpath maps to a `course_source_links` row,
   `claimed` if an indexed listing has `claimed_course_id`,
   `indexed_listing` if an active indexed listing exists,
   absent otherwise.
8. Bundle upload:
   only for `license_class='permissive'`; return 409 for unknown/restricted.
   Presigned upload comes from existing storage service. Completion verifies
   sha256 and size, updates `mirrored_bundle_key`, sets `hosting_mode`, and
   enqueues 15.7 job if that job type exists; if 15.7 has not merged yet, hide
   enqueue behind a no-op service with a TODO named `enqueue_observation_scan`.

Response shapes:

```json
POST /v1/admin/indexing/listings:batch-upsert
{
  "run_id": "...",
  "items": [
    {
      "canonical": "gh:owner/repo#skills/foo",
      "title": "Foo Skill",
      "summary": "...",
      "original_author": "octocat",
      "license_spdx": "MIT",
      "source_commit": "abc123",
      "tags": ["coding"],
      "channels": [{"hub_slug":"lobehub","hub_url":"https://...","hub_verified":true}],
      "inferred_map": {
        "version": 1,
        "package": {"slug": "foo-skill"},
        "components": {"capabilities": {"foo-skill": {"entrypoint": "skills/foo/SKILL.md"}},
                       "runtime": {"include": ["skills/foo/**"],
                                   "entrypoint": "skills/foo/SKILL.md"}}
      },
      "map_flags": ["skillmap_frontmatter_missing"],
      "bundle": null
    }
  ]
}
```

Per-item result:

```json
{"canonical":"gh:owner/repo#skills/foo","status":"created","indexed_listing_id":"..."}
```

Minimum tests:

- Indexer package: canonical normalization, each adapter with HTML/JSON
  fixtures, robots/rate-limit call assertion, dedupe across hubs, dry-run zero
  POSTs, pusher batching and redaction.
- Backend: admin-only enforcement, batch cap, idempotent upsert, channel
  union/update, license classification, mirrored license gate at DB and
  service layer, known lookup across indexed/source-linked/claimed states.
- Public audit test: `packages/indexer` must not import from
  `backend repository` or reference private paths.

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a maintained derivative with lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
