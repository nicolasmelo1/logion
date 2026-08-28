<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.11.1 — Publisher-integrated consented observation projections

> **Implementation status (2026-08-24): not built.** No `logion instrument`
> command, no instrumentation-profile schema, no reporter, no publisher-receipt
> ingestion. The parts that exist were built for this phase from 15.11: the
> `shadow` identity tier, the `outcome`/`task_class`/`duration_bucket`/
> `integration_version` fields on the observation envelope, and
> `consent_policy_digest` on usage receipts.
>
> **This revision corrects the phase's premise.** The previous version assumed
> Logion could generate native projections carrying a bundled reporter that
> runs automatically wherever the resource is installed. That is not what the
> distribution formats permit, and the plan contradicted itself: its own
> capability table already said metadata in `SKILL.md` is a declaration, not an
> execution. The mechanism below is narrower and buildable; the honesty
> boundary is now the same in every section.
>
> **Dogfood — Level 2.1 (publisher-side adoption):** a resource owner adds one
> Logion instrumentation profile, publishes a native projection, and a fresh
> user accepts one precise disclosure during install or first activation.
> Subsequent supported uses emit only the approved minimum receipt without
> requiring the full Logion CLI or a second Logion installation.
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
  → Logion generates a thin native projection
  → user installs the resource through its normal manager
  → manager or first activation shows one exact telemetry disclosure
  → user accepts, chooses local-only, or declines
  → the bundled reporter emits approved minimum receipts
  → Logion reconciles them to the original ResourceVersion
  → evidence, feedback, scorecards, and improvement candidates accumulate
