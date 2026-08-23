<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.11 — Native-use observation, linked feedback, and reviews

> **Implementation status (2026-08-22): built, partially proven.** The usage
> spool, receipt and feedback APIs, integrations commands, harness observation
> hooks (Claude Code, Codex), Hermes lifecycle observation adapter,
> Hermes/Pi explicit-report fallback, consent enforcement, and
> consent-driven upload are implemented. The phase is **not complete**:
> the proving-ground evidence still relies on replaying a recorded
> `PostToolUse` payload into the installed hook rather than the harness
> delivering that payload live, and the remaining "Still open" items below
> are not yet closed. The existing CLI inventory scan is not proof of use and
> must not be described as observation telemetry.
>
> **Gate:** both mandatory scenarios passed with a real agent driver on
> 2026-08-17 (`claude-code`/`claude-haiku-4-5`, local-devrig) against the
> tightened scenario and projection assertion; the cross-repo audit reports
> no critical findings. The observation in that evidence comes from piping
> the harness's recorded `PostToolUse` payload into the installed hook, not
> from that hook firing live — a live hook needs a `logion` on PATH that
> carries `usage observe`.
>
> **Still open before this phase may be called complete:**
> 1. Prove a live hook end to end, with the harness itself delivering the
>    payload to an installed CLI, rather than the documented replay
>    fallback.
> 2. Published first-party artifacts: `packages/harness-plugins/` now
>    contains the observer scaffold, but no official `npx skills add`
>    companion or `npx plugins add` observer package is published on the
>    stable coordinates, so the clean-machine onboarding contract remains
>    unbuilt.
> 3. Generic self-review is only detectable for resources that project to a
>    Course, because `resources` has no owner column.
> 4. Pseudonymous signing and receipt-vs-review consent are now implemented in
>    code and covered by focused tests, but the real-agent phase evidence and
>    gate artifacts have not yet been re-recorded on top of those changes.
>
> **Dogfood — Level 2 (real use and feedback):** the implementing agent acquires a resource through any supported channel, uses it in its ordinary harness, and submits feedback through Logion linked to the exact original `ResourceVersion`.
> **After this phase:** Logion can learn from resources installed by `npx skills`, `npx plugins`, `hf`, or Logion itself without forcing a new acquisition workflow.
> **Honesty boundary:** observation means “probably used”; feedback means “an agent/user reported an outcome”; neither is a controlled evaluation or universal quality claim.

## Product thesis

This is the first compounding data loop:

```text
native install → exact inventory attribution → harness observes use
→ local pending usage → agent/user reports outcome
→ generic resource feedback → optional Course-review projection
→ aggregate demand/failure signal → funded improvement
```

The highest-value early signal is not “which resource is popular in a catalog?” It is “which exact versions people actually use, for which task classes, with what outcome and friction?”

## Mandatory dogfood prompt for the implementing agent

Run after the phase is implemented:

```text
You are implementing Phase 15.11. Prove that feedback works when Logion did not
perform the installation.

1. Search Logion for a resource relevant to this phase:
   `logion listings search --query "agent hooks privacy telemetry feedback"
   --include-indexed --limit 5 --json`.
2. Select an external Agent Skill with an exact `npx_skills` distribution and a
   published Course/Resource with a Logion bundle.
3. Ask for approval. Install the external skill directly with the exact displayed
   `npx skills add ...` command, not `logion resources acquire`.
4. Run `logion resources reconcile --from skills --scope repo-root --json`; require an
   exact resource/version match.
5. Enable Logion observation for the current harness with
   `logion integrations enable HARNESS --dry-run`, inspect the config diff, ask for
   approval, then enable it.
6. Use the externally installed skill on a bounded Phase 15.11 implementation task.
7. Run `logion usage pending --json`; verify the exact resource/version/channel.
8. Submit:
   `logion feedback submit RESOURCE_ID VERSION_ID --rating N --usefulness N
   --reliability N --tool-safety N --token-efficiency N
   --completed-task|--not-completed-task --task-class software-development
   --body "Resource-focused feedback with no repository-private data" --json`.
9. If that resource/version projects to a CourseVersion and review eligibility allows
   it, verify the response contains `course_review_projection`. Otherwise verify that
   generic feedback succeeded without fabricating a marketplace buyer review.
10. Repeat one use with observation disabled and prove zero hook spool/write/upload.
11. Save `artifacts/dogfood/phase-15.11.md` with acquisition channel, inventory record,
   hook diff, observation IDs, pending output, consent mode, feedback ID, projection
   disposition, and privacy canary result.
```

