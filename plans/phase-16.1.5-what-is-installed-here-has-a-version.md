<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.1.5 — What is installed here has a version, and its use is recorded against it

Logion publishes a SHA-256 for its own companion skill at
`/.well-known/agent-skills/index.json`. The copy of that skill installed on the
founder's machine has a different digest, has had one since it was copied in on
2026-06-28, and nothing on the machine knows.

```text
published   sha256:faf7f7f7cf3e42760f3c3decea7be42048c726ce8d9998900d409c441188ef0e
installed   sha256:366a74d9854983a9c31b39581985d98ef6f1fb3e6151a858ebbcae12c1016b63
```

The published digest matches `packages/agent-companion/SKILL.md` exactly, so the
landing's drift test is doing its job. The gap is on the other side, where
nothing is watching: the artifact that is loaded into every session.

## The census, measured 2026-09-08

Fourteen skills are installed at `~/.claude/skills/`, all of them loaded into
every session on this machine:

| Family | Installed | Version on disk | Upstream | State |
| :-- | :-- | :-- | :-- | :-- |
| `logion` | 2026-06-28 | `manifest.json` 0.1.4 | published digest, CLI at 0.1.15 | **stale** |
| `factory-*` (4) | 2026-08-18 | none | `software-factory` `v0.4.0`, tagged 2026-09-04 | **2 of 4 differ from the tag** |
| `amy-*` (7) | 2026-09-03/05 | none | `amy` `main` | 6 match HEAD, which is not a release |
| `amy-develop` | 2026-09-03 | none | **withdrawn upstream** | still installed, still loaded |
| `antikus-code-review` | 2026-07-31 | none | not recorded anywhere | unknown |
| `find-skills` | symlink | none | `~/.agents/skills/` | out of this tree |

`amy-develop` is the sharpest one. Commit `a850603` in `amy` is titled *"chore(skills):
amy-develop belongs to this repository, not to the install"* — the skill was
deliberately removed from the installable set. It is still on this machine, and
it is still in the skill list of every session started here. Upstream withdrew
it and the machine never heard.

**One of the fourteen carries a version at all, and it is Logion's own, and it
is wrong.** None carries a digest that anything checks.

Beyond the skills:

- **18 `@amykit/plugin-*` packages at 0.2.0**, installed into amy's home and
  invisible to `~/.claude/plugins/installed_plugins.json`, which knows exactly
  one plugin on this machine: `frontend-slides@2.1.0`.
- **`sf` 0.4.0**, a cargo-installed binary invoked as `sf check`, used in this
  workspace and inside amy.

This is the product's own thesis, at N=1, failing on the founder's own laptop:
nobody publishes what an installed artifact actually is, so nobody can tell you
whether the thing you are running is the thing that was measured.

## Why the loop 15.11 shipped cannot see any of it

Four mechanical reasons, all of them findable in the code rather than inferred:

1. **It has never been switched on here.** `~/.logion/integrations.json` is
   `{}`. There is no `usage/` spool and no `inventory/` directory. Consent
   defaults to `off` per harness, which is right, and nobody ever said yes.
2. **Attribution is path-based against acquisition receipts.**
   `cli/usage/attribution.py` matches path-shaped arguments against
   `_receipts.load_receipts()`. With no receipts, every observation resolves to
   nothing and is dropped.
3. **A receipt requires a catalog match.** `resources reconcile` records a
   receipt only where a locally installed artifact resolves to a *unique
   catalog resource*. None of these artifacts is catalogued, so no receipt can
   exist, so nothing is attributable. This is the actual blocker and it is one
   rule.
4. **`discover_native_state` knows two managers**, `skills` (a
   `skills-lock.json`) and `plugins` (`.agents/plugins/manifest.json`,
   `.claude/plugins.json`, `plugins.json`). Every artifact above arrived by
   directory copy, by npm into amy's home, or by cargo. None of the three files
   it reads is in play.

And a fifth, which is deliberate and should stay deliberate:
`_PATH_TOKEN_RE` requires a separator before a token counts as a path, because
*"a bare word like `pytest` is a program name, not evidence"*. `sf check` is a
bare word. **software-factory cannot be observed today even in principle.**

## The shape: index what is already being run, then the existing loop works

The cheap correct move is not a second observation mechanism. It is to make
these artifacts catalogued subjects, because everything downstream — receipts,
attribution, `usage pending`, `feedback submit --rating` against a version — is
already built and already tested, and starts working the moment a subject
exists.

All three families are public and indexable under the settled
`indexed → improving → claimed` boundary, with attribution, source link and
honest tiering:

- **amy plugins** — 18 npm packages under `@amykit/`, with versioned releases
  and a repository field pointing at the directory each came from;
- **software-factory** — a public repository with tags `v0.2.0`, `v0.3.0`,
  `v0.4.0`, and a `catalog/` whose fingerprint `sf` 0.4.0 already compares
  against a committed value under `L2.CATALOG_ONLY_TIGHTENS`;
- **the skills** — files, with digests, some already published.

They are first-party in the sense that matters: the same person wrote them.
That is a disclosure obligation, not a disqualification. They are tiered
`indexed`, the authorship relation is recorded, and **a subject this operator
authored is never the example used to argue that the method is independent.**
Publication of anything from this corpus goes through
[`../maintainer documentation: measurement-publication-playbook.md`](../maintainer documentation: measurement-publication-playbook.md).

## Version identity, which is not the same fact three times

- **A skill** is a directory. Identity is its content digest, resolved against
  the publisher's digest where one is published — Logion publishes one, `amy`
  and `software-factory` do not. Where upstream publishes no digest, identity
  is (source repository, tag or commit, path) and the receipt carries
  `verification: unverified` rather than implying a check that did not happen.
