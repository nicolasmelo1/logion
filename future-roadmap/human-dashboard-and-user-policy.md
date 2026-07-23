<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Human Dashboard And User-Side Policy

> **2026 direction note:** this surface governs generic resource inventory,
> observation consent, feedback disclosure, issuer trust, acquisition policy,
> and node activity. Course-only language is a compatibility example.

Logion's CLI surface today is agent-first (companion-safe envelopes, compact
JSON, recall). This document plans the complementary human-first surface: a
local dashboard for configuring what agents get when they use Logion courses,
and the user-side policy file that backs it.

Neither ships in `logion` 0.2.0. The readiness and enforcement seed now lives
in [`plans/phase-15.15-isolated-first-runner-node.md`](../plans/phase-15.15-isolated-first-runner-node.md)
(runner doctor, project-scoped resolution, and sandbox enforcement).
Native inventory plus `off|local-only|prompt|auto` feedback consent lands earlier
in [`plans/phase-15.10`](../plans/phase-15.10-native-acquisition-artifact-delivery-and-inventory.md)
and [`plans/phase-15.11`](../plans/phase-15.11-native-use-observation-linked-feedback-and-reviews.md);
the dashboard must configure those existing policies rather than inventing a second
telemetry preference.

## The Three Policy Artifacts

The trust model needs three declarative artifacts, two of which already exist
or are planned:

```text
1. capabilities.yaml            what the CREATOR declares the course needs
                                (shipped; runtime.requires, tools, secrets, ...)
2. execution policy export      the REVIEWED projection of that declaration
                                (planned; phase 16.2)
3. user policy                  what the USER grants on their machine
                                (this document; does not exist yet)
```

Artifact 3 is the missing piece. Without it, "configure what the agent has
access to" has no user-owned source of truth — only creator declarations and
platform review.

## User Policy File (The "Logionfile", Reframed)

The original idea was a Dockerfile-like `Logionfile`. The intent is right; the
metaphor is wrong. A Dockerfile is an imperative build recipe. What the user
needs to express is declarative: "on this machine / in this project, agents
may use these env vars, these runtimes, these paths, these domains."

So the artifact is a declarative, schema-versioned policy file — closer to
`devcontainer.json` or the phase 16.2 policy shape than to a Dockerfile.
Imperative provisioning stays where it already lives: `runtime.install` in
`capabilities.yaml`, disclosure-only, never auto-run.

### Location and layering

The file reuses the phase 15.10 layered-home resolution exactly:

```text
~/.logion/policy.yaml                 global user policy
<project>/.logion/policy.yaml         project policy, shadows global
LOGION_HOME set                       single-home mode, single policy
```

No new root-level file competing with `.logion/`. Project shadows root by
key, same semantics as layered recall/installs.

### Shape (directional)

```yaml
policy_version: 1
env:
  # references + grant scope only — NEVER values (see Secrets below)
  - name: OPENAI_API_KEY
    grant: all            # all | per-course list | none
  - name: DATABASE_URL
    grant:
      courses: ["course-id-a"]
runtimes:
  allow: [python3, node, uv]
network:
  allow_domains: ["api.openai.com"]
filesystem:
  write: ["workspace/output"]
defaults:
  human_approval_required: true
```

### Secrets rule

The policy file stores **references and grant decisions, never secret
values**. Readiness/doctor surfaces report env vars as `set` / `unset` only.
If Logion ever stores values, that is a separate, explicit decision (OS
keychain, not plaintext) — not a v1 concern. This keeps the CLI out of the
secret-store business and preserves the existing "no implicit secret
forwarding" principle.

### Enforcement semantics over time

The file's meaning upgrades with the sandbox stages in
[Sandbox And Runtime Trust](sandbox-and-runtime-trust.md):

```text
Stage 1-2 (disclosure/guardrails):  policy is compared and displayed —
                                    "course requires X; your policy grants/does
                                    not grant X" — nothing is enforced
Stage 3+ (real sandbox):            runtime receives the INTERSECTION of
                                    exported execution policy ∩ user policy
```

