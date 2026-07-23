<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Agent proving-ground and customer fidelity

## Purpose

The proving ground is Logion's executable customer. It answers a harder
question than “does the endpoint return 200?”:

> Can a cheap general-purpose agent, given a realistic customer goal and public
> product access, successfully use this feature end to end?

If not, the phase is unfinished even when conventional tests pass.

## Test pyramid

Every phase keeps all four layers:

1. unit tests for canonicalization, policy, state machines, and failures;
2. integration tests for API/database/CLI boundaries;
3. scripted proving-ground runs for deterministic scenario orchestration;
4. real-agent proving-ground runs against the local API.

The fourth layer is the completion gate. It uses GPT-5.4-mini by default or
Claude Haiku when the former provider is unavailable.

## Scenario fidelity

A good scenario:

- starts with the same public docs/integration/CLI a customer sees;
- supplies a goal, constraints, and realistic fixture;
- makes the agent discover commands and returned IDs;
- uses real role-scoped auth and a clean workspace;
- drives native tools when the product delegates to them;
- measures API/file/crypto/sandbox outcomes independently of agent prose;
- includes a denial, retry, or idempotency case;
- records enough redacted artifacts to diagnose failure.

A bad scenario gives the model private endpoint names, database IDs, a command
transcript to imitate, or a test-only helper that completes the product action.

## Cheap-model principle

The target is not to prove that an expensive frontier model can brute-force a
confusing product. A cheap model exposes missing affordances:

- unclear help and onboarding;
- hidden state or identifiers;
- non-actionable errors;
- excessive multi-step ceremony;
- brittle integration assumptions;
- permission and consent ambiguity.

Prompts may be improved when they become more customer-realistic. They must not
be tuned into implementation scripts. When a cheap agent repeatedly fails, fix
the product surface before blaming the model.

## Local API and external boundaries

The Logion API runs through `local-devrig` so tests are reproducible and do not
mutate production. External ecosystems use the most faithful bounded fixture:

- real `npx skills`/`npx plugins` against local fixture repositories;
- real `hf` command boundary with pinned small/recorded Hub fixtures;
- real MCP protocol server fixtures;
- separate local databases/keys for multi-node tests;
- real sandbox boundary with harmless adversarial canaries.

Mocks are permitted below these customer-visible boundaries, not in place of the
boundary being tested.

## Evidence and regression use

Each successful run retains scenario/model/version, prompts, redacted
transcripts, timeline, observed assertions, fixture digests, API/log snapshots,
cost, and elapsed time.

When a production bug occurs:

1. minimize it into a safe fixture;
2. add it to the owning phase scenario or a named regression scenario;
3. reproduce failure with a cheap real model;
4. fix the product;
5. require two clean passes if the failure was flaky.

## Relationship to protocol proof

The proving ground also demonstrates each protocol layer independently rather
than treating “ARD/AKTP” as one Logion-owned format. Protocol phases must test:

- AI Catalog publication and consumption with a clean external consumer;
- ARD discovery that returns valid AI Catalog entries, including a conformant
  local Agent Finder and bounded fixtures derived from the official
  `ard-connectors/agent-finders.json` directory;
- optional AKTP evidence with a consumer that understands no Logion internals;
- independent issuer policies, signature failures, replay/idempotency, and
  disclosure boundaries.

Passing Logion's own codec round trip alone is insufficient. Live queries to
third-party Agent Finders are staging smoke tests, not deterministic phase
gates.

The normative implementation checklist and commands are in
[the mandatory phase gate](../plans/agent-proving-ground-phase-gate.md).
