# Logion Agent Proving Ground

Multi-agent product proving ground for Logion.

This package is a **scenario runner for validating product behavior with
autonomous agents**. It is not normal CI and is not a substitute for unit tests.
It answers the question: *can an autonomous agent actually complete a real product
workflow?*

## What this package ships

- A deterministic **mock API adapter** (`mock`) with in-memory product state.
- A **scripted driver** (`scripted`) that fakes agent behavior for scenario
  authoring and contributor development.
- A **scenario schema** (YAML + Pydantic) describing agents, phases, goals and
  assertions.
- A **runner** that executes phases, collects transcripts, runs assertions and
  writes artifacts.

## What this package does **not** ship

This package does not yet ship real agent drivers (Codex, Claude,
opencode, etc.) or adapters that talk to the private backend.

Real release proof requires real agent drivers. The `mock`/`scripted` path is
only for contributor development and scenario authoring.

## Quick start

```bash
# list built-in scenarios
logion-agent-proving-ground list

# validate a scenario
logion-agent-proving-ground validate builtin:skill_report_contract

# run the built-in scenario with mock API and scripted agent
logion-agent-proving-ground run builtin:skill_report_contract \
  --api-adapter mock \
  --agent-driver scripted

# inspect a run report (use the artifact_root printed by `run`)
logion-agent-proving-ground report .runs/proving-ground/<run-id>
```

## Release gate: `marketplace_loop`

`builtin:marketplace_loop` is the full creator/learner/operator product
loop (publish → purchase → use → review → bounty → approve → admin
check). It is a release-gate proof, not normal PR CI. From the repo root:

```bash
make dev-up MODE=prod ROLE=admin   # or MODE=mock for mechanics only
make doctor AGENT=codex
make agent-proving-ground-release  # LOGION_PROVING_GROUND_AGENT_DRIVER=... to override
```

Observed-effect assertions against a real API need credentials:

- `LOGION_PROVING_GROUND_ROLE_KEYS_FILE` — JSON mapping devrig roles to
  `{"api_key": "...", "agent_id": "..."}` (agent_id optional), or
- a single `LOGION_PROVING_GROUND_API_KEY` / `LOGION_API_KEY` shared by
  all personas (personal-account contributor mode).

Without keys, API assertions report `unsupported`: required ones fail
the run, `optional: true` ones are skipped. Admin assertions are
capability-gated the same way. See
[`docs/release-checklist.md`](../../docs/release-checklist.md) for the
release policy and waiver format.

### Reproducing the e2e run

Key prerequisites for a clean e2e run against a live local API:

1. The API schema must be fully migrated before running.
2. Seed the database and grant credits to the seller and buyer personas
   (bounty funding requires creator credits).
3. Truncate marketplace tables between runs to avoid stale data causing
   false assertion passes.
4. The `hermes` driver needs `LOGION_PROVING_GROUND_ROLE_KEYS_FILE` pointing
   to the devrig role keys JSON.

## Authoring scenarios

Scenarios live in YAML:

```yaml
schema_version: "1"
name: my_scenario
api_adapter: mock

description: A short description of what is being proven.
agents:
  - id: learner
    role: Learner using a Logion course
    driver: scripted

phases:
  - id: use_course
    actor: learner
    goal: Use the fixture course for a tiny task.
    assertions:
      - type: api.course_exists
        params: {status: published}

final_assertions:
  - type: timeline.no_unredacted_secret
```

Public contributors can add scenarios without private API access. Local
maintainers can run stronger adapters with DB/log assertions in follow-up
work.

## Project structure

```text
agent_proving_ground/
  cli.py              # command-line interface
  config.py           # constants and exceptions
  models.py           # shared Pydantic models
  runner.py           # scenario execution engine
  timeline.py         # append-only JSONL event log
  artifacts.py        # redacted artifact store
  redaction.py        # secret redaction helpers
  api_adapters/       # adapter protocol and mock
  drivers/            # driver protocol and scripted
  assertions/         # assertion registry and implementations
  scenarios/          # schema, loader and built-in scenarios
  testsupport/        # test-only fakes
```

## Development

```bash
make test        # run tests
make lint        # ruff check
make type-check  # mypy
make ci-checks   # lint + type-check + test
```

## License

MIT
