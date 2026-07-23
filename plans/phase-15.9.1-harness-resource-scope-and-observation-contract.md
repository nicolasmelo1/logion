<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.9.1 — Harness resource scope and observation contract

> **Dogfood status:** contract-level dogfood starts here by detecting the real
> resources already visible to the implementing agent's harness. Native
> acquisition becomes mandatory in 15.10 and observation/feedback in 15.11.
> **Product rule:** Logion adapts to the harness's native resource locations and
> lifecycle. It does not flatten every installation into a global Logion home.

## Goal

Close both directions of the harness integration:

```text
harness-native resource
  → Logion inventory/reconciliation
  → attributed local use
  → consented feedback
```

and:

```text
Logion-indexed resource
  → native acquisition plan
  → install into the requested harness scope
  → harness discovers and uses it
  → the same observation/feedback path
```

An implementation that supports only one direction is incomplete.

## Installation identity

Scope is part of an installation's identity. The minimum local identity is:

```text
(resource_version_id, distribution_id, harness, scope_kind, scope_root,
 target_path, native_manager, native_receipt_digest)
```

Two copies of one version in different repositories are two installations with
different use histories. They may point to the same immutable resource version,
but Logion must never merge their local policy, attribution, feedback queue, or
removal/update state.

`scope_root` is canonicalized without uploading the raw local path. A stable
local installation ID may be submitted; the server receives a salted or
node-scoped opaque scope ID only when the user submits feedback.

## Scope vocabulary

The public CLI uses these semantic scopes:

- `repo-current`: current working directory.
- `repo-parent`: an explicitly selected parent between CWD and repository root.
- `repo-root`: the detected topmost Git repository root.
- `user`: the harness's per-user location.
- `admin`: a machine/container administrator location.
- `system`: harness-bundled resources; read-only inventory, never installed or
  modified by Logion.
- `custom`: explicit user path with no inferred semantics.

`project` remains a compatibility alias for `repo-root` until callers migrate.
`global` remains a compatibility alias for `user`; new receipts store the
semantic value, not the alias.

The default for an agent launched inside a Git repository is `repo-root`.
Logion must never silently fall back from a failed repo install to `user`.
Outside a repository, an omitted scope produces a plan requiring explicit
`user` confirmation.

## Codex contract

Codex scans `.agents/skills` from CWD through every parent up to the repository
root. Logion must support each distinct repository target:

| Scope | Target |
| --- | --- |
| `repo-current` | `$CWD/.agents/skills/<skill>/` |
| `repo-parent` | `$SELECTED_PARENT/.agents/skills/<skill>/` |
| `repo-root` | `$REPO_ROOT/.agents/skills/<skill>/` |
| `user` | `$HOME/.agents/skills/<skill>/` |
| `admin` | `/etc/codex/skills/<skill>/` |
| `system` | bundled by Codex; inventory only |

The current `~/.codex/skills` projection is legacy and must not be offered as
the default. During migration, detect it as an unverified legacy installation,
offer exact reconciliation/copy into `.agents/skills`, and never delete it
without explicit approval.

Nested repository skills remain distinct. If the same named skill is visible at
more than one scanned level, inventory shows every candidate, its precedence
context, and an ambiguity state; Logion does not pretend Codex merged them.

## Claude Code contract

Claude Code uses:

- project `.claude/skills/<skill>/`;
- personal `$HOME/.claude/skills/<skill>/`;
- plugin-provided `<plugin>/skills/<skill>/`.

It discovers project skills from the starting directory through parents to the
repository root and may discover nested project skills on demand. Map
`repo-current|repo-parent|repo-root` to the corresponding `.claude/skills`
directory and `user` to `$HOME/.claude/skills`. Plugin resources retain the
plugin distribution identity rather than being copied and mislabeled as a
normal project skill.

## Hermes contract

Hermes keeps its writable source of truth under the active profile's
`$HERMES_HOME/skills` (normally `$HOME/.hermes/skills`) and can scan explicit
`skills.external_dirs`.

For `user`, install through Hermes's native Hub/lifecycle when supported or into
the active profile's skill directory. For repository scope, prefer one shared
`.agents/skills` target and register it as an external directory for the
isolated Hermes profile. Record that Hermes can modify writable external
directories; repo skills therefore follow repository review and permissions.

Hermes profiles are different agent identities. Their homes, memories, sessions,
skills, credentials, and observation spools must not be shared unless a user
explicitly configures one shared repo skill directory.

## Pi contract

Pi discovers:

- project `.pi/skills` and `.agents/skills` from CWD through repository root;
- user `$HOME/.pi/agent/skills` and `$HOME/.agents/skills`;
- package-provided skills and explicit configured/CLI paths.

Prefer `.agents/skills` for cross-harness repo/user installs and `.pi/skills`
only for Pi-specific content. Package-provided resources retain package
identity. A `--skill` one-session path is an ephemeral attachment, not a durable
installation, unless the user later adopts it into a persistent scope.

