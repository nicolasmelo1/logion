<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.1.4 — A published entry resolves

On 2026-09-08 an outside scanner scored `www.logion.sh` **72/100** for agent
readiness: `npx ax audit`, the MIT-licensed CLI for ora, whose check set is the
one Vercel's readiness tool runs. The score is not the finding and this plan
does not chase it. Following our own catalog's three entries by hand is.

## What our own catalog does when an agent follows it

Measured 2026-09-08, against the live hosts rather than the repository, because
the landing edge is what serves the apex:

| Entry | URL | Result |
| :-- | :-- | :-- |
| `urn:air:logion.sh:openapi:marketplace-v1` | `api.logion.sh/openapi.json` | 200, 288 KB |
| `urn:air:logion.sh:skill:logion` | `www.logion.sh/.well-known/agent-skills/logion/SKILL.md` | 200, digest matches the one `agent-skills/index.json` publishes |
| `urn:air:logion.sh:catalog:node` | `api.logion.sh/.well-known/ai-catalog.json` | **403 — `{"detail":"ai_catalog.public feature flag is disabled"}`** |

One entry in three is a dead pointer, and the builder that emits it says why
that is the worst available outcome. From `ai_catalog()` in
`packages/landing/landing/main.py`:

> Entries are read from site.yaml rather than assembled here, so the catalog
> can only ever advertise an artifact the content file actually declares — a
> catalog entry pointing at nothing is worse for an agent than no catalog at
> all.

Declaring is not resolving. The docstring states an invariant that nothing
checks, and the guarantee it does offer — that an entry exists in `site.yaml` —
is satisfied by the entry that fails.

**The design is right and this plan does not change it.** The `site.yaml`
comment argues the case: the apex stays the single discovery entry point and
nests the node catalog rather than duplicating it, because two documents
answering one well-known URI on two hosts would make the apex and the API
disagree about what Logion offers. That reasoning holds. What is wrong is that
the nested pointer names a document gated behind `ai_catalog_public`, which
defaults off in `api/feature_flags/seed.py` and is off in production.

So there are two implementations of one document: one hand-curated from
`site.yaml` and served by the landing edge, one generated from the resource
layer and served by the API with the switch off. The scanner passed us on
catalog presence, because presence is what it measures. Presence is precisely
the signal Logion exists to say is not evidence, and we shipped the version of
that failure that is ours.

## The exported contract does not say how to authenticate

`api.logion.sh/openapi.json`, read 2026-09-08: **117 paths, 46 of them POST,
`components` carries `schemas` and nothing else.** No `securitySchemes`, no
top-level `security`, no per-operation `security`. The API is bearer
authenticated in practice and its published contract declares none of it.

ora reported this obliquely, as a missing 401 with `WWW-Authenticate` and
missing RFC 9728 metadata. The sharper statement is available from our own
artifact, and `packages/contract-audit/contract_audit/load_openapi.py` already
reads that artifact on every audit. An agent that fetches the contract — the
first entry in our own catalog, the one that resolves — cannot learn how to
authenticate against it. Publishing more well-known documents does not fix
that; the contract admitting its own scheme does, and the documents are worth
adding after it.

## Ten POSTs move money and one path in the whole API is idempotent

`idempotency_key` appears in the contract on exactly one path,
`/v1/executions/jobs`, as a body field. These ten POSTs move money or
entitlements and none of them carries an idempotency key in any form:

```text
/v1/credits/top-ups                    /v1/bounties
/v1/courses/{course_id}/purchase       /v1/bounties/{id}/payouts
/v1/admin/bounties                     /v1/bounties/{id}/submissions
/v1/admin/bounties/{id}/fund           /v1/bounties/{id}/submissions/{id}/open-pr
/v1/admin/bounties/{id}/submissions/{id}/accept
/v1/admin/bounties/{id}/submissions/{id}/reject
```

The consumer this API is designed for is an agent, and an agent retries. A
retried `POST /v1/credits/top-ups` after a gateway timeout is a double charge,
and a retried payout is a double payout. Whether the key is an
`Idempotency-Key` header or a body field is a contract decision; that the money
paths have neither is not.

## The one field Logion should not be leaving empty

Neither the host block nor any entry carries a `trustManifest`. From the pinned
specification (`protocol-specs/upstream/ai-catalog/specification/ai-catalog.md`,
authoritative over this summary):

```text
TrustManifest = { identity, ?identityType, ?trustSchema, ?attestations,
                  ?provenance, ?privacyPolicyUrl, ?termsOfServiceUrl,
                  ?signature, ?metadata }
Attestation   = { type, uri, ?digest, ?size, ?description }
ProvenanceLink= { relation, sourceId, ?sourceDigest, ?registryUri,
                  ?statementUri, ?signatureRef }
```

A company whose product is attestation about artifacts publishes a catalog with
the attestation slot blank. That is worth fixing for the same reason the dead
entry is: it is our own surface making our own argument badly.

