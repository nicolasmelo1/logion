# Pinned protocol specifications

This directory gives humans and coding agents offline, reviewable access to the
normative sources Logion implements. It prevents plans, summaries, or model
memory from silently becoming a substitute for the actual protocol.

## Read order

For work involving catalog entries, media types, identity, trust, discovery,
search, Agent Finders, federation, or AKTP links:

1. read this file;
2. inspect [`UPSTREAM.lock.json`](UPSTREAM.lock.json) for the exact upstream
   repository, commit, license, and file hashes;
3. read the applicable normative snapshot:
   - [AI Catalog specification](upstream/ai-catalog/specification/ai-catalog.md);
   - [ARD specification](upstream/ard/spec/ard.md);
4. consult the machine-readable artifacts, not prose alone:
   - [ARD CDDL](upstream/ard/spec/schemas/ard.cddl);
   - [ARD OpenAPI](upstream/ard/spec/schemas/ard.openapi.yaml);
   - [ARD repository's AI Catalog JSON Schema](upstream/ard/spec/schemas/ai-catalog.schema.json);
5. only then read Logion's implementation plan.

The AI Catalog snapshot also includes its upstream example and ReSpec
configuration. The ARD snapshot includes its URN naming guide, the ADR that
defines placeholder URNs, and the conformance executable referenced by the
spec. These are useful context, but normative language and authoritative
schemas win over examples.

## Layer boundary

```text
AI Catalog       typed catalog and entry representation
ARD              pre-invocation search/discovery returning those entries
native protocol  execution or acquisition through MCP, A2A, Skills, hf, etc.
AKTP             optional Logion-proposed evidence/improvement relations
```

AI Catalog and ARD are independent upstream specifications with independent
versioning. AKTP must not redefine their base objects, discovery behavior, or
conformance claims.

## Authority and drift policy

- Files under `upstream/` are byte-for-byte snapshots. Never edit them locally.
- The upstream source at the commit in `UPSTREAM.lock.json` is authoritative.
- Logion plans and code comments are non-normative. When they conflict with a
  pinned source, the pinned source wins until a reviewed pin update says
  otherwise.
- A newer upstream `main` does not silently change Logion. Updating a pin is a
  dedicated review that records upstream diffs, compatibility impact, fixture
  changes, migration needs, and the new hashes.
- The public and private repositories carry the same snapshots through the
  canonical mirror. Public contributors can inspect the exact basis for every
  conformance claim.

Run the offline integrity gate:

```bash
python3 scripts/check_protocol_specs.py
```

## Current upstreams

- AI Catalog: <https://github.com/Agent-Card/ai-catalog>, normative source
  `specification/ai-catalog.md`, documentation <https://ai-catalog.io/>.
- ARD: <https://github.com/ards-project/ard-spec>, normative source
  `spec/ard.md`, documentation
  <https://agenticresourcediscovery.org/spec/>.
- ARD Agent Finder directory:
  <https://github.com/ards-project/ard-connectors/blob/main/agent-finders.json>.
  This directory is a separately pinned runtime discovery input in the 15.12
  phase,
  not part of either vendored normative specification.

The original license files are stored beside each snapshot. AI Catalog
specification/documentation is CC-BY-4.0; ARD is Apache-2.0.
