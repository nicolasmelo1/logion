<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.1.2 — A plan is one pull request

Phase 16.1 is one entry in `phase-integrity.yaml`: one canonical plan, one
scenario, nine assertions. Measured on 2026-09-07, the day its gate sealed,
this is what that one entry has cost:

| Repository | Pull requests | File changes | Insertions |
| --- | --- | --- | --- |
| `logion` | #317 | 95 | 10,655 |
| `backend repository` | #176 | 16 | 1,414 |
| this workspace | #166, #169, #171, #172, #173 | 28 | 2,374 |

Seven pull requests, 139 file changes, 14,443 inserted lines — and the phase is
not finished. Two of its criteria are still in `DEFERRED.md`
with no check designed, and
[`driven-actor-performs-the-measured-flow.md`](driven-actor-performs-the-measured-flow.md)
exists to reseal it. 15.15 has the same shape: eight assertions, one pull
request in the public repository at 58 files and 9,554 insertions.

Nothing about that is reviewable. A 10,655-line pull request is read for style
and merged on trust, which is the exact failure the phase gate was built to
prevent, arriving through the door the gate does not watch.

## Both rules exist, and here is what each reports today

`sf 0.4.0` carries them: catalog `f4c2b4b783a5`, 38 rules,
`L4.PLAN_PROOF_BUDGET` among them and `L3.GATE_COVERS_THE_PLAN` carrying the
criterion floor as well as the coverage half. Nothing has to ship upstream
first. Measured by enabling each rule against each repository and reverting:

| | `plans/*.md` in scope | `sf check` runs | `L4.PLAN_PROOF_BUDGET` | `L3.GATE_COVERS_THE_PLAN` |
| --- | --- | --- | --- | --- |
| workspace | 40 | pre-commit | **33 findings** | duplicate |
| `logion` | 43 mirrored | pre-commit **and CI** | **31 findings** | **here** |
| `backend repository` | 0 | pre-commit | inert | inert |

All 64 are the floor — *"this plan has no acceptance criteria"* — and **not one
plan exceeds the 60% debt budget**, including the three documents of step 5a at
18%, 20% and 18%. The rule that is supposed to be hard to satisfy is already
satisfied everywhere it applies; what is unsatisfied is the floor.

`logion` reports 31 rather than 33 because its mirror is stale in both
directions: it still carries the five plans of
[16.1.1](phase-16.1.1-a-gate-outlives-its-plan.md), all of which do have
criteria, and it is missing two that do not.

In `backend repository` the rule is inert and `sf` says so in the words the plan
would otherwise have had to guess: *"scope matches no plan file: it can never
measure a plan's proof budget."*

One thing is still owed upstream, and it is not either of these. `logion`'s
policy enables an `L3` rule requiring a driven actor to receive a goal — the
one step 5d depends on — and no released catalog has it, so `sf check` reports
that citation in `logion/docs/factory-rules.md` today, in the document that
exists to explain it. That is a finding this plan inherits rather than creates.

A note on what is not in scope here: `cargo install --git ... --locked` with no
tag tracks whatever `main` is, so the catalog these two rules come from is not
pinned anywhere. 0.4.0 ships the rule for exactly that
(`L2.CATALOG_ONLY_TIGHTENS`, which compares the running catalog against a
committed fingerprint). It is the obvious follow-on and it is not this plan.

## What the two rules do, and what they do not

Neither `L4.PLAN_PROOF_BUDGET` nor `L3.GATE_COVERS_THE_PLAN` measures a diff.
No rule can: the diff does not exist when the plan is written, which is when
the decision that produces it is made. What they do is make a *split* honest,
which is the only lever available before the code exists.

`L4.PLAN_PROOF_BUDGET` is the floor. It requires a plan to carry at least one
acceptance criterion and keeps the share marked `deferred:` or `unspecified:`
under a budget. Without it, splitting 16.1 into three children is trivially
gamed by giving two of them nothing to prove — they would look as green as the
one that did the work. Measured across the 41 documents in `plans/`: **33 carry
no acceptance criterion at all.** Of the eight that do, `15.14` and `16.8`
carry checkboxes with no proof marker on any of them, and `release-0.2` carries
22 checkboxes with markers on 4. The floor is not a hypothetical.

`L3.GATE_COVERS_THE_PLAN` is the weld. Every `assertion:` a criterion names
must appear in the gate's `required_assertions`, and a gate that requires
nothing needs a plan with at least one undeferred criterion. Split 16.1 into
16.1.a and 16.1.b and each child's gate has to cover its own promises, or the
split is just a smaller document in front of the same unproven work.

The thing that forces the split is neither of them, and this plan should not
pretend otherwise: it is a ceiling on what one entry may demand.

## The ceiling

One phase entry, one scenario, and **at most five assertions**. Above that, the
phase splits into numbered children, each of which seals on its own.

Assertion count is the right unit because it is what makes a phase
all-or-nothing. Nine assertions in one gate is nine distinct observable effects
that must *all* land before anything can be sealed, so the pull request cannot
be smaller than the whole phase. Three children of three assertions each seal
three times, and the third one landing late costs the first two nothing.

Activation breadth is the wrong unit, and the data says so: 16.1 declares three
public activation prefixes and produced 10,655 insertions, while 15.14.1
declares six and produced far less. Plan length is the wrong unit too, for the
reason the catalog already gives for measuring ratio instead of markdown — it
measures how much somebody wrote.

