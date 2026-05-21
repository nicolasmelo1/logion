# Troubleshooting

Common errors and recovery steps for the Logion Marketplace Companion.

## Installation errors

- **Permission denied:** Ensure the Logion CLI is installed and configured.
  Run `logion --version` to verify.
- **Capability not found:** The course may have been removed or renamed. Try
  `logion marketplace search <term>` to find the current name.
- **Version conflict:** An installed capability may conflict with the new one.
  Use `logion skill list` to inspect installed capabilities.

## Marketplace search errors

- **Network timeout:** Check internet connectivity and Logion API status.
- **Authentication required:** Run `logion auth login` to authenticate.
- **Rate limited:** Wait and retry. The companion implements exponential
  backoff automatically.

## Local recall errors

- **Index not found:** Run `logion recall index` to build the initial local
  recall index.
- **Stale results:** Run `logion recall index --rebuild` to refresh.
- Recall is read-only and cannot corrupt installed capabilities.

## Packaging errors

- **Manifest validation failed:** Check `course/capabilities.yaml` for required
  fields. Run `python scripts/package_skill.py` for detailed errors.
- **Missing references:** Ensure all files referenced in SKILL.md exist.
- **Critical secrets detected:** The packaging check fails on
  high-confidence patterns (PEM certificate headers, provider-specific
  token prefixes, AWS access-key prefixes, and private key markers).
  Remove actual secrets from package files. Low-confidence patterns
  like generic words produce warnings but do not fail the check in
  documentation files.

## Confirmation gate failures

- If the agent proceeds without confirmation on a gated action, file a bug.
- If a gated action is confirmed but fails, check the error message and retry
  after resolving the underlying issue.