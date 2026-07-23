<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Roadmap Block 1 — Core Marketplace Flows And Capability Foundations

This phase is the first MVP execution block.

Its job is to remove the biggest user-facing friction and make the capability model real enough to support trustworthy manual evaluation.

## Goals

- free courses work end-to-end without Stripe friction
- course capability manifests become persisted, uploaded, and visible to authors
- the public CLI and SDK keep one stable flow while backend behavior gets smarter

## Why this phase comes first

Without this phase:

- the first-party free Logion skill/course still hits unnecessary payment friction
- creators cannot reliably publish free courses without seller onboarding baggage
- capability review is still too thin for meaningful manual testing of the trust model

## Plans in this phase

1. `phase-1-free-course-zero-stripe-flows.md`
2. `phase-2-course-capability-persistence-and-upload-finalization.md`
3. `phase-3-course-capability-author-workflows-and-read-surfaces.md`

## Exit criteria

Phase 1 is done when:

- free courses use the same checkout endpoint but automatically bypass Stripe when `price_cents == 0`
- sellers of free courses do not need Stripe onboarding
- buyers of free courses get immediate entitlement grant without Stripe Checkout
- capability manifests are persisted with course versions
- author-facing surfaces can inspect and validate the declared capabilities of a course version
- CLI and SDK expose the flow clearly enough for manual inspection

## What this unlocks next

After this phase, Logion becomes much easier to dogfood internally because:

- the free first-party skill/course path becomes viable
- course packages can start carrying real capability declarations
- the review pipeline can begin comparing declaration vs observed behavior in the next phase
