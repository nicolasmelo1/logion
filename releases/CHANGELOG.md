# Changelog

All notable changes to the Logion packages are documented in per-package
CHANGELOG files below their respective directories. This top-level file
aggregates the current released version of each package.

## 0.1.15

### Features
- **cli**: indexed listing discovery opt-in and get command (#207) — @Nicolas Leal
- **agent-proving-ground**: cross_session_skill_use builtin scenario (#204) — @Nicolas Leal
- **indexer**: add public skill hub sources (#202) — @Nicolas Leal
- **landing**: lead with the proof-over-popularity thesis (#198) — @Nicolas Leal
- **indexer**: add public skillhub indexer package (#191) — @Nicolas Leal
- **cli**: courses source-link commands + proving-ground GitHub observer (#188) — @Nicolas Leal
- **landing**: smooth scroll and stacked-section scrolling (#185) — @Nicolas Leal
- **cli**: phase 15.5.2 auto GitHub PR submissions (#179) — @Nicolas Leal
- **bot**: issue-mention bounty bot grammar, parser, and replies (#178) — @Nicolas Leal
- **landing**: setup-complete handoff page\n\n- Add /setup/complete route with setup_mode context\n- Render linked GitHub state with masked install command CTA\n- Add setup-complete.js to claim handoff via URL fragment\n- Update site.yaml copy and hide sign-in CTA in setup mode\n- Add landing route tests (#156) — @Nicolas Leal
- **social-management**: add --file option to post commands (#157) — @Nicolas Leal
- **social-management**: add alerts channel support (#154) — @Nicolas Leal
- **skillmap**: add deterministic package-map inference engine (#153) — @Nicolas Leal
- **cli**: shell tab-completion + auto-open browser in github connect (#155) — @Nicolas Leal

### Bug Fixes
- **scanners**: ignore eval wording in comments (#205) — @Nicolas Leal
- **indexer**: parse lockfile URL schemes (#203) — @Nicolas Leal
- **indexer**: expand hub catalog coverage (#200) — @Nicolas Leal
- **indexer**: crawl skills.sh sitemaps (#199) — @Nicolas Leal
- **indexer**: retry transient tarball fetches (#197) — @Nicolas Leal
- **indexer**: preserve run diagnostics and partial state (#196) — @Nicolas Leal
- **indexer**: close indexing reliability gaps (#194) — @Nicolas Leal
- **cli**: call the real SDK setup-token redeem; register package-map error codes (#193) — @Nicolas Leal
- **scanners**: pull Trivy vuln DB from mirror, GHCR fallback (#186) — @Nicolas Leal
- **landing**: fingerprint static asset URLs; add hero engraving (#184) — @Nicolas Leal
- **landing**: polish setup-complete — right-aligned nav, redirect home on bad handoff (#183) — @Nicolas Leal
- **cli**: tolerate unwritable auto-update state (#182) — @Nicolas Leal
- **landing**: copy rewrite, mobile perf path, setup-state CTA fixes (#181) — @Nicolas Leal
- **bot**: derive top-up URL from bounty_url; pin reply copy with golden tests (#180) — @Nicolas Leal
- **scanners**: match quoted uv dependencies (#177) — @Nicolas Leal
- **scanners**: block runtime code acquisition (#176) — @Nicolas Leal
- **cli**: gate bounty PR commands behind --yes, add fork guidance and JSON envelopes (#175) — @Nicolas Leal
- **landing**: setup-complete follow-ups — expired state on direct visit, noindex, @login nav (#172) — @Nicolas Leal
- **social-management**: harden file post input (#166) — @Nicolas Leal

### Performance
- **cli**: defer runtime imports during parser setup (#189) — @Nicolas Leal

### Documentation
- **readme**: reframe to the end-goal — verifiable capability network (#167) — @Nicolas Leal
- update Discord invite link to current vanity URL\n\n- Replace expired invite in README badge\n- Replace expired invite in landing site footer (#158) — @Nicolas Leal

### Chores
- **release**: prepare companion v0.1.14 (#206) — @Nicolas Leal

**Contributors:** @Nicolas Leal

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