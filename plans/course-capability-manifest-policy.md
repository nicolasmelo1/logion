<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Course Capability Manifest And Execution Policy Plan

> **Historical / superseded.** Capability persistence/review (old phases 2–5)
> shipped — current state lives in [`../maintainer documentation: `](../maintainer documentation: ).
> Runner enforcement now belongs to
> [`phase-15.15`](phase-15.15-isolated-first-runner-node.md), with typed
> evaluator projection in [`phase-16.2`](phase-16.2-typed-evaluators-and-skill-reference-evaluator.md).

This umbrella plan is now split into PR-sized implementation plans:

1. `plans/phase-2-course-capability-persistence-and-upload-finalization.md`
2. `plans/phase-3-course-capability-author-workflows-and-read-surfaces.md`
3. `plans/phase-4-course-capability-review-pipeline-and-mismatch-detection.md`
4. `plans/phase-5-course-capability-review-decisions-and-buyer-visibility.md`
5. `plans/phase-15.15-isolated-first-runner-node.md` and
   `plans/phase-16.2-typed-evaluators-and-skill-reference-evaluator.md`

## How To Use This Set

- Treat each file above as one PR.
- Land them in order.
- Do not start the next PR until the previous PR has merged and its OpenAPI / client
  regeneration is stable.
- Keep runtime sandboxing out of these PRs; the output of this plan set is a trustworthy
  declaration + review + export surface, not hosted secure execution.

## Why The Split

The original document mixed five different scopes:

- upload-time manifest ingestion
- author UX
- review mismatch detection
- review decisions and buyer-safe visibility
- runner-facing execution policy export

Trying to land all of that in one implementation PR would create a review surface that is
far too broad across:

- `backend repository/packages/api`
- `logion/packages/client`
- `logion/packages/cli`

The split files keep each PR narrow enough that the changed models, endpoints, CLI
commands, generated SDK surfaces, and tests stay reviewable.