- **An amy plugin** is `name@version` from npm, and amy's own home records
  which are installed. That state file is one adapter in
  `discover_native_state`, in the same shape as the two already there.
- **software-factory** is a release tag *plus* the catalog fingerprint. Two
  builds at the same tag with different rule catalogs are not the same subject
  for anything we would want to say about them, and `sf` already computes that
  fingerprint for its own rule.

The last one carries a prerequisite that belongs to the operator, not to the
code: 16.1.2 records that `cargo install --git ... --locked` with no tag tracks
whatever `main` is. **A subject that is "whatever main was that day" cannot be
measured.** Installing from the tag is a one-line change to the install
command, and it is the whole of what "pinned at the release version" requires.
Nothing inside `software-factory` changes.

## The bare-word exception, stated as narrowly as it can be

To observe `sf`, exactly one thing changes: an executable name is attributable
**only when it exactly equals the program name declared by a censused
installation**. No path is inferred, no other token in the command line is
read, the command string still never leaves memory, and an unrecognised program
name is still dropped. That is a lookup against a declared whitelist, not path
inference, so the sentence in `attribution.py` stays true as written: a bare
word is still not evidence — a bare word that matches a declared installation
is.

## Nothing in amy or software-factory is modified

This is the constraint in the ask and it is also the correct engineering
position: **an artifact that has to be modified before it can be measured
cannot be measured by a third party**, which would make the whole thesis
circular. The observer is the harness-level `PostToolUse` hook the CLI already
writes through `integrations enable`, plus a census command. amy's plugins,
workflows, gates and packages are untouched. `software-factory` is untouched;
only which build is installed changes.

## Two profiles, because one of the machines belongs to an employer

amy runs against `revv` repositories at work. The envelope already carries no
path, prompt, tool argument or free text, and `scope_id` is an HMAC keyed by
the local home rather than a hash of the repository path — so nothing in a
record names a work repository. That is necessary and not sufficient.

- The **work profile stays `local-only`**: it spools and never uploads. What
  may leave that machine is a hand-reviewed aggregate — counts per artifact
  version — not per-event receipts.
- The **personal profile runs at `prompt`**, so every upload is an explicit
  act.
- `DO_NOT_TRACK` / `LOGION_DO_NOT_TRACK` continue to win over both.

## Feedback is written after a task, not after an observation

`logion feedback submit RESOURCE_ID VERSION_ID --rating ... --task-class ...`
already exists and already requires a version. The 15.16 rule holds unchanged:
passive observation never justifies a rating. A report is written after a real
task, names the exact version, and says what happened.

At N=1 the honest claim is "one operator, N sessions, this version", the report
says so in those words, and a measurement is not an endorsement. That sentence
has to appear beside the finding rather than in a footer, which is the same
rule every other Logion surface is held to.

## What this is not

- **Not 15.11.1.** That is observation of *other people's* users, needs
  consent, and is off the critical path. This is one operator observing his own
  machine.
- **Not telemetry, and not a product surface.** No dashboard ships here.
- **Not a reason to move commerce earlier**, and not an independence claim.
  First-party evidence about artifacts the operator wrote is disclosed as
  exactly that.

## Acceptance criteria

- [ ] `logion inventory census` lists every installed skill, plugin and
      declared program with a version identity or an explicit `unknown`, and an
      artifact with no upstream is reported rather than skipped
      (proof: test:packages/cli/tests/test_inventory_census.py)
- [ ] An installed artifact with no catalog match receives a local receipt
      marked `unverified` instead of no receipt at all
      (proof: test:packages/cli/tests/test_reconcile_uncatalogued.py)
- [ ] An installed artifact whose digest differs from its upstream's published
      digest is reported as drifted, with the stale companion skill on this
      machine as the fixture
      (proof: test:packages/cli/tests/test_inventory_census.py)
- [ ] An installed artifact whose upstream withdrew it is reported as orphaned
      rather than as current, with `amy-develop` as the fixture
      (proof: test:packages/cli/tests/test_inventory_census.py)
- [ ] amy's home plugin state is an adapter in `discover_native_state`
      alongside `skills` and `plugins`, and adding it changes no existing
      adapter's behaviour
      (proof: test:packages/cli/tests/test_reconcile_uncatalogued.py)
- [ ] A program name is attributed only on exact match against a censused
      installation, and an unknown bare word is still dropped
      (proof: test:packages/cli/tests/test_usage_attribution_programs.py)
- [ ] `software-factory`'s subject identity is the release tag together with
      the catalog fingerprint, and two builds at one tag with different
      catalogs are two versions
      (proof: test:packages/cli/tests/test_inventory_census.py)
- [ ] A profile in `local-only` spools and never opens a connection, proven the
      same way `off` is
      (proof: test:packages/cli/tests/test_usage_upload.py)
- [ ] Every feedback report from this corpus names the exact version it is
      about and carries the first-party authorship disclosure
      (proof: test:packages/cli/tests/test_cli_courses_source_link.py)
- [ ] One report per family exists, written after a real task on a real
      repository
      (proof: unspecified:a report an operator writes is not producible by a
      test; what a check can hold is that the record exists and names a version,
      which the criterion above already does)

**Exit condition:** on both machines, every artifact loaded into a session
resolves to a named version; `logion usage pending` is non-empty after an
ordinary working day with no change made to amy or to software-factory; the
stale companion skill, the two drifted `factory-*` skills and the orphaned
`amy-develop` are each reported by name rather than discovered by hand; and at
least one feedback report exists per family, naming the exact version it is
about.
