<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Normative carry-overs

Inherited implementation contracts that survived the retirement of their
original plan files. These are **binding** on 15.10/15.11/15.11.1 and are not
waived by any resequencing. Read this file when implementing identity,
acquisition, reconciliation, or observation — not otherwise.

Split out of `next-steps.md` on 2026-08-17 so the execution order stays short.
The text below is unchanged.

Exit condition: each carry-over is either resolved in the phase that owns it
(endpoint exists / adapter shipped / HMAC contract implemented) or explicitly
re-scoped in writing; the envelope conflict below is closed with one schema
remaining normative.

## Known carry-overs

- there is no `versions/from-source` materialization endpoint or
  `publish-from-repo` command — repo publishing stops at the source link;
- the platform-bounty admin lane is API-only (no SDK resource, no
  `logion admin bounties` CLI subgroup);
- `cli/_observation.py` ships the local observation envelope/spool writer as a
  library with no production command wired to it;
- `resources acquire` behavior is owned by 15.10;
- the normative `scope_id`/`installation_id` HMAC and cryptographic
  publisher-signature verification are not implemented;
- the indexer has no `lobehub` adapter (`skillsmp` and `smithery` shipped
  instead), and the `hermes_docs` adapter has no seed entry.

## Local installation identity

This contract remains mandatory; the existing inventory must not approximate it
with a plain path hash.

Each profile/node creates a random 256-bit `local_node_secret` as exactly 32 raw
bytes (no encoding/newline) at
`$LOGION_HOME/identity/local-node-secret`. The identity directory is owner-only
`0700` and the atomically created file is `0600` (or platform-equivalent ACL).
Opaque IDs use HMAC-SHA-256 with domain-separated canonical UTF-8 inputs:

```text
scope_id = base64url(HMAC-SHA-256(
  local_node_secret,
  "logion-scope-v1\0" + harness + "\0" + scope_kind + "\0" + canonical_scope_root
))

installation_id = base64url(HMAC-SHA-256(
  local_node_secret,
  "logion-installation-v1\0" + resource_version_id + "\0" + distribution_id
  + "\0" + harness + "\0" + native_manager + "\0" + scope_kind + "\0"
  + scope_id + "\0" + relative_target_path + "\0" + native_receipt_digest
))
```

Each `\0` is one NUL byte (`0x00`); NUL is forbidden inside components.
`base64url` uses RFC 4648's URL-safe alphabet without `=` padding.
`resource_version_id` and the server-issued `distribution_id` are lowercase,
hyphenated RFC 4122 UUIDs. `harness` and `scope_kind` are canonical lowercase
CLI identifiers. `native_manager` is
`<canonical-lowercase-name>@<exact-version>`. `relative_target_path` uses NFC,
`/` separators, no leading slash, and no empty, `.` or `..` segment; it
preserves case on case-sensitive volumes and is Unicode-casefolded on
case-insensitive volumes.

`native_receipt_digest` is `sha256:<64 lowercase hex>` over RFC 8785 canonical
JSON bytes of a fixed-schema native evidence record containing manager
name/version, native receipt or lock identifier, canonical source, immutable
revision, and content digest—never a raw local path. Without exact native
evidence, neither `native_receipt_digest` nor `installation_id` may be minted;
the item remains an unlinked local candidate. A dry-run may emit `scope_id` only
after this HMAC contract exists, but never invents an installation identity.

