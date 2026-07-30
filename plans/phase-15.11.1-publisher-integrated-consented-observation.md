<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.11.1 — Publisher-integrated consented observation projections

> **Dogfood — Level 2.1 (publisher-side adoption):** a resource owner adds one
> Logion instrumentation profile, publishes a native skill/plugin projection,
> and a fresh user accepts one precise disclosure during install or first
> activation. Subsequent supported uses emit only the approved minimum receipt
> without requiring the full Logion CLI or a second Logion installation.
> **After this phase:** Logion can enter through the resource publisher's
> existing distribution instead of convincing every end user to adopt the whole
> Logion suite.
> **Honesty boundary:** an install is not use, activation is not success, and a
> publisher-integrated receipt is first-party field evidence rather than an
> independent evaluation.

## Why this subphase exists

Phase 15.11 makes a separately installed Logion companion observe resources
already present in a harness. That remains the universal opt-in path, but it
leaves a difficult adoption step for an individual who only wants one skill,
plugin, MCP connector, or model.

This subphase adds the complementary publisher path:

```text
publisher owns resource/version
  → Logion generates thin native projections
  → user installs the resource through its normal manager
  → manager/harness shows one exact telemetry disclosure
  → user accepts, chooses local-only, or declines
  → bundled hook/reporter emits approved minimum receipts
  → Logion reconciles them to the original ResourceVersion
  → evidence, feedback, scorecards, and improvement candidates accumulate
```

The resource remains useful when Logion is unavailable or consent is denied.
The full CLI remains valuable for operators, evaluators, runners, contributors,
and users who want local inventory or bounties, but it is not a per-user
prerequisite for this narrow receipt path.

## Product contract

The publisher configures Logion once for a canonical resource version. Logion
produces or validates the native distribution surfaces needed by supported
harnesses:

```text
canonical ResourceVersion
  ├─ portable Agent Skill distribution
  ├─ Claude plugin projection with supported lifecycle hook
  ├─ Codex plugin projection when the pinned release exposes a verified hook
  ├─ other capability-tested harness projections
  └─ native artifact unchanged for unsupported harnesses
```

These are distributions of one resource version, not duplicate resources or
Logion-owned wrappers. Every emitted receipt names the original publisher and
exact version. A projection has its own distribution digest and integration
version so that faults in the reporter can be distinguished from faults in the
resource.

The preferred author command is conceptually:

```text
logion instrument RESOURCE_VERSION \
  --targets agent-skill,claude-plugin,codex-plugin \
  --events activated,completed,failed
```

The command must produce a reviewable plan/diff before writing. It must not
publish a package, widen permissions, or enable network delivery without
explicit publisher approval.

## Consent UX

The manager or harness presents the consent gate during installation when that
lifecycle exists, otherwise on first activation before the first observation
write or network request:

```text
This skill uses Logion to send usage metadata:
resource/version, activation, completion/failure, approximate duration,
and harness type.

It does not send prompts, files, paths, tool inputs/outputs, secrets,
credentials, case content, or identity.

[Allow] [Local only] [Do not allow]
```

The copy must be generated from the exact profile rather than a generic
“telemetry” label. It lists every outbound data category, endpoint/operator,
retention-policy link, and whether a pseudonymous installation identifier is
used.

Consent is stored against:

```text
publisher identity
+ canonical resource identity
+ instrumentation-profile digest
+ destination endpoint/operator
+ outbound data categories
+ consent mode and scope
```

Patch/minor resource updates may reuse consent only while this tuple and the
publisher's declared compatibility policy remain unchanged. Re-prompt before
the first event when the publisher changes, endpoint changes, categories widen,
retention materially changes, or a previously local-only profile enables
network delivery. A silent profile expansion is invalid.

Denial is fail-open for the resource:

- `off`: no observation file, spool, identifier, or network request;
- `local-only`: local counters/receipts only, inspectable and deletable;
- `allow`: only the approved narrow receipt class may be uploaded;
- ratings, prose feedback, prompts, artifacts, eval inputs/results, and public
  evidence publication require their own explicit actions or policies.

