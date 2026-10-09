<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Normative carry-overs

Inherited implementation contracts that survived the retirement of their
original plan files — 15.10, 15.10.1, and 15.11 among them. These are
**binding** and are not waived by any resequencing or by a plan being deleted.
Read this file when implementing identity, acquisition, reconciliation, or
observation — not otherwise.

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
- `resources acquire` behavior is owned by 15.10;
- the normative `scope_id`/`installation_id` HMAC and cryptographic
  publisher-signature verification are not implemented;
- the indexer has no `lobehub` adapter (`skillsmp` and `smithery` shipped
  instead), and the `hermes_docs` adapter has no seed entry;
- **neither 15.10 nor 15.10.1 has a sealed real-agent phase gate.** Both plans
  required one and both plans are now retired. The scenarios exist
  (`acquisition_install_scope_safety`,
  `dsh_plugin_discovery_install_and_reconcile`) and both phases have real
  dogfood records against live managers, but `logion/artifacts/phase-gates/`
  holds only `phase-15.11`, `phase-15.12`, and `phase-15.14.1`, and there is no
  run report for either scenario. The obligation survives the plan;
- **the Logion dsh plugin is unpublished.** `plugins/dsh-plugin/`
  (`@logionsh/dsh-plugin`) sits at `0.1.0` with no `dsh-plugin-v*` tag, so
  15.10.1's "installs through dsh's native flow from its public distribution
  point" criterion is unmet. Release procedure is in `logion/RELEASING.md`; the
  roadmap sequences this as a distribution experiment after step 6.

Shipped shape for acquisition, inventory, reconciliation, and the dsh path is
[`../maintainer documentation: native-acquisition-and-inventory.md`](../maintainer documentation: native-acquisition-and-inventory.md).

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

### Envelope conflict — resolved 2026-08-27

Two envelopes were normative for the same record: the live `UsageObservation`
spool schema, and the richer `cli/_observation.py` envelope (task class,
outcome, ordered timestamps, integration version), which had no production
caller. **Settled by adoption and deletion**: `cli/usage/observations.py` is the
single normative envelope, carrying the richer fields, and `cli/_observation.py`
is deleted. The spool rejects a record whose `integration_version` does not
match, so a stale hook cannot write the old shape.

### Envelope fields — decided 2026-08-27, unbuilt

Recorded here rather than in `15.11` because that phase is closed and its plan
file is being retired; this contract has to outlive it. It is not waived by any
resequencing, and it belongs to whichever phase next touches the envelope.

The shipped envelope records `harness` as a bare lowercase slug with no version,
and records nothing about the model. Both are gaps. The sequencing argument is
the same for both and is about schema, not product: the spool rejects any record
whose `integration_version` does not match, so adding a field later is a version
bump that invalidates every installed hook. **The cheapest moment to change a
strictly-versioned envelope is while the installed base is approximately zero** —
true now, false after 0.2. Gate item in [`release-0.2.md`](release-0.2.md).

