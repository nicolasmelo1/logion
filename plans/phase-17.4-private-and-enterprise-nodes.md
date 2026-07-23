<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 17.4 — Private and enterprise nodes

> **Dogfood status:** Logion runs a private staging node with the same deployment and policy model sold to organizations.
> **After this phase:** organizations can evaluate private resources and selectively exchange attestations without uploading proprietary inputs.
> **Honesty boundary:** private evidence is not publicly inspectable unless its owner deliberately publishes a disclosure-safe attestation.

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

Offer a sustainable product layer around open protocols.

## Dogfood prompt for the implementing agent

```text
Search Logion for a resource about multi-tenancy, self-hosting, enterprise security,
SSO/RBAC, or data residency. Recall first; on LOW/NONE search the store for
"self hosted multi tenant SSO RBAC data residency". Follow the mandatory
acquisition/reconciliation protocol and use it to review a private staging
deployment and tenant-isolation tests. Save `artifacts/dogfood/phase-17.4.md`; submit feedback
once the private node completes an eval while disconnected from Logion SaaS.
```

## Deployment SKUs and boundary

- Define one private-node artifact/config with profiles: isolated single organization and managed multi-tenant. Do not fork protocol semantics or maintain an enterprise-only runner.
- Private node owns database, object storage, signing keys, ARD catalog visibility, AKTP feed visibility, runners, policies, billing/quotas, and backups.
- SaaS control plane may deliver licenses/updates/support only; node continues core discover/evaluate/verify during SaaS outage.

## Tenancy/security model

- Add `organization_id` to private resource/evidence/policy/job/artifact records via explicit repositories and row-level/service checks; public global resources are mounted/read-only or imported with provenance.
- SSO OIDC/SAML adapter, SCIM later only if demanded; roles: org admin, policy admin, sponsor, evaluator operator, resource maintainer, viewer, auditor.
- Customer-managed or deployment-local encryption/signing keys; documented rotation/export/restore. Secrets never appear in support telemetry.
- Egress and federation disabled by default; per-destination allowlists and disclosure policy.

## Selective disclosure

Private attestation export contains public subject commitment/digest, predicate/result summary, issuer/key, method, timestamp, limitations, and artifact commitments. It excludes private resource identity/inputs/artifacts unless explicitly selected. Verifier must distinguish `artifact undisclosed` from missing/tampered.

## Code/infra

- Add organization/policy/RBAC packages and migration strategy in private API; centralize authorization dependency rather than scattering conditionals.
- Parameterize existing Terraform/compose for private node, external DB/object-store options, backup/restore, TLS, health, air-gapped image bundle/update verification.
- Admin UI/CLI for org, SSO, roles, quotas, retention, keys, export/import, federation policy, audit export.
- License enforcement must not block offline verification/export of customer-owned evidence after subscription lapse.

## Tests/acceptance additions

- Cross-tenant ID enumeration/search/cache/object-key/job/artifact/key/backup tests.
- SaaS network blackhole test: local ARD, eval, evidence verification, policy, and audit still work.
- Air-gap install/update, backup/restore, key rotation, selective disclosure, support bundle redaction.
- Independent penetration/security review before managed multi-tenant GA.

## Build

- Self-hosted/private deployment profile and organization tenancy.
- Private ARD catalogs, local runners, local authority policies, and local artifact storage.
- Selective evidence disclosure with redacted predicates and digest commitments.
- SSO/RBAC, audit export, retention, data residency, quotas, and cost controls.
- Federated public/private routing without leaking resource existence.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_17_4_private_node`.

- **Prompt/actors:** two organization admins and members receive: “Install the
  approved private resource, evaluate it locally, export only the explicitly
  allowed aggregate attestation, and prove the other organization cannot see
  our catalog, feedback, artifacts, or identities.”
- **Environment:** run with outbound Logion SaaS access blocked after initial
  public package installation; organizations use separate keys/storage.
- **Assertions to add:** `api.private_catalog_isolated`,
  `api.private_eval_completed_offline`,
  `api.selective_attestation_exported`,
  `api.private_data_not_disclosed`, and
  `security.tenant_keys_and_storage_separate`.
- **Evidence:** retain deployment/profile versions, org-scoped IDs, denied
  probes, export digest/policy, offline proof, redaction, and no 500s.

## Gates

- Private fixtures never appear in public search, feeds, logs, or metrics.
- Organization can operate during Logion SaaS outage.
- Exported attestations verify without access to undisclosed artifacts and clearly state limitations.
- Backup/restore preserves identities, keys, policies, and audit history.