Respect the strongest applicable opt-out, including Logion `off`,
`DO_NOT_TRACK`, and a supported native manager's telemetry-disable setting.
Native-manager consent never silently counts as Logion consent.

## Instrumentation profile

Define a versioned Logion-owned profile separate from AI Catalog, ARD, Agent
Skills, and each plugin format. Illustrative shape:

```yaml
schema: logion.instrumentation/v1alpha1
subject:
  resource_id: urn:air:example.com:skill:review-helper
  resource_version: "1.4.2"
  distribution_digest: sha256:...
publisher:
  identity: did:web:example.com
delivery:
  endpoint: https://evidence.logion.sh/v1/field-receipts
  mode: asynchronous-batch
events:
  - resource.activated
  - resource.use.completed
  - resource.use.failed
fields:
  - resource_id
  - resource_version
  - distribution_digest
  - event
  - outcome
  - duration_bucket
  - harness
  - integration_version
excluded:
  - prompt
  - file_content
  - local_path
  - tool_arguments
  - tool_results
  - model_context
  - secrets
  - user_identity
```

The actual schema must define bounded enums, size limits, endpoint policy,
canonical serialization, profile digesting, version negotiation, and unknown
field rejection before implementation.

### Protocol boundary

AI Catalog remains the typed catalog/entry representation. ARD remains
pre-invocation discovery. Native formats remain responsible for install and
execution. AKTP remains the evidence/improvement overlay.

- Do not add Logion consent, hook, or receipt semantics to an AI Catalog base
  object or claim that ARD performs instrumentation.
- A Catalog Entry may preserve a namespaced scalar metadata reference to a
  publisher-hosted instrumentation profile only where the pinned schema and
  conformance suite accept it. The native artifact/plugin profile remains the
  runtime authority.
- Agent Skill or plugin metadata is namespaced under that native format's
  extension rules. Unknown metadata being tolerated does not prove that a
  harness executes a hook.
- If an upstream manager gains a standard permission or lifecycle extension,
  prefer a fixture-backed upstream proposal/adoption over a Logion-only fork.
- Run `python3 scripts/check_protocol_specs.py` and both relevant conformance
  suites before changing catalog publication or discovery behavior.

## Projection capability model

Do not promise one mechanism across all harnesses. Each adapter pins and tests:

```yaml
publisher_instrumentation:
  install_disclosure: supported|first-activation|unsupported
  skill_activation_hook: supported|unsupported
  completion_hook: supported|heuristic|unsupported
  plugin_bundled_reporter: supported|unsupported
  local_spool: supported|unsupported
  network_delivery: supported|unsupported
  verified_harness_version: "..."
  evidence_fixture: "..."
```

Release behavior:

| Surface | Required behavior |
| --- | --- |
| Claude plugin | Bundle a native plugin/skill-scoped hook only after pinning the official plugin and hook contract; show disclosure at install or before first activation. |
| Codex plugin | Ship only after a recorded current-release fixture proves the relevant plugin lifecycle and hook. If install-time permission UI is unavailable, use a non-networking first-activation gate. |
| Plain `npx skills add` | Treat install receipt separately from use. Do not claim automatic use telemetry unless the manager or target harness exposes a verified extension/hook. |
| Static Agent Skill without hooks | Preserve full skill functionality, declare observation `unsupported`, and offer publisher analytics only through a compatible plugin projection or separately installed Logion companion. |
| MCP/plugin/model distributions | Apply the same capability declaration; remote execution does not authorize TLS interception, credential access, probes, or provider-side modification. |

For `skills.sh`, prepare an upstream proposal for a generic, manager-owned
permission prompt plus post-install observer registration. Until accepted and
pinned, metadata in `SKILL.md` is a declaration only. It cannot cause Vercel's
installer or an arbitrary harness to execute Logion code.

## Reporter architecture

The generated reporter is tiny, open source, content-addressed, and native to
the projection. It may call the Logion receipt endpoint directly; it must not
silently install the full CLI.

Required properties:

- never blocks, delays, or changes the resource's primary behavior;
- writes through one shared, versioned local spool implementation where the
  harness permits it;
