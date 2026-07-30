<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Logion — Next Steps

We plan in cycles, but the post-15.8 architecture now has one strict dependency spine:

`public planning + protocol-convergence outreach → generic resources → native scope contract → acquisition/use feedback → publisher-integrated consented observation → AI Catalog publication + ARD discovery → portable evidence → local multi-agent node → independent verification → improvement liquidity`.

Each `phase-*.md` is an implementation contract. A subphase should fit one focused PR or one explicit operator rollout; umbrellas define gates, not parallel implementation tickets.

## Current release cycle

1. [`cycle-0-contract-e2e-hardening.md`](cycle-0-contract-e2e-hardening.md)
   is the immediate gate: repair API/public-contract drift, enforce additive
   `/v1` compatibility, and prove supported CLI/API pairs.
2. `cycles/cycle-1-to-release.md` ships the
   MVP after Cycle 0 is green. Phases 13.x and 14.x still gate first users.

The additional focused plans
[`cli-api-compatibility-matrix.md`](cli-api-compatibility-matrix.md) and
[`indexer-run-progress-observability.md`](indexer-run-progress-observability.md)
belong to those current hardening/release cycles; they do not alter the strict
post-15.8 product sequence below.

## Completed foundation for the new direction

The delivered slices through the former 15.9.1 plan have been consolidated and
their old plan files retired; the shipped shape is documented in maintainer
documentation
(`api.md`, `database-schema.md`, `cli-structure.md`,
`review-and-trust-pipeline.md`, `marketplace-economy.md`,
`repository-structure.md`, `agent-proving-ground.md`). That foundation
provides GitHub identity and the sign-in→install handoff, package maps and
repo source links, the bounty PR bot and merge policy, external skill
indexing, indexed-listing observation scanning with honest discovery tiers,
platform-funded bounties on ownerless listings, the generic resource identity
layer, and the
harness scope vocabulary, read-only inventory, blocked dry-run planning, and
local observation envelope library. This retirement does **not** claim that
native acquisition, harness-integrated observation, HMAC local identity, or
feedback shipped.

Phase 15.8 was the pivot point: Logion can sponsor improvements on ownerless
indexed resources before network liquidity exists.

Known carry-overs from that range, tracked here rather than in a retired plan:

- there is no `versions/from-source` materialization endpoint or
  `publish-from-repo` command — repo publishing stops at the source link;
- the platform-bounty admin lane is API-only (no SDK resource, no
  `logion admin bounties` CLI subgroup);
- `cli/_observation.py` ships the local observation envelope/spool writer as a
  library with no production command wired to it; no harness hook/plugin,
  automatic spool write, upload, or feedback submission is shipped;
- `resources acquire` is a blocked, zero-write plan only. Current resource
  versions expose no usable distribution URL, permissions remain unresolved,
  and `--no-dry-run` returns `logion.error`; real acquisition is owned by 15.10;
- the retired scope plan's normative `scope_id`/`installation_id` HMAC and
  cryptographic publisher-signature verification are not implemented. Their
  complete carry-over contract is retained below;
- the indexer has no `lobehub` adapter (`skillsmp` and `smithery` shipped
  instead), and the `hermes_docs` adapter has no seed entry.

### Normative carry-over: local installation identity

This contract remains mandatory for 15.10/15.11 implementation; the existing
inventory must not approximate it with a plain path hash.

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

### Normative carry-over: acquisition, reconciliation, and observation

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
`unlinked`. Name similarity is never identity. The current runtime correctly
uses `signature-present-unverified`; `signed` remains reserved until canonical
serialization, algorithms, publisher-key binding, rotation/revocation, and
failure behavior are implemented.

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
An observation is not a rating.

## Cross-cutting ASM collaboration gate

[`asm-logion-collaboration-and-protocol-convergence-gate.md`](asm-logion-collaboration-and-protocol-convergence-gate.md)
starts exploratory outreach to ASM creator Yi Guo as soon as the plan is
publicly shareable. It is not another implementation phase or an ASM adoption
decision. It prevents Logion and ASM from independently freezing competing
selection descriptors, ranking layers, or invocation/cost receipts.