`canonical_scope_root` is
`<platform>:<normalized-absolute-path>` (`posix` or `windows`), after resolving
symlinks/junctions, normalizing NFC and `/`, and removing trailing separators
except filesystem roots. POSIX preserves case. Windows removes `\\?\`,
uppercases drive letters, and casefolds only when the containing volume is
case-insensitive; UNC server/share follows the same volume rule. Missing or
unresolved roots fail closed. Neither the canonical root nor raw path enters an
outbound payload. Unsalted/plain path hashes are forbidden. Moving a checkout,
rotating the secret, changing profile/node/receipt, or changing scope creates a
new local identity; migration must be explicit. Deterministic cross-language
vectors for both HMACs are required before release.

## Acquisition, reconciliation, and observation

15.10 must turn the current blocked plan into real acquisition only after the
API supplies a validated immutable distribution and the plan reports target,
version/distribution/manager, native argv or copy operation, collisions,
digest/provenance verification, observation state, permissions, and required
confirmation. Non-dry-run requires explicit approval when creating a scope,
replacing content, widening permissions, configuring a hook/plugin, or crossing
repo → user/admin. It must also own installation/update/removal isolation,
validated receipts, exact reconciliation, and fresh-harness discovery.

Reconciliation order remains: (1) native receipt/lock plus immutable revision;
(2) canonical source plus revision and content digest; (3) a cryptographically
verified signature over canonical bytes/digest whose key is validly bound to
the publisher; otherwise `signature-present-unverified`, `ambiguous`, or
`unlinked`. **Name similarity is never identity.** The current runtime correctly
uses `signature-present-unverified`; `signed` remains reserved until canonical
serialization, algorithms, publisher-key binding, rotation/revocation, and
failure behavior are implemented.

> This reconciliation order is what makes a remote MCP endpoint resolve to
> `unlinked`/`ambiguous` rather than to an exact version — see Loop D in
> [`release-0.2.md`](release-0.2.md).

15.11 owns real harness hook/plugin observation, attributed native use,
consented upload, and immutable-version-linked feedback. Its fixed local
envelope may carry only event, canonical harness, opaque harness session and
installation/scope IDs, exact resource version when known, scope kind, closed
task class/outcome, ordered RFC3339 timestamps, and integration version. It
must reject raw prompts, source code, paths, arguments, secrets, model context,
terminal output, and arbitrary fields. Consent remains: `off` = no spool or
network; `local-only` = local attribution only; `prompt` = queue a
minimum-disclosure proposal; `auto` = only the separately documented narrow
receipt class. Ratings, prose, and raw task data always need separate consent.
**An observation is not a rating.**

### Envelope conflict — resolve before 0.2

Two envelopes are currently normative for the same record: the live
`UsageObservation` spool schema, and the richer `cli/_observation.py` envelope
described above (task class, outcome, ordered timestamps, integration version),
which has no production caller. 15.11.1 either adopts one or the other is
deleted. Both cannot stay authoritative. This is a gate item in
[`release-0.2.md`](release-0.2.md).

## Publisher-integrated observation — capability correction

[`15.11.1`](phase-15.11.1-publisher-integrated-consented-observation.md)
declares a static Agent Skill without hooks as
`publisher_observation_unsupported`. **That is out of date.** Claude Code
supports a `hooks` field in `SKILL.md` frontmatter; hooks declared there are
registered when the skill is invoked and persist for the rest of the session,
with an `once: true` option. Verified against the current published skills and
hooks references, 2026-08-17.

Two constraints that must be written into the phase before implementation:

1. `hooks` is a Claude Code extension, **not** part of the Agent Skills spec.
   The spec permits `name`, `description`, `license`, `compatibility`,
   `metadata`, `allowed-tools`, and an unknown key is a **hard packaging error**
   for claude.ai upload, the Skills API, and `package_skill.py`. Instrumenting a
   skill this way costs the publisher those distribution paths. `metadata` is
   the only in-spec, portable carrier for an instrumentation-profile reference,
   and it is declarative only — it cannot execute.
2. There is **no consent prompt before a skill-registered hook runs a command**.
   The disclosure gate is entirely Logion's responsibility, and a
   network-calling hook inside a third party's artifact is the single largest
   reputational risk in the product. Consent must be a visible, verifiable
   badge, never fine print. The existing fail-open and exact-disclosure
   requirements in that plan are the floor, not the ceiling.

Because of (1), prefer plugin and MCP projections first, where the hook is a
native, expected mechanism. Skill-frontmatter instrumentation ships only where a
publisher explicitly accepts the packaging trade-off.