Until a runner exists, never imply the file constrains anything at runtime.

## Human Dashboard

A local web UI served by the CLI, in the spirit of tools like
[executor](https://github.com/UsefulSoftwareCo/executor) (local service +
governance UI). It is the general **human console** for Logion: everything a
person consults or decides — while agents keep using the CLI/companion
surface. It composes existing CLI/SDK data paths; it is not a second product
with its own backend.

### Command surface

Proposed entrypoint:

```text
logion human dashboard
```

`human` is the namespace for surfaces meant for people, not agents. Two
mechanisms make that real (naming alone is social, not technical):

- dashboard refuses to start in non-TTY/CI sessions (same detection as
  `_first_run.py`);
- nothing under `human` is ever listed in the companion-safe command surface
  in `maintainer documentation: cli-structure.md`.

Fallback option if a whole namespace feels heavy when implementation starts:
plain `logion dashboard` with the same two guards. Decide when building;
the guards matter more than the name.

### Scope

Buyer/user side:

- installed skills, global and project scope side by side, with shadowing
  shown (15.10 provenance data);
- per-skill view: version, description, and the `runtime.requires` readiness
  split into **Configured** vs **Pending** (the 15.11 doctor data, rendered);
- credits balance, recent ledger, and top-ups (existing `credits top-up`
  flow — the mutation is the same API call the CLI already makes);
- available updates with permission-expansion diffs (new tools, shell,
  network, domains, secrets) before the user accepts;
- open bounties on installed skills ("this skill you use has 2 open
  bounties");
- edit the user policy file (grants for env references, runtimes, domains);
- profile editing (identity data the API already exposes);
- connected agents/harnesses: which harnesses have companion copies and
  skill dirs wired (`agent_copies.json` + `_harness/` adapter data), add or
  remove one.

Creator side:

- published courses/skills and their versions, review status, and feedback;
- bounties on published skills: see open ones, open/fund new ones;
- edit `course/capabilities.yaml` for a local bundle with inline validation
  (`courses capabilities validate` rendered as a form/editor).

Every section maps to an existing CLI command or SDK call — the dashboard is
a viewer/editor over the same envelopes, and the user policy file remains the
source of truth for grants. All open source: someone who dislikes the UI
edits the YAML / uses the CLI directly, or builds another UI on the same
files and envelopes. No forking required.

### Delivery order within the dashboard

Ship read views first (skills, readiness, credits, bounty visibility), then
file editors (user policy, `capabilities.yaml`), then API mutations
(top-ups, bounty creation, profile) — mutations reuse existing confirmation
semantics from the CLI (`_confirm.py`) so the dashboard never becomes a
softer path around guarded flows.

### Explicitly not in v1

- storing secret values;
- executing install commands from the UI;
- any claim of runtime containment;
- hosted/multi-user dashboard.

## Sequencing

```text
now (0.2.0 train):   phase 15.11 — requires readiness at install/inspect/doctor
after 15.10 lands:   user policy file skeleton (layered resolution reuse)
after 16.2 lands:    dashboard v1 — readiness + policy + exported policy view
sandbox stage 3+:    policy file becomes enforcement input (intersection rule)
```

## Do

- Keep the policy file declarative and schema-versioned.
- Reuse 15.10 home resolution for policy location and shadowing.
- Keep secret values out of Logion state; references and set/unset only.
- Keep the dashboard a viewer/editor over files and existing CLI data paths.
- Keep human surfaces out of the companion-safe list and out of non-TTY runs.

## Don't

- Don't build an imperative Logionfile; provisioning stays disclosure-only.
- Don't imply the policy file or dashboard enforce anything before Stage 3.
- Don't block 0.2.0 on any of this — only 15.11 rides that train.
- Don't invent a second config root outside `.logion/`.
