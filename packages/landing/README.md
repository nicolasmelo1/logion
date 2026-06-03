# logion-landing

The public Logion landing page.

FastAPI app serving the marketing site at `/`, plus `/terms`,
`/privacy`, and a `/health` probe.

## Layout

```
landing/
  main.py           FastAPI app, routes, env handling
  content/
    site.yaml       Source of truth for copy, links, contact
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
- `CLAWSERA_LANDING_HOST` / `CLAWSERA_LANDING_PORT` (legacy fallback)

## Test

```bash
uv run pytest packages/landing/tests -q
```

## License

MIT