The phase fails if dogfood requires reinstalling the external skill through Logion.

## Dependencies

- The 15.9.1 harness resource scope and observation requirements carried
  forward as a contract; they are not a claim that observation shipped in
  15.9.1.
- 15.9 resource/version/projection identity.
- 15.10 local acquisition inventory and reconciliation.
- Existing CourseReview API, auto-review consent, pseudonymous/agent identity, CLI local state/redaction, and supported harness projections.

## Upstream contracts to pin before coding

- `skills` install/use/list/update semantics and lock/state format: <https://github.com/vercel-labs/skills>
- `skills` telemetry opt-out contract: <https://www.skills.sh/docs/cli>
- Vercel's plugin installation/observer precedent: <https://vercel.com/changelog/introducing-vercel-plugin-for-coding-agents> and <https://github.com/vercel/vercel-plugin>
- Hugging Face CLI and agent-skill entry surface: <https://huggingface.co/docs/huggingface_hub/en/guides/cli>
- Codex scopes: <https://developers.openai.com/codex/skills>
- Claude Code scopes: <https://code.claude.com/docs/en/slash-commands>
- Hermes skills/profiles: <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills> and <https://hermes-agent.nousresearch.com/docs/user-guide/profiles/>
- Pi skills: <https://www.mintlify.com/badlogic/pi-mono/coding-agent/skills>

Logion's consent must be independent from upstream telemetry preferences but respect the strongest local opt-out signal where reasonable (`DO_NOT_TRACK`, upstream disable flag, and Logion's own explicit `off`). Never assume upstream consent implies Logion consent.

## Separate the three signal classes

### 1. Local observation

A local, privacy-minimized hint that a harness referenced an installed resource. It is not uploaded unless consent policy permits.

### 2. Usage receipt/telemetry

A structured, rating-free statement that an attributed resource participated in a task/session. It may include coarse task class, harness, outcome known/unknown, and counters/buckets. It is opt-in, pseudonymous where allowed, and never becomes a review automatically.

### 3. Feedback/review

An intentional post-task report containing subjective rating dimensions and completed-task status. It may be agent-authored under the user's configured policy. It becomes a Course review only through explicit projection rules.

Do not collapse these tables or labels.

## Local observation architecture

```text
native manager / Logion inventory
             │ exact installed paths + resource/version
             ▼
harness hook/plugin ── minimal event ──▶ logion usage observe
                                              │
                                              ▼
                               resolve against local inventory
                                              │
                                              ▼
                     $LOGION_HOME/usage/observations.jsonl
                                              │
                           pending/session-end feedback prompt
```

Raw hook payloads, prompts, commands, file contents, paths, and tool arguments exist only in memory long enough to resolve attribution. They are not written to the spool or sent.

Every native integration writes the same versioned local envelope to the shared
Logion spool. Harness plugins and hooks never call the remote API directly: the
CLI owns attribution, consent, redaction, retry, and upload.

## Observation schema

`logion/packages/cli/cli/usage/observations.py`:

```python
@dataclass(frozen=True)
class UsageObservation:
    schema_version: Literal[1]
    observation_id: str
    observed_at: str
    harness: str
    event: Literal["resource_invoked", "resource_file_read", "resource_tool_used"]
    resource_id: str
    version_id: str
    resource_type: str
    acquisition_channel: str
    installation_id: str
    scope_kind: Literal[
        "repo-current", "repo-parent", "repo-root",
        "user", "admin", "system", "custom"
    ]
    scope_id: str
    session_hash: str | None
```

No free-text or path field is allowed. A test pins the dataclass/schema fields.
`installation_id` and `scope_id` are the opaque, profile/node-scoped HMAC
identifiers defined by 15.9.1. Observation code consumes the IDs stored in the
validated local acquisition receipt; it never recomputes them with a plain path
hash and never serializes the underlying local root/path.

Deduplicate `(session_hash, resource_id, version_id, event)` within a bounded window. Unknown/ambiguous local attribution is dropped locally with an optional debug counter; never guess.

## Integration surfaces

### First-party observer packages

Ship the same observer through native workflows:

- a Logion companion Agent Skill installable through `npx skills add <official-logion-source> --skill logion`;
- a Logion observer plugin installable through `npx plugins add <official-logion-plugin>`;
- the existing Logion CLI/companion installer;
- documented thin hooks for harnesses not supported by the plugin manager.

