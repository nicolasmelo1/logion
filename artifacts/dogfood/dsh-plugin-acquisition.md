# DeepSeek Harness (dsh) plugin acquisition dogfood record

Run date: 2026-08-15. Everything below was executed against a real `dsh`
install; nothing here is a fixture standing in for the manager.

## Manager

| | |
| --- | --- |
| Package | `@deepseek-ai/dsh@0.1.0-rc.6` (npm `latest` at run time) |
| `dsh --version` | `0.1.0-rc.6` |
| Package manager it forwards to | pnpm 11.21.0 |

## What the real manager does

Recorded from the running manager, not from documentation:

- Profiles live at `$DSH_HOME/profiles/<name>`. Setting `DSH_HOME` to a
  repository-owned directory keeps every profile inside that repository.
- A profile declares itself in its own `package.json` under
  `dsh.profile.bundles`. **There is no standalone `dsh.profile` file.**
- `dsh plugin --profile <name> add <spec>` records the bundle in **both**
  `dependencies` (with the resolved, revision-pinned spec) and
  `dsh.profile.bundles`.
- pnpm does **not** write `gitHead` into an installed bundle's manifest.
  The profile's dependency spec is the manager's own record of the
  revision it fetched, so that is what identity is read from.
- `@deepseek-ai/dsh-base` is always present in `bundles`; it carries no
  revision and is reported unattributed rather than guessed at.

## Acquisition

Plan (server-owned, fetched from the local API):

```json
{
  "selected_channel": "dsh",
  "native": {
    "tool": "dsh",
    "tested_version": "0.1.0-rc.6",
    "argv": ["dsh", "plugin", "--profile", "default", "add",
             "github:logion-fixtures/dsh-plugin#0123…4567"],
    "revision": "0123…4567"
  },
  "permissions": {
    "network": false,
    "tools": ["@deepseek-ai/dsh-tools"],
    "secrets": [],
    "source": "declared_by_publisher"
  }
}
```

Executed acquisition into a repository scope, against a local Git bundle
pinned to commit `b7c264c9238e3c6664f096cb9206f36089ea4373`:

```
installed_paths: ['.dsh/profiles/default/node_modules/dsh-hello-plugin']
verification:    source_revision
native_evidence:
  manager_name:       dsh
  manager_version:    0.1.0-rc.6        # the version that actually ran
  immutable_revision: b7c264c9238e3c6664f096cb9206f36089ea4373
  declared_capabilities: {patch: ./cordis.patch.yml, dependencies: []}
notes: ['declared capabilities are publisher claims, not verified']
```

Scope isolation: `~/.dsh` **was never created**. The install exists only
under the repository's own harness home.

Reconciliation over that state, read-only, without reinstalling:

```
dsh-hello-plugin        revision b7c264c9…  (from the profile's pinned spec)
@deepseek-ai/dsh-base   unsupported: unreadable manifest — not attributed
```

## Product friction

1. **The plan document is stale.** It specifies `dsh.plugin.json` and the
   `dsh-plugin` GitHub topic. Neither matches the shipped manager:
   manifests are `package.json` with a `dsh` key.
2. **No enumerable third-party index exists yet.** `dsh-external/hub`
   does not resolve publicly, and the `dsh-plugin` topic returns ~3,800
   mostly unrelated repositories. Only the harness repository is
   enumerable, so that is the sole default seed; third-party targets must
   be added explicitly.
3. **`gitHead` is not a usable identity source** under pnpm. Any adapter
   that assumes npm's packing behaviour will fail closed on every real
   install.
4. **Git-hosted bundles need `allowBuilds`.** pnpm blocks their `prepare`
   script until the exact key is allowlisted in the profile's
   `pnpm-workspace.yaml`, and dsh surfaces that as an actionable message.
   Logion does not edit that file; the operator does.

## Not done

No rating, review, or usage claim was submitted — observation and
feedback are a later lane. The proving-ground acquisition phase still
needs a Git-hosted fixture bundle
published under a real account; the local bundle above proves the channel
but is not reachable from CI.
