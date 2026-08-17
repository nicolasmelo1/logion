<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.10.1 — DeepSeek Harness (dsh) native adapter, plugin acquisition channel, and Logion dsh plugin

> **Implementation status (2026-08-14): not shipped.** This document is the
> normative future contract and acceptance gate. It is the first application of
> the 15.9.1 harness contract and the 15.10 acquisition contract to an
> ecosystem that launched after both were written.
>
> **Dogfood — Level 1.1 (new-ecosystem acquisition):** the implementing agent
> must install the real `dsh` CLI, install the Logion dsh plugin through dsh's
> own native flow, discover an indexed dsh plugin through Logion, acquire it,
> reconcile a second plugin that was installed directly with dsh, and prove a
> fresh dsh session loads what the inventory says it loads.
> **After this phase:** a dsh user can see the Logion plugin, install it, and
> use the central Logion loop — search, evidence, acquire, inventory,
> reconcile — without leaving their harness or abandoning dsh's native
> plugin management.
> **Honesty boundary:** acquisition proves possession, not usage, usefulness,
> safety, or quality. Every evidence surface shown inside dsh is first-party
> ("Logion observed"); nothing in this phase may present or imply "network
> verified", which requires Phase 16.

## Why this phase exists

DeepSeek Harness (`dsh`) shipped 2026-08-13 as an MIT developer preview built
on the Cordis plugin kernel: every capability — models, tools, skills,
sessions, sandboxes, storage, loops, UI — is a plugin. Distribution is
registry-less: plugins are GitHub repositories tagged with the `dsh-plugin`
topic and carry a `dsh.plugin.json` manifest. There is no marketplace, no
trust layer, and no verification model.

That is exactly the gap Logion's wedge thesis names, at day one of the
ecosystem instead of after it hardens. Two properties make dsh a better-than-
usual fit for the existing contracts:

- Cordis plugins declare their dependencies and provided services statically
  (typed coeffects). That is a machine-readable declared-capability surface
  that feeds the acquisition plan `permissions` display and, later, the
  declared-vs-observed evidence lane — without inference.
- Cordis effects are revertible: unloading a plugin structurally undoes what
  it installed. This makes bounded install/inspect/rollback flows cheaper.

The integration follows the standing rule: **native managers remain native**.
Logion does not host, mirror, or replace dsh plugin distribution. It indexes,
attributes, displays evidence, plans acquisition, delegates installation to
the native flow, and remembers one canonical local inventory.

Because dsh is a developer preview that announces compatibility-breaking
changes, the convergence kill criterion "collaboration depends indefinitely on
an unreviewed moving branch" applies. The consequences are contractual:

- every adapter pins the exact tested `dsh` version and manifest schema and
  **fails closed on any unknown format/version** rather than misattributing;
- no DeepSeek-specific protocol contract (coeffect schema in the catalog, a
  Cordis-shaped receipt, a selection descriptor) is frozen in this phase;
- upstream engagement follows the ASM collaboration pattern: approach early,
  prove one seam, upstream after evidence. Proposing that DeepSeek publish an
  AI Catalog document is Phase 17.1 material, not this phase.

## Mandatory dogfood prompt for the implementing agent

This prompt is a release gate and runs after the implementation is test-green:

```text
You are implementing Phase 15.10.1. Dogfood Logion's dsh path for real.

1. Install the pinned tested dsh release in an isolated HOME and record the
   exact version.
2. Install the Logion dsh plugin through dsh's documented native install flow
   (no manual file copying). Confirm a fresh dsh session lists it.
3. From inside dsh, use the Logion plugin to search for a dsh plugin capability
   and inspect one indexed result: exact version, canonical source, revision,
   digest, license, declared dependencies/services, and acquisition command.
4. Run the dry-run acquisition, review the plan, then approve and acquire it
   through the delegated native dsh flow into a fixture repository scope.
5. Install a second, different dsh plugin directly with dsh (bypassing Logion),
   then run Logion inventory and reconcile and confirm the direct install is
   attributed to the exact indexed ResourceVersion without reinstalling it.
6. Start a fresh dsh session and confirm it discovers both plugins with the
   same files/digests recorded by inventory.
7. Save artifacts/dogfood/phase-15.10.1.md with dsh version, plugin manifest
   digests, resource/version IDs, acquisition plans, approval, exact executed
   commands, installed paths, reconciliation outcome, and product friction.
8. Do not submit any rating, review, or usage claim: observation and feedback
   are 15.11. Record blockers instead.
```

