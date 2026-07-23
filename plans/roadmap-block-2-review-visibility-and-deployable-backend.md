<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Roadmap Block 2 — Review Visibility And Approved Capability Surfaces

This phase turns the capability system into a reviewer trust surface, an author feedback surface, and a safe approved-capability surface on already-authorized reads.

## Goals

- reviewers can detect mismatches between declared and observed course behavior
- approved capability data becomes visible without leaking moderation evidence

## Why this phase comes second

Phase 1 makes capabilities and free-course flows real.
Phase 2 turns them into launchable trust and visibility primitives.

Without this phase:

- review evidence remains too generic for high-signal human moderation
- authors still have to reverse-engineer capability-related rejections
- approved capability visibility remains too weak for trustworthy acquisition/use surfaces

## Plans in this phase

4. `phase-4-course-capability-review-pipeline-and-mismatch-detection.md`
5. `phase-5-course-capability-review-decisions-and-buyer-visibility.md`

## Exit criteria

Phase 2 is done when:

- review jobs can compare declared capabilities with review findings
- reviewers can approve/reject with capability-aware evidence
- authorized course/version reads expose approved capability summaries without leaking moderation internals
- author feedback can point to specific capability mismatch reasons

## What this unlocks next

After this phase, the project becomes ready for a real connected manual test environment:

- trust surfaces are visible
- review decisions are meaningful
- the first-party skill, installer, and landing work can target a stable trust model
