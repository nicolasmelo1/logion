<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.8: Platform-Funded Bounties On Indexed Listings

> Builds the `improving` tier. Depends on 15.6/15.7 (indexed listings exist and
> are discoverable) and 15.5 (PR bot, for the restricted-license branch).
> Economic boundary (from
> [`future-roadmap/economic-network-and-rewards.md`](../future-roadmap/economic-network-and-rewards.md)):
> `funding authority != publication authority != trust authority`. **Do not let
> money move faster than trust.** **PRs: exactly one per repo** — one
> `backend repository` PR (funder + target + acceptance + attribution) and one
> `logion` PR (CLI/admin surface).

## Goal

Logion (as sponsor) funds a bounty on an **ownerless indexed listing**, a real
contributor gets paid for accepted work through the normal payable/cash-out
path, and the listing advances to `improving` with **true dual attribution** —
no false authorship, no owner required, no auto-pay.

## The gap being closed

Today (verified in code): `Bounty.course_id` is `NOT NULL`; `funding_mode`
defaults `'creator_funded'`; create/open/fund/accept are owner-gated; funding
debits the creator's credit account. All four assumptions get a second lane.

## 1. Bounty target + funder model (`backend repository` PR)

**Migration `0035_platform_bounties.py`:**

```python
op.alter_column("bounties", "course_id", nullable=True)
op.add_column("bounties", sa.Column(
    "indexed_listing_id", sa.Uuid(),
    sa.ForeignKey("indexed_listings.id"), nullable=True, index=True))
op.create_check_constraint(
    "ck_bounties_exactly_one_target", "bounties",
    "(course_id IS NOT NULL) != (indexed_listing_id IS NOT NULL)")
# funding_mode gains a value (no enum table; extend the service-level guard):
#   'creator_funded' | 'platform_funded'
op.add_column("bounties", sa.Column(
    "deliverable_kind", sa.String(32), nullable=False,
    server_default=sa.text("'hosted_improvement'")))
op.create_check_constraint(
    "ck_bounties_deliverable_kind", "bounties",
    "deliverable_kind in ('hosted_improvement', 'external_pr')")
```

**Constants (`api/bounties/constants/funding_mode.py`):**

```python
FUNDING_MODE_CREATOR = "creator_funded"
FUNDING_MODE_PLATFORM = "platform_funded"
```

**Platform funder = ledger, not a fake user.** No `credit_accounts` row (that
table is per-user by constraint). Platform funding posts double-entry journals
against a new ledger account code in `api/payments/constants/ledger.py`:

```python
LEDGER_ACCOUNT_PLATFORM_BOUNTY_SPONSORSHIP = "platform_bounty_sponsorship"
```

`FundBountyService` branches: `creator_funded` → existing credit debit;
`platform_funded` → journal `platform_bounty_sponsorship` (debit) →
`platform_credit_liability` (credit) with idempotency key
`f"platform-bounty-fund:{bounty_id}"`, plus a `bounty_fundings` row with new
column `funder_type` (`'creator'|'platform'`, same migration). Platform
funding is **admin-only** (below); there is no API path where a non-admin
moves platform money.

### License gate → deliverable kind (inherited from 15.6)

At creation the service derives `deliverable_kind` from the listing:
`license_class='permissive'` → `hosted_improvement` (improved bundle hosted on
the listing); `restricted|unknown` → `external_pr` (work lands as a PR on the
source repo via the 15.5 bot mechanics; Logion hosts nothing). Stored on the
bounty so the acceptance path doesn't re-derive.

## 2. Admin surface — create/fund/accept (`backend repository` PR)

Platform-funded lifecycle is admin-mediated end to end:

```text
POST  /v1/admin/bounties                          RequireAdminOnly
      body: {indexed_listing_id, title, description, reward_amount_cents,
             submission_deadline?}          -> draft, funding_mode=platform_funded
PATCH /v1/admin/bounties/{id}/funding             RequireAdminOnly  (platform journal)
PATCH /v1/admin/bounties/{id}/submissions/{sid}/acceptance   RequireAdminOnly
      body: {decision_reason, eval_evidence?: {...}}
PATCH /v1/admin/bounties/{id}/submissions/{sid}/rejection    RequireAdminOnly
```