If this phase cannot acquire a real dsh plugin through the real `dsh` flow and
reconcile a real out-of-band install, it does not pass.

## Dependencies

Hard prerequisites, in order:

1. **15.10 gap closure.** The audited defects block this phase and are owned
   by 15.10, not duplicated here:
   - `verification: exact` must recompute the aggregate content digest
     client-side and fail closed on mismatch;
   - the bundle download egress must go through the guarded HTTP path
     (no `urllib.urlopen`, no `file://`, explicit timeout);
   - `logion resources reconcile` must read real native manager state with
     `--from` sources instead of re-emitting Logion's own receipts;
   - channel adapters must derive installed paths and lock entries from
     manager state, never from a Logion-invented slug or an arbitrary
     lockfile entry.
2. **Indexer generic resource path.** The dormant `DiscoveredResource` /
   `_serialize_resource_item` pipeline must be wired and the indexer↔API type
   vocabulary mismatch (`skill`/`plugin` vs `agent_skill`/`agent_plugin`)
   resolved with an explicit mapping. Without this, no new ecosystem's entries
   carry `resource_type` or distributions.
3. 15.9.1 harness resource scope and observation contract (shipped).
4. 15.10 acquisition plan/receipt/HMAC identity contracts (shipped surface).

## Upstream contracts to pin before coding

- DeepSeek Harness repository and releases:
  <https://github.com/deepseek-ai/deepseek-harness>
- dsh CLI entry point and install flow: `npx @deepseek-ai/dsh` (pin exact
  package version; record install/plugin-management commands as documented at
  the pinned release, not from memory)