The official source coordinates must be filled with the actual published repository/package before implementation; placeholder coordinates cannot ship.

The skill teaches the agent to inspect `logion usage pending`, submit feedback after meaningful use, and respect user consent. The plugin/hook observes lifecycle/tool events. Neither bundles API secrets.

### Clean-machine onboarding contract

`npx skills add` installs skill files, not a trusted system binary. Do not conceal a binary installation inside skill activation.

On a machine with a supported agent and Node but no Logion CLI:

1. `npx skills add <official-logion-source> --skill logion` installs the signed/pinned Logion companion skill through the user's existing manager.
2. On first relevant activation, the skill performs a read-only `command -v logion`/version check.
3. If missing, it explains why the local CLI is required for inventory, privacy filtering, hooks, feedback, and credentials; it displays the official installer/version/checksum path and asks for approval.
4. After approval, it uses the existing official Logion installer and verifies version/checksum. It must not execute an unpinned arbitrary `curl | sh` assembled from marketplace metadata.
5. It runs `logion integrations detect`, shows the exact enablement/config diff and consent modes, then asks before enabling.
6. The user may keep only the companion skill without telemetry/feedback; no hook or upload consent is implicit.

On a machine with `npx plugins`, the official Logion plugin may bundle the thin observer/hook code supported by the plugin format, but still delegates identity, inventory resolution, consent, spool, redaction, and API writes to the verified Logion CLI. If the CLI is absent it follows the same explicit bootstrap contract.

Target one-command entry surfaces:

```bash
npx skills add OFFICIAL_LOGION_SOURCE --skill logion
npx plugins add OFFICIAL_LOGION_PLUGIN
```

These commands must appear on the landing/README with truthful qualifiers: the first installs the companion skill; the second installs the observer plugin; neither silently opts the user into upload or auto-feedback.

### Published artifact requirements

- Official source/release ownership and stable coordinates.
- Immutable release tag/commit and content digest recorded as the Logion `ResourceVersion`.
- Package map identifies companion, bootstrap references, supported harnesses, and required `logion` CLI range.
- Provenance/SBOM/checksums for plugin/npm artifacts.
- Installation fixtures for project/global, supported agents, update, uninstall, and no-CLI bootstrap.
- `npx skills update` / plugin updates preserve user consent and Logion inventory attribution.

### CLI commands

```bash
logion integrations detect [--json]
logion integrations enable HARNESS [--dry-run] [--mode prompt|auto|local-only]
logion integrations disable HARNESS
logion integrations status [--json]
logion usage observe --harness HARNESS --stdin
logion usage pending [--since 24h] [--json]
logion usage dismiss OBSERVATION_GROUP_ID
logion feedback submit RESOURCE_ID VERSION_ID ...
logion feedback list --mine [--json]
```

`usage observe`:

- exits 0 on parse/resolution/spool failure so it never breaks the harness;
- reads at most 1 MiB and finishes within two seconds;
- writes fixed-schema records only;
- with feedback/telemetry off, performs zero read/write/network work after config check;
- logs diagnostics only under explicit debug.

### Supported harness strategy

- Prefer the `npx plugins` format when the current agent supports it.
- For Claude Code/Codex/other hook-capable harnesses, marker-keyed merges install one thin hook that writes the shared local observation envelope.
- For unsupported harnesses, the companion may record explicit resource activation/use from the agent's own workflow; it must not scrape shell history.
- Configuration edits are `--dry-run`, idempotent, preserve unknown user config, and uninstall only `_logion_managed` entries.

The implementer must verify each harness's current hook schema against official documentation and commit recorded fixtures. Never trust old field names from this plan.

The release matrix is explicit:

| Harness | Repository resources | User resources | Observation path |
|---|---|---|---|
| Codex | `.agents/skills` from CWD through repository root | `~/.agents/skills` | supported extension/hook where available; otherwise explicit companion report |
| Claude Code | `.claude/skills` | `~/.claude/skills` | native plugin/hooks |
| Hermes | repository-specific `skills.external_dirs`/profile | `~/.hermes/skills` | lifecycle integration or explicit companion report |
| Pi | `.pi/skills` or `.agents/skills` from CWD through root | `~/.pi/agent/skills` or `~/.agents/skills` | extension where supported; otherwise explicit companion report |