The first contact happens before Phase 15.12 design freeze. Concrete co-design
uses Phase 15.11 artifacts and must resolve the one-subject/one-receipt boundary
before Phase 15.17 or Phase 16.7 publishes a wire contract. Silence or
non-agreement keeps the projects independent and authorizes no compatibility
claim.

## Phase 15 — first useful node

Umbrella: [`phase-15-native-resource-loop-and-first-ai-catalog-ard-node.md`](phase-15-native-resource-loop-and-first-ai-catalog-ard-node.md).

| Phase | Outcome | Dogfood level |
| --- | --- | --- |
| [`15.10`](phase-15.10-native-acquisition-artifact-delivery-and-inventory.md) | Hosted artifact downloads plus `npx skills`, `npx plugins`, and `hf` acquisition/reconciliation | Level 1: acquisition |
| [`15.11`](phase-15.11-native-use-observation-linked-feedback-and-reviews.md) | Observe native usage and submit generic feedback linked to the exact resource/Course | Level 2: real feedback |
| [`15.11.1`](phase-15.11.1-publisher-integrated-consented-observation.md) | Let publishers ship thin consented skill/plugin projections that emit minimum receipts automatically without requiring the full Logion CLI | Level 2.1: publisher-side adoption |
| [`15.12`](phase-15.12-ai-catalog-publication-and-ard-discovery.md) | AI Catalog publication/ingestion plus server-side ARD Agent Finder indexing from `ard-connectors`, with zero-duplicate self-crawl and no premature ASM-specific contract | Level 3: discovery |
| [`15.13`](phase-15.13-portable-scan-evidence.md) | Signed portable evidence from current scanners | Level 4: evidence |
| [`15.14`](phase-15.14-feedback-driven-platform-bounties.md) | Choose platform-funded improvements from attributed usage and friction | Level 5: demand → improvement |
| [`15.14.1`](phase-15.14.1-local-multi-agent-first-node-foundation.md) | Isolated founder-operated roles on one MacBook | Level 5.5: local roles |
| [`15.15`](phase-15.15-isolated-first-runner-node.md) | First isolated CPU runner using the proving ground | Level 6: execution |
| [`15.16`](phase-15.16-first-party-resource-dogfood-loop.md) | Recurring acquire → use → feedback/evidence → bounty → improvement → rerun loop | Level 7: full product |
| [`15.17`](phase-15.17-aktp-evidence-and-improvement-feed-v0.md) | AKTP v0 as an ARD-linked evidence/improvement feed | Level 8: protocol |

**Phase 15 exit:** a resource installed through Logion or a native manager is exactly attributed, used, receives linked feedback, is discovered through ARD, scanned, exercised, improved through a feedback-driven bounty, and rerun by the Logion-operated first node.

## Phase 16 — independent verification

Umbrella: [`phase-16-distributed-evaluation-and-independent-verification.md`](phase-16-distributed-evaluation-and-independent-verification.md).

1. [`16.1 — Eval contract and reference runner`](phase-16.1-eval-contract-and-reference-runner.md)
2. [`16.2 — Typed evaluators and skill reference evaluator`](phase-16.2-typed-evaluators-and-skill-reference-evaluator.md)
3. [`16.3 — Runner registry and network jobs`](phase-16.3-runner-registry-and-network-jobs.md)
4. [`16.4 — Deterministic replication and agreement`](phase-16.4-deterministic-replication-and-agreement.md)
5. [`16.5 — Eval attestations and cross-node authority`](phase-16.5-eval-attestations-and-cross-node-authority.md)
6. [`16.6 — Benchmark-backed bounties`](phase-16.6-benchmark-backed-bounties.md)
7. [`16.7 — Evidence search and issuer-aware ranking`](phase-16.7-evidence-search-and-issuer-aware-ranking.md)
8. [`16.8 — Portable field evidence and aggregation`](phase-16.8-portable-field-evidence-and-aggregation.md)
9. [`16.9 — Benchmark/field reconciliation`](phase-16.9-benchmark-field-reconciliation.md)
10. [`16.10 — External runner onboarding and conformance`](phase-16.10-external-runner-onboarding-and-conformance.md)
11. [`16.11 — MCP registry adapter and safe probes`](phase-16.11-mcp-registry-adapter-and-safe-probes.md)
12. [`16.12 — Hugging Face metadata and constrained model evaluation`](phase-16.12-hugging-face-metadata-and-constrained-model-evaluation.md)

