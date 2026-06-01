# Security Policy

## Supported Versions

| Package | Supported versions |
|---|---|
| `logion-client` (Python SDK) | Latest minor release |
| `logion-cli` | Latest minor release |
| `logion-agent-companion` | Latest minor release |

Only the latest minor version of each package receives security patches.

## Reporting a Vulnerability

**Do not file a public issue for a security vulnerability.**

Instead, please use one of these private channels:

- **Preferred:** Open a private vulnerability report at  
  [https://github.com/nicolasmelo1/logion/security/advisories/new](https://github.com/nicolasmelo1/logion/security/advisories/new)
<!-- NOTE: we do not yet own the `logion.dev` domain. Once it is registered
     and a security mailbox is set up, update this address (and the matching
     references in CODE_OF_CONDUCT.md and README.md). Until then, the GitHub
     private vulnerability report above is the only working channel. -->
- **Fallback:** Email [security@logion.dev](mailto:security@logion.dev)

You can expect an initial response within 72 hours.

## Disclosure Policy

We follow a **90-day disclosure window**. After a vulnerability is confirmed,
we will:

1. Prepare a fix and coordinate a release.
2. Credit the reporter (unless they prefer to remain anonymous).
3. Publish the advisory after the fix is released.

The disclosure window may be shortened by mutual agreement between the
maintainer and the reporter.

## Scope

**In scope:**

- The public packages published from this repository:
  `logion-client`, `logion-cli`, and `logion-agent-companion`.
- The OpenAPI contract at `contracts/openapi/v1.json` as shipped in
  this repository.

**Out of scope:**

- Rate limiting on public endpoints (intentional design).
- Reports that require physical access to infrastructure.
- Social-engineering attacks.
- Denial-of-service attacks against public endpoints.

If you discover a vulnerability in the backend services that power the
Logion platform, please report it through the same channels above and we
will route it to the appropriate team internally.