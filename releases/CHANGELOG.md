# Changelog

All notable changes to the Logion packages are documented in per-package
CHANGELOG files below their respective directories. This top-level file
aggregates the current released version of each package.

## 0.1.14

### Bug Fixes
- **scanners**: avoid executable-code findings for full-line comments (#205) — @Nicolas Leal
- **release**: pass the semantic-release config option before the subcommand (#206) — @Nicolas Leal

**Contributors:** @Nicolas Leal

## 0.1.13

### Features
- **landing**: landing GitHub signin (#150) — @Nicolas Leal
- **agent-proving-ground**: phase 18.3 remote/local-devrig adapters and local assertions (#142) — @Nicolas Leal
- **agent-proving-ground**: add real agent drivers for phase 18.2 (#140) — @Nicolas Leal
- agent proving ground core (phase 18.1) (#139) — @Nicolas Leal
- **identity**: add GitHub identity CLI commands and SDK methods (#136) — @Nicolas Leal
- **credits**: add --currency flag to top-up CLI command (#134) — @Nicolas Leal

### Bug Fixes
- **cli**: harden setup token onboarding (#152) — @Nicolas Leal
- **ci**: move private-referencing e2e guide out of public repo, fund bounty in mock loop (#148) — @Nicolas Leal
- **proving-ground**: phase-isolated scaffolding and bounty submission visibility (#146) — @Nicolas Leal
- **agent-proving-ground**: fix Hermes local-devrig flow (#144) — @Nicolas Leal
- **agent-proving-ground**: isolate marketplace assertions (#143) — @Nicolas Leal
- **cli**: sync agent skill copies after updates (#137) — @Nicolas Leal

### Refactors
- **proving-ground**: flatten package layout, default claude-code to haiku (#149) — @Nicolas Leal

### Documentation
- fix installer redirect claim and post-publish README wording (#135) — @Nicolas Leal

### Chores
- sync OpenAPI contract from the API source of truth (#129) — @Nicolas Leal

**Contributors:** @Nicolas Leal

## 0.1.12

### Features
- **release**: auto-generate changelog from merged PRs (#133) — @Nicolas Leal

### Bug Fixes
- **update**: clean installer output and docs guidance (#132) — @Nicolas Leal
- **cli**: align Codex skill path and companion cleanup (#131) — @M'ael

**Contributors:** @M'ael, @Nicolas Leal

## 0.1.0 (Initial Release)

- **logion-cli**: 0.1.0
- **logion-client**: 0.1.0
- **logion-companion**: 0.1.0