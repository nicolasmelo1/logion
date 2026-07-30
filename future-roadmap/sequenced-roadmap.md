<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Sequenced future roadmap

This is the authoritative ordering for future work. Detailed contracts live in
`plans/`. Do not implement a future-roadmap item merely because it appears here.

## North star

Build the smallest useful node that observes real resource use, converts
privacy-controlled outcomes into actionable improvements, and can have its
claims independently reproduced.

The sequence is deliberately network-shaped without requiring a network on day
one. Logion operates the first node and dogfoods every role until independent
operators arrive, just as a marketplace founder manually supplies the first
side of a market.

## Stage 0 — preserve the existing product

The delivered 15.1–15.9 foundation remains valuable:

- account and GitHub identity;
- publishing and immutable Course versions;
- PR-based bounty delivery;
- third-party skill indexing;
- observation scans and discovery tiers;
- platform-funded bounties with explicit approval and ledger invariants;
- generic typed resource identity, filtered resource reads, native-scope
  inventory, and truthful blocked acquisition planning.

Do not big-bang rename Course/skill surfaces. `Resource` is the generic identity
underneath them. Existing APIs and CLI commands remain compatibility
projections.

## Cross-cutting checkpoint — converge before integrating ASM

As soon as the public planning mirror can link the decision, approach ASM
creator Yi Guo using
[`plans/asm-logion-collaboration-and-protocol-convergence-gate.md`](../plans/asm-logion-collaboration-and-protocol-convergence-gate.md).
This exploratory contact happens before Phase 15.12 design freeze; it does not
wait for an adapter and does not claim a partnership.

After Phase 15.11 supplies real identity, consent, usage-receipt, and feedback
artifacts, decide with Yi whether ASM owns the shared selection descriptor and
invocation/cost receipt, whether only primitives are shared, or whether the
projects remain independent. Phase 15.17 and Phase 16.7 cannot freeze competing
wire contracts while that decision is unresolved.

See [ASM collaboration and protocol convergence](asm-collaboration-and-protocol-convergence.md).

## Stage 1 — make native use observable and useful

The planning mirror, generic resource identity/backfill, and the shipped subset
of harness-native scope semantics are now foundation rather than future phases;
their former 15.8.1, 15.9, and 15.9.1 plan files are retired by the canonical
mirror. Stage 1 implementation resumes at Phase 15.10 and runs through 15.14.
The unimplemented HMAC identity, acquisition, reconciliation verifier, and
harness-integrated observation contracts remain normative carry-over in
`plans/next-steps.md` and are owned by 15.10/15.11.

### 1. Generic resource identity

Represent skills, plugins, MCP servers, models, and hosted Courses with stable
canonical source identity plus immutable versions. Backfill existing listings
and Courses without breaking their public behavior.

Success is identity/reconciliation accuracy, not number of imported listings.

### 2. Real acquisition and inventory

Support two paths:

- Logion-hosted bundles where Logion really owns delivery and entitlement;
- delegated native acquisition through `npx skills`, `npx plugins`, `hf`, or
  another explicitly supported manager.

Reconcile both into one local inventory. Never fuzzy-link an installation to a
resource merely because names look similar.

Inside a repository, install to that repository's native harness scope by
default. Codex/Claude/Hermes/Pi adapters must preserve their real discovery
paths and precedence instead of mapping everything to a fake global/project
binary.

### 3. Workflow-native observation and feedback

Ship a Logion skill/plugin that users can add to their existing workflow.
Detect attributed use locally, queue feedback, show the exact outbound payload,
and submit only with the selected consent mode. Link the feedback to acquisition
and immutable resource version. Project eligible hosted Course feedback into
the existing review domain.

This is the highest-priority data loop. Without it, funding decisions remain
catalog speculation.

### 4. AI Catalog publication and ARD interoperability