**Phase 16 exit:** at least one independent operator reproduces a bounded evaluation and issues a verifiable attestation without Logion-owned compute or credentials.

## Phase 17 — ecosystem and hardening

Umbrella: [`phase-17-open-ecosystem-and-production-hardening.md`](phase-17-open-ecosystem-and-production-hardening.md).

1. [`17.1 — AI Catalog/ARD/AKTP conformance and upstream proposals`](phase-17.1-ai-catalog-ard-aktp-conformance-and-upstream-proposals.md)
2. [`17.2 — Independent node federation`](phase-17.2-independent-node-federation.md)
3. [`17.3 — Resource claims and commercial rails`](phase-17.3-resource-claims-and-commercial-rails.md)
4. [`17.4 — Private and enterprise nodes`](phase-17.4-private-and-enterprise-nodes.md)
5. [`17.5 — Trust-boundary invariant tests`](phase-17.5-trust-boundary-invariant-tests.md)
6. [`17.6 — Public narrative and landing truth pass`](phase-17.6-public-narrative-and-landing-truth-pass.md)

## Phase 18 — prove it is a network

[`phase-18-network-liquidity-and-independent-operation.md`](phase-18-network-liquidity-and-independent-operation.md) requires useful non-founder supply and demand for three consecutive months. It explicitly rejects a token, fake subsidized volume, a mandatory global payment rail, or an owned GPU fleet.

## Sequencing rules

- Every active 15.10+ subphase adds a named builtin scenario and is incomplete
  until it passes [the cheap real-agent proving-ground gate](agent-proving-ground-phase-gate.md)
  against the locally running API. Scripted scenarios validate the harness but
  cannot close a phase. The HMAC, acquisition/reconciliation, and observation
  carry-over gates above are inherited by 15.10/15.11 rather than waived.
- AI Catalog owns the typed catalog/entry model; ARD owns intent-oriented
  discovery and registry interaction over those entries. AKTP must recreate
  neither.
- Selection/value metadata and invocation receipts have exactly one public
  owner. Follow the ASM collaboration gate before adding a Logion equivalent;
  adapters do not justify duplicate schemas.
- Logion is open-source first: public planning and contribution surfaces are a
  product invariant, while commercial rails remain optional.
- Repository scope is the default inside a repository. No harness adapter may
  silently install into a user-global directory.
- `Resource` is the protocol identity; `Course`, indexed listing, and skills commands remain compatible product projections.
- Logion runs every path first, including hosted artifact download and native-manager reconciliation, through the same public contracts used by other operators.
- Users keep `npx skills`, `npx plugins`, `hf`, and future native workflows;
  Logion integrates attribution, evidence, and feedback instead of imposing a
  replacement installer. A publisher-integrated projection may bundle a tiny
  consented reporter, but denial keeps the resource working and a static Skill
  without verified hooks never fabricates automatic observation.
- First-party evidence is valuable but labeled first-party until independently reproduced.
- Skills come first. MCP execution follows strict safe probes. Hugging Face starts metadata-first; larger model evaluation waits for compatible external or sponsor-funded compute.
- No phase may require Logion to own a GPU fleet.
- No public claim can be stronger than its underlying evidence and local authority policy.

## Already shipped

Phases 1–12 are done. The proving ground is also existing infrastructure, not a future Phase 18. Current behavior lives in [`../maintainer documentation: `](../maintainer documentation: ), with recurring release verification in [`../maintainer documentation: release-smoke-checklist.md`](../maintainer documentation: release-smoke-checklist.md).

The older roadmap blocks are historical context only. This file supersedes their future sequencing where they conflict.
