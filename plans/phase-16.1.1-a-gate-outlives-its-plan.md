<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.1.1 — A gate outlives its plan

A plan is a thing you are about to do. A gate is a thing that stays true. This
workspace welds the two together: every entry in
`packages/contract-audit/policy/phase-integrity.yaml` names a canonical plan,
`phase_integrity.py` reports `canonical plan for phase X is missing` the moment
that file goes, and `evidence_contract.validate()` refuses an
`evidence_contracts` block whose phase has no entry. A delivered plan therefore
cannot be deleted, and [`next-steps.md`](next-steps.md) already says so as a
sequencing rule: *"Closing a phase is not retiring its plan, and from 15.15 on
it usually must not be."*

So `plans/` has become an archive. Forty-one documents, three of which —
15.14.1, 15.15 and 16.1 — carry work that is delivered and sealed and cannot be
moved, because moving it deletes a check. The one question the directory exists
to answer, what is next, is answered by one table inside a 383-line file, and
every closure makes the file longer.

## What deleting them actually did

Five plans were retired the other way, before that rule existed: `15.10`,
`15.10.1`, `15.11`, `15.11.1` and `15.12`, deleted from this workspace on
2026-08-27. All five are still published on the public repository's `main`
today. `plans/` is mirrored there by `scripts/sync_public_roadmap.py`, the
deletion never arrived, and `make public-roadmap-sync-check` names all five
right now as `unexpected mirror file`, next to a stale manifest.

Deleting a delivered plan did not retire it. It moved the surviving copy to the
one repository where nobody maintains it — published, unlinked and eleven days
stale — while the record of what shipped was compressed into a
`Plan retired 2026-08-27` footnote in the execution order.

That is the whole argument for this plan in one observation: a retirement that
is half a deletion has no owner, no check and no evidence that it completed.

## Where a delivered plan goes

To `maintainer documentation: phases/<number>-<slug>.md`: numbered, carrying its acceptance
criteria settled, its exit condition, the sealed gate it produced, and the
paragraph of argument that says what the phase turned out to be about.

That is already where the shipped shape lives. The retirements the execution
order records point at `../maintainer documentation: ` for what was delivered — native
acquisition, native observation, catalog and ARD discovery — except 15.11.1,
which was never built and points at git history. The change is that the
document *moves* instead of being paraphrased by a footnote, and that it keeps
its number.

The number is not decoration. The pre-Phase-15 roadmap blocks were deleted on
2026-08-18 for reusing `15`, `16` and `17` for phases that mean something else
today, and nothing in the workspace would notice that happening again. An
archive keyed by number does: a number is spent once, and a spent number
reappearing in `phases:` becomes a finding instead of an archaeology problem.
Sub-numbering inherits the property — `16.1.1` is a child of `16.1`, archives
as its sibling, and cannot quietly become a second `16.1`. That is what makes
the split in [`16.1.2`](phase-16.1.2-a-plan-is-one-pull-request.md) safe to do
repeatedly, and it is why this document is `16.1.1` rather than a slug: it sits
between 16.1 and 16.2, and it spends a number to say so.

`maintainer documentation: ` is not mirrored to the public repository, so a plan that moves
there leaves it. That is the intended direction, and the mechanism already
exists: the sync unlinks a mirror file whose source is gone. It is the half
that has never run.

## docs integrity

`phase-integrity.yaml` governs work in flight. Nothing governs a document after
its work lands, which is exactly why a retirement could sit half-done for
eleven days without a red check anywhere.

So the archive gets a policy of its own:
`packages/contract-audit/policy/docs-integrity.yaml`, read by
`contract_audit/docs_integrity.py`, scanned from `contract_audit check --mode
fast` next to `phase_integrity.scan`, with its mutations in
`tests/unit/test_docs_integrity.py`, where `make contract-audit-test` runs them
in CI. Six claims, each of them a way retiring a phase has already gone wrong
or could:

**A number is spent once.** No number appears twice in the archive, and none
appears in the archive and in `phases:` at the same time.

**A retirement is atomic.** Removing a `phases:` entry without adding the
archived document for its number is a finding, and an archived document whose
number still has a live entry is a finding. Both halves land in one commit or
neither does.

**The seal outlives the entry.** An archived document names its sealed gate
under `artifacts/phase-gates/` in the public checkout, that file exists, and
the digests it recorded still verify. Retiring an entry retires the obligation;
it must not retire the evidence.

**Debt does not evaporate.** Every criterion arriving in the archive is `- [x]`
with a dated settlement note, or still carries the `deferred:` /
`unspecified:` marker that `make deferrals` indexes. Closing a phase must not
become a way to empty `DEFERRED.md`.

**A standing invariant is re-homed before its phase goes.**
`server_authoritative_request_fields` is checked only for *activated* phases,
and 15.15 and 16.1 are the two entries carrying it. Removing those entries
removes a guard on live code that nobody would think to re-add. So the policy
grows a `standing:` block keyed by archived document rather than by phase, and
an entry carrying a standing key cannot retire until that key has a home there.

**A document lives in one place.** A file present under both `plans/` and the
archive is a finding — the check the five stale mirror files needed and did not
have.

