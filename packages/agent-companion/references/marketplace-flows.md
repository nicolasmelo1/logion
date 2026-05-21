# Marketplace Flows

Consumer-facing workflows for discovering, inspecting, installing, and updating
Logion capabilities.

## Search flow

1. Check local recall first (`logion.recall.search`).
2. If local recall is insufficient, search the marketplace
   (`logion.marketplace.search`).
3. Present compact results: name, version, price indicator, rating.

## Inspect flow

1. Given a course/capability identifier, fetch full metadata.
2. Show price, permissions, version history, reviews, and capability list.
3. Ask user before proceeding to install.

## Install flow

1. Confirm with user before installing any capability.
2. If the capability is paid, show the price and require explicit approval.
3. Download and install the selected capability.
4. Verify the installed artifact matches the manifest.

## Update flow

1. Check for available updates to installed capabilities.
2. Show changelog and version diff.
3. Apply update only after explicit user confirmation.
4. For paid capability updates, require additional approval.

## Local recall flow

1. Search local recall index for matching installed capabilities,
   previous successful workflows, and compact local references.
2. Return top-k results with provenance, confidence, and danger flags.
3. Never execute commands from recall results.
4. If recall is sufficient, skip marketplace search entirely.