- batches and uploads asynchronously with bounded retries and storage;
- redacts before persistence, not only before upload;
- rejects undeclared fields and oversized payloads;
- exposes status, exact pending payloads, export, deletion, and disable;
- deduplicates by event/installation without creating a stable cross-resource
  tracking identity;
- verifies endpoint TLS and never accepts publisher-supplied credentials for
  Logion;
- emits integration health separately from resource outcome;
- supports deterministic removal when the plugin/resource is uninstalled.

One plugin hook may observe several resources from the same publisher package,
but every event still resolves to one exact distribution and
`ResourceVersion`. It may not infer use merely because a skill was installed,
listed, loaded into context, or available to the model.

## Receipt and evidence semantics

Keep these facts separate:

1. `resource.installed`: manager completed an install.
2. `resource.activated`: a verified native lifecycle event selected/loaded the
   resource.
3. `resource.use.completed|failed|abandoned|unknown`: the harness exposed a
   trustworthy terminal signal.
4. `feedback.submitted`: an agent/user intentionally supplied a report.
5. `eval.completed`: a controlled evaluator produced a separately scoped
   result.

Only 2–3 are normal-use receipts. Neither becomes a star rating, verified
review, benchmark result, safety claim, or automatic bounty recommendation by
itself.

Publisher-integrated receipts carry issuer/integration provenance and are
labeled `publisher_integrated_field_observation`. Aggregation must expose
sample size, version coverage, consent mode, harness coverage, concentration,
and known blind spots. Independent runners and controlled evals remain
separate evidence classes.

## Improvement and bounty path

Consented receipts may:

- reveal version-specific failure clusters;
- trigger a post-use feedback request under the user's policy;
- populate owner-facing scorecards and regression candidates;
- nominate an eval, reproduction, documentation, adapter, or source change;
- contribute to a bounty candidate after cohort, abuse, deliverability, and
  acceptance-authority checks.

They never spend money, publish a bounty, assert a root cause, or claim that a
closed upstream resource can be modified automatically. Follow Phase 15.14's
operator approval and deliverable-authority boundary.

## Implementation slices

### Public repository

- Add a versioned instrumentation-profile schema, fixtures, validator, and
  profile-diff command.
- Add `logion instrument ... --dry-run` projection planning.
- Generate capability-gated Claude/Codex plugin projections and portable static
  Skill fallback from one canonical resource-version input.
- Add the minimal reporter/spool library without a dependency on the full CLI.
- Add inspect/disable/delete/export behavior and reproducible package manifests.
- Publish a compatibility table generated from recorded real-harness fixtures.

### Private repository

- Add narrow field-receipt ingestion keyed to canonical resource/version,
  profile digest, publisher, distribution, and integration version.
- Store consent proof/version without storing raw local paths or identity.
- Add idempotency, rate limits, retention/deletion, endpoint abuse controls,
  aggregation thresholds, and publisher-facing health/scorecard projections.
- Keep install, activation, field outcome, feedback, and eval evidence in
  distinct typed records.

### Upstream work

- Propose a generic permission-and-observer lifecycle to `skills.sh`/Agent
  Skills managers rather than requesting a Logion-specific privileged hook.
- Contribute native plugin permission improvements where a harness lacks a
  precise install/first-activation disclosure.
- Record accepted/rejected/upstream-pending states; do not make Phase 15.11.1
  depend on unmerged upstream work for already capable harnesses.

## Required tests

- Consent allow/local-only/deny, cancellation, non-interactive install, profile
  expansion, publisher/endpoint change, uninstall, and reinstall.
- Denial leaves the skill/plugin operational and produces byte-identical
  no-telemetry state.
- Privacy canaries for prompt, file, path, tool arguments/results, secrets,
  identity, and legal/customer content never reach memory serialization,
  spool, request, logs, or error reporting.
- Install does not fabricate activation; activation does not fabricate
  completion; missing terminal hooks emit `unknown` or no terminal receipt.
- Offline bounded spool, retry, corruption recovery, deduplication, retention,
  deletion, endpoint failure, and Logion outage.
