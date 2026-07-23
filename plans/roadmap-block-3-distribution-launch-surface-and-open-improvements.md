<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Roadmap Block 3 — Distribution, Launch Surface, Infra, And Open Improvements

> **Historical / superseded.** This block describes the (now mostly shipped)
> phase-by-phase arc. The live plan is
> `cycles/cycle-1-to-release.md`; some phase
> links below were renumbered/absorbed and may be stale. The current
> post-launch plans start at Phase 15 in `plans/next-steps.md`.

This phase packages Logion into something users can actually discover, install, and operate from their existing agent workflow.

## Goals

- the first-party Logion companion/product exists as a real public artifact
- releases and installation are simple
- the public landing page explains the product clearly
- local release-readiness dogfood proves the end-to-end product loop before deployment
- GitHub-backed publishing and bounty collaboration exist as optional creator
  workflows
- deployable infra lands after the local product loop and integration compiler are validated
- the roadmap leaves room for open improvement proposals beyond creator-funded bounties

## Why this phase comes third

The earlier phases make the product trustworthy.
This phase makes it distributable, explainable, and finally deployable when launch is actually near.

## Plans in this phase

6. `phase-6-logion-marketplace-companion-product-v1.md` and technical sub-plans:
   - `phase-6.1-agent-companion-package-and-product-contract.md`
   - `phase-6.2-bootstrap-skill-and-low-context-routing-policy.md`
   - `phase-6.3-local-installation-cache-and-update-workflow.md`
   - `phase-6.4-eval-harness-and-scenario-catalog.md`
   - `phase-6.5-llama-cpp-gguf-local-model-evaluation.md`
   - `phase-6.6-dspy-offline-optimization-experiments.md`
   - `phase-6.7-logion-cli-gaps-for-skill-distribution.md`
   - `phase-6.8-agent-assisted-course-authoring-and-management.md`
   - `phase-6.9-local-recall-fuzzy-finder-guardrail.md`
7. `phase-7-public-release-installer-pipeline.md`
8. `phase-8-landing-page-v1.md`
9. `phase-9-credits-and-smooth-acquisition-flow.md` — MVP-blocking; replaces per-course Stripe Checkout with credit top-up + atomic credit-debit purchases, adds the referral program (Lanes A and B), re-denominates bounties in credits, and ships landing/legal copy updates (sub-phases 9.1–9.8). All payouts are synchronous, user-triggered HTTP requests — no scheduled job, no worker process.
10. `phase-10-local-release-readiness-and-e2e-dogfood` (done; plan files removed — the recurring manual checklist lives in [`maintainer documentation: release-smoke-checklist.md`](../maintainer documentation: release-smoke-checklist.md)) — prove the full local marketplace, CLI, fixture course, companion, and agent-harness loop before deployment
11. Public scanners and reproducible publication policy (done; plan files
    removed — current behavior lives in
    [`maintainer documentation: review-and-trust-pipeline.md`](../maintainer documentation: review-and-trust-pipeline.md),
    [`maintainer documentation: public-repo-overview.md`](../maintainer documentation: public-repo-overview.md),
    and
    [`maintainer documentation: local-development-and-devrig.md`](../maintainer documentation: local-development-and-devrig.md))
12. Vendor integration compiler exploration was deferred; current telemetry
    direction prefers one Logion entrypoint before vendor plugin sprawl.
13. `phase-13-cheap-mvp-infra-iac-and-backups.md` — production-shaped deployment and backup work after local dogfood has validated what is being deployed
15. [`phase-15-native-resource-loop-and-first-ai-catalog-ard-node.md`](phase-15-native-resource-loop-and-first-ai-catalog-ard-node.md) — shipped GitHub/indexing foundation followed by native acquisition/feedback and the first AI Catalog-compatible, ARD-discoverable improvement node
16. [`phase-16-distributed-evaluation-and-independent-verification.md`](phase-16-distributed-evaluation-and-independent-verification.md) — portable evals, runner-supplied compute, and independent verification
17. [`phase-17-open-ecosystem-and-production-hardening.md`](phase-17-open-ecosystem-and-production-hardening.md) — conformance, federation, commercial rails, and trust hardening
18. [`phase-18-network-liquidity-and-independent-operation.md`](phase-18-network-liquidity-and-independent-operation.md) — useful activity not operated or manually coordinated by Logion

## Exit criteria

Phase 3 is done when:

- the first-party Logion Marketplace Companion package can be installed and used without GEPA/DSPy runtime dependencies
- GitHub Releases and the installer can deliver CLI + skill in one path
- the landing page explains what Logion is, how to install it, and the legal basics
- buyers can top up credits once via Stripe Checkout and acquire paid courses atomically (no browser redirect at install time); creators pull fiat via synchronous `logion payments cash-out`; referral program (product + creator lanes) and credit-funded bounties are live; landing + four legal pages (Terms, Privacy, Credits Terms, Referral Terms) are live (Phase 9)
- the full marketplace loop has passed local dogfood, including fixture course publication, acquisition, companion install/use, notifications, referrals, bounties, reviews, feature flags, payments, and reports
- automated E2E coverage protects the core local marketplace path
- the vendor integration compiler can generate deterministic packages for Hermes Agent, Claude Code, and Codex from a generic manifest
- the backend can be deployed through reproducible IaC once local dogfood and compiler reference backends are ready
- if needed at launch, execution policy export is available for install/runtime gating

## Bounties and open improvements

I do think your concern is valid: if only course creators can open funded work, some valuable courses may stagnate even when the marketplace sees obvious improvements.

My recommendation is:

- keep creator-funded bounties as one path
- add open improvement proposals as a second path
- allow platform-sponsored or third-party-sponsored bounties that are attached to a course but not owned by the course creator

That gives the marketplace three improvement lanes:

1. creator-funded bounty
2. sponsor/platform-funded bounty
3. unfunded open proposal that can later be accepted, sponsored, or turned into a bounty

That direction makes sense, but I would still treat it as a post-core-MVP extension rather than a blocker for the first launch.
