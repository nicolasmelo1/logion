# Logion Marketplace Companion

> First-party companion package for discovering, acquiring, installing,
> updating, creating, and managing Logion courses and capabilities.

## Why this package exists

Logion is a marketplace for agent capabilities (courses).  Most
marketplaces ask the agent to load the catalog into context to figure
out what to do — that doesn't scale.  This package ships a small
**bootstrap skill** (`/logion`) that an agent loads once and then uses to drive
the public `logion` CLI on demand, so the agent never has to hold the
catalog in context.

The package also dogfoods Logion itself: it is intended to ship **as a
course on Logion**.  Once published, anyone can fund bounties against
it — improvements to routing accuracy, fewer tokens at bootstrap,
sharper reference-routing — without us having to hand-tune the skill
ourselves.

Two distribution paths:

1. **Download installer** — a single script that bundles the public
   CLI + SDK + this skill onto a user's machine.
2. **Logion marketplace** — published as a normal course so any Logion
   user can install it through the same CLI verbs the skill itself
   uses.

## Product contract

- **One always-on companion skill** — `SKILL.md` is the bootstrap.
- **Two user groups:**
  1. Capability consumers (discover, install, update).
  2. Course creators / operators (author, publish, manage).
- **No runtime dependency** on DSPy, GEPA, cloud models, or private
  backends.  DSPy is an optional extra used only by
  [`evals/optimizers/dspy/`](evals/optimizers/dspy/README.md) for
  offline candidate generation.
- **Local recall first** — read-only fuzzy search before marketplace
  API.
- **CLI offload** — agents drive Logion via the public CLI verbs
  (`logion recall search`, `logion listings search`,
  `logion courses get`, `logion skills install`, …) so the catalog
  never has to be held in agent context.

## Package layout

```
packages/agent-companion/
├── README.md                 ← This file
├── SKILL.md                  ← Bootstrap skill (always loaded)
├── pyproject.toml            ← Python project config and dev deps
├── Makefile                  ← Guardrail + eval + optimizer targets
├── .env.example              ← Local dev env defaults (HF, llama.cpp, DSPy)
├── course/
│   └── capabilities.yaml     ← Logion capability manifest — declares
│                                env vars, network hosts, filesystem
│                                paths, and tools this course needs.
├── references/               ← On-demand reference docs
│   ├── creator-course-management.md
│   ├── account-and-identity.md
│   ├── notifications-and-reports.md
│   ├── credits-and-payments.md
│   ├── referrals.md
│   ├── bounties.md
│   ├── course-review-queue.md
│   ├── admin-operations.md
│   └── troubleshooting.md
├── scripts/
│   └── package_skill.py      ← Validates the published bundle layout
├── tests/                    ← Structural + harness + manifest tests
└── evals/                    ← Eval harness, scenarios, optimizers
    ├── README.md             ← Eval harness contract + scenario format
    ├── run_eval.py           ← CLI entry point (fake + live providers)
    ├── harness/              ← Schema, graders, fake/llama-cpp providers
    ├── scenarios/            ← YAML scenario suites (decision-policy)
    │   └── reference_routing/  ← reference-routing scenarios (kept in
    │                            a subdir so the decision-policy walker
    │                            doesn't glob them with the wrong schema)
    ├── catalogs/             ← Marketplace catalog fixtures
    ├── reports/              ← Eval run reports (gitignored)
    ├── commands/             ← Python entry points (download models,
    │                            boot llama-server, run optimizers).
    │                            Cross-OS replacement for the old
    │                            evals/scripts/*.sh.
    └── optimizers/dspy/      ← DSPy offline optimization (optional)
        └── README.md         ← Optimizer + promotion contract
```

## Sub-READMEs

- [`evals/README.md`](evals/README.md) — eval harness contract,
  scenario format, tool-trace vocabulary, grader semantics, release
  gates.
- [`evals/optimizers/dspy/README.md`](evals/optimizers/dspy/README.md)
  — DSPy offline optimizer setup, signatures, metric formula,
  renderer gates, promotion process.

## Quick start

```bash
# Install dev dependencies (no DSPy).
uv sync

# Install with DSPy extras (only needed for offline optimization).
uv sync --group dspy

# Run all verification checks (lint + format + typecheck + tests
# + package-check + fake-provider eval).
make verify
```

## Make targets

