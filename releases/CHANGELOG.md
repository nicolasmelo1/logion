# Changelog

All notable changes to the Logion packages are documented in per-package
CHANGELOG files below their respective directories. This top-level file
aggregates the current released version of each package.

## 0.2.0.dev1

### Features
- **landing**: serve the agent discovery surfaces (#281) — @Nicolas Leal
- **cli**: add Hermes lifecycle observation adapter (#279) — @Nicolas Leal
- scaffold packages/harness-plugins observer plugin (#273) — @Nicolas Leal
- **cli**: add explicit-report fallback for Hermes and Pi (#272) — @Nicolas Leal
- **agent-proving-ground,cli,client**: native-use observation and feedback (#260) — @Nicolas Leal
- **dsh**: add native harness plugin acquisition (#259) — @Nicolas Leal
- **cli**: execute resource acquisition with local inventory receipts (#255) — @Nicolas Leal
- **cli**: harness scope contract, resource acquire/inventory, observation envelope (#246) — @Nicolas Leal
- **resources**: add generic resource surfaces and proving ground (#239) — @Nicolas Leal
- **proving-ground**: exercise real GitHub bounty flow (#238) — @Nicolas Leal
- **proving-ground**: add identity oauth observed-effect scenario (#235) — @Nicolas Leal
- **indexer**: record aggregate run progress (#221) — @Nicolas Leal
- **landing**: tell the product through agent workflows (#220) — @Nicolas Leal
- **landing**: AKTP protocol page + header link + colorized transcripts (#216) — @Nicolas Leal

### Bug Fixes
- **release**: install factory checks tool (#286) — @Nicolas Leal
- **release**: sync workspace before orchestration (#285) — @Nicolas Leal
- **landing**: make Accept negotiation cache-safe, and say when to use Logion (#284) — @Nicolas Leal
- **release**: clarify development release operations (#283) — @Nicolas Leal
- **landing**: declare www as the canonical host, and guard it (#282) — @Nicolas Leal
- **release**: route development builds to testpypi (#280) — @Nicolas Leal
- **cli**: run Codex usage hooks synchronously (#278) — @Nicolas Leal
- **proving-ground**: let the rig own the reconcile bookkeeping (#277) — @Nicolas Leal
- **proving-ground**: stop a server invariant depending on agent compliance (#276) — @Nicolas Leal
- **harness-plugins**: apply ruff format (#275) — @Nicolas Leal
- **cli**: consolidate observation envelope into UsageObservation (#271) — @Nicolas Leal
- **cli**: auto-update must not replace an editable install (#274) — @Nicolas Leal
- **phase-gates**: name the criterion this non-blocking caveat stands against (#270) — @Nicolas Leal
- **proving-ground**: make the observation gate prove a live hook (#266) — @Nicolas Leal
- **client**: sync OpenAPI contract with resource-feedback integrity changes (#264) — @Nicolas Leal
- **cli,proving-ground**: make use observation real and consent enforceable (#263) — @Nicolas Leal
- **cli**: make the acquisition preview, inventory, and reconcile honest (#257) — @Nicolas Leal
- **cli**: close phase 15.10 acceptance gaps (#256) — @Nicolas Leal
- **proving-ground**: name scenarios by behavior (#254) — @Nicolas Leal
- **deps**: update vulnerable security dependencies (#253) — @Nicolas Leal
- **cli**: align resources with public contract (#249) — @Nicolas Leal
- **deps**: bump datamodel-code-generator for CVE fixes (#252) — @Nicolas Leal
- **proving-ground**: correct artifact-backed queries, envelope privacy, and acquire plan executability (#248) — @Nicolas Leal
- **cli**: harden harness scope contract, acquire plan, and observation envelope (#247) — @Nicolas Leal
- **proving-ground**: enforce resource backfill integrity (#244) — @Nicolas Leal
- **client**: classify platform bounty admin operations (#230) — @Nicolas Leal
- **cli**: rank query results by relevance (#227) — @Nicolas Leal
- **landing**: refine lightning and scrolling (#226) — @Nicolas Leal
- **deps**: update gitpython security release (#222) — @Nicolas Leal
- **indexer**: bound write request timeouts (#215) — @Nicolas Leal
- **indexer**: encode github content paths (#214) — @Nicolas Leal
- **indexer**: tolerate transient github disconnects (#212) — @Nicolas Leal
- **indexer**: remove lobehub source (#211) — @Nicolas Leal

### Performance
- **indexer**: enrich repositories concurrently (#219) — @Nicolas Leal

### Refactors
- **proving-ground**: remove phase label (#245) — @Nicolas Leal

### Documentation
- state the attribution-and-evidence thesis in the README (#265) — @Nicolas Leal
- **roadmap**: sync retired phase contracts (#250) — @Nicolas Leal
- **roadmap**: ground ARD in AI Catalog connectors (#237) — @Nicolas Leal
- **roadmap**: publish canonical planning (#236) — @Nicolas Leal
- **landing**: native-use beat after install + v1 event-log line on /aktp (#217) — @Nicolas Leal
- **readme,landing**: network continual learning — shown, not told (#213) — @Nicolas Leal

### Tests
- **proving-ground**: validate resource projection backfill e2e (#241) — @Nicolas Leal

### CI
- **contract**: record approved v1 main change (#232) — @Nicolas Leal
- **contract**: allow approved v1 default change (#231) — @Nicolas Leal
- **contract**: check public v1 compatibility (#228) — @Nicolas Leal
- publish skillmap and sync OpenAPI contract (#224) — @Nicolas Leal

### Chores
- sync OpenAPI contract from the internal API repo (#269) — @Nicolas Leal
- adopt software-factory, and retire the checks it now covers (#267) — @Nicolas Leal
- **lint**: ban typing.Any, type the JSON boundaries, and split oversized commands (#261) — @Nicolas Leal
- sync OpenAPI contract from the internal API repo (#251) — @Nicolas Leal
- sync OpenAPI contract from the internal API repo (#243) — @Nicolas Leal
- sync OpenAPI contract from the internal API repo (#242) — @Nicolas Leal
- sync resource contract (#240) — @Nicolas Leal
- sync OpenAPI contract from the internal API repo (#234) — @Nicolas Leal
- **client**: classify capabilities operation (#233) — @Nicolas Leal
- sync OpenAPI contract from the internal API repo (#229) — @Nicolas Leal

**Contributors:** @Nicolas Leal

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