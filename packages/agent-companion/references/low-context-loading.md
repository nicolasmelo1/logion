# Low-Context Loading

Strategies for keeping context usage minimal when using the companion.

## Bootstrap-only loading

The companion ships a single SKILL.md as the always-on bootstrap. All other
content (references, templates, scripts) is loaded on demand, not at startup.

## Local recall first

Before searching the Logion marketplace API, the companion checks the local
recall index — a compact on-device index of installed capabilities, proven
workflows, and compact local references. This avoids unnecessary API calls and
context bloat from large search results.

## Top-k results

Both local recall and marketplace search return a small number of candidates
(top-5 by default) rather than exhaustive lists. Each result includes minimal
metadata: name, version, confidence/relevance, and a one-line description.

## Lazy reference loading

References (`references/*.md`) are only loaded when the agent determines it
needs them. For example, `references/troubleshooting.md` is only loaded after a
command fails, not at bootstrap.

## Marketplace search is fallback

Marketplace search is only performed when local recall and existing installed
capabilities do not cover the user's need. This reduces both token usage and API
calls.

## Capability install loads one artifact

When a user chooses to install a capability, only that specific artifact is
loaded. The full catalog is never loaded into context.