| Target | What it does |
|---|---|
| `make test` | pytest suite (structural + harness + optimizer wiring + manifest). |
| `make lint` | `ruff check` over the package. |
| `make format-check` | `ruff format --check`. |
| `make typecheck` | mypy over packaging scripts. |
| `make package-check` | Validate the published bundle layout. |
| `make eval` | Fake-provider eval suite (deterministic, no LM needed). |
| `make eval-llama-cpp` | Boot llama-server from a provider yaml and run the eval suite against it.  Pass `MODEL=<id>` and `LLAMA_EXTRA_ARGS="-m .models/..."` as needed. |
| `make download-models` | Fetch the local GGUF models (Qwen3-8B/4B, Gemma3-4B). |
| `make split-scenarios` | Deterministic train/dev/test split for offline optimization. |
| `make optimize-policy` | DSPy offline optimization of the decision-policy signature (requires `--group dspy`). |
| `make optimize-policy-llama-cpp` | One-shot helper: boot llama-server, split scenarios, run the decision-policy optimizer, write candidate + program JSON, tear server down. |
| `make optimize-references` | DSPy offline optimization of the reference-routing signature against the fake provider. |
| `make optimize-references-llama-cpp` | One-shot reference-routing optimization against a local llama-server. |
| `make verify` | lint + format-check + typecheck + test + package-check + eval. |

The llama-cpp / optimizer targets delegate to Python modules under
`evals/commands/` (`download_models`, `run_llama_cpp_eval`,
`optimize_dspy`).  Each is invokable directly with `--help` if you
want to bypass make and pass flags yourself.

## Capability manifest

`course/capabilities.yaml` declares the full surface this package
needs when installed as a Logion course:

- **tools** — `file`, `terminal`, `web`
- **network.allow_domains** — HuggingFace (Hub + LFS + Xet CDNs),
  `127.0.0.1` / `localhost` (local llama-server), `pypi.org` +
  `files.pythonhosted.org` (uv sync), `github.com` +
  `objects.githubusercontent.com` (uv's python-build-standalone
  bootstrap)
- **filesystem.read** — `.`
- **filesystem.write** — `.models`, `evals/reports`,
  `evals/optimizers/dspy/generated_candidates`
- **secrets.env** — every `LOGION_*`, `DSPY_*`, `HF_*`, `QWEN3_*`,
  `GEMMA3_*`, `LLAMA_*`, `MODEL_CACHE_DIR` env var the package code
  reads.  Matches `.env.example`.
- **human_approval** — `required: false`; per-action approval lives
  in `SKILL.md`'s `safety.requires_confirmation` enum.

The manifest is validated by the same Pydantic schema the Logion API
enforces on publish. See the capability-manifest schema in the Logion API
source code.

## Eval harness (in brief)

The eval harness scores agent traces against scenarios on four
product axes — routing, course-selection, safety, context-efficiency
— plus update-policy handling.  Graders are deterministic; the LM is
the variable.

```bash
# Fast deterministic evaluation (fake provider, no LM)
make eval

# Local LM evaluation (Qwen3-8B-Q4 via llama.cpp)
make download-models
make eval-llama-cpp MODEL=qwen3-8b-q4km \
    LLAMA_EXTRA_ARGS="-m .models/Qwen3-8B-GGUF/Qwen3-8B-Q4_K_M.gguf"
```

Full scenario list, format, tool-trace contract, and grader
semantics: [`evals/README.md`](evals/README.md).

## DSPy offline optimization (in brief)

DSPy is **never** a runtime dependency.  It lives only under
[`evals/optimizers/dspy/`](evals/optimizers/dspy/README.md) for
offline candidate generation.  The optimizer proposes
signature-instruction rewrites and bootstraps few-shot demos; a human
reviews the resulting diff and hand-translates promotion-worthy prose
into `SKILL.md`.  Promotion is never automatic.

```bash
# Boot llama-server and run an end-to-end optimization
make optimize-policy-llama-cpp MODEL=qwen3-8b-q4km OPTIMIZER=mipro_v2
```

Full setup, metric formula, renderer gates, and promotion contract:
[`evals/optimizers/dspy/README.md`](evals/optimizers/dspy/README.md).

## CLI is not where DSPy lives

DSPy is intentionally **not** exposed through the `logion` CLI.  The
CLI is for end users (agents and operators) interacting with the
marketplace; DSPy optimization is a developer-only workflow against
the eval harness.  Invoke the optimizer scripts directly via
`uv run --group dspy python -m evals.commands.optimize_dspy` or
through the `make` targets above.

## License

This bundle ships with its own `LICENSE` file and is currently released under
MIT for dogfooding and marketplace submission.