## Other harnesses

Each adapter declares capabilities rather than inheriting assumptions:

```yaml
harness: example
adapter_version: 1
resource_kinds: [agent_skill, agent_plugin, mcp_server]
scope_targets:
  repo-root: ".example/skills"
  user: "~/.example/skills"
native_manager: "example skills"
observation:
  mechanism: plugin
  version: 1
  delivery: local-spool
```

Unknown harnesses use `custom` path inventory and prompt-mode feedback only.
They do not receive automatic telemetry hooks, inferred precedence, or native
manager claims.

## Acquisition plan

`logion resources acquire ... --scope repo-root --harness codex --dry-run`
must show:

- resolved repository root and target path;
- resource/version/distribution/native manager;
- whether the path will be created, updated, reused, or conflicts;
- currently visible same-name resources at other scopes;
- exact native argv or copy operation;
- digest/provenance verification;
- observation integration state;
- permissions and confirmation required.

The plan is zero-write. The non-dry run requires explicit approval when it
creates a new scope target, replaces content, widens permissions, configures a
hook/plugin, or crosses from repo to user/admin scope.

## Native-to-Logion reconciliation

Adapters inventory the harness's real locations before Logion's canonical
cache. Reconciliation order is exact:

1. native manager receipt/lock ID plus immutable revision;
2. canonical source plus revision and content digest;
3. signed bundle/resource digest;
4. otherwise `ambiguous` or `unlinked`.

Name similarity is never enough. Reconciliation records the observed scope and
does not move/reinstall content.

## Observation and telemetry

Plugins/extensions/hooks emit a versioned local envelope:

```json
{
  "event": "resource.use.completed",
  "harness": "codex",
  "harness_session_id": "opaque-local",
  "installation_id": "local-id",
  "resource_version_id": "when-exact",
  "scope_kind": "repo-root",
  "scope_id": "opaque-local",
  "task_class": "software-development",
  "outcome": "completed|failed|abandoned|unknown",
  "started_at": "RFC3339",
  "finished_at": "RFC3339",
  "integration_version": "..."
}
```

Raw prompts, source code, paths, tool arguments, secrets, model context, and
arbitrary terminal output are not fields. The integration writes to the shared
Logion local spool/library; it must not reimplement identity, redaction,
consent, retries, or API submission separately per harness.

Consent behavior:

- `off`: no spool and no network.
- `local-only`: local attribution/inventory only.
- `prompt`: queue a minimum-disclosure feedback proposal.
- `auto`: send only the separately documented narrow receipt class; ratings,
  prose reviews, and raw task data still require explicit policy/consent.

An observation is not a rating. The agent/user reviews the proposed payload
before feedback submission.

## Required harness matrix

Each adapter test covers:

- repo-current, repo-parent/root, user, and unsupported admin/system behavior;
- detection of pre-existing native resources;
- install of an indexed resource into the requested repo and no global copy;
- same skill in two repos without state collision;
- update/removal isolated to one installation;
- exact/ambiguous/unlinked attribution;
- hook/plugin enabled, disabled, malformed, duplicated, and offline;
- no raw task data in local or submitted envelopes;
- a fresh harness session discovering and using the installed resource.

Codex, Claude Code, Hermes, and Pi are release-gating adapters. OpenCode remains
supported and joins the same matrix. A custom adapter is not evidence that a
named harness works.

## Acceptance gates

### Mandatory real-agent scenario

Add `builtin:phase_15_9_1_harness_scope_contract` and pass it with GPT-5.4-mini
or Claude Haiku against the locally running API.

- Seed repositories `xpto/nested` and `acme`, isolated user/admin homes, and the
  same indexed skill version at multiple native locations.
- Prompt: “Tell me which resources Codex can use from this nested directory,
  where each came from, and which repository location would receive a new
  install. Do not install globally. Repeat for Claude, Hermes, and Pi using
  their native discovery rules.”
- The agent uses public detect/inventory/dry-run surfaces, not direct API or
  database queries.
- Assert exact precedence, stable scope/root IDs, no cross-repository leakage,
  user/admin visibility only where appropriate, stable dry-run, and typed
  unsupported behavior.
- Retain harness versions, cwd/repo root, sanitized targets, adapter capability
  declarations, prompt, and no-500 proof.

- Installing while CWD is repository XPTO defaults to XPTO's native repository
  scope, never a global/user directory.
- A resource installed outside Logion is inventoried and linked without
  reinstall when exact evidence exists.
- A resource found through Logion is installed through the harness/native
  lifecycle at the chosen scope and is visible in a fresh harness session.
- Both paths emit the same minimal local observation contract and can produce
  feedback linked to the original immutable resource version.
- Each harness-specific integration is thin, open source, independently
  testable, and fails open for the harness workflow when Logion is unavailable.
