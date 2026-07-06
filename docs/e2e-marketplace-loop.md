# E2E Marketplace Loop — Reproducible Setup Guide

This guide explains how to reproduce the full `marketplace_loop` proving-ground
e2e scenario from a clean environment. Any model or harness should be able to
follow these steps and get a passing run.

## Prerequisites

1. **Three repos** checked out side-by-side:

   ```bash
   ~/workspaces/personal/logion           # public repo (this one)
   ~/workspaces/personal/logion-private    # private backend
   ~/workspaces/personal/logion-workspace  # coordination
   ```

2. **Python tooling**: `uv` installed, Python 3.12+.

3. **PostgreSQL** running locally with the logion database seeded.

4. **Hermes CLI** installed (`pipx install hermes-cli` or equivalent).

## Step 1: Start the API server

From the `logion-private` repo:

```bash
cd ~/workspaces/personal/logion-private/packages/api
make dev-up MODE=prod ROLE=admin   # starts API + DB
```

Verify the API is healthy:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

## Step 2: Run database migrations

The API schema must be fully migrated. From `logion-private`:

```bash
cd ~/workspaces/personal/logion-private/packages/api
env -u VIRTUAL_ENV uv run alembic -c alembic.ini upgrade head
```

Verify:

```bash
env -u VIRTUAL_ENV uv run alembic -c alembic.ini current
```

## Step 3: Seed the database

```bash
cd ~/workspaces/personal/logion-private
env -u VIRTUAL_ENV uv run python -m api.scripts.dev_seed
```

## Step 4: Grant credits to the seller and buyer

The default seed gives sellers 0 credits, which blocks bounty funding.
Grant credits before each e2e run:

```bash
cd ~/workspaces/personal/logion-private
env -u VIRTUAL_ENV uv run python -m api.scripts.admin_credits \
  grant --email seller-a@dev.logion.sh --credits 100000 \
  --reason "proving-ground-e2e"

env -u VIRTUAL_ENV uv run python -m api.scripts.admin_credits \
  grant --email buyer-a@dev.logion.sh --credits 100000 \
  --reason "proving-ground-e2e"
```

> **Note:** `--reason` must be unique across runs. Append a version suffix
> (e.g. `-v2`) if re-running.

## Step 5: Reset stale data between runs

If you have run the e2e before, the database accumulates stale courses,
bounties, and submissions from prior runs. These cause false assertion passes.
Truncate marketplace tables before each clean run:

```bash
PGPASSWORD=logion psql -h localhost -U logion -d logion -c "
TRUNCATE TABLE
  bounty_submissions,
  bounty_fundings,
  bounty_payouts,
  bounties,
  course_reviews,
  course_rating_summaries,
  course_version_rating_summaries,
  course_publication_review_findings,
  course_publication_reviews,
  entitlements,
  course_upload_session_assets,
  course_upload_sessions,
  course_assets,
  course_versions,
  courses,
  credit_ledger_entries,
  credit_top_ups,
  credit_accounts,
  creator_payable_balances
CASCADE;
"
```

Then re-seed (Step 3) and re-grant credits (Step 4).

## Step 6: Run the proving ground

From the `logion` (public) repo:

```bash
cd ~/workspaces/personal/logion

# Install the proving-ground package if not already installed
env -u VIRTUAL_ENV uv pip install -e packages/agent-proving-ground

# Run the e2e scenario
LOGION_PROVING_GROUND_ROLE_KEYS_FILE=~/workspaces/personal/logion-workspace/.devrig/proving-ground-role-keys.json \
env -u VIRTUAL_ENV uv run logion-agent-proving-ground run \
  builtin:marketplace_loop \
  --api-adapter local-devrig \
  --devrig-root "$(pwd)" \
  --agent-driver hermes \
  --out .runs/proving-ground/marketplace
```

## Expected result

All 7 phases and all assertions must pass:

```
status: passed

phase creator_publishes_course: completed
phase admin_approves_publication: completed
phase learner_buys_uses_reviews: completed
phase creator_opens_bounty: completed
phase learner_submits_bounty_work: completed
phase creator_accepts_bounty: completed
phase admin_reviews_marketplace_state: completed

assertion api.course_exists: passed (×2)
assertion api.purchase_exists: passed
assertion api.usage_report_exists: passed
assertion api.review_exists: passed
assertion api.bounty_exists: passed
assertion api.bounty_submission_exists: passed
assertion api.bounty_accepted: passed
assertion api.admin_state_observed: passed
assertion api.no_double_credit_debit: passed
assertion api.course_remains_purchasable: passed
assertion logs.no_500s: passed
assertion db.exact_credit_ledger: passed
assertion timeline.no_unredacted_secret: passed
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `bounty_exists` fails with `status: open` | Agent created bounty but didn't fund it | Check `success_hint` includes `logion bounties fund`; ensure seller has credits |
| `bounty_accepted` fails | No submission on the bounty, or bounty not funded | Seed credits for seller; check bounty status is `funded` before accepting |
| Agent hits max turns | Complex phase exhausting 80 turns | Bump `--max-turns` in `hermes.py` or simplify scenario |
| `purchase_exists` / `review_exists` fails for free courses | Buyer role queries `/v1/courses/mine` (sees 0 owned courses) | Assertion uses `_candidate_course_ids` with owner role fallback |
| Phase 2 fails (course stays `draft`) | Agent didn't complete publish+review flow | Check hermes agent has `--yolo` flag and correct env vars |
| API 500 on bounty funding | DB migration missing `funder_user_id` column | Run `alembic upgrade head` in logion-private |
| `session has no uploads to push` | CLI can't parse v1 JSON envelope from `uploads create` | Fixed in PR #145 (v1 envelope unwrapping) |

## Architecture notes

- **Agent driver**: The `hermes` driver spawns a real Hermes CLI subprocess per
  phase with a PTY. Each phase gets its own `--max-turns` budget (default 80).
- **API adapter**: The `local-devrig` adapter queries the live local API using
  role-specific API keys from `proving-ground-role-keys.json`.
- **Assertions**: API assertions check real state (courses, purchases, reviews,
  bounties). Log/DB assertions check for 500s and credit ledger consistency.
- **Baseline filtering**: Before each run, the adapter captures existing
  marketplace state (course IDs, bounty IDs, review IDs) and filters them from
  assertion queries so only entities created during the run are matched.