- `dsh.plugin.json` manifest schema at the pinned release
- Plugin discoverability: the `dsh-plugin` GitHub topic
  (<https://github.com/topics/dsh-plugin>) and the semi-central hub list
  (`dsh-external/hub`) — verify during implementation which of the two is
  authoritative enough to crawl (decision gate below)
- Cordis kernel semantics (plugin identity, config entry tree, service keys):
  <https://github.com/cordiverse> and the Cordis paper
  (<https://github.com/cordiverse/paper>)

Record exact tested versions and fixture provenance in the PR. dsh is a
developer preview: adapters must fail closed on an unsupported manifest or
state format/version rather than silently misattribute, and every dsh version
bump requires re-running the recorded-fixture suite before the pin widens.

## Product contract

### dsh as a harness

Add `dsh` to the 15.9.1 harness adapter set (`codex`, `claude`, `hermes`,
`pi`, `opencode`, `custom`). The adapter must declare, with recorded fixtures:

- native plugin locations and the Cordis declarative config entry tree that
  registers a plugin (installing a plugin = the native manager adding an
  entry; Logion never hand-edits the config tree in place of the manager);
- scope kinds supported (`repo-*`, `user`) and precedence, with the standard
  default: repository root inside a Git worktree, no silent fallback to
  `user`;
- observation capability: **none in this phase** — the adapter declares
  `observation: unsupported` honestly; hooks are 15.11 scope;
- failure behavior for unsupported dsh versions, malformed manifests, and
  missing state (fail closed, actionable error, no partial writes).

### `dsh` distribution channel

Extend the 15.10 channel set (`logion_bundle`, `npx_skills`, `npx_plugins`,
`hf`, `git`, `manual`) with:

```text
dsh   upstream Git-hosted Cordis plugin acquired through the dsh native flow
```

Channel rules inherited unchanged from 15.10: the channel is not the resource
identity; evidence attaches to `ResourceVersion.content_digest`; the same
plugin reachable as a Git repo and as a dsh plugin collapses into one resource
with multiple distributions; `native.argv` is a display/execution array, never
a shell string; the server never executes it.

The acquisition plan's `native` block uses `tool: "dsh"`, the pinned tested
version, the documented install argv, the upstream locator, and the immutable
revision (40-char commit). `permissions` is populated from the manifest's
declared dependencies/services when the pinned schema exposes them, and is
labeled *declared by publisher, not verified* — this phase must not imply
enforcement or verification of declared capabilities.

### Identity and reconciliation rules

The 15.10 attribution ladder applies verbatim (exact Logion marker → native
manifest/lock plus immutable revision → content digest → canonical source plus
verified subpath → unresolved). dsh-specific sharpenings:

- a Cordis plugin name or config entry `id` is **never** identity by itself;
- `dsh.plugin.json` is read only at a pinned `schema_version`-equivalent;
  unknown versions quarantine the entry as `unsupported_manifest`, which can
  never mint an `installation_id`;
- multiple candidate resources produce `ambiguous` with candidate IDs and no
  attribution; name similarity is never identity;
- reconciling a plugin installed directly with dsh must not move, rewrite, or
  reinstall it, and must not touch dsh's config tree or lock state.

### The Logion dsh plugin (entry surface)

A thin wrapper following the standing harness strategy
(`harness command → wrapper → logion CLI --json → render host-native
response`). Contract:

- distributed the way real dsh plugins are distributed at the pinned release
  (public Git repository tagged `dsh-plugin`, npm package if that is the
  documented flow) so a dsh user discovers and installs it natively;
- declares the minimum Cordis dependencies it needs; it must not request
  model, sandbox, or storage services it does not use;
- surfaces exactly: search/list, resource inspection with first-party evidence
  and provenance, dry-run acquisition plan display, approval-gated acquire,
  inventory, reconcile;
- contains no business logic: every operation shells to the public `logion`
  CLI with `--json` and renders the result; no separate vendor code path;
- never proxies Logion credentials into the dsh context beyond invoking the
  locally configured CLI, and never writes secrets into Cordis config entries;
- degrades honestly: when the `logion` CLI is absent it explains how to
  install it and does nothing else.

## Implementation

### `logion` (public)

- `packages/indexer/logion_indexer/adapters/dsh_hub.py` — discovery adapter
  implementing the two-member adapter protocol, registered in
  `cli.py:_get_adapter`, seeded in `seeds/sources.yaml` (the seed-name test
  must resolve it).
  **Decision gate:** implement against the cheapest authoritative source. If
  `dsh-external/hub` (or the pinned-release equivalent) is an enumerable repo
  list, crawl it as a plain repository target and defer GitHub topic search.
  Add a `topic` mode to `github_direct` only if no enumerable list exists;
  topic search uses the GitHub search API (different rate limits, mutable
  ranked results) and must record discovery provenance per listing.
- Wire the dormant generic-resource path (`DiscoveredResource`,
  `ResourceDedupPlan`, `_serialize_resource_item`) into `pipeline.py`/`cli.py`
  and add the explicit indexer↔API `resource_type` mapping (dependency 2).
- `packages/cli/cli/_harness/dsh.py` — harness adapter per the 15.9.1
  contract.
- `packages/cli/cli/commands/resources/_channels/dsh.py` — channel adapter
  (acquire via delegated native flow; discovery of installed state from dsh's
  own manifest/config, mirroring the `skills_lock` fail-closed pattern).
- The Logion dsh plugin package/repository (location decided with the
  distribution pin above; if in-monorepo, `packages/dsh-plugin/`).
- Reconcile support: `logion resources reconcile --from dsh` reading dsh
  state without mutation.

### `backend repository`

- Add `CHANNEL_DSH` to `api/resources/constants/distribution_channels.py` and
  the `CHANNEL_NATIVE_TOOL` map (`dsh` → `dsh`).
- Extend indexed upsert to create `dsh` (and `git`) distributions from
  trustworthy source/package-map data with pinned revisions; ambiguous or
  missing revision is quarantined or `manual`-only, as in 15.10.
- Reuse the 15.10 stable errors; `resource_native_tool_unsupported` and
  `resource_native_tool_version_unsupported` must be reachable for unsupported
  dsh versions (15.10 gap closure makes them exist).
- No new endpoints. No dsh-specific fields in the acquisition plan beyond the
  existing generic `native`/`permissions` blocks.

## Security and privacy

- All 15.10 defenses apply: argv-only execution (no shell), sanitized
  environment, cwd pinned, timeout, output cap, archive traversal defenses,
  no secret logging.
- `dsh.plugin.json` and Cordis config content are untrusted input everywhere:
  in the indexer, in reconciliation, and in the plugin wrapper. Manifest
  fields never become CLI flags without validation.
- Cordis plugins are executable artifacts. This phase installs them only via
  the native manager with explicit user approval; it never loads, executes, or
  probes plugin code itself (execution/probing discipline arrives with the
  16.x evaluator/MCP-style lanes).
- Declared coeffects are displayed as publisher claims. A mismatch lane
  (declared vs observed) is future evidence work; this phase must not label
  declared capabilities as verified.
- The Logion dsh plugin sends nothing anywhere except through the local
  `logion` CLI; no telemetry, no review submission, no usage claims (15.11).

## Tests

### Indexer

- Recorded fixtures for the pinned hub/topic source: happy path, missing
  manifest, unknown manifest version (quarantined with reason), duplicate
  plugin across sources (single resource, multiple distributions).
- Generic resource path: dsh listings arrive with `resource_type` and a `dsh`
  distribution row; vocabulary mapping round-trips; second run is
  zero-change idempotent.

### CLI

- Harness adapter fixtures per 15.9.1: native locations, scope precedence,
  repo/user isolation, unsupported-version failure, `observation: unsupported`
  declared.
- Channel adapter: fake-executable tests asserting exact argv and no shell;
  recorded real-`dsh` fixtures for install output/state at the pinned version;
  fail-closed on unknown state format; pre-existing install reconciled without
  mutation; ambiguous identity never links; second reconcile zero-change.
- Receipts: `channel: "dsh"` receipts carry `native_evidence` with
  `manager_name: "dsh"`, pinned `manager_version`, canonical source, immutable
  revision; digest/HMAC rules inherited from 15.10 unchanged.
- Install the same plugin in fixture repositories `xpto` and `acme`; distinct
  receipts, no cross-repo or user-scope leakage.
- Launch a fresh real dsh session and assert native discovery of the exact
  installed plugin (no fake dsh executable).

### Logion dsh plugin

- Loads in a real pinned dsh session; renders search/inspect/plan/inventory
  from `logion ... --json` fixtures; absent-CLI degradation; no secret
  material in any Cordis config entry it writes.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add a
builtin scenario named by behavior:

**`builtin:dsh_plugin_discovery_install_and_reconcile`** — the scenario YAML,
fixtures, queries, and typed assertions land in
`logion/packages/agent-proving-ground/` with the implementation, per the gate
checklist. This phase is incomplete until the scenario passes with a real
cheap agent against the locally running API.

- **Actors/fixtures:** one `operator` (developer persona). A dev-rig seed
  target (`make proving-ground-seed SCENARIO=dsh_plugin_acquisition`)
  publishes: an isolated HOME with the pinned real `dsh` CLI installed; the
  Logion dsh plugin installable through dsh's native flow; fixture repository
  `xpto`; two local Git fixture plugins with valid pinned-schema
  `dsh.plugin.json` manifests, both indexed into the local catalog with `dsh`
  distributions; and one poisoned fixture whose advertised digest mismatches
  its content. No fake `logion`, `dsh`, or adapter executable.
- **Customer prompt (goal, not transcript):** "You use DeepSeek Harness. From
  inside dsh, use the Logion plugin to find a lightweight capability for
  repository xpto, check what Logion knows about it (source, version, digest,
  license, declared permissions), install it into that repository — not
  globally — and show what was installed. One plugin was already installed
  here directly with dsh: make Logion recognize it too, without reinstalling
  anything. Then prove a fresh dsh session actually loads what you installed.
  Do not call Logion's HTTP API directly."
- **Flow:** discover through the Logion plugin → inspect → dry-run → approved
  acquire via delegated native dsh flow → inventory → reconcile the
  out-of-band install → rerun acquire (idempotent) → fresh dsh session
  discovery.
- **Assertions:** `api.resource_acquisition_exists`,
  `api.resource_distribution_selected` (allowed channel `dsh`),
  `files.installed_artifact_digest_matches`,
  `files.inventory_receipt_matches`, `api.native_install_reconciled` (the
  direct dsh install attributed without reinstall),
  `api.acquisition_idempotent`, plus a new typed assertion
  `files.native_harness_discovers_installation` (fresh-session dsh state lists
  the installed plugin with the inventoried digest); require `logs.no_500s`.
- **Negative case/evidence:** acquiring the poisoned fixture fails closed on
  digest mismatch, creates no success receipt, and leaves dsh state untouched;
  reconciliation of an unknown-manifest-version plugin yields
  `unsupported_manifest`, never an attribution. Retain dsh version/output,
  manifest digests, receipt/artifact digests, and proof of zero duplicate
  state.
- **Drivers:** standard gate contract — `codex`/`gpt-5.4-mini` primary,
  `claude-code`/`claude-haiku-4-5` fallback, `api_adapter: local-devrig`.

## Acceptance criteria

- [ ] An indexed dsh plugin discovered through Logion is acquired into a
      repository scope through the real delegated `dsh` flow, with receipt,
      digest, and HMAC identity per the 15.10 contract.
- [ ] A plugin installed directly with dsh is reconciled to the exact indexed
      `ResourceVersion` without reinstalling, moving, or rewriting dsh state.
- [ ] The Logion dsh plugin installs through dsh's native flow from its public
      distribution point and surfaces search → evidence → plan → acquire →
      inventory → reconcile by shelling to the public CLI.
- [ ] A fresh dsh session discovers the exact installed plugins; installing in
      `xpto` creates nothing in user scope or another repository.
- [ ] Unknown `dsh` versions and unknown manifest formats fail closed with
      stable errors and can never mint an `installation_id`.
- [ ] Every dry-run remains zero-write and shows channel, revision, digest,
      declared permissions (labeled as publisher-declared), and exact argv.
- [ ] All evidence shown in the dsh surface is labeled first-party; no surface
      claims or implies independent/network verification.
- [ ] Existing harness adapters, channels, and `skills`/`resources` CLI
      behavior remain compatible.
- [ ] The mandatory dogfood artifact exists with one real Logion-mediated dsh
      acquisition and one real out-of-band reconciliation.

## Rollout

1. Indexer discovery + catalog listings with `dsh` distributions (read-only
   reach; no acquisition).
2. Reconciliation of existing dsh installs (`--from dsh`) without executing
   the manager.
3. Delegated `dsh` acquisition behind a per-channel feature flag.
4. Logion dsh plugin published through the native distribution point.

Metrics mirror 15.10 (planned/started/succeeded/failed acquisition,
verification level, reconcile matched/ambiguous/drifted, native tool/version,
channel) — no user project paths. Each dsh version bump re-runs recorded
fixtures before the tested-version pin moves.

## Out of scope

Usage observation, hooks, feedback, and reviews for dsh (15.11/15.11.1);
signed portable evidence (15.13); evaluation of dsh plugins, including
comparative service-key evaluation (16.2+); MCP-style safe probes of plugin
code (16.11 pattern); any DeepSeek-specific protocol contract, catalog schema,
or receipt format (17.1 upstream-proposal territory); mirroring or hosting dsh
plugin artifacts; executing or sandbox-probing plugin code.
