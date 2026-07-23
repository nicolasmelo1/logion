<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.17 — AKTP evidence and improvement feed v0

> **Dogfood — Level 8 (protocol):** Logion's live first-party loop emits the same feed another node would consume.
> **After this phase:** ARD-discovered resources can advertise an AKTP endpoint for evidence, jobs, bounties, outcomes, and supersession events.
> **Honesty boundary:** the feed transports signed statements; consumers choose issuers and policy. It is not a global truth ledger.

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

Define the minimum AKTP extension that ARD does not provide: portable evidence and an improvement workflow.

## Dogfood prompt for the implementing agent

```text
Find and use a Logion course about append-only event protocols, cryptographic
signatures, distributed systems, or API versioning. Recall first:
`logion recall search "signed append only event feed protocol" --limit 5`.
On LOW/NONE search the marketplace with
`logion listings search --query "event feed protocol signature versioning"
--include-indexed --limit 5 --json`. Inspect the exact resource/version, follow the
mandatory acquisition/reconciliation protocol, and use it to review replay resistance,
cursor semantics, key rotation, and
forward compatibility. Record concrete use in `artifacts/dogfood/phase-15.17.md`.
After self-import passes, send exactly one honest usage review; otherwise record why
no review was valid.
```

## Normative protocol package

Create a public package/directory `packages/aktp-spec/` containing:

- `README.md`, threat model, versioning/compatibility policy, JSON Schemas, canonical examples, changelog, and conformance fixtures;
- a small Python codec/verifier used by the indexer/CLI and vendored or packaged for the private API;
- generated examples from fixtures, never hand-maintained examples that can drift;
- protocol namespace `aktp.dev` or another neutral namespace when available; `sh.logion.*` is allowed only for Logion-specific predicates.

Wire version v0 must state media types, size limits, timestamp format, canonicalization (JCS), digest/signature algorithms, stable error behavior, and must-ignore rules for unknown event types/fields.

## Event envelope

```json
{
  "aktp_version": "0",
  "event_id": "uuid",
  "event_type": "evidence.published",
  "origin": "https://api.logion.sh",
  "sequence": 123,
  "occurred_at": "RFC3339",
  "resource": {"ard_id": "...", "digest": "sha256:..."},
  "object": {"id": "...", "digest": "sha256:...", "url": "..."},
  "issuer": {"id": "...", "key_id": "..."},
  "extensions": {},
  "signature": "base64url"
}
```

Cursor is opaque and binds origin, last sequence, filter, and protocol version. Sequence is monotonic per origin, allocated transactionally. It is ordering, not a global clock. Event ID uniqueness plus origin prevents replay. Relays preserve the original envelope/signature.

## Backend implementation

- Migration adds `protocol_events`, issuer keys/rotation metadata if 15.11 did not, and peer-import checkpoints only for self-import tests in this phase.
- Add `api/aktp/{schemas,repositories,services,controllers}/`: transactional outbox writer, feed reader, object resolver, keys document, and self-import verifier.
- Domain services publish outbox events after their owning transaction succeeds. Prefer a transactional outbox row written in the same DB transaction; a worker signs/publishes. Never publish to the network before commit.
- Endpoint set: node/capability document advertised from ARD, paginated feed, event by ID, public keys, referenced public object. Exact paths follow the neutral spec package.
- Filters may narrow type/resource/time but cannot change sequence semantics. Response has hard item/byte caps and ETag.

## Public repo implementation

- `logion aktp feed --node URL [--cursor] [--type]`, `verify FILE|URL`, and `import --dry-run`.
- Import stores a local SQLite/test-node projection or calls the generic resource/evidence APIs; dry-run never mutates.
- Add indexer resolution of optional ARD AKTP links without making them mandatory for resource discovery.

## Security/abuse rules

- Apply the same SSRF resolver policy as 15.10.
- Verify envelope signature and object digest before import; an event is not authority merely because valid.
- Cap feed pages, object fetch bytes, decompression ratio, clock skew, and backfill horizon.
- Payout event contains a receipt/status reference, never credentials or an executable payment promise.
- Bounty rewards from foreign nodes are display-only until a local sponsor explicitly imports/accepts terms.

## Tests and conformance

- Golden event per type, canonicalization across key order/Unicode/numbers, unknown fields/type, invalid signature/digest, sequence gap/duplicate/reorder, key rotation, cursor tamper/filter mismatch, and replay.
- Transaction rollback emits no event; retry emits one event.
- Self-export/import into a clean database is lossless and second import creates zero rows.
- ARD-only client fixture ignores the optional AKTP link and still discovers resources.
- Compatibility harness runs public codec against backend feed in CI.

## Rollout

Start read-only with only `evidence.published` from public 15.11 evidence. Add job/bounty/outcome event types one at a time behind flags after their redaction review. No third-party peer import in production until Phase 17.2.

## Build

- Publish a versioned, append-only event feed with cursor pagination and stable event IDs.
- Support `feedback.published`, `feedback.superseded`, `evidence.published`, `evidence.superseded`, `improvement.recommended`, `job.offered`, `job.completed`, `bounty.opened`, `submission.delivered`, `outcome.accepted`, and `payout.recorded`.
- Reference ARD resource IDs and immutable digests; never duplicate discovery metadata as protocol authority.
- Sign events and expose issuer metadata, key rotation, replay protection, and retention policy.
- Add an optional AKTP endpoint/capability link to the ARD descriptor.
- Implement `logion aktp feed|verify|import --dry-run` and an SDK codec.
- Self-import Logion's feed into a clean test node and reconcile it against source records.

## Explicit non-goals

- No custom peer discovery.
- No token, blockchain, global settlement, or global reputation score.
- No assumption that another node accepts Logion evidence.
- No cross-node job claiming until Phase 16.
- No raw acquisition event, passive observation, individual usage receipt, private feedback body, local path, or user identity in the public feed. `feedback.published` requires explicit public visibility and carries only its disclosure-safe statement; aggregate field evidence is formalized in 16.8.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_17_aktp_feed`.

- **Actors/seed:** publisher-node and consumer-node operators with independent
  homes, databases, issuer keys, and trust stores. Seed scan evidence, an
  aggregate feedback predicate, and one improvement state transition; raw
  observations/review text are ineligible.
- **Publisher prompt:** “Publish this node's portable evidence and improvement
  events through AKTP. Show what is deliberately excluded.”
- **Consumer prompt:** “Import the feed into this clean node, verify each event,
  inspect resource history, then import the same page again.”
- **Assertions to implement:** `api.aktp_feed_page_valid`,
  `crypto.aktp_events_verified`, `api.aktp_events_imported`,
  `api.aktp_import_idempotent`, `api.aktp_lineage_resolves`, and
  `api.private_feedback_not_exported`.
- **Negative/evidence:** reject a mutated payload under an existing ID and an
  unknown issuer without poisoning cursor/history. Retain event/envelope
  digests, issuer keys, cursor behavior, counts, projection, exclusions,
  redaction, and no-500 proof.

## Acceptance gates

- Export/import is lossless, idempotent, resumable, and signature-verifiable.
- Feed consumers can distinguish observation, evaluation, sponsorship, delivery, and payout.
- An ARD-only client still discovers and uses the resource without AKTP.
- Protocol examples are generated from passing conformance fixtures.