Five is a judgement, not a measurement. The four live entries carry nine,
eight, nine and six, so a ceiling of five would have split every one of them,
which is the intended effect. What is honest to say is that no closure has yet
happened *under* this ceiling, so the number carries a review date and the
first two closures after it either confirm it or move it.

## Why the table reads that way

The answer differs per repository because `sf check` does not run in the same
places and the three do not hold the same files.

**`L4.PLAN_PROOF_BUDGET` goes on in the workspace and in `logion`.** The
workspace holds the canonical plans; `logion` holds the mirror and is the only
one of the three that runs `sf check` in continuous integration, on the same
pull requests where the implementation lands. Both are needed: the workspace
copy is where a plan is written, the public copy is where a reviewer meets it.

It stays **off in `backend repository`**, and the reason is written in that
repository's `docs/factory-rules.md` rather than implied. Its `plans/` holds
`next-steps.md` and nothing else, the rule excludes the execution order by
default, and `L5.NO_INERT_RULE` reports the result. A rule that cannot fire has
to say so rather than read as protection, which is the argument
`L6.DATA_RACES_ARE_DETECTED` already carries in `logion`.

**`L3.GATE_COVERS_THE_PLAN` goes on in `logion` only.** It needs a gate that
names a plan, and `logion` is the one repository where every part of that claim
resolves: the mirrored plan under `plans/`, the sealed manifest under
`artifacts/phase-gates/`, the assertion handlers under
`packages/agent-proving-ground/`, and a workflow that runs `sf check` on every
pull request. In the workspace it would report the same fault as
`PHASE_GATE_OMITS_PLAN_ASSERTION` at the same boundary — the pre-commit hook —
and two reports of one fault is what the workspace policy already refuses. In
`backend repository` there is no plan and no manifest to point at.

That makes the public policy a **projection** of `phase-integrity.yaml`, in the
same shape as the OpenAPI contract: canonical on one side, projected to the
other, and the projection's fidelity checked from the only place that can see
both. So `contract_audit` grows one claim — the `gates:` block in the public
policy declares exactly the assertions the canonical phase entry requires — and
the projection is generated rather than retyped, by
[16.1.3](phase-16.1.3-the-documentation-is-read-out-of-the-code.md).

## What enabling a rule actually costs here

Per rule, per repository, and worth stating because it is why this is three
pull requests and not one: a mutation fixture under
`.software-factory/mutations/<RULE>/` (`L5.EVERY_CHECK_HAS_A_MUTATION_TEST`
requires the directory, `sf verify` requires it to trip), a section of prose in
that repository's rules document (`L4.EVERY_RULE_HAS_A_WHY`), and `sf lock` in
the same commit (`L2.FACTORY_CONFIG_IS_LOCKED`).

`L4.PLAN_PROOF_BUDGET` also arrives with 33 existing violations here and 31 in
the mirror. Its ratchet is an allowlist, so `sf ratchet` can hold them — but
`L2.NO_PERMANENT_EXCEPTION` requires a review date on every frozen exception,
which is the correct pressure. The 33 are not one problem: most are reference
documents that were never plans — `positioning-and-independence.md`,
`normative-carry-overs.md` and `consumption-adoption-ladder.md` are standing
policy with no work of their own, and the execution order already says so.
Those belong out of the rule's scope by moving out of `plans/`, not in the
allowlist. The ones that are genuinely
plans and genuinely promise nothing checkable are the finding, and they are the
reason the rule is worth its cost.

## Acceptance criteria

- [ ] `L4.PLAN_PROOF_BUDGET` is enabled in the workspace and in `logion`, each
      with a mutation fixture that trips it under `sf verify`
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [ ] `L4.PLAN_PROOF_BUDGET` is disabled in `backend repository` with the inert
      reason written in its rules document, not merely omitted
      (proof: unspecified:a disabled rule produces no finding to assert on;
      the claim is a property of the policy comment and the diff)
- [ ] `L3.GATE_COVERS_THE_PLAN` is enabled in `logion` against a declared gate
      whose `plan` is the mirrored phase plan, and it is not inert
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [ ] Dropping an assertion from the public policy's `gates:` block, while the
      canonical phase entry still requires it, turns the audit red
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [ ] A phase entry demanding more than five assertions in one scenario is a
      finding, and the ceiling carries a review date
      (proof: test:packages/contract-audit/tests/unit/test_phase_integrity.py)
- [ ] A phase split into numbered children keeps every assertion its parent
      required, across the children, with none dropped in the split
      (proof: test:packages/contract-audit/tests/unit/test_phase_integrity.py)
- [ ] No document in `plans/` is a standing reference rather than work: the
      ones the execution order already describes as having no work of their own
      have moved to `maintainer documentation: `
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [ ] Every remaining `L4.PLAN_PROOF_BUDGET` violation is in the ratchet
      allowlist with a review date, and the allowlist is smaller than 33
      (proof: unspecified:the allowlist size is a property of the committed
      ratchet, and no run can assert what the right size is)
- [ ] `sf verify` is green in all three repositories and `sf check` is green in
      the two where these rules are on
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)

**Exit condition:** a plan that promises nothing turns `sf check` red in the
workspace and in `logion`'s continuous integration; a gate in the public policy
that requires less than its canonical phase entry turns the audit red; a phase
entry demanding more than five assertions is a finding; and the next phase
after 16.2 lands as numbered children whose largest pull request a reviewer can
read in one sitting.