An adapter is “supported” only after a recorded real-harness fixture and its
customer-like proving scenario pass. Directory scanning alone is inventory,
not use observation.

### Pre-existing remote and closed MCP resources

The user may install a vendor plugin or remote MCP connector through its
original marketplace/client and install the Logion companion separately.
Logion must then adapt to that native installation:

- inventory the harness's plugin-manager state and MCP configuration without
  rewriting either;
- reconcile the original publisher, public plugin/source revision, declared
  remote endpoint, manifest, and available digest to the exact
  `ResourceVersion`;
- preserve the vendor plugin, MCP server, and each local installation as
  distinct distribution/resource/installation identities;
- attribute supported harness tool-use events to the original publisher's
  resource rather than creating a Logion-owned wrapper or duplicate listing;
- exclude OAuth tokens, prompts, tool arguments/results, documents, local
  paths, and arbitrary model context from inventory and observations.

The default observation path is a consented Logion hook/plugin beside the
vendor integration. Logion does not silently proxy TLS, replace the MCP
endpoint, inject itself into OAuth, or require reinstalling the vendor
resource. After the user enables the Logion integration and selects a consent
mode, supported hooks may reconcile and spool minimal events automatically.
If a harness exposes no trustworthy local tool-use event, Logion reports
inventory-only support and may offer explicit prompt-mode feedback; it must
not infer invocation from installation, connector availability, quota changes,
or network traffic.

Normal authorized use may produce privacy-minimized observations and
intentional feedback. Active Logion-run probes/evals against a remote server
remain governed by the owner opt-in, public-test policy, terms, credentials,
and synthetic-input controls in Phase 16.11. User authorization to use a
service is not permission for Logion to benchmark or probe it independently.

## Feedback API contract

### Database

Add:

```text
resource_usage_receipts
  id UUID PK
  resource_id, resource_version_id
  reporter_agent_id / pseudonymous_subject_id
  identity_tier shadow|account|verified
  acquisition_channel
  task_class VARCHAR(64)
  harness VARCHAR(64)
  outcome completed|not_completed|unknown
  coarse counters/buckets JSONB
  consent_policy_digest
  observed_at, submitted_at
  receipt_digest UNIQUE per reporter

resource_feedback
  id UUID PK
  resource_id, resource_version_id
  reporter_agent_id / pseudonymous_subject_id
  identity_tier
  acquisition_channel
  rating SMALLINT
  usefulness, reliability, tool_safety, token_efficiency NUMERIC
  completed_task BOOLEAN
  task_class VARCHAR(64)
  body TEXT NULL
  created_at, updated_at
  source_receipt_id NULL
  UNIQUE(reporter_subject, resource_version_id, task_class)

resource_feedback_course_projections
  feedback_id UUID PK/FK
  course_review_id UUID NULL
  disposition projected|not_a_course|ineligible|self_review|paid_entitlement_missing
  created_at
```

Keep CourseReview as the marketplace-facing commercial review. Generic feedback is the source for all resource types and acquisition channels.

### API

- `POST /v1/resources/{resource_id}/versions/{version_id}/usage-receipts`
- `POST /v1/resources/{resource_id}/versions/{version_id}/feedback`
- `GET /v1/resources/{resource_id}/feedback`
- `GET /v1/resources/{resource_id}/feedback/summary`
- `GET /v1/feedback/mine`

Use `api/resource_feedback/{repositories,services,controllers,responses}/`. Projection calls the existing Course review domain service; never writes CourseReview directly.

Stable dispositions/errors:

```text
feedback_resource_version_mismatch
feedback_acquisition_not_attributed
feedback_invalid_score
feedback_body_private_data_detected
feedback_self_review_blocked
feedback_course_projection_ineligible
feedback_paid_entitlement_required
usage_receipt_consent_required
usage_receipt_duplicate
```

## Projection rules

Generic feedback projects to CourseReview only when all are true:

- exact `ResourceVersion → CourseVersion` projection exists;
- reporter is not the owner/author under existing self-review rules;
- Course/version is reviewable;
- free/open Course policy or active paid entitlement permits a marketplace review;
- feedback is intentional, not synthesized solely from passive observation;
- reporter has not already projected an equivalent feedback row.

External installation of an open resource can produce generic feedback. It does not create a paid entitlement. If the same artifact is a paid Course, the generic feedback remains visible in the resource evidence surface but is not mislabeled “verified buyer review.”

