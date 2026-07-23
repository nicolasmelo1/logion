<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.12 — Hugging Face metadata and constrained model evaluation

> **Dogfood status:** Logion indexes Hugging Face models and evaluates only small/local or sponsor-funded models needed by its own workflows.
> **After this phase:** models enter the network without requiring Logion to own a GPU fleet.
> **Honesty boundary:** metadata validation is not model evaluation; externally funded/operated GPU evidence identifies the actual runner and hardware.

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

Support model resources while preserving the bring-your-own-compute architecture.

## Dogfood prompt for the implementing agent

```text
Find a Logion resource about Hugging Face model evaluation, local GGUF/llama.cpp,
model cards, or ML benchmarking. Recall first; on LOW/NONE search the store for
"Hugging Face GGUF model evaluation model card". Inspect an exact resource/version,
follow the mandatory acquisition protocol, and use it to review the metadata
adapter and one CPU-sized model eval. Record exact model revision/runtime/hardware and
resource use in `artifacts/dogfood/phase-16.12.md`; submit one honest feedback report only
after actual use. Never download large weights or incur paid inference without a
separate explicit budget approval.
```

## Hugging Face ingestion

- Use official Hub APIs with token optional only for authorized private dogfood; public indexing must work unauthenticated within rate limits.
- Resource canonical URI binds repo type/model ID. Version binds immutable commit SHA; file digests use Hub/LFS metadata and are verified on download.
- Store model card fields, license, gated/private state, library/framework, pipeline tags, architecture, parameter count, tensor formats, quantizations, languages, datasets/base models declared, downloads/likes as time-stamped source metadata only.
- Do not translate popularity into evidence/authority and do not ingest remote custom code as executable.

## Metadata evidence predicates

Descriptor completeness/validity, license/provenance, artifact inventory/digests, pickle/unsafe serialization presence, known dependency/runtime findings, declared-vs-observed format, and model-card claims. `trust_remote_code=true` requirement is a risk observation and execution deny by default.

## Weight-fetch policy

- Indexing fetches metadata only. Evaluation contract declares exact files, total bytes, expected digests, runtime, hardware, estimated duration/cost, and license/gating authorization.
- Coordinator schedules only after compatible runner offer and sponsor hard cap. Runner downloads directly from approved Hub host into content-addressed cache with quota; no coordinator proxy or permanent default mirror.
- Gated/private weights require runner-local scoped token and produce private evidence unless license/disclosure permits.

## Constrained evaluator

- Reuse companion llama.cpp/GGUF driver for tiny models; extract/adapt as a library instead of copying.
- Record model commit/file/quantization, tokenizer, runtime/image digest, CPU/GPU model/VRAM/RAM, threads/batch/context, prompt-template digest, generation parameters/seeds, warmup, and measured tokens/latency.
- Start with deterministic structured-output/routing fixtures used by Logion. Quality results are benchmark-specific; no general “better model” score.
- Larger/API models run only on external or sponsor-funded compatible evaluator plugins under the same contract.

## Code/tests

- `indexer/adapters/hugging_face.py`, HF fixtures/cache/rate-limit tests, resource type projections.
- `evaluators/model/` descriptor, llama.cpp adapter, cache/digest enforcement, result normalizer.
- Fixtures: metadata-only, LFS digest, gated, custom-code, unsafe pickle, changed revision, oversized plan, incompatible hardware, corrupt cache, deterministic tiny fake/GGUF.
- Cost/scheduler tests prove no offer/download when cap or compatible runner is absent.

## Rollout

Metadata index first behind source limits. Then one already-used companion GGUF on Logion CPU runner. No automatic full-Hub crawl and no GPU purchase. Publish evaluated labels only after inference evidence exists.

## Build

- Hugging Face adapter for model card, revision, files, license, framework, architecture, declared tasks, and immutable revision/digests.
- Metadata/provenance/vulnerability predicates available without inference.
- Constrained reference path for small GGUF/CPU models already supported by the companion.
- Hardware-aware eval contracts and runner capability matching for larger models.
- Sponsor budget estimates and hard ceilings before any paid inference job.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_12_hf_constrained_model`.

- **Prompt:** “Find a small compatible model through Logion, inspect provenance,
  license and file sizes, download only the pinned allowed artifact with `hf`,
  reconcile it, and run the bounded CPU evaluation. Refuse anything outside my
  200 MB policy.”
- **Fixtures:** recorded/local HF metadata for an allowed tiny artifact,
  oversized weights, mutable revision, gated artifact, and license omission;
  the native `hf` boundary remains real.
- **Assertions to add:** `api.hf_resource_indexed`,
  `files.hf_revision_pinned`, `api.hf_acquisition_reconciled`,
  `api.model_eval_receipt_exists`, `files.download_budget_respected`, and
  `api.disallowed_model_not_downloaded`.
- **Evidence:** retain repo/revision/file digests, native CLI output, bytes,
  license/provenance, eval receipt/cost, redaction, and no 500s.

## Gates

- Indexing never downloads model weights by default.
- Evaluation never schedules without compatible volunteered or funded compute.
- Model revision, quantization, runtime, hardware, and generation settings are attested.
- Metadata-only resources cannot display an evaluated badge.
- Production API/worker hosts never download model weights.
- Every paid or GPU evaluation exposes sponsor cap, actual runner/operator, actual hardware, and actual cost in its receipt.
