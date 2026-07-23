<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.8.1 — Public planning mirror and contribution workflow

> **Dogfood status:** this is an open-source governance prerequisite. Its
> canonical-to-public workflow must publish every later phase change.

## Goal

Keep `plans/` and `future-roadmap/` in the private maintainer workspace as the
canonical implementation source while publishing deterministic, sanitized
mirrors at the same paths in the public `logion` repository.

## Direction of authority

```text
canonical maintainer workspace
  → sanitize + validate + manifest
  → public repository sync PR
```

There is one source of truth. The public mirror is intentionally
contribution-friendly but not a second independently merged planning history.

## Public contribution path

1. A contributor opens a public PR against `plans/` or `future-roadmap/`.
2. Maintainers review the idea and request any product/security clarification.
3. Before merge, an accepted patch is applied to the canonical private source.
4. The canonical sync regenerates the public mirror and manifest.
5. The contributor remains credited in the public PR/commit and, where
   appropriate, in the canonical change.

A public planning PR is never silently overwritten or merged only in the
mirror. GitHub Discussions remain appropriate for ideas that do not yet have a
specific document patch.

## Sanitization boundary

The exporter:

- copies Markdown only;
- removes private repository identifiers and private-only relative links;
- preserves public plan titles, product contracts, scenarios, gates, and
  sequencing;
- rejects secrets, absolute user paths, credentials, and unrecognized private
  markers rather than guessing;
- adds a generated-source/contribution notice;
- writes deterministic SHA-256 entries to
  `docs/roadmap-sync-manifest.json`;
- deletes mirror Markdown files no longer present in the canonical source.

The public security audit continues scanning these directories for secrets and
private identifiers. Only the old blanket ban on public planning vocabulary is
scoped away for `plans/` and `future-roadmap/`.

## Automation

Canonical workspace commands:

```bash
make public-roadmap-sync PUBLIC_REPO=/path/to/logion
make public-roadmap-sync-check PUBLIC_REPO=/path/to/logion
```

A private-repository GitHub workflow runs on canonical planning changes,
checks out the public repository with a narrowly scoped secret, regenerates the
mirror, runs public guardrails, and opens or updates a public sync PR. It never
pushes directly to public `main`.

Required private secret:

```text
PUBLIC_ROADMAP_TOKEN
```

The token is scoped only to contents and pull requests on the public repository.
Fork PRs never receive it.

## Concrete implementation

Canonical workspace:

- add `scripts/sync_public_roadmap.py` with render and `--check` modes;
- add `.github/workflows/sync-public-roadmap.yml`;
- add both Make targets and deterministic sanitizer fixtures;
- treat every `plans/*.md` and `future-roadmap/*.md` file as mirror input.

Public repository:

- allow the two root directories in `.allowed-root-files`;
- scope planning-language exemptions in `scripts/audit_public_safe.py` to those
  directories while continuing to reject private identifiers and secrets;
- add `scripts/check_roadmap_mirror.py` and run it from `make ci-checks`;
- document the public contribution/canonicalization workflow in `AGENTS.md` and
  `CONTRIBUTING.md`.

Tests use temporary canonical/public Git repositories and cover byte-stable
reruns, changed/deleted files, stale manifests, broken private links, private
markers, absolute paths, secret patterns, untracked extra mirror files, and
concurrent contributor changes. The workflow must create a fresh bot branch and
PR; it never force-pushes or writes public `main`.

## Drift rules

- Private `--check` compares canonical rendered bytes with the public checkout.
- Public CI recomputes the manifest and rejects undocumented mirror edits.
- External public PRs update the manifest with the public helper only for
  review; they are not merged until the canonical source produces the same
  content.
- A sync PR includes source commit, aggregate digest, changed files, and any
  sanitization rejection.
- Concurrent public edits cause the sync workflow to stop and request maintainer
  reconciliation; it does not force-push over a contributor branch.

## Acceptance gates

### Mandatory real-agent scenario

Add `builtin:phase_15_8_1_public_planning_contribution` and run it with
GPT-5.4-mini or Claude Haiku. Use a disposable public checkout while the normal
local API/devrig remains healthy.

- Prompt: “Read the public ordered plans, identify the first unfinished phase
  after 15.8, and propose a one-line clarification through the documented
  contribution workflow. Do not invent a second source of truth.”
- The agent must find `plans/next-steps.md`, edit the correct numbered public
  phase, update the manifest with the documented helper, and explain the
  canonicalization step before merge.
- Assert `files.ordered_phase_found`, `files.public_plan_patch_created`,
  `files.roadmap_manifest_valid`, `files.private_marker_absent`,
  `files.doc_links_valid`, and `git.canonicalization_boundary_respected`.
- A private link/secret or edit to an automation branch is the negative case
  and must fail closed.
- Retain the prompt, patch, helper output, selected phase number, and all
  guardrail results. Scripted tests alone do not close this phase.

- A one-line canonical plan edit deterministically changes the corresponding
  public file and manifest.
- A deleted canonical document disappears from the mirror through a reviewable
  public PR.
- A private marker or broken generated link fails sync before push.
- Public CI accepts a clean generated mirror and rejects a modified file with a
  stale manifest.
- Contributor documentation explains how a public patch becomes canonical and
  preserves attribution.
