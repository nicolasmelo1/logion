# logion-landing

The public Logion landing page.

FastAPI app serving the marketing site at `/`, the documentation at `/docs`,
plus `/terms`, `/privacy`, and a `/health` probe.

`GET /` also supports `Accept: text/markdown` and returns the non-visual
landing content as Markdown for agents, terminals, and lightweight docs
ingestion.

## Layout

```
landing/
  main.py           FastAPI app, routes, env handling
  docs_site.py      Renders the generated documentation artifact
  content/
    site.yaml       Source of truth for copy, links, contact
    landing.md      Markdown projection served via Accept: text/markdown
    docs.json       GENERATED — do not edit. See below.
  templates/        Jinja2 templates (base, index, legal)
  static/           CSS, JS, ASCII hero frames
tests/              Route, content, and asset tests
```

## Run locally

```bash
uv run logion-landing
```

Environment:

- `LOGION_LANDING_HOST` (default `127.0.0.1`)
- `LOGION_LANDING_PORT` (default `8001`)

## Test

```bash
uv run pytest packages/landing/tests -q
```

## License

MIT

## Documentation at `/docs`

`content/docs.json` is **generated** by `scripts/gen_docs.py` at the repository
root, from three sources: the OpenAPI contract (`contracts/openapi/v1.json`),
the CLI's argparse tree, and the hand-written guides in `docs/marketplace/`.

It is a build-time artifact rather than a runtime import for a deployment
reason: this app deploys with `packages/landing/` as its Vercel root directory,
so it cannot read `contracts/` or import the `cli` package — the same constraint
that makes `/install.sh` a redirect to raw GitHub.

```bash
make docs-generate                          # from the repository root
uv run python scripts/gen_docs.py --check   # what CI runs
```

`make check-docs` is part of `make ci-checks`. A contract sync that adds an
endpoint, or a new CLI flag, turns the build red until the artifact is
regenerated and committed.

`docs_site.py` only reads the artifact — it must never derive content, or the
generated reference stops being the single source and starts being two.