The API response explains the projection disposition.

## Identity and consent

### Pseudonymous participation

- Free resource discovery, reconciliation, local observation, and local pending usage do not require signup.
- A random local pseudonymous subject may sign/upload feedback only after explicit consent policy is stored.
- If the backend supports provisional agents, the local subject attaches later to an account without changing historical IDs.
- Identity tier is carried into aggregation; it is not a hidden multiplier.
- Money, authorship, claims, and paid entitlement stay account-gated.

### Consent modes

```text
off         no observation spool, upload, feedback prompt, or network call
local-only  local observation/pending; no upload
prompt      local observation; agent asks before each feedback submission
auto        user explicitly opted in; agent may submit one post-task feedback report
```

`auto` does not infer a rating from file reads. The agent must have task outcome context and must generate the structured report at meaningful task completion. Users can inspect, edit, delete, export, or disable.

## Agent companion behavior

At resource/task completion:

1. Read `logion usage pending --json`.
2. Match only resources actually used in the current session.
3. If `prompt`, present resource/version, channel, task class, proposed scores/body, and ask.
4. If `auto`, submit once under stored consent.
5. If task outcome is unknown or resource only read incidentally, leave pending or dismiss—do not rate.
6. Record the feedback ID/tombstone locally so repeated hooks do not create repeated reviews.

Review body contains resource-focused observations only, never prompt, repository name, code, customer data, or personal information.

## Aggregation read model

Resource feedback summary exposes:

- unique reporter count by identity tier;
- attributed use/feedback count by acquisition channel;
- completed-task rate with sample size;
- rating dimensions with sample size;
- task-class distribution under minimum-cohort privacy threshold;
- recent version coverage and confidence/limitations;
- Course-review projection counts separately.

Do not rank yet. Do not call passive receipt volume “users” without explaining pseudonymous subjects and dedup.

## Files to change

### Public repository

- `packages/cli/cli/_local_state.py` or split inventory/usage modules.
- New `packages/cli/cli/usage/`.
- New `packages/cli/cli/commands/integrations/`.
- New `packages/cli/cli/commands/feedback/`.
- Update `commands/courses/report_usage.py` to write the local reported tombstone after API success.
- Update companion `SKILL.md` usage flow; keep context addition compact.
- Add `packages/harness-plugins/` or official plugin-format package.
- Publish official Logion skill/plugin acquisition artifacts and provenance.
- Client Resource feedback APIs/types.

### Private repository

- Migration/models for receipts, feedback, projections, pseudonymous subject if not already supported.
- `api/resource_feedback/`.
- Reuse Course review validation/projection service.
- Resource feedback summary/search integration.
- Rate limits, abuse detection, deletion/export, observability.

## Required tests

- Exact path/source/digest inventory resolution; ambiguous basename/source drops.
- Hook parsers with recorded official payload fixtures for every supported harness.
- Two repositories with the same resource produce distinct installation/scope
  IDs; observation in one cannot attach to the other or to user-global state.
- Real Codex, Claude, Hermes, and Pi sessions cover native discovery plus the
  best supported observation path; unsupported event types fail locally.
- Plugin-format install/uninstall/status and marker-keyed config merges.
- `off` means byte-identical local state and zero network; `local-only` means zero upload.
- Raw prompt, command, path, repo, env, secret, and tool payload canaries never reach spool/request/log.
- Concurrent append, torn line, rotation, dedup, unknown schema, clock skew.
- Pending grouping/tombstone/dismiss and one-shot semantics.
- Generic feedback for Logion bundle, direct `npx skills`, `npx plugins`, and `hf` acquisition records.
- Pre-existing vendor plugin plus OAuth remote MCP reconciliation: exact
  publisher/resource/version attribution when evidence supports it, no
  reinstall/reconfiguration/proxy, and typed inventory-only behavior when the
  harness exposes no trustworthy tool-use hook.
- Course projection happy/free, no Course, paid entitlement missing, self-review, duplicate upsert.
- Pseudonymous/account attach and identity-tier aggregation.
- Sybil/rate-limit and minimum-cohort privacy fixtures.
- End-to-end direct native install → reconcile → observe → pending → feedback → projection disposition.

## Rollout

1. Local-only observation on Logion's own development harnesses.
2. Prompt-mode generic feedback from the team.
3. Published Logion companion skill and observer plugin.
4. Invite-only external prompt-mode beta.
5. Pseudonymous upload after privacy/abuse review.
6. Auto mode only for users who explicitly enable it.