**Harness version — add.** `claude-code` in March and `claude-code` in August are
not the same harness, and the difference can move a result more than the model
does ([arXiv:2605.23950](https://arxiv.org/abs/2605.23950)). Without it, the
"harness coverage" that every published `n` is required to carry does not name
anything specific. Zero tokens, no new data category, no new consent question.

**Model slug — add, as a closed allowlist only.** Without it a field cohort
silently aggregates across Opus, Haiku and gpt-5.4-mini, which are not one
population; "fails only on a small model" is exactly the finding a publisher can
act on and a bounty can fix. Conditions, all mandatory:

- a **closed allowlist of coarse slugs**, never free text, never a private
  endpoint or deployment name;
- **declared per adapter**, like every other capability here — most adapters will
  honestly report they cannot see it, and that refusal is the correct outcome
  rather than an inference;
- same consent axis as the rest of the envelope, and suppressed in aggregates
  below the minimum cohort, because a model slug at low `n` is mildly
  identifying;
- if it cannot be a closed enum, it does not ship.

This does **not** reopen the `model context` prohibition above, and the
distinction is load-bearing: the prohibition covers prompts, system text and
conversation state. A coarse model slug is an environment label of the same kind
as `harness`. `15.11.1`'s instrumentation profile keeps `model_context` in its
`excluded` list unchanged.

The slug is what makes **model-harness pair** evidence possible, which is the one
form of model ranking that is not commodity — everyone publishes model rankings,
nobody publishes pair rankings, and `harness` already being first-class is why
Logion can.

**Measured token counts — refuse.** No hook payload carries per-resource token
attribution, so any number here would be inferred, and an inferred number is what
this file forbids everywhere else. Token measurement belongs to `16.2`, where the
runner controls the loop. The existing `token_efficiency` score stays a declared
opinion, not a measurement.

## Publisher-integrated observation — designed, not built

The publisher path — a resource owner instruments their own artifact so a user
who never installs the Logion CLI can consent to and emit a narrow usage receipt
— was designed in full and **never implemented**. It is not on any queue. The
full design is in git history at
`plans/phase-15.11.1-publisher-integrated-consented-observation.md` (retired
2026-08-27); its capability tiers and per-client coverage are already reflected
in the shipped typed refusals documented in
[`../maintainer documentation: native-use-observation-and-feedback.md`](../maintainer documentation: native-use-observation-and-feedback.md).

**Why it is not built — the reasoning, so it is not re-derived wrongly.** It is
tempting to call this the Google Analytics move: the publisher gets their own
numbers, Logion gets visibility outside its own realm. That role is real, but
this is the expensive way to fill it.

1. **The cheap version is already on the critical path.** Cross-hub install
   reconciliation (step 2) gives a publisher something no hub can give them —
   presence and version coverage of their artifact across every indexed hub —
   and, as [`next-steps.md`](next-steps.md) puts it, de-fragmentation needs no
   consent and no client-side code. Same trade, none of the machinery.
2. **The mechanism's own premise limits its reach.** It works only for a client
   whose hook contract is pinned to an exact release with a recorded payload
   fixture. Today that is Claude Code and Codex; everything else resolves to
   `unsupported`, and the Hermes fixture the design treated as gate-required was
   never recorded. "Instrument once, reach everyone" was never true.
3. **The distribution problem it existed to solve has a cheaper answer.** Its
   job was reaching people who never install the Logion CLI. The public answer
   surface ([`public-answer-surface.md`](public-answer-surface.md)) does that
   with no consent, no client-side code, and no publisher adoption.

**The trigger that would make it right.** Today, instrumenting is a *push* at
publishers who have never heard of Logion, which is why it reads as noise.
Revisit when it becomes a *pull*: **a publisher who already holds a Logion
report about their own artifact asks to see it continuously, for their own
users.** At that point the adoption problem is already solved and the mechanism
is worth its cost. That demand comes from step 8 outreach, not from step 1
supply — so nothing before step 8 should schedule this.

One constraint outlives it, because it binds any future harness integration and
is recorded nowhere else.

### Claude Code `SKILL.md` frontmatter hooks

Claude Code supports a `hooks` field in `SKILL.md` frontmatter; hooks declared
there register when the skill is invoked and persist for the session, with an
`once: true` option (verified 2026-08-17). Two constraints:

1. `hooks` is a **Claude Code extension, not part of the Agent Skills spec**.
   The spec permits `name`, `description`, `license`, `compatibility`,
   `metadata`, `allowed-tools`, and an unknown key is a **hard packaging error**
   for claude.ai upload, the Skills API, and `package_skill.py`. Instrumenting a
   skill this way costs the publisher those distribution paths. `metadata` is the
   only in-spec, portable carrier for a reference of this kind, and it is
   declarative only — **metadata a manager tolerates is not metadata a harness
   executes.**
2. There is **no consent prompt before a skill-registered hook runs a command**.
   The disclosure gate is entirely Logion's responsibility, and a network-calling
   hook inside a third party's artifact is the single largest reputational risk
   in the product. Consent must be a visible, verifiable badge, never fine print.

Because of (1), prefer plugin and MCP surfaces first, where a hook is a native,
expected mechanism. Skill-frontmatter instrumentation ships only where a
publisher explicitly accepts the packaging trade-off.