```

The resource remains useful when Logion is unavailable or consent is denied.
The full CLI remains valuable for operators, evaluators, runners, contributors,
and publishers, but it is not a per-user prerequisite for this narrow receipt
path.

## The premise correction

Three upstream facts, verified 2026-08-24, bound what this phase may claim.

1. Agent Plugins 1.0.0 is a **directory format**, not an npm package: a
   `plugin.json` manifest, `skills/` holding Agent Skills, an optional
   `mcp.json`, and reverse-domain **client-specific namespaces** that carry
   hooks. `npx plugins add owner/repo` installs it; the npm package `plugins`
   is the installer, not the distribution channel.
   (<https://github.com/vercel-labs/open-plugin-spec>,
   <https://github.com/vercel/vercel-plugin>)
2. The portable core is therefore **declarative**. Nothing in it guarantees
   that any client executes code. Execution lives in the client namespaces,
   which means it is a per-client capability, pinned per client release.
3. A static Agent Skill is markdown. Metadata a manager tolerates is not
   metadata a harness executes.

The consequence is that "the publisher ships a reporter and telemetry flows"
is only true for a client whose hook contract Logion has pinned against an
exact release with a recorded payload fixture. Everywhere else it is false, and
a plan that promises it everywhere produces an implementation that infers use
from installation.

So the phase declares three tiers, and the tier decides what the projection may
claim. A projection never upgrades itself at runtime.

| Tier | Condition | May claim |
| --- | --- | --- |
| `hook` | the client's hook contract is pinned to an exact release, a payload fixture is recorded in the repository, and the reporter runtime is present | automatic use observation |
| `explicit_report` | no lifecycle hook, but the skill's own text can instruct the agent to report use through a documented command | reported use only |
| `unsupported` | no pinned hook, or no reporter runtime, or the pinned release drifted | nothing — inventory and install facts only |

A tier is resolved per client, so the phase declares its client coverage
explicitly rather than promising "supported harnesses".

| Client | How Logion delivers the observer | Tier | Events it may honestly report | Payload fixture | Gate |
| --- | --- | --- | --- | --- | --- |
| Claude Code | client-namespace hook entry → `settings.json` `PostToolUse` | `hook` | activation and terminal outcome | recorded (`claude_code_post_tool_use.json`) | required |
| Codex | client-namespace hook entry → `.codex/hooks.json` `PostToolUse` | `hook` | activation and terminal outcome | recorded (`codex_post_tool_use.json`) | required |
| Hermes | generated stdlib-only Python plugin under `~/.hermes/plugins/logion-observer/`, registered through the harness's `register_hook`, enabled in `~/.hermes/config.yaml` | `hook`, **user scope only** | `resource.activated` **only** | **must be recorded — none exists yet** | **required** |
| DeepSeek Harness | `@logionsh/dsh-plugin`, a Cordis bundle whose patch loads the package by name | `explicit_report` today | use reported through the `logion_*` tools | not recorded | not gate-required |
| Everything else | portable static skill, no observer | `unsupported` | none | — | — |

Three of those rows carry constraints an implementer must not smooth over:

- **Hermes reports activation, never completion.** The shipped observer fires
  on `action == "loaded"` for a named skill and derives the candidate skill
  directory locally. There is no terminal signal in that event, so a Hermes
  profile declares `events: ["resource.activated"]` and the reporter must never
  synthesize `completed` or `failed` from it. Hermes observation is also
  user-scoped until the harness config becomes scope-aware; a repository-scoped
  Hermes projection resolves to `unsupported`, not to a user-scoped write.
- **Hermes needs a different runtime binding.** Its plugin is Python, not a
  hook command line, which is why the reporter below is a contract with two
  bindings rather than one file.
- **DeepSeek Harness is respected, not advertised.** Its `agent/*` event
  vocabulary and scoped listeners could carry a real lifecycle observer, and
  the plugin is the delivery vehicle for it. It stays `explicit_report` in this
  phase because the harness is a developer preview that announces breaking
  changes and the adapter pins one exact release (`0.1.0-rc.6`), fail-closed.
  Promoting it to `hook` requires pinning a release range and recording a
  fixture first, in that order — the same bar as any other client, and the
  reason its evidence is not gate-required here.

## Product contract

The publisher configures Logion once for a canonical resource version. Logion
produces a **projection directory**, which is a distribution of one resource
version — not a duplicate resource and not a Logion-owned wrapper.

```text
<publisher-repo>/                      # installed as `owner/repo`
├── plugin.json                        # portable core, Agent Plugins 1.0.0
├── skills/<resource-slug>/SKILL.md    # the publisher's artifact, byte-identical
├── .logion/
│   ├── instrumentation.json           # the profile (below)
│   ├── capability.json               # the resolved tier and why
│   ├── consent.json                  # written at install/first activation only
│   └── reporter/report.mjs           # the reporter, dependency-free
└── <client-namespace>/                # hook entry, only for tier `hook`
```

Rules the generator enforces:

- The portable core is copied, never rewritten. A digest comparison proves the
  publisher's artifact is byte-identical inside the projection.
- Every emitted receipt names the original publisher and the exact version.
- The projection carries its own `distribution_digest` and `integration_version`
  so a fault in the reporter is distinguishable from a fault in the resource.
- `logion instrument` produces a reviewable plan and diff before writing. It
  never publishes a package, widens permissions, or enables network delivery
  without explicit publisher approval.

Publisher-side authoring command:

```bash
logion instrument RESOURCE_VERSION \
  --targets agent-plugin,static-skill \
  --events activated,completed,failed \
  --dry-run
```

The publisher has the Logion CLI. The end user does not. That asymmetry is the
whole point of the phase and is the reason `logion instrument` lives in the
CLI while the reporter does not depend on it.

## The instrumentation profile

One versioned, Logion-owned file, separate from AI Catalog, ARD, Agent Skills,
and any plugin format. It is the only thing the reporter reads.

```json
{
  "schema": "logion.instrumentation/v1",
  "subject": {
    "resource_id": "urn:air:example.com:skill:review-helper",
    "resource_version": "1.4.2",
    "distribution_digest": "sha256:..."
  },
  "publisher": { "identity": "did:web:example.com" },
  "delivery": {
    "endpoint": "https://api.logion.sh/v1/resources/RESOURCE_UUID/versions/VERSION_UUID/publisher-receipts",
    "mode": "asynchronous-batch",
    "max_batch": 20,
    "max_spool_bytes": 262144
  },
  "events": ["resource.activated", "resource.use.completed", "resource.use.failed"],
  "fields": [
    "resource_id", "resource_version", "distribution_digest", "event",
    "outcome", "duration_bucket", "harness", "integration_version"
  ],
  "excluded": [
    "prompt", "file_content", "local_path", "tool_arguments", "tool_results",
    "model_context", "secrets", "user_identity"
  ],
  "integration_version": "logion.publisher-reporter.v1"
}
```

Implementation requirements for the schema, all fail-closed:

- bounded enums for `event`, `outcome`, and `duration_bucket`; reuse the exact
  vocabularies already shipped in `packages/cli/cli/usage/observations.py`
  rather than defining a second set;
- size limits per field and per payload;
- canonical serialization (sorted keys, no insignificant whitespace) so the
  profile digest is reproducible;
- unknown top-level and unknown field-name rejection;
- an endpoint policy: HTTPS only, one host, no redirects followed;
- a validator plus a `--diff` mode that shows what changed between two profile
  versions and whether the change widens data categories.

The schema, its fixtures, its validator, and the reporter live in
`packages/instrumentation/` in the public repository. Nothing in that package
may import the CLI. The generator resolves `delivery.endpoint` to concrete
identifiers at generation time — a profile shipped with a template in it is
invalid, because the reporter must not build URLs.

## The reporter

One contract, two runtime bindings, because the clients do not agree on a
runtime:

| Binding | Artifact | Used by |
| --- | --- | --- |
| Node | `.logion/reporter/report.mjs`, dependency-free ES module | Agent Plugins clients (Claude Code, Codex) |
| Python | `.logion/reporter/report.py`, standard library only | Hermes, whose plugin API is Python |

Node is available for the first binding because the ecosystem's own installer
is Node, and Python for the second because the harness plugin runs in-process;
both are assumptions to be **checked, not trusted** — a missing runtime
resolves the tier to `unsupported`.

Both bindings read the same profile, compute the same digests, emit the same
event shape, and are covered by one shared conformance suite in
`packages/instrumentation/tests/conformance/`. The suite is the contract: a
third binding is added by making it pass, and a binding that diverges on any
case fails the build rather than shipping a second dialect.

Required behavior, in order, identical in every binding:

1. Read the hook payload from stdin, bounded to 1 MiB. On any parse failure,
   exit 0 silently.
2. Resolve `.logion/consent.json`. If it is absent, or its mode is `off`, or
   `DO_NOT_TRACK`/`LOGION_DO_NOT_TRACK` is set to anything outside
   `{"", "0", "false", "no", "off"}`, exit 0 and write nothing.
3. Redact before persistence, not before upload: build the event from the
   profile's `fields` allowlist only, dropping every other key. A field not in
   the allowlist never enters memory as part of the event.
4. Append to a bounded local spool next to the projection. When the spool
   reaches `max_spool_bytes`, drop the oldest batch and record the drop count —
   never grow without limit and never block.
5. Under `local-only`, stop here.
6. Under `allow`, batch asynchronously with bounded retries and exponential
   backoff to the profile endpoint, verifying TLS. Deduplicate by
   `(event_id, installation_id)`.
7. Exit 0 always, in under one second of wall clock on the calling path. The
   resource's behavior must not change whether the reporter succeeds, fails, or
   is absent.

Prohibitions, each of which needs a test:

- never install, download, or exec the Logion CLI or any other binary;
- never accept publisher-supplied credentials for Logion;
- never create a stable identifier that correlates a user across resources;
- never infer use from installation, listing, availability, or context loading;
- never emit a terminal outcome the client did not report — absent terminal
  signal is `unknown` or no terminal event at all.

Each binding also exposes, as plain subcommands on the same file:
`status`, `pending`, `export`, `delete`, `disable`. A user who never installs
the Logion CLI must still be able to see, export, and erase everything held
locally, and to turn it off.

One hook may observe several resources from the same publisher package, but
every event still resolves to exactly one distribution and one
`ResourceVersion`.

## Capability model and the drift gate

`capability.json` is generated, never hand-written:

```json
{
  "tier": "hook",
  "client": "claude-code",
  "pinned_release": "...",
  "hook_contract_fixture": "packages/instrumentation/fixtures/claude-code/post-tool-use.json",
  "reporter_binding": "node",
  "reporter_runtime": { "required": "node>=22", "present": true },
  "events": ["resource.activated", "resource.use.completed", "resource.use.failed"],
  "reason": null
}
```

The Hermes equivalent differs in three fields and nothing else:
`"client": "hermes"`, `"reporter_binding": "python"`, and
`"events": ["resource.activated"]`. A Hermes `capability.json` that claims a
terminal event is invalid, and the validator rejects it.

At install and at every activation the projection re-resolves the tier. Any of
the following forces `unsupported` with a populated `reason`, and it is a
downgrade only — never a silent fallback to inferred telemetry:

- the installed client version is outside the pinned range;
- the client's hook config shape no longer matches the recorded fixture;
- the reporter runtime is missing;
- `capability.json` is missing, unparseable, or its digest does not match.

This is the behavior `files.capability_claims_fail_closed_on_drift` asserts, and
it is the reason the phase can advertise a harness at all.

## Consent UX

The manager or client presents the gate during installation where that
lifecycle exists, otherwise on first activation, always **before** the first
observation write or network request.

```text
This skill uses Logion to send usage metadata:
resource/version, activation, completion/failure, approximate duration,
and harness type.

It does not send prompts, files, paths, tool inputs/outputs, secrets,
credentials, case content, or identity.

[Allow] [Local only] [Do not allow]
```

The copy is generated from the exact profile, not from a generic "telemetry"
label. It lists every outbound data category, the endpoint and operator, the
retention-policy link, and whether a pseudonymous installation identifier is
used. A profile whose `fields` cannot be rendered into that copy is invalid.

Consent is stored against the tuple:

```text
publisher identity
+ canonical resource identity
+ instrumentation-profile digest
+ destination endpoint/operator
+ outbound data categories
+ consent mode and scope
```

`consent.json` holds the tuple and its digest locally; the server stores only
the digest. Patch and minor resource updates may reuse consent while the tuple
and the publisher's declared compatibility policy are unchanged. Re-prompt
before the first event when the publisher changes, the endpoint changes,
categories widen, retention materially changes, or a previously local-only
profile enables network delivery. A silent profile expansion is invalid.

Denial is fail-open for the resource:

- `off`: no observation file, spool, identifier, or network request;
- `local-only`: local counters/receipts only, inspectable and deletable;
- `allow`: only the approved narrow receipt class may be uploaded;
- ratings, prose feedback, prompts, artifacts, eval inputs/results, and public
  evidence publication require their own explicit actions or policies.

Respect the strongest applicable opt-out, including Logion `off`,
`DO_NOT_TRACK`, and a supported native manager's telemetry-disable setting.
Native-manager consent never silently counts as Logion consent.

## Receipt and evidence semantics

Keep these facts separate:

1. `resource.installed`: manager completed an install.
2. `resource.activated`: a verified client lifecycle event selected or loaded
   the resource.
3. `resource.use.completed|failed|abandoned|unknown`: the client exposed a
   trustworthy terminal signal.
4. `feedback.submitted`: an agent or user intentionally supplied a report.
5. `eval.completed`: a controlled evaluator produced a separately scoped result.

Only 2 and 3 are normal-use receipts. Neither becomes a star rating, verified
review, benchmark result, safety claim, or automatic bounty recommendation by
itself.

Publisher-integrated receipts are labeled
`publisher_integrated_field_observation` and carry issuer and integration
provenance. Aggregation exposes sample size, version coverage, consent mode,
harness coverage, concentration, and known blind spots. Independent runners and
controlled evals remain separate evidence classes.

## Backend

A new domain in the private repository: `packages/api/api/publisher_receipts/`,
following `maintainer documentation: api-development-guidelines.md` (controller per use case,
schemas in the controller module, services as classes, repository for
persistence).

- Operation `submit_publisher_receipt`:
  `POST /resources/{resource_id}/versions/{version_id}/publisher-receipts`.
- Migration `0048_publisher_receipts` creates `resource_publisher_receipts`
  (`0047` is the current head; take the next free number if it moved).
  Do not overload `resource_usage_receipts`: that table has no provenance
  columns, so a publisher receipt stored there would be indistinguishable from
  a CLI-originated one, and the label this phase requires would be a lie.
  Columns beyond the 15.11 receipt shape:
  `instrumentation_profile_digest`, `distribution_digest`,
  `integration_version`, `publisher_identity`, `observation_class`,
  `consent_policy_digest`, and a unique `receipt_digest` for idempotency.
- Server-authoritative, never accepted from the request: `identity_tier`,
  `pseudonymous_subject_id`, `publisher_verified`, `consent_policy_digest`.
  The reporter runs on the user's machine, so each of these is otherwise a fact
  the publisher would be asserting about the user. The phase-integrity policy
  enforces this; a request schema that declares any of them fails the audit.
- Anonymous receipts reuse the 15.11 contract: a signed pseudonymous subject,
  verified by `resource_feedback/services/pseudonymous_subject.py`, with the
  subject id derived server-side. Do not add a second signing scheme.
- Add idempotency, rate limits, retention and deletion, endpoint abuse
  controls, aggregation thresholds, and publisher-facing health and scorecard
  projections.
- Install, activation, field outcome, feedback, and eval evidence stay distinct
  typed records. No write path from a receipt to `resource_feedback`,
  `course_reviews`, an eval result, a bounty, or a payment.

## Protocol boundary

AI Catalog remains the typed catalog/entry representation. ARD remains
pre-invocation discovery. Native formats remain responsible for install and
execution. AKTP remains the evidence and improvement overlay.

- Do not add Logion consent, hook, or receipt semantics to an AI Catalog base
  object, and do not claim ARD performs instrumentation.
- A Catalog Entry may preserve a namespaced scalar metadata reference to a
  publisher-hosted instrumentation profile only where the pinned schema and
  conformance suite accept it. The native artifact or plugin profile remains
  the runtime authority.
- Agent Skill and plugin metadata is namespaced under that format's extension
  rules. Tolerated metadata is not executed metadata.
- If an upstream manager gains a standard permission or lifecycle extension,
  prefer a fixture-backed upstream proposal over a Logion-only fork.
- Run `python3 scripts/check_protocol_specs.py` and both relevant conformance
  suites before changing catalog publication or discovery behavior.

## Improvement and bounty path

Consented receipts may reveal version-specific failure clusters, trigger a
post-use feedback request under the user's policy, populate owner-facing
scorecards and regression candidates, nominate an eval, reproduction,
documentation, adapter, or source change, and contribute to a bounty candidate
after cohort, abuse, deliverability, and acceptance-authority checks.

They never spend money, publish a bounty, assert a root cause, or claim that a
closed upstream resource can be modified automatically. Follow Phase 15.14's
operator approval and deliverable-authority boundary.

## Implementation order

Work top to bottom. Each step is verifiable before the next one starts.

1. **Profile schema.** `packages/instrumentation/` with the JSON Schema,
   fixtures (one valid, one per rejection rule), the validator, the canonical
   digest function, and `--diff`. Reuse the enums from
   `packages/cli/cli/usage/observations.py`; a grep-pinned test forbids a
   second vocabulary.
2. **Client fixtures.** Record a real payload per pinned client under
   `packages/instrumentation/fixtures/<client>/`, and pin the release range.
   Claude Code and Codex already have theirs in
   `packages/cli/tests/fixtures/hook_payloads/` — reuse those rather than
   recording a second copy. **Hermes has none**: record its skill-load event as
   `packages/instrumentation/fixtures/hermes/skill-loaded.json`, taken from a
   real Hermes session, not hand-written. That fixture is the gating artifact
   for the required Hermes leg.
3. **Reporter.** The conformance suite first, then both bindings against it:
   `report.mjs` and `report.py`, each with its subcommands, unit tests for every
   numbered behavior and every prohibition in [The reporter](#the-reporter), and
   a runtime-absent case. Neither binding may be merged while the suite has a
   case it does not cover.
4. **Generator.** `logion instrument` in
   `packages/cli/cli/commands/instrument/`: resolve the canonical
   `ResourceVersion`, emit the projection tree per target, compute digests,
   resolve the tier per client, write `capability.json`, and print the plan and
   diff under `--dry-run`. Approval-gated write, zero-write dry run. Targets:
   `agent-plugin` (Claude Code, Codex), `hermes-plugin`, `static-skill`, and
   `dsh-plugin` — the last emitting the Cordis bundle shape
   `@logionsh/dsh-plugin` already uses, at tier `explicit_report`.
5. **Backend.** The `publisher_receipts` domain, migration
   `0048_publisher_receipts`, and the SDK resource. Regenerate the OpenAPI
   contract and run `make contract-audit`.
6. **Scenario.** The proving-ground scenario below, its fixtures, its queries,
   its assertions, and the scripted integration test.
7. **Gate.** Run the scenario twice with a real driver, seal
   `artifacts/phase-gates/phase-15.11.1.json`, and record any caveat as a
   caveat rather than as a passing claim.

The gate activates as soon as *any* activation path exists, and
`packages/instrumentation/` is one of them, so **step 1 turns it red**, not
step 5. That is intended: the entry fails closed the moment the implementation
starts, and it must not be loosened to keep a branch green, which is exactly
the reward-hacked completion the check exists to reject.

The consequence is operational, and it decides how this phase is built. While
the gate is red on `main`, the pre-commit hook fails for every commit in the
repository, including work unrelated to this phase, and a permanently red gate
stops being a signal because a genuinely new failure looks identical to the
expected one. So build this phase on one integration branch: merge each step
into that branch, and merge the branch into `main` only when the scenario and
the sealed evidence make the gate green.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md) and its
scenario implementation checklist. Add
`builtin:phase_15_11_1_publisher_integrated_observation` at
`packages/agent-proving-ground/agent_proving_ground/scenarios/builtin/phase_15_11_1_publisher_integrated_observation.yaml`
with `api_adapter: local-devrig`, `driver_config` pinning
`codex: gpt-5.4-mini`, `claude-code: claude-haiku-4-5`, and
`hermes: glm-5.1` (provider `ollama-cloud`), and no
`scripted`/`mock`/`local-process` agent driver. All three are pinned in the
phase policy, and the audit fails with `PHASE_REAL_DRIVER_CONFIG_MISSING` if
the scenario omits any of them.

Three actors, isolated homes and workspaces:

- `publisher` — has the Logion CLI, owns the resource, instruments it.
- `consumer` — **no Logion CLI on PATH or in the workspace**, installs the
  projection through the real native manager against a local fixture repo.
- `hermes_consumer` — a Hermes-driven agent, also with no Logion CLI. Hermes
  must be the driver for this actor: its observer fires on a skill load inside
  a Hermes process, so no other driver can produce that event, and a leg that
  replays the payload proves nothing (the same trap 15.11's live-hook assertion
  exists to close).
- `operator` — observes API state only.

Phases:

1. **Publisher prompt:** "Instrument this exact review skill version for the
   clients Logion supports. Generate only supported projections. The end user
   must not need the Logion CLI. Show me the exact disclosure and the outbound
   fields before publishing."
2. **Consumer prompt:** "Install the publisher's plugin through the native
   manager. Allow the disclosed minimum usage metadata, use the skill once, and
   show me what Logion received."
3. **Consumer prompt (negative leg):** "Turn the telemetry off and use the
   skill again."
4. **Hermes leg (required):** `hermes_consumer` installs the `hermes-plugin`
   projection, accepts the disclosure, and uses the skill once inside Hermes.
   Assert a real activation receipt from the live plugin, and assert that no
   terminal outcome was recorded — Hermes cannot report one, and inventing one
   is the failure this leg exists to catch.
5. **Fallback leg:** install the static-skill projection in a client with no
   pinned hook. Assert normal skill use, a declared
   `publisher_observation_unsupported` capability, and zero events.
6. **Drift leg:** move the installed client's pinned marker out of range, then
   activate. Assert the capability downgrades to `unsupported` with a reason,
   and that no event is emitted.

Assertions, all required and none `optional: true`:

| Assertion | Where it lives | What it reads |
| --- | --- | --- |
| `files.instrumentation_profile_valid` | `assertions/files.py` | the generated profile validates and its digest matches |
| `files.native_projection_digest_matches` | `assertions/files.py` | the portable core inside the projection is byte-identical to the publisher's artifact |
| `files.consent_recorded_before_observation` | `assertions/files.py` | `consent.json` mtime and content precede any spool entry or request |
| `files.no_full_cli_installed` | `assertions/files.py` | no `logion` on the consumer's PATH, home, or workspace |
| `files.resource_works_when_disabled` | `assertions/files.py` | the skill's own output artifact exists in the disabled leg |
| `files.publisher_observation_unsupported_declared` | `assertions/files.py` | `capability.json` says `unsupported` with a reason, and the spool is absent |
| `files.capability_claims_fail_closed_on_drift` | `assertions/files.py` | after the drift leg the tier is `unsupported` and no new event exists |
| `files.hermes_hook_projection_observed` | `assertions/files.py` | the live Hermes plugin produced an activation event for the exact version, with no terminal outcome attached |
| `api.publisher_receipt_exact_resource_version` | `assertions/api.py` | the stored receipt names the exact version, publisher, distribution digest, profile digest, integration version |
| `api.install_not_counted_as_use` | `assertions/api.py` | install produced no activation and no terminal outcome |
| `api.private_payload_absent` | `assertions/api.py` | no excluded category appears in the stored record or the API log |
| `api.disabled_use_zero_receipts` | `assertions/api.py` | zero receipts server-side for the disabled leg, not merely a suppressed upload |
| `api.publisher_receipt_never_rates_or_funds` | `assertions/api.py` | no `resource_feedback`, `course_reviews`, eval, bounty, or ledger row resulted |
| `logs.no_500s` | existing | — |

Every one of these must also be wired for `local-devrig`: add the observed-effect
queries to `api_adapters/_queries.py` and add each assertion's token (the part
after the dot) to the enumerated set in `api_adapters/local_devrig.py`. The
phase-integrity audit fails with `PHASE_ASSERTION_MOCK_ONLY` for any required
assertion whose token is absent from that file, so a scenario that passes
locally can still fail the gate on this alone.

**Evidence to retain:** pinned client and manager versions, the plugin
manifest, profile and distribution digests, the disclosure copy, the
consent-policy digest, the redacted receipt, the disabled-leg zero-write proof,
the drift-leg capability downgrade, and the no-500 proof.

## Acceptance criteria

Each criterion names the check that proves it. `assertion:` names an assertion
this phase's gate requires in `packages/contract-audit/policy/phase-integrity.yaml`;
`test:` is a test path in either checkout. The auditor rejects a criterion with
no marker and a marker naming an assertion the gate does not require.

- [ ] `logion instrument` turns one canonical `ResourceVersion` into an Agent
      Plugins directory whose portable core is byte-identical to the
      publisher's artifact and whose recorded digests match the generated tree.
      (proof: assertion:files.native_projection_digest_matches)
- [ ] The instrumentation profile validates against its pinned schema, and one
      resource version keeps one identity across the plugin and static
      projections while distribution and integration faults stay
      distinguishable.
      (proof: assertion:files.instrumentation_profile_valid)
- [ ] A fresh user sees the exact generated disclosure and can allow, choose
      local-only, or decline before any observation state or network request
      exists.
      (proof: assertion:files.consent_recorded_before_observation)
- [ ] Accepted receipts reach the API from a machine with no Logion CLI
      installed.
      (proof: assertion:files.no_full_cli_installed)
- [ ] Declining or disabling telemetry never prevents normal resource use.
      (proof: assertion:files.resource_works_when_disabled)
- [ ] A disabled or declined projection produces zero receipts server-side,
      not merely a suppressed upload.
      (proof: assertion:api.disabled_use_zero_receipts)
- [ ] A projection with no pinned client hook, or no available reporter
      runtime, declares `publisher_observation_unsupported`, keeps the resource
      fully functional, and emits no event.
      (proof: assertion:files.publisher_observation_unsupported_declared)
- [ ] When the pinned client release or hook contract drifts from the recorded
      fixture, the capability claim fails closed to `unsupported` instead of
      falling back to inferred telemetry.
      (proof: assertion:files.capability_claims_fail_closed_on_drift)
- [ ] Hermes is a supported `hook` client: its generated stdlib-only plugin
      produces a real activation receipt from a live Hermes session, and no
      terminal outcome is ever attached to it.
      (proof: assertion:files.hermes_hook_projection_observed)
- [ ] The DeepSeek Harness projection ships as a Cordis bundle at tier
      `explicit_report`, reporting use through its `logion_*` tools without
      claiming automatic observation.
      (proof: deferred:dsh is a developer preview pinned to one exact release, so its projection is built and its live evidence is deliberately not gate-required until a release range is pinned and a payload fixture recorded)
- [ ] Every receipt names the exact `ResourceVersion` plus publisher,
      distribution digest, profile digest, and integration version.
      (proof: assertion:api.publisher_receipt_exact_resource_version)
- [ ] Install, activation, and terminal outcome stay separate facts: an install
      never becomes a use, and a missing terminal signal never becomes a
      completion.
      (proof: assertion:api.install_not_counted_as_use)
- [ ] No prompt, file content, path, tool argument, tool result, secret, or
      user identity reaches the request, the stored record, or the logs.
      (proof: assertion:api.private_payload_absent)
- [ ] A publisher receipt can inform scorecards and improvement candidates but
      cannot create a rating, a review, an eval result, bounty funding, or a
      payment.
      (proof: assertion:api.publisher_receipt_never_rates_or_funds)
- [ ] AI Catalog, ARD, native execution, and AKTP evidence semantics remain
      separate and pass the pinned protocol integrity gate.
      (proof: test:scripts/check_protocol_specs.py)

## Required tests

These are unit and integration obligations, not gate assertions. They are the
reason the gate above can be short.

- Consent: allow, local-only, deny, cancellation, non-interactive install,
  profile expansion, publisher change, endpoint change, uninstall, reinstall.
- Denial produces a byte-identical no-telemetry state, and the resource's own
  output is unchanged between the allowed and denied legs.
- Privacy canaries for prompt, file content, path, tool arguments, tool
  results, secrets, identity, and legal or customer content: none may reach
  memory serialization, spool, request, logs, or error reporting.
- Install does not fabricate activation; activation does not fabricate
  completion; a missing terminal hook yields `unknown` or no terminal receipt.
- Reporter: offline spool bound, retry and backoff, corruption recovery,
  deduplication, retention, deletion, endpoint failure, Logion outage, missing
  runtime, and a spool at its size limit.
- Exact publisher, resource, version, and distribution attribution across
  updates and across two same-named skills.
- Projection reproducibility: instrumenting the same version twice produces
  identical digests.
- Capability fixture drift downgrades the claim rather than falling back.
- Full CLI absent: a supported projection still collects the approved narrow
  receipt, and the unsupported static fallback remains functional and honest.
- Receipt ingestion cannot create ratings, evals, public evidence, bounty
  funding, or payment without the separate required action.

## Release and re-verification on completion

Sealing the gate is not the last step. The phase's central claim is that a user
with no Logion CLI gets receipts, and a run against the working tree cannot
prove that — the tree is exactly what such a user does not have. So the phase
completes against a published artifact.

1. Cut a development release with the **Release all Logion packages** workflow,
   `version: 0.2.0.dev2`, `publish_store: false`. The current line is
   `0.2.0.dev1`; the orchestrator bumps the four Python packages itself, so do
   not hand-edit `pyproject.toml`. The PEP 440 `.devN` suffix is what routes
   every Python publisher to the `testpypi` environment and
   `https://test.pypi.org/legacy/`.
2. Expect the npm wrapper to be skipped. That is deliberate: npm prerelease
   syntax is not PEP 440, so `@logionsh/cli` takes a separately planned
   release rather than a misleading shared version.
3. Install the published build in a clean environment, from TestPyPI with PyPI
   as the fallback index — TestPyPI does not mirror third-party dependencies:

   ```bash
   uv tool install \
     --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ \
     'logion-cli==0.2.0.dev2'
   ```

4. Re-run the publisher leg (`logion instrument`) with that installed CLI, then
   re-run the consumer, Hermes, fallback, and drift legs with no CLI in the
   environment at all. Every consumer-side assertion must hold against the
   published artifact, not only against the checkout.
5. Record in the phase evidence: the installed version, the TestPyPI file
   digests, and which legs ran against the published build. A development build
   does not touch `manifest-stable.json` or `manifest-latest.json` and is not a
   marketplace-attributed companion version — do not describe it as one.
6. Promote to a stable `0.2.0` only through the normal release flow, after the
   dev build has carried a full pass.

If a consumer leg passes on the checkout and fails on `0.2.0.dev2`, the phase
is not complete. That gap is the packaging bug this step exists to find, and it
is the one bug the proving ground structurally cannot see.

## Rollout and kill criteria

1. First-party publisher package, local-only by default.
2. Invite-only external publisher with one verified client.
3. Accepted narrow uploads with inspect, delete, and disable surfaces.
4. A second independently maintained publisher and a second supported client.
5. Upstream proposal for a portable install-consent and observer lifecycle,
   fixture-backed, filed against the Agent Plugins specification rather than
   against a single client.

Track consent acceptance and decline, activation-to-receipt integrity, exact
attribution, reporter errors, uninstall success, feedback conversion, and
publisher action on the resulting improvements. Never track task contents.

Narrow or stop the approach if the reporter materially affects resource
reliability, disclosures cannot be precise, exact attribution falls below the
Phase 15.11 threshold, users cannot effectively disable or delete, or
publishers do not act on the resulting evidence.

## Out of scope

Covert telemetry, universal static-Skill execution, TLS interception, prompt or
tool-payload capture, cross-resource identity tracking, a new AI Catalog or ARD
runtime contract, independent-eval claims, automatic ratings, automatic bounty
funding, mandatory Logion CLI installation, or mandatory marketplace
acquisition.
