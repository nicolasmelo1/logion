<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 17.2 — Independent node federation

> **Dogfood status:** Logion peers with staging and independent nodes through the same public feed/import surfaces.
> **After this phase:** nodes exchange evidence and improvement events while preserving local storage, settlement, and authority.
> **Honesty boundary:** federation is not shared governance or automatic trust.

## Mandatory dogfood protocol

The phase-specific prompt below is implementation work, not optional documentation. The implementing agent must exercise the interoperable resource loop delivered by 15.10–15.11:

1. run local recall, then `logion listings search --query "SEARCH_QUERY" --include-indexed --limit 5 --json` only on LOW/NONE;
2. inspect the exact `ResourceVersion`, distributions, evidence, permissions, license, and acquisition plan—not only a Course projection;
3. obtain explicit approval, run `logion resources acquire RESOURCE_ID --version VERSION_ID --scope repo-root --channel auto --dry-run --json`, then acquire through the recommended Logion or native channel;
4. run `logion resources reconcile --scope repo-root --json` and require exact version attribution;
5. use the resource in the normal harness on this phase's real task and verify it appears in `logion usage pending --json`;
6. submit exactly one intentional post-task report:

```bash
logion feedback submit RESOURCE_ID VERSION_ID \
  --rating 1..5 \
  --usefulness 0.0..5.0 \
  --reliability 0.0..5.0 \
  --tool-safety 0.0..5.0 \
  --token-efficiency 0.0..5.0 \
  --completed-task \
  --task-class TASK_CLASS \
  --body "One or two resource-focused sentences; no private repository data" \
  --json
```

Use `--not-completed-task` when appropriate. Record the feedback ID and `course_review_projection` disposition. A native external installation is valid dogfood; Logion must not require reinstalling it. If acquisition, exact attribution, consent, or actual use is absent, record the blocker and **do not submit feedback/review**. Passive observation alone never justifies a rating.

## Goal

Support a network of operators without a central database pretending to be decentralized.

## Dogfood prompt for the implementing agent

```text
Use Logion to find a resource about federation, event replication, sync protocols, or
distributed data. Recall first; on LOW/NONE search "federation event replication sync
protocol". Follow the mandatory acquisition/reconciliation protocol and use it to review
partition, loop, replay, and backfill behavior. Record `artifacts/dogfood/phase-17.2.md`.
Submit feedback once two clean nodes converge after a forced partition.
```

## Federation model

Peers are configured from an AI Catalog origin and/or an approved ARD Agent
Finder/registry. A namespaced optional entry/result relation may advertise AKTP.
There is no bespoke global node registry, `known_nodes` crawl, or implicit
trust. Adding a peer remains a local operator action/policy.

Each node stores peer origin, pinned/allowed keys, protocol range, event filters, import authority policy, byte/rate/backfill budgets, cursor/checkpoint, health, and suspension reason. Settlement and job acceptance remain local.

## Sync algorithm

```text
resolve AI Catalog origin and/or ARD registry under SSRF policy
fetch advertised AKTP capability + keys
negotiate supported version
resume opaque peer cursor
for each bounded page/event:
  verify origin/event/signature/key-at-time/object digest
  reject replay/loop/oversize/unsupported required semantics
  apply local event-type/resource/issuer policy
  store immutable foreign envelope and import disposition
  project accepted object via owning domain service
commit page + cursor atomically
backoff/suspend on repeated protocol or security failure
```

Relay adds transport metadata outside the signed origin envelope. It cannot rewrite event or issuer. Track `(origin,event_id)` and hop trace to prevent loops.

## Backend/operator surfaces

- Add `api/federation/` peer config, sync service/job handler, foreign envelope repository, import disposition, checkpoint, health, and controllers.
- CLI/admin: peer add (dry-run validation), list, inspect, sync, pause, resume, remove, reset-checkpoint with confirmation, and export support bundle.
- Metrics per peer: lag, pages/events/bytes, accepted/rejected by reason, signature/key failures, loops, object errors, last success.
- Notifications for suspension/key change/protocol incompatibility.

## Consistency and deletion

- Imported evidence is append-only. Peer removal stops sync and hides projections according to local policy but retains signed history/audit unless retention law requires private-data deletion.
- Tombstone/supersession is another signed event and subject to policy; it never deletes third-party evidence silently.
- Cursor reset cannot duplicate domain objects due to origin/event/object idempotency.

## Tests/rollout

- Two/three-node topology, relay, loop, duplicate, reorder, gap, partition, stale cursor, key rotation, malicious key swap, unsupported version, SSRF, object tamper, peer removal/re-add.
- 10k-event backfill under byte/query/runtime budgets and crash at each transaction boundary.
- Stage with two Logion clean nodes, then one independent node, while imported events remain display-only until authority policy explicitly accepts them.

## Build

- Peer configuration through AI Catalog/ARD-discovered namespaced AKTP
  endpoints; no bespoke global peer registry.
- Cursor sync, backfill, retry, dedupe, rate limits, and peer removal.
- Origin/issuer preservation across relays and loop prevention.
- Local import policy by event type, issuer, resource type, and budget exposure.
- Partition/recovery and protocol-version compatibility behavior.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_17_2_node_federation`.

- **Actors/prompt:** independent operators configure two local nodes only
  through public surfaces: “Exchange allowed catalogs/evidence, survive a
  temporary partition, resume, and explain the converged provenance without
  treating remote policy as local authority.”
- **Fixtures:** conflicting metadata, supersession, deletion/tombstone,
  duplicate event, unknown issuer, and a partition injected between pages.
- **Assertions to add:** `api.nodes_federated`,
  `api.partition_resume_converges`, `api.federation_idempotent`,
  `api.remote_provenance_preserved`, `api.local_policy_retained`, and
  `api.no_cross_node_double_payout`.
- **Evidence:** retain node/key IDs, cursor checkpoints, pre/post state digests,
  conflict decisions, ledgers, cost, redaction, and no 500s.

## Gates

- Two nodes exchange signed events without sharing database credentials.
- Removing a peer stops future sync but preserves verified history.
- Relay cannot impersonate the original issuer.
- Network partitions converge without duplicate jobs or payouts.
- A foreign `payout.recorded` event never posts to the local ledger.
- Operator can reproduce every accept/reject disposition from envelope plus policy digest.