## What lands here, and what does not

The machinery, plus the one retirement that is already overdue. The five
2026-08-27 numbers get archive documents; because their plan text is only in
git history, each is a short numbered record naming what shipped, where the
shipped shape lives, and its sealed gate where one exists — `15.11` and `15.12`
have one, `15.11.1` was never built and its record says so. Spending the number
is the point; restoring 2,000 lines of superseded design is not.

The four live phases stay where they are. 15.14.1, 15.15, 16.1 and 16.2 are
still being read as evidence contracts, and whether a live phase's plan moves
at its own closure or at the release that contains it is a question the first
closure under this machinery should answer, not this document.

`L3` in the workspace's `sf` policy is untouched here.
`phase-integrity.yaml` remains the phase gate, for the reason its own comment
gives — two gates for one thing is worse than one. Which `sf` rules turn on,
and where, is [16.1.2](phase-16.1.2-a-plan-is-one-pull-request.md).

## Numbered, and deliberately ungated

16.1.1, 16.1.2 and 16.1.3 are numbered because they are work between 16.1 and
16.2 and the execution order should say so. None of them becomes an entry in
`phase-integrity.yaml`.

A phase entry demands a named builtin scenario, a pinned real driver and a
sealed manifest, because a phase is a claim that something shaped like a
customer reached an effect. A policy change and a generator have no customer
effect to reach, and inventing a scenario so that one could be sealed is the
reward-hacking shape this workspace exists to refuse. Their proof kind is
`test:`, which is what that marker is for.

Which makes the archive's claim stronger rather than weaker: **a number is
spent once, whether or not it ever carried a gate.** `docs-integrity.yaml` is
keyed by number, not by the presence of a `phases:` entry, so these three
retire into `maintainer documentation: phases/` on exactly the same terms as 15.12 did.

## Acceptance criteria

- [x] Removing a `phases:` entry without its archived document turns the audit
      red, and so does an archived document whose number still has a live entry
      (settled 2026-09-07: the `spent:` ledger makes the atomicity claim hold
      for every number the workspace consumed, not only the two carrying a
      standing invariant — dropping 15.14.1 or 16.2 from `phases:` now goes red)
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [x] A number appearing twice in the archive, or in both the archive and
      `phases:`, is a finding
      (settled 2026-09-07)
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [x] An archived document whose sealed gate is missing, or whose recorded
      digest no longer verifies, is a finding
      (settled 2026-09-07)
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [x] A criterion arriving in the archive neither settled with a date nor
      carrying its debt marker is a finding, and the debt an archived document
      carries is still listed by `make deferrals`
      (settled 2026-09-07: the archive is a third source in
      `deferral_ledger.collect`, so an archived `deferred:`/`unspecified:`
      marker keeps its row in DEFERRED.md)
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [x] A phase entry carrying `server_authoritative_request_fields` cannot
      retire until a `standing:` entry names the document that inherited it
      (settled 2026-09-07)
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [x] A document present under both `plans/` and `maintainer documentation: phases/` is a
      finding
      (settled 2026-09-07)
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [x] `maintainer documentation: phases/` holds a numbered record for 15.10, 15.10.1, 15.11,
      15.11.1 and 15.12, each naming what shipped, where the shipped shape
      lives, and its sealed gate where one exists
      (settled 2026-09-07)
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [x] The `shared_docs` scope in `doc-denylist.yaml` covers
      `maintainer documentation: **/*.md`, so the archive is scanned by the same leak checks
      as the rest of the shared documentation
      (settled 2026-09-07: also fixed the glob rooting — the denylist scanned
      from `public_repo.parent`, one directory above the workspace, where the
      globs matched nothing)
      (proof: test:packages/contract-audit/tests/unit/test_security.py)
- [x] A number with no `phases:` entry still archives, and re-using it is
      still a finding, so 16.1.1-16.1.3 are covered by the same claim as a
      gated phase
      (settled 2026-09-07: the test archives 16.1.1 — no phase entry, no gate —
      records it spent, and requires green plus a finding on re-entry)
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [ ] The five retired plans are gone from the public repository and
      `make public-roadmap-sync-check` is clean
      (proof: unspecified:the mirror is a property of two checkouts and one
      merged sync pull request, not of a run in this one — and the sync
      workflow itself is red for a reason outside this diff: the missing
      PUBLIC_ROADMAP_TOKEN secret and its guardrail step calling two scripts
      the public repository deleted in #267. The workflow file is fixed here;
      the secret is Nico's to create)
- [ ] Whether a live phase's plan moves at its closure or at the release that
      contains it is decided by the first closure under this machinery
      (proof: unspecified:16.1 sealed on 2026-09-07 and its evidence contract
      is still being read; deciding now is deciding without the case)

**Exit condition:** `make contract-audit-fast` runs `docs_integrity` beside
`phase_integrity`; `maintainer documentation: phases/` carries a numbered record for every
retired phase; removing a `phases:` entry without one turns the audit red; the
five 2026-08-27 files are gone from the public repository; and `plans/` holds
one fewer document every time something ships instead of one more.
