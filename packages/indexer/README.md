# logion-indexer

External skillhub indexer for Logion: crawl skill hubs, resolve every
skill to its GitHub identity, dedup across hubs, and batch-upsert to
the Logion admin API.

## Installation

```bash
uv pip install logion-indexer
```

## Usage

```bash
# Full pipeline: crawl → resolve → dedup → push
logion-indexer run --dry-run

# Crawl only (no push)
logion-indexer crawl --json

# Push a pre-built plan
logion-indexer push --plan plan.json

# Check credentials and API reachability
logion-indexer doctor
```

## Environment variables

- `LOGION_INDEXER_GITHUB_TOKEN` — GitHub API token
- `LOGION_INDEXER_API_KEY` — Logion admin API key
- `LOGION_BASE_URL` — Logion API base URL

## License

MIT