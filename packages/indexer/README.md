# logion-indexer

External skillhub indexer for Logion: crawl skill hubs, resolve every
skill to its GitHub identity, run skillmap inference, dedup across hubs,
mirror permissive-license bundles, and batch-upsert to the Logion admin
API.

## Installation

`logion-indexer` depends on the `logion-skillmap` workspace package, which
is not yet published to PyPI, so install from source:

```bash
git clone https://github.com/nicolasmelo1/logion.git
cd logion
uv sync --all-packages
uv run logion-indexer --help
```

## Seed file

The hubs to crawl are listed in a seed file. The bundled default is
`logion_indexer/seeds/sources.yaml`; override it with `--seed-file PATH`
or `LOGION_INDEXER_SEED_FILE`. Each entry names an adapter and a target:

```yaml
version: 1
sources:
  - {adapter: github_direct, mode: repo, target: anthropics/skills}
  - {adapter: skills_sh,   target: "https://www.skills.sh/"}
  - {adapter: skills_lock, target: "https://raw.githubusercontent.com/vercel-labs/open-agents/main/skills-lock.json"}
```

## Usage

```bash
# Full pipeline: crawl → enrich → validate → mirror → push
logion-indexer run --dry-run

# Crawl only, print the plan as JSON (no push)
logion-indexer crawl --json

# Check credentials, robots.txt for seed hubs, and API reachability
logion-indexer doctor
```

### Two-step crawl / push (failure-resume path)

`crawl --out` writes a complete plan — the full serialized create/update
items, not just ids — which `push --plan` later pushes verbatim. This lets
you crawl once and push later or elsewhere without re-crawling:

```bash
logion-indexer crawl --out plan.json
# ... later / on another host ...
logion-indexer push --plan plan.json
```

Bundle bytes are not stored in the plan file, so `push --plan` is
link/metadata only; the full `run` pipeline mirrors bundles inline.

### Options

- `--only ADAPTER` — run a single adapter from the seed file.
- `--limit N` — cap items discovered per adapter.
- `--rps FLOAT` — per-host request rate (default 1.0).
- `--cache-dir PATH` — on-disk HTTP cache directory (conditional GETs via
  ETag / Last-Modified). Defaults to `~/.cache/logion-indexer`, also
  overridable via `LOGION_INDEXER_CACHE_DIR`.

## Environment variables

- `LOGION_INDEXER_GITHUB_TOKEN` — GitHub API token. Strongly recommended:
  inference and mirroring make many GitHub API calls and will hit
  anonymous rate limits without one.
- `LOGION_INDEXER_API_KEY` — Logion admin API key.
- `LOGION_BASE_URL` — Logion API base URL.
- `LOGION_INDEXER_SEED_FILE` — seed file path.
- `LOGION_INDEXER_CACHE_DIR` — on-disk HTTP cache directory.

## License

MIT