**Filling it is not a trust claim, and the sequencing matters.** `identity`,
`provenance` and the policy URLs are facts about who we are and where the
artifact came from; they go in now. `attestations` is a list of URIs to
findings, and a `trustManifest` whose attestations point at our own marketing
is the self-rating that
[`positioning-and-independence.md`](positioning-and-independence.md) forbids —
the same failure as a store issuing its own score. An attestation entry appears
only when its `uri` resolves to a real, reproducible finding a reader can check
with no account, which is the step 6 artifact, not this plan's.

On `identityType`: `site.yaml` already argues why the host identifier is a bare
domain rather than `did:web:logion.sh` — resolving a DID requires serving a DID
document we do not publish. ora serves `did:web:ora.ai`. Copying the form to
score a check while the document 404s would be a worse version of the failure
this plan opens with.

## What is refused, and why it is not a backlog

Five of ora's failing checks are presence-and-popularity measures: `Listed on
skills.sh`, `Skills.sh skill quality`, `ChatGPT app listed`, `Wikipedia /
Wikidata`, `Agent Plugins manifest`. Two of them are satisfied by publishing
into a competing index. That is the category Logion left, and its own README
records why volume there is lost and irrelevant. They do not enter the backlog,
and a later reader should not rediscover them as oversights.

Also refused: displaying or storing the 0–100 score anywhere in Logion's
surfaces or documents. A registry's mutable quality value is never promoted
into an authoritative Logion field — the rule already written for ARD-supplied
relevance in
[`../maintainer documentation: ai-catalog-and-ard-discovery.md`](../maintainer documentation: ai-catalog-and-ard-discovery.md)
covers this exactly.

Not refused, but not here: WebMCP, NLWeb `/ask`, A2A agent card, `auth.md`.
Emerging surfaces with no consumer we currently serve. `Brand name
discoverability` — a search for "Logion" returns eight results without our
domain — is real information about a generic name colliding with older
meanings, and it is not a site fix.

## One thing this measurement did change

[`../maintainer documentation: ai-catalog-and-ard-discovery.md`](../maintainer documentation: ai-catalog-and-ard-discovery.md)
records that on 2026-08-17, of eleven announced ARD backers and nine adjacent
vendors, only `huggingface.co` served `/.well-known/ai-catalog.json`. As of
2026-09-08 `ora.ai` serves a valid one: `specVersion 1.0`,
`did:web:ora.ai`, entries including an MCP server card. That is a second
catalog in the wild and a candidate `ard-connectors` source. It is not an
issuer #2 candidate: readiness of a website is a different subject class from
behaviour of a catalogued artifact, and the milestone is not moved by it.

## Non-goals

**No `ax` in the measurement path.** It measures a different subject, and
putting a third-party npm package inside the runner or scanner chain would put
someone else's release cadence in the path of the thing we sell.

**No new well-known document nothing consumes.** The failure here is documents
that do not resolve, and adding more of them is the same mistake.

## Acceptance criteria

- [ ] Every catalog entry served by the landing resolves in the test suite, and
      an entry whose URL is served by another host is published only with the
      check that proves it resolving alongside it
      (proof: test:packages/landing/tests/test_landing_agent_discovery.py)
- [ ] `urn:air:logion.sh:catalog:node` either resolves in production or is not
      advertised, and the entry cannot be reinstated without the check
      (proof: unspecified:the state of `ai_catalog_public` in production is not
      observable from any test in either repository; the choice between
      enabling the flag and withdrawing the entry is made when it is made)
- [ ] The exported OpenAPI declares a security scheme and every authenticated
      operation references one, checked where the audit already loads it
      (proof: test:packages/contract-audit/tests/unit/test_load_openapi.py)
- [ ] A 401 from an authenticated path carries `WWW-Authenticate`
      (proof: test:packages/contract-audit/tests/unit/test_load_openapi.py)
- [ ] Every POST that moves credits, entitlements, bounty funds or payouts
      declares an idempotency key, and adding a money-moving POST without one
      turns the audit red
      (proof: test:packages/contract-audit/tests/unit/test_load_openapi.py)
- [ ] The host block and every entry carry a `trustManifest` whose `identity`
      resolves, generated rather than retyped
      (proof: test:packages/landing/tests/test_landing_agent_discovery.py)
- [ ] An `attestations` entry whose `uri` does not resolve to a published
      finding fails the build, so the slot cannot be filled with marketing
      (proof: test:packages/landing/tests/test_landing_agent_discovery.py)
- [ ] No Logion document or surface carries a third-party readiness score as a
      Logion fact
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)
- [ ] The ARD adoption paragraph in `ai-catalog-and-ard-discovery.md` states
      what was true at its most recent probe and names the date
      (proof: test:packages/contract-audit/tests/unit/test_docs_integrity.py)

**Exit condition:** every entry in every catalog Logion publishes resolves for
an agent that follows it with no account; the exported contract states how to
authenticate against it; no money-moving POST can be added without an
idempotency key; the trust manifest carries identity and provenance and is
structurally incapable of carrying an attestation that does not resolve; and
the five presence checks are recorded as refused rather than pending.