Metrics: integration enabled/disabled, attribution exact/ambiguous/dropped, pending/feedback conversion, channel, identity tier, projection disposition, failure code, deletion/opt-out. Never include paths/prompts/task contents.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:native_use_observation_and_feedback`.

- **Actors/fixture:** two fresh agent processes have isolated homes and work in
  repositories `xpto` and `acme`; an `operator` observes API state. The seed creates a real
  `npx skills`-compatible review helper, and the first session installs the
  official Logion integration with its documented customer command.
- **First prompt:** “Install the indexed review helper for this repository only
  and use it to review repository xpto. Keep telemetry at the default privacy
  mode. Do not install it globally.”
- **Second prompt:** “Continue my work. Show feedback Logion queued from
  capabilities I actually used, let me inspect exactly what would be sent, and
  submit an honest review linked to the original resource.”
- **Assertions to implement:** `files.native_use_observed`,
  `files.feedback_pending`, `api.resource_feedback_exists`,
  `api.feedback_linked_to_acquisition`,
  `api.course_review_projection_exists`,
  `api.raw_observation_not_uploaded`, and
  `api.feedback_submission_idempotent`; also assert no observation from `xpto`
  attaches to the same resource installed in `acme`.
- **Consent/evidence:** session one uploads no prompts, repository content, or
  raw events. Retain integration version, observation/pending receipt IDs,
  consent mode, feedback ID, source link, redacted payload, and no-500 proof.

Add `builtin:remote_private_mcp_feedback`:

- **Fixture:** a public vendor plugin manifest points to an OAuth-protected
  remote MCP fixture whose implementation and data are unavailable to Logion.
  The vendor connector is installed first through the native manager; the
  Logion companion is installed and enabled separately.
- **Prompt:** “Use the already-installed vendor connector for this task. Let
  Logion attribute its use to the original vendor resource without reinstalling
  it, changing its endpoint, or recording the request or response.”
- **Assertions to implement:** `files.remote_mcp_reconciled`,
  `files.vendor_install_unchanged`, `files.no_mcp_proxy_installed`,
  `api.remote_mcp_use_attributed`, `api.original_publisher_preserved`,
  `api.remote_mcp_feedback_linked`, and
  `api.remote_mcp_private_payload_not_recorded`. Run the same fixture in a
  harness without tool-use hooks and require an explicit
  `inventory_only_observation_unsupported` result with no fabricated event.
- **Evidence:** retain public manifest/source/endpoint/version digests, local
  installation and observation IDs, consent mode, redacted feedback ID, and
  before/after hashes proving that vendor configuration was not rewritten.

## Acceptance criteria

- [ ] A skill installed directly by `npx skills add` can be observed and receive feedback linked to the exact Logion `ResourceVersion` without reinstalling through Logion.
- [ ] A Logion-hosted Course, Vercel plugin, and HF revision use the same generic feedback contract.
- [ ] A pre-existing vendor plugin backed by a closed OAuth remote MCP server
      can be reconciled and, where the harness exposes a trustworthy hook,
      observed through a separately installed Logion companion without proxying,
      reinstalling, or claiming ownership of the original resource.
- [ ] Passive observation never creates a rating or CourseReview.
- [ ] Eligible feedback projects through the existing Course review service; ineligible feedback remains useful and clearly labeled.
- [ ] `off` produces no local observation state and no network request.
- [ ] The official Logion skill/plugin integrates feedback into a user's existing agent workflow.
- [ ] Codex, Claude, Hermes, and Pi have tested native scope discovery and a
      declared observation path or an honest explicit-report fallback.
- [ ] From a clean machine, `npx skills add OFFICIAL_LOGION_SOURCE --skill logion` installs the companion; first use can install/verify the CLI with explicit approval and then preview/enable a harness integration.
- [ ] `npx plugins add OFFICIAL_LOGION_PLUGIN` installs the observer integration without duplicating identity, inventory, spool, redaction, or API-write logic.
- [ ] Neither native install command silently opts the user into observation upload or automatic feedback.
- [ ] Dogfood submits a real feedback record for an externally installed resource and records the Course projection disposition.

## Out of scope

ARD discovery (15.12), signed scanner evidence (15.13), sponsorship selection (15.14), isolated execution (15.15), controlled evals, universal reputation, covert telemetry, or automatic funding.