- Exact publisher/resource/version/distribution attribution across updates and
  two same-named skills.
- Generated projection reproducibility and digest verification.
- Harness capability fixture drift fails release claims closed rather than
  silently falling back to inferred telemetry.
- Full CLI absent: supported plugin still collects the approved narrow receipt,
  while unsupported static-skill fallback remains functional and honest.
- Receipt ingestion cannot create ratings, evals, public evidence, bounty
  funding, or payment without the separate required action.

## Mandatory proving-ground scenario

Add `builtin:phase_15_11_1_publisher_integrated_observation` and run it with a
fresh isolated publisher and consumer:

- **Publisher prompt:** “Instrument this exact review skill version for Claude
  and Codex. Generate only supported native projections. The end user must not
  install the full Logion CLI. Show the exact disclosure and outbound fields
  before publishing.”
- **Consumer prompt:** “Install the publisher's plugin through the native
  manager. Allow the disclosed minimum usage metadata, use the skill once, and
  show me what Logion received. Then disable telemetry and use the skill again.”
- **Assertions:** `files.instrumentation_profile_valid`,
  `files.native_projection_digest_matches`,
  `files.consent_recorded_before_observation`,
  `files.no_full_cli_installed`,
  `files.resource_works_when_disabled`,
  `api.publisher_receipt_exact_resource_version`,
  `api.install_not_counted_as_use`,
  `api.private_payload_absent`, and
  `api.disabled_use_zero_receipts`.
- **Fallback leg:** install the portable static Skill in a harness without
  lifecycle hooks. Assert normal skill use, an explicit
  `publisher_observation_unsupported` capability, and zero fabricated events.
- **Evidence:** retain pinned harness/manager versions, manifests, profile and
  distribution digests, disclosure copy, consent-policy digest, redacted
  receipt, disabled-run zero-write proof, and no-500 proof.

## Acceptance criteria

- [ ] A publisher can configure one canonical `ResourceVersion` and generate
      supported native projections without hand-writing per-harness telemetry.
- [ ] A fresh user sees the exact disclosure once and can allow, choose
      local-only, or decline before any observation state/network request.
- [ ] On a supported plugin/hook path, accepted minimum receipts flow
      automatically without the full Logion CLI.
- [ ] Declining or disabling telemetry never prevents normal resource use.
- [ ] The same resource version remains one identity across portable Skill and
      plugin projections; distribution/integration faults remain distinguishable.
- [ ] Static Skill installations without a verified lifecycle hook report
      unsupported use observation and never pretend metadata is executable.
- [ ] AI Catalog, ARD, native execution, and AKTP evidence semantics remain
      separate and pass the pinned protocol integrity gate.
- [ ] Install, activation, completion/failure, feedback, and eval records remain
      separate facts throughout API, aggregation, and UI.
- [ ] Publisher field receipts can inform scorecards and improvement candidates
      but cannot auto-rate, auto-fund, or create an undeliverable bounty.
- [ ] The mandatory real-agent scenario passes for every advertised harness;
      capability claims fail closed when an upstream release drifts.

## Rollout and kill criteria

1. First-party publisher package, local-only by default.
2. Invite-only external publisher with one verified plugin harness.
3. Accepted narrow uploads with inspect/delete/disable surfaces.
4. Second independently maintained publisher and second supported harness.
5. Upstream manager proposal for portable install consent/observer lifecycle.

Track consent acceptance/decline, activation-to-receipt integrity, exact
attribution, reporter errors, uninstall success, feedback conversion, and
publisher action on resulting improvements. Never track task contents.

Narrow or stop the approach if the reporter materially affects resource
reliability, disclosures cannot be precise, exact attribution falls below the
Phase 15.11 threshold, users cannot effectively disable/delete, or publishers
do not act on the resulting evidence.

## Out of scope

Covert telemetry, universal static-Skill execution, TLS interception, prompt or
tool-payload capture, cross-resource identity tracking, a new AI Catalog/ARD
runtime contract, independent-eval claims, automatic ratings, automatic bounty
funding, mandatory Logion CLI installation, or mandatory marketplace
acquisition.
