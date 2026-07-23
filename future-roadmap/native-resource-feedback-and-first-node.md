<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Native resource feedback and first-node strategy

## Why this is the product

Logion does not need to win installation. Existing tools already install
skills, plugins, MCP integrations, and models. It needs to make the resulting
resource use attributable, inspectable, improvable, and economically actionable.

The product is a workflow integration plus a network node:

```text
catalog/index
  → native or hosted acquisition
  → local inventory and exact reconciliation
  → attributed use
  → consented feedback
  → portable evidence
  → improvement funding
  → reproduction and outcome history
```

The CLI/API remain useful, but the primary adoption surface is the official
Logion skill/plugin installed into a workflow the customer already uses.

Two loops must remain complete:

1. Logion installs an indexed resource into the chosen harness's exact
   repository/user/admin scope and a fresh harness session discovers it.
2. Logion recognizes a resource installed outside Logion, observes attributed
   use through the harness integration, and submits consented feedback linked
   to the original immutable version.

Repository scope is the default inside a Git repository; user-global fallback
must be explicit.

## The first node

Logion itself supplies the initial node and market operations:

- index public resource metadata;
- distribute only the artifacts it actually hosts;
- delegate to native managers for everything else;
- use indexed resources in real Logion development;
- capture honest feedback through the same customer integration;
- run bounded CPU scans/evals;
- fund small improvements with explicit approval;
- publish issuer-labeled evidence and outcomes.

This is not pretending to be decentralized. It is bootstrap. Every public claim
must distinguish first-party, subsidized, and independently reproduced results.

## Data advantage

The useful dataset is not raw surveillance. It is a privacy-controlled graph:

```text
canonical resource/version
  ← acquisition receipt
  ← attributed local use
  ← explicit feedback/outcome
  → failure cluster
  → funded improvement
  → candidate version
  → reproducible evidence
  → later field outcome
```

Store the minimum needed at each edge. Raw prompts, repository contents, paths,
secrets, and passive event streams stay local unless a separate explicit
customer action discloses a bounded artifact.

## Distribution strategy

Meet users where they are:

- `npx skills add` installs a Logion companion skill;
- `npx plugins add` installs the observer/integration plugin where supported;
- the companion installs/verifies the CLI only with approval;
- `hf` remains responsible for Hub downloads;
- Logion's CLI provides search, reconciliation, inventory, evidence, feedback,
  and node/operator flows.

Do not force customers to reinstall a native resource through Logion merely to
attribute it. Reconcile exact canonical source, revision, and digest.

## Defensibility tests

The strategy becomes defensible only if:

- integrations remain installed and used;
- exact attribution materially exceeds ambiguous attribution;
- feedback predicts worthwhile improvements;
- resource owners accept and act on the resulting work;
- reproduced outcome history changes buyer/operator decisions;
- independent parties join because existing activity is valuable.

A large scraped catalog alone fails this test. So does a beautiful protocol
with no recurring use.

## Capital constraints

The first node must fit:

- one developer machine and/or small CPU server;
- bounded API spend on cheap agents;
- content-addressed evidence artifacts, not mirrored public ecosystems;
- participant-supplied compute for later specialized jobs;
- sponsor-funded budget for exceptional expensive evaluation.

On day one this can be the founder's MacBook: host Hermes operates isolated
consumer, evaluator, contributor, sponsor, and auditor containers. Distinct
containers provide role/state isolation but remain labeled one first-party
operator until an external party joins.

If a proposed feature requires owned accelerator inventory to demonstrate basic
value, it is outside the current product thesis.

## Required proof loop

Every capability in this strategy must be exercised by a customer-like prompt
in the agent proving ground, against a locally running API, using GPT-5.4-mini
or Claude Haiku. This ensures the docs, integration, CLI, API, permissions, and
state transitions work as one product rather than isolated endpoints.
