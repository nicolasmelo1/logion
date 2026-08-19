# Logion Observer Plugin

Thin harness hooks for use observation, installable via
`npx plugins add @logion/observer`.

## What this plugin does

- Installs a `PostToolUse` hook that pipes a minimal payload to
  `logion usage observe --harness <name> --stdin`.
- The hook is `async` with a timeout so it never blocks the harness.
- Uninstall removes only Logion-owned hook entries.

## What this plugin does NOT do

- It does not install the full Logion CLI.
- It does not upload anything directly — all network writes go through
  the CLI's consent-gated upload path.
- It does not collect prompts, file contents, paths, tool arguments,
  secrets, or model context.
- It does not infer use from installation, listing, or availability.

## Prerequisites

The Logion CLI must be on PATH. If missing, the hook exits 0 silently
(never breaks the harness) and the companion skill guides the user
through installation with explicit approval.

## Install

```sh
npx plugins add @logion/observer
```

## Uninstall

```sh
npx plugins remove @logion/observer
```

Removes only `_logion_managed` entries; user hooks are preserved.