Contributor-side reuse: `GET /v1/bounties` (list) gains target polymorphism —
items expose `target: {kind: 'course'|'indexed_listing', id, title, tier}`;
`POST /v1/bounties/{id}/submissions` works unchanged for platform bounties
(submitter needs no relationship to the listing).

**Acceptance authority without an owner** (`accept_platform_bounty_submission.py`):

- caller must be admin/reviewer (`RequireAdminOnly` route + role re-check in
  service);
- acceptance requires a recorded rationale: `decision_reason` non-empty;
  optional `eval_evidence` JSON is stored verbatim on the submission's
  `evidence` field (**16.1 convergence**: when eval-backed bounty contracts
  land, `eval_evidence` becomes the machine-checked artifact; the field
  contract is defined now so 16.1 doesn't migrate);
- **never auto-pay**: this endpoint is the only acceptance path for platform
  bounties; the 15.5 merge-webhook policy explicitly excludes
  `funding_mode='platform_funded'` (test-pinned);
- acceptance emits `events` row `platform_bounty_accepted` with actor, reason,
  listing id;
- payout: contributor accrues via the existing
  `creator_payable_balances` path (`source='bounty_award'`) — standard net,
  standard delayed cash-out, all anti-fraud preconditions inherited. No new
  money movement code.

## 3. Improvement lands on the listing (`backend repository` PR)

On acceptance of a `hosted_improvement` deliverable:

1. submission's improved bundle (uploaded through the normal
   upload-session flow against a **staging area**, keyed to the submission)
   replaces the listing's mirrored bundle: new S3 key
   `indexed/{listing_id}/improved/{submission_id}.tar.gz`;
   `mirrored_bundle_key` repointed; previous key retained (history).
   **Both keys, `candidate_capabilities`, and all attribution rows survive
   claiming**: if the eventual claimer selects `base_bundle='original'`
   (17.3), the improvement is not discarded — 17.3 converts it into an
   `improvement_proposals` row on the resulting course, referencing this
   improved-bundle key. The contributor's bounty payout is final at
   acceptance and is never affected by later claim decisions;
2. `tier` → `'improving'`;
3. **dual attribution rows** — new table (same migration):

```python
op.create_table(
    "listing_attributions",
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("indexed_listing_id", sa.Uuid(),
              sa.ForeignKey("indexed_listings.id"), nullable=False, index=True),
    sa.Column("role", sa.String(32), nullable=False),
    # 'original_author' | 'contributor' | 'sponsor'
    sa.Column("display_name", sa.String(255), nullable=False),
    sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=True),
    sa.Column("bounty_id", sa.Uuid(), sa.ForeignKey("bounties.id"), nullable=True),
    sa.Column("source_url", sa.String(1024), nullable=True),
    ... timestamps ...,
    sa.CheckConstraint("role in ('original_author','contributor','sponsor')",
                       name="ck_listing_attributions_role"),
)
```

   Ingestion (15.6) backfills the `original_author` row; acceptance adds
   `contributor` (the submitter) + `sponsor` (`display_name='Logion'`).
   Discovery (15.7 detail endpoint + search items) renders all three,
   original author first — the copy must never imply the original author
   wrote the improvement (fixed template string, test-asserted:
   `"improved by {contributor}, funded by Logion — original by {author}"`);
4. **candidate capabilities**: the bounty deliverable must include a
   `course/capabilities.yaml`; it is stored on the listing as
   `candidate_capabilities` (new JSON column, same migration) with
   `mode='candidate'` — the middle rung of observed → candidate → attested.
   Missing/invalid manifest → acceptance blocked with 422
   `candidate_capabilities_required` (parse with the existing
   `parse_course_capability_manifest`);
5. observation re-scan (15.7) re-enqueued against the improved bundle.

`external_pr` deliverables skip 1/4/5: acceptance requires a merged PR
recorded via the 15.5 `bounty_submission_prs` row (admin still decides;
`merged` is evidence, not a trigger); listing advances to `improving` with
attribution + `source_url` pointing at the merged PR.

## 4. CLI (`logion` PR)

