<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Sandbox And Runtime Trust

> **2026 direction note:** begin with one isolated CPU runner on a developer
> machine or small server, then participant-supplied runners. Sandbox evidence
> is issuer-scoped, never a global “safe” verdict. Owned GPU infrastructure is
> outside the strategy.

Logion's current trust model is publication-oriented. The future trust model
should also include runtime containment.

## Current State

The current roadmap already builds strong foundations:

- `course/capabilities.yaml`
- capability persistence on course versions
- publication gates for missing/invalid capability manifests
- observed-vs-declared capability mismatch detection
- scanner findings
- human review
- buyer-safe approved capability summaries
- planned execution policy export

The current execution policy plan intentionally does **not** include:

- local sandbox implementation
- VM/container isolation
- Linux namespace isolation
- hosted execution
- secret injection runtime

That boundary is correct for MVP.

## Principle

The trust sequence should be:

```text
declaration -> review -> policy export -> enforcement -> automation -> autonomy
```

Do not allow automation or bounty-driven execution to outrun enforcement.

## Why Sandbox Matters

Agent courses and skills can influence:

- terminal commands
- filesystem reads/writes
- browser behavior
- network calls
- secrets
- user workflows
- paid actions
- production code

That makes them a supply-chain surface, not just content.

For B2B, sandboxing is not a nice-to-have. It is likely to become a buying
requirement.

## Bounty Submissions Are Untrusted

Treat bounty submissions as untrusted input.

A submitted improvement should not be:

- automatically executed by creators
- automatically installed by buyers
- automatically released to production
- treated as trusted because it came through Logion

Any accepted improvement that changes a course should become a new course
version and pass the normal publication pipeline.

## Runtime Policy

Execution policy export should become the bridge between reviewed capabilities
and runtime containment.

A policy can describe:

- allowed tools
- shell enabled/disabled
- network enabled/disabled
- allowed domains
- filesystem read paths
- filesystem write paths
- required secrets
- human approval requirements
- destructive action flags
- external write flags

Initially this is disclosure and contract. Later it becomes enforcement input.

## Local Sandbox Roadmap

### Stage 1: Policy consumption

The CLI/companion can fetch execution policy and show it before install/update.

Goals:

- make permission expansion visible
- require explicit approval for higher-risk updates
- record local install metadata
- warn when host harness cannot enforce policy

### Stage 2: Process-level guardrails

Before full VM/container isolation, add practical local guardrails where possible:

- explicit working directory
- limited environment variables
- no implicit secret forwarding
- dry-run or preview modes
- install receipts
- local policy cache
- warnings for unenforceable policy areas

This is not a full sandbox, but it reduces accidental risk.

Stages 1–2 are also where the human-facing surfaces plug in: the requires
readiness and runner doctor (now in `plans/phase-15.15-isolated-first-runner-node.md`),
the user-side policy file, and the local human dashboard. See
[Human Dashboard And User-Side Policy](human-dashboard-and-user-policy.md).
At Stage 3+ the user policy file becomes enforcement input: the runtime
receives the intersection of exported execution policy and user policy.

### Stage 3: Container or namespace sandbox

Add a real containment mode for course tests and selected execution:

- isolated filesystem mount
- explicit read/write paths
- network allowlist
- secret allowlist
- resource limits
- clean temp workspace
- artifact capture
- logs/traces

This can start as local Linux/container support before broader OS support.

### Stage 4: Hosted sandbox execution

Offer hosted sandbox runs for:

- review
- enterprise validation
- bounty submission evaluation
- eval/regression checks
- creator test runs

Hosted sandboxing should be billed/limited because it has compute cost and abuse
risk.

### Stage 5: Sandbox attestations

Once sandbox runs are deterministic enough, emit attestations:

- what policy was enforced
- what files were touched
- what domains were contacted
- which tests/evals ran
- which command produced which artifact
- whether execution stayed inside policy

These attestations can later travel with the course version.

## Harness Integration Implications

Harnesses differ in what they can enforce.

Logion should distinguish:

- policy declared
- policy reviewed
- policy exported
- policy enforceable by this harness
- policy actually enforced in this run

Do not imply enforcement where the host harness cannot provide it.

## Enterprise Requirements

For Teams/Enterprise, sandbox policy should support:

- org-level minimum sandbox mode
- org-level blocked tools
- approved domain lists
- secret forwarding policy
- required human approvals
- private reviewer approval
- audit logs for install and execution
- blocked installs when policy cannot be enforced

This is one of the strongest B2B differentiators against generic skill hubs.

## Relationship To Agent Voting And RLAF

Agent voting, RLAF, or eval-based improvement should start as review evidence,
not release authority.

Acceptable early use:

- summarize proposed improvement
- run regression checks
- compare outputs
- produce traces
- help human reviewer decide

Too risky before sandbox:

- automatic payout based on agent votes
- automatic release based on eval score
- canary rollout of unreviewed bounty submissions
- executing untrusted submissions in creator workspaces

## Product Rule

The product should consistently communicate:

```text
Logion review establishes publication trust.
Sandboxing establishes runtime containment.
Bounties establish economic coordination.
None of these replaces the others.
```