Publish Logion's own conformant
[AI Catalog](https://ai-catalog.io/), self-crawl it, and ingest approved
catalogs directly. Separately expose/query
[ARD](https://agenticresourcediscovery.org/) discovery over the same entries.
AI Catalog defines the typed/nestable catalog representation; ARD defines
pre-invocation discovery/registry behavior. Neither establishes evidence
authority.

Bootstrap actual discovery by synchronizing the official
[`ard-connectors` Agent Finder directory](https://github.com/ards-project/ard-connectors/blob/main/agent-finders.json)
into the server-side indexer. Query enabled Agent Finders on bounded schedules;
do not install those connectors or finder preferences into customer clients.

Phase 15.12 remains artifact-agnostic. It may preserve an unknown ASM media type
or namespaced metadata under the pinned upstream rules, but it adds no
ASM-specific production contract until the collaboration ownership matrix is
written. One generic external fixture is enough to prove preservation.

### 5. Feedback-driven work

Cluster repeated attributed failures and let an operator draft a platform
bounty. Draft, approval, publication, funding, acceptance, and payout stay
separate. No opaque model automatically spends money.

Free contributions remain first-class: a node may accept an improvement PR or
submission and record evidence/lineage without creating escrow or payout.
Funding is one optional coordination mechanism, not the definition of the
improvement network. See
[`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md).

### Stage 1 exit

A real user or agent can acquire a resource through the workflow it already
uses, Logion can attribute actual use without raw prompt upload, the user can
submit linked feedback, and an operator can turn a qualified recurring problem
into an auditable funded improvement.

Kill or narrow the strategy if attribution is unreliable, users will not enable
the integration, or feedback is too sparse/noisy to improve decisions.

## Stage 2 — prove one node end to end

Covered by Phase 15.15–15.17.

### 1. Isolated first runner

Run bounded CPU work on a developer machine or one small separate server. Sign
receipts binding resource, environment, inputs, outputs, assertions, and
limitations. Do not buy a GPU fleet.

Phase 15.14.1 starts with the founder's existing host Hermes plus isolated
Docker/Podman role agents on one MacBook. This closes the operational loop
cheaply while remaining explicitly first-party.

### 2. First-party dogfood program

Logion supplies initial demand and operations:

- uses indexed third-party resources in real development tasks;
- records honest failures/inconclusive outcomes;
- funds a small number of observed improvements;
- runs bounded verification;
- publishes first-party evidence with explicit issuer labels.

This is legitimate bootstrap only while the metrics distinguish founder,
first-party, subsidized, and independent activity.

### 3. AKTP evidence/improvement feed

Publish signed, append-only evidence and improvement events linked to ARD
resource IDs. Keep raw observations, private feedback, paths, prompts, and user
identity off the public feed.

AKTP does not duplicate an ASM/native invocation or cost receipt. It references
the original signed object by subject, issuer, media type, and digest. If the
ASM collaboration has not resolved receipt ownership, AKTP v0 excludes those
receipt semantics and ships only the non-overlapping public
evidence/improvement stream.

### Stage 2 exit

The entire acquire → use → feedback → fund → improve → rerun lineage exists for
at least one real resource and can be audited through public surfaces. Claims
say “Logion observed” rather than “the network proved”.

## Stage 3 — add independent verification

Covered by Phase 16.

Order:

1. portable eval contract and local reference runner;
2. typed evaluators, starting with skills;
3. runner registry and participant-supplied compute;
4. deterministic replication by distinct runners;
5. signed eval attestations and local authority policy;
6. benchmark-backed bounty acceptance;
7. issuer-aware evidence search/ranking;
8. privacy-safe aggregate field evidence;
9. reconciliation of benchmark and field outcomes;
10. clean external-runner onboarding/conformance;
11. MCP metadata and safe probes;
12. Hugging Face metadata plus tiny constrained evaluation.

Phase 16.7 applies replaceable local policy to evidence and declared selection
inputs. It does not create a second universal service-value manifest or global
score. If collaboration converges, the agreed pinned ASM selector is one public
reference profile; if not, Logion keeps the boundary generic and makes no ASM
compatibility claim.

The coordinator schedules work; it does not promise compute it does not own.
Model weights remain at their native host/cache unless a bounded evaluation has
an explicit size, license, runner, and sponsor policy.

### Stage 3 exit

An independently operated runner reproduces a bounded claim, disagreement is
represented honestly, and one node-local bounty is settled against verifiable
evidence.

Do not proceed to broad federation if “independent runner” still means another
process controlled by the founder.

## Stage 4 — open ecosystem and production hardening

Covered by Phase 17.

- Keep AI Catalog, ARD, and AKTP codecs and executable conformance public.
- Publish an ASM–Logion conformance/ownership report only if both projects
  approved the wording; contribute shared fixes upstream rather than forking.
- Propose missing attestation/evidence affordances upstream with fixtures rather
  than forking discovery semantics casually.
- Federate independently administered nodes with distinct issuer policy.
- Let owners claim already indexed resources without erasing pre-claim history.
- Support private nodes and selective disclosure.
- Enforce a machine-readable trust-invariant manifest.
- Keep landing/docs claims generated from a capability registry and reproduced
  by a clean customer-like proving-ground scenario.

### Stage 4 exit

Two independent nodes exchange and verify allowed evidence, keep different
authority policies, survive partition/key rotation, and complete one improvement
workflow without a central truth dependency.

## Stage 5 — measure real network liquidity

Covered by Phase 18.

Only now optimize for:

- independent sponsors discovering and funding work;
- independent contributors/runners discovering and completing it;
- repeated resource-owner participation;
- time from attributed problem to verified improvement;
- follow-on use outcomes after the improvement;
- node operation without founder credentials/intervention.

Exclude founder-controlled, self-dealing, circular, duplicate-identity, and
unlabeled subsidized activity from independent-liquidity metrics.

The proving-ground scenario validates mechanics and exclusions. It cannot
simulate the required months of real independent production behavior.

## Permanent testing gate

Every active implementation phase from 15.10 onward must add and pass its named
builtin scenario under `logion/packages/agent-proving-ground`. Retiring the old
15.9/15.9.1 files does not waive any carry-over gate now owned by 15.10/15.11.

Required properties:

- locally running real API via `local-devrig`;
- GPT-5.4-mini by default or Claude Haiku as the cheap real-model substitute;
- fresh role-scoped workspaces;
- customer goal prompt instead of hidden API instructions;
- public CLI/integration/native-manager path;
- deterministic observed-effect assertions;
- redacted retained evidence;
- negative/idempotency path;
- no required unsupported assertion.

See [the normative gate](../plans/agent-proving-ground-phase-gate.md).

## Explicitly deferred

These require new observed demand and a fresh decision document:

- owned GPU capacity or training marketplace;
- arbitrary model hosting/mirroring;
- custom universal package manager;
- custom Merkle/chunk network;
- metered capability payments or streaming settlement;
- generic automatic skill composition/router;
- tokens, blockchain, global reputation, or global consensus;
- automatic bounty spending driven only by telemetry or an LLM.

## Review cadence and kill discipline

At each stage, review:

- unique attributed active users/agents;
- exact vs ambiguous attribution;
- feedback consent and completion;
- percentage of funded work tied to observed use;
- time/cost per verified loop;
- independent operator/sponsor/contributor share;
- repeat use and outcome after an improvement;
- proving-ground pass rate and failure taxonomy.

Pause the next infrastructure stage when the prior customer loop is not growing.
Fix adoption, integration, privacy, or usefulness first. A more elaborate
protocol cannot manufacture missing use.