```bash
# admin lane (LOGION_ENABLE_ADMIN=1)
logion admin bounties create --indexed-listing LISTING_ID --title ... --reward-cents N [--json]
logion admin bounties fund BOUNTY_ID [--yes] [--json]          # platform journal; --yes required
logion admin bounties accept BOUNTY_ID SUBMISSION_ID --reason "..." [--eval-evidence FILE.json] [--yes]
logion admin bounties reject BOUNTY_ID SUBMISSION_ID --reason "..." [--yes]
# contributor lane (existing commands; target rendering only)
logion bounties list --tier indexed [--json]      # shows target kind + tier
```

Envelope kinds `logion.admin.bounties.*`. Companion `references/bounties.md`
gains a "Platform-funded (ownerless) bounties" section: how to find them
(`bounties list --tier indexed`), that acceptance is admin/eval-gated, that
payout follows the normal cash-out, and the dual-attribution promise.

## 5. Tests

Backend (`packages/api/tests/`):

- `test_platform_bounty_model.py` — exactly-one-target CHECK (both-null and
  both-set rejected), deliverable-kind CHECK, funder_type column.
- `test_platform_bounty_funding.py` — platform funding posts the sponsorship
  journal (balanced, idempotent re-fund no-op), no credit_accounts touched,
  non-admin → 403, creator-funded regression untouched.
- `test_platform_bounty_acceptance.py` — admin acceptance requires reason,
  stores eval_evidence, accrues contributor payable (`bounty_award`),
  emits event, double-accept idempotent-rejects (409), **merge webhook cannot
  accept a platform bounty** (explicit test), auto-pay impossible (no payout
  row until the normal cash-out flow).
- `test_improvement_landing.py` — bundle repoint + history, tier advance,
  three attribution rows, fixed attribution copy, candidate manifest required
  (422 on missing/invalid), re-scan enqueued; `external_pr` branch: no S3
  writes, merged-PR evidence required.
- `test_license_gate_deliverable.py` — permissive → hosted, restricted &
  unknown → external_pr, derived at creation and immutable after.

CLI: `test_cli_admin_bounties.py` — gating, `--yes` on money paths,
envelopes, eval-evidence file loading; companion eval scenario
`bounty-platform-funded.yaml` (agent explains admin gating + attribution).

## 6. Acceptance criteria

- [ ] Admin creates+funds a bounty on an ownerless indexed listing from the
      platform sponsorship account; ledger journals balance; idempotent.
- [ ] Contributor submits, is accepted only by an explicit admin decision
      with a recorded reason, and accrues payout through the unchanged
      payable/cash-out path — never instantly, never automatically.
- [ ] Listing advances to `improving` with original-author + contributor +
      sponsor attribution and a stored `candidate_capabilities` manifest.
- [ ] Restricted/unknown-license listings route to external PRs; Logion hosts
      no derivative of them (DB constraint from 15.6 still holds).
- [ ] Acceptance confers zero ownership and zero publication trust (listing
      remains unowned/unpublished; claim is 17.3).

## Out of scope

- Machine-executed eval gates (16.1 — the `eval_evidence` field is its
  landing zone); claims/ownership (17.3); sponsorship by anyone other than
  the platform.

## Implementation appendix — compare against current code

Current repo shape to respect:

- Bounty code exists in `backend repository/packages/api/api/bounties` with
  controllers/services/repositories/constants and tests. Extend that domain.
- Payments/credits/ledger code exists under `api/credits` and `api/payments`.
  Platform funding must use the existing ledger abstractions, not a new money
  table.
- CLI admin commands already live in `logion/packages/cli/cli/commands/admin.py`
  and bounties in `cli/commands/bounties.py`.
- Indexed listing tables are from 15.6/15.7 under listings.

Branch targets for 0.1.x live compatibility:

| Work item | Repo | Target branch | Reason |
| --- | --- | --- | --- |
| Bounty schema extensions, platform funding services, admin endpoints, indexed-listing tier/attribution updates | `backend repository` | `main` | Safe if admin-only and existing creator-funded bounty paths remain backward compatible. |
| CLI admin bounty commands and contributor list rendering | `logion` | `0.2.0` | New user/admin visible functionality for 0.2.0. |
| Companion bounty guidance/eval | `logion` | `0.2.0` | Agents should not advertise platform-funded indexed bounties in 0.1.x. |
| Non-platform sponsorship | none | out of scope | Do not generalize funders yet. |

Backend implementation steps:

1. Migration extends `bounties`:
   add nullable `indexed_listing_id fk indexed_listings.id`,
   `target_kind course|indexed_listing`,
   `deliverable_kind hosted_bundle|external_pr`,
   `funder_type creator|platform`, `platform_funded_at null`,
   `eval_evidence json null`. Add CHECK exactly one target:
   `(course_id IS NOT NULL AND indexed_listing_id IS NULL) OR
   (course_id IS NULL AND indexed_listing_id IS NOT NULL)`.
2. Same migration adds `listing_attributions` if 15.6 did not include it, and
   adds `candidate_capabilities json null`, `improved_bundle_key null`,
   `improved_source_url null` to `indexed_listings`.
3. Keep existing bounty status constants. Add target/deliverable/funder
   constants in `api/bounties/constants`.
4. Extend repositories without breaking existing method signatures. If a
   method assumes `course_id` non-null, either add a new method for indexed
   bounties or branch internally with tests for old paths.
5. Add `CreatePlatformBountyService`: admin-only; load indexed listing; derive
   `deliverable_kind` from license class (`permissive -> hosted_bundle`,
   otherwise `external_pr`); set `funder_type='platform'`; status should match
   the existing created/open lifecycle.
6. Add `FundPlatformBountyService`: admin-only and idempotent. Post a balanced
   platform sponsorship journal using existing credits ledger. Do not debit a
   user `credit_account`. Mark funded/open consistently with current bounty
   flow.
7. Extend submission acceptance:
   platform bounty can only be accepted by admin endpoint with `reason`;
   merge webhook from 15.5 must never auto-accept platform bounties.
8. Hosted bundle acceptance path:
   require uploaded bundle; parse `course/capabilities.yaml` with existing
   `parse_course_capability_manifest`; store as
   `candidate_capabilities.mode='candidate'`; store/repoint improved bundle;
   set listing tier `improving`; enqueue observation re-scan.
9. External PR acceptance path:
   require merged PR evidence from 15.5 submission PR table; store source URL;
   no bundle storage; set tier `improving`.
10. Attribution:
    ensure `original_author` exists from ingestion; add `contributor` from
    accepted submission agent/user; add `sponsor` display name `Logion`.
    Search/detail rendering must use fixed copy:
    `improved by {contributor}, funded by Logion - original by {author}`.
11. Payout:
    accrue the contributor payable using existing accepted-bounty payout path.
    Do not create instant payout or new cash-out code.

Admin endpoint plan:

```text
POST /v1/admin/bounties
POST /v1/admin/bounties/{bounty_id}/fund
POST /v1/admin/bounties/{bounty_id}/submissions/{submission_id}/accept
POST /v1/admin/bounties/{bounty_id}/submissions/{submission_id}/reject
```

Request bodies:

```json
{"indexed_listing_id":"...","title":"...","reward_cents":5000}
```

```json
{"reason":"meets eval evidence","eval_evidence":{"scenario":"manual-v1"}}
```

Error mapping:

- non-admin -> 403;
- both course and indexed target -> 422 `bounty_target_invalid`;
- hosted bundle missing candidate manifest -> 422
  `candidate_capabilities_required`;
- restricted license with hosted bundle -> 409 `license_requires_external_pr`;
- webhook merge trying to accept platform bounty -> ignored plus event, or
  409 in direct service tests.

CLI implementation steps:

1. Extend `cli/commands/admin.py` with nested `admin bounties`.
2. Keep `LOGION_ENABLE_ADMIN=1` gating consistent with existing admin
   commands.
3. Money/decision commands require `--yes`; missing confirmation returns
   `confirmation_required`.
4. `--eval-evidence FILE.json` reads JSON with clear parse errors and passes it
   unchanged to backend.
5. Extend `bounties list --tier indexed` rendering in the existing bounties
   command. Do not hide creator-funded bounties.

Minimum tests:

- DB CHECK tests for exactly-one target and deliverable/funder constants.
- Regression tests for existing creator-funded course bounty create/fund/list.
- Platform funding ledger balance/idempotency tests.
- Acceptance tests for hosted bundle, external PR, missing reason, double
  accept, webhook non-acceptance, payout accrual but no instant payout.
- Indexed listing detail/search tests for tier `improving`, attribution rows,
  and candidate capabilities.
- CLI admin tests for gating, `--yes`, JSON envelopes, and eval evidence file.

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a derivative with a named owner and immutable lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
