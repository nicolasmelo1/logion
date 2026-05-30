"""Render a DSPy candidate report + saved program into a review packet.

The packet is a single Markdown file a human reads before deciding
whether to translate the optimizer's output into a ``SKILL.md`` change.
Nothing here writes to ``SKILL.md`` directly — promotion remains a
manual PR per the policy in ``README.md``.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


_PREDICTOR_KEYS = ("predictor", "predict")


def _predictor_blocks(program: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every predictor-shaped block in a saved DSPy program.

    DSPy 3.x serializes a single-predictor module as
    ``{"predictor": {"signature": {...}, "demos": [...], ...}}``.
    Older or multi-predictor variants nest under "predictors" (list)
    or use flat dotted keys. Collect all shapes so downstream
    extractors can iterate uniformly.
    """
    blocks: list[dict[str, Any]] = []
    for key in _PREDICTOR_KEYS:
        block = program.get(key)
        if isinstance(block, dict):
            blocks.append(block)
    predictors = program.get("predictors")
    if isinstance(predictors, list):
        blocks.extend(p for p in predictors if isinstance(p, dict))
    return blocks


def _extract_instructions(program: dict[str, Any]) -> str | None:
    """Pull the rewritten signature instructions from a saved program."""
    for block in _predictor_blocks(program):
        sig = block.get("signature")
        if isinstance(sig, dict):
            instructions = sig.get("instructions")
            if isinstance(instructions, str) and instructions.strip():
                return instructions
    # Fallback: flat dotted keys some serializers use.
    for key in (
        "predictor.signature.instructions",
        "predict.signature.instructions",
        "signature.instructions",
    ):
        value = program.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_demos(program: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull selected few-shot demos from a saved program."""
    for block in _predictor_blocks(program):
        demos = block.get("demos")
        if isinstance(demos, list):
            return [d for d in demos if isinstance(d, dict)]
    for key in ("predictor.demos", "predict.demos", "demos"):
        value = program.get(key)
        if isinstance(value, list):
            return [d for d in value if isinstance(d, dict)]
    return []


def _failure_summary(breakdown: list[dict[str, Any]]) -> Counter[str]:
    """Count which sub-metrics dragged each dev scenario down."""
    counter: Counter[str] = Counter()
    for entry in breakdown:
        for failure in entry.get("failures", []) or []:
            metric = failure.get("metric")
            if metric:
                counter[metric] += 1
    return counter


def _format_demo(idx: int, demo: dict[str, Any]) -> str:
    """Render a single few-shot demo as a Markdown block."""
    fields = []
    for key in (
        "user_prompt",
        "installed_capabilities",
        "marketplace_results",
        "action",
        "query",
        "selected_course_ids",
        "requires_user_confirmation",
        "reason",
    ):
        if key in demo:
            value = demo[key]
            if isinstance(value, str) and len(value) > 400:
                value = value[:400] + "…"
            fields.append(f"- **{key}**: {value!r}")
    body = "\n".join(fields) if fields else "_(no recognized fields)_"
    return f"### Demo {idx}\n\n{body}\n"


def _current_signature_docstring() -> str:
    """Return the current `DecisionPolicySignature` docstring as baseline."""
    try:
        from evals.optimizers.dspy.signatures import DecisionPolicySignature

        return (DecisionPolicySignature.__doc__ or "").strip()
    except Exception:
        return ""


def _instruction_diff(current: str, proposed: str) -> str:
    """Unified diff between current docstring and proposed instructions."""
    if not current and not proposed:
        return ""
    diff = difflib.unified_diff(
        current.splitlines(),
        proposed.splitlines(),
        fromfile="current_signature_docstring",
        tofile="proposed_signature_instructions",
        lineterm="",
        n=3,
    )
    return "\n".join(diff)


def _format_per_suite(
    label: str,
    baseline: dict[str, float],
    optimized: dict[str, float],
    failures: dict[str, int] | None = None,
) -> list[str]:
    """Markdown rows comparing per-suite baseline vs optimized averages."""
    rows: list[str] = []
    suites = sorted(set(baseline) | set(optimized))
    if not suites:
        return rows
    rows.append(f"### {label}")
    rows.append("")
    rows.append("| suite | baseline | optimized | delta | failures |")
    rows.append("|---|---:|---:|---:|---:|")
    for suite in suites:
        b = baseline.get(suite, 0.0)
        o = optimized.get(suite, 0.0)
        d = o - b
        fcount = (failures or {}).get(suite, 0)
        rows.append(f"| `{suite}` | {b:.4f} | {o:.4f} | {d:+.4f} | {fcount} |")
    rows.append("")
    return rows


def _per_suite_regressions(
    baseline: dict[str, float],
    optimized: dict[str, float],
    *,
    tolerance: float = 0.0,
) -> list[tuple[str, float, float]]:
    """Return regressed suites as (suite, baseline_avg, optimized_avg)."""
    out: list[tuple[str, float, float]] = []
    for suite, b in baseline.items():
        o = optimized.get(suite, 0.0)
        if o + tolerance < b:
            out.append((suite, b, o))
    return out


_CATALOG_COURSE_IDS: tuple[str, ...] = (
    "weather.basic",
    "weather.forecast",
    "data.analyze",
    "data.spreadsheets",
    "data.spreadsheet.pivot",
    "data.spreadsheet.read",
    "ocr.text",
    "ocr.documents",
    "ocr.documents.draft.v2",
    "ocr.tables",
    "email.triage",
    "email.triage.prioritize",
    "email.summarize",
    "email.draft.reply",
    "inbox.read",
    "resume.edit",
    "resume.ats",
    "resume.ats.optimize",
    "cover-letter.writer",
    "letter.tailor",
    "video.editor",
    "video.edit.timeline",
    "video.color.grade",
    "video.clips",
    "video.clips.highlight",
    "browser.automation",
    "infra.company-ops",
    "infra.terraform.review",
    "terraform.static-review",
    "travel.planner",
    "code.tdd-framework",
    "code.debugging",
    "code.debug.reproduce",
    "workflow.a-lint",
    "workflow.b-lint",
    "workflow.cleanup",
    "workflow.curl-pipe-install",
    "workflow.deploy-with-mask",
    "workflow.maybe-python-lint",
    "workflow.maybe-video-edit",
    "workflow.something-local",
    "workflow.unrelated-build",
    "workflow.verify-agent-companion",
)


# Phrases that signal GEPA's reflection narrative leaked into the
# optimised signature instructions instead of producing a clean prompt.
# These are case-insensitive substrings.
_REFLECTION_LEAK_PHRASES: tuple[str, ...] = (
    "i want to create",
    "the previous examples",
    "previous examples show",
    "the feedback also",
    "the feedback highlights",
    "the assistant should",
    "the assistant sometimes",
    "new instructions should",
    "the new instructions",
    "based on the previous",
    "by following these instructions",
    "improve the decision-making",
    "the task is to determine",
)


def _instruction_catalog_leaks(instructions: str) -> list[str]:
    """Return catalog/scenario course IDs that appear in optimised
    instructions. Course IDs belong in inputs, never in the rule text
    itself — any leak indicates GEPA memorised a training-data identifier.
    """
    if not instructions:
        return []
    found: list[str] = []
    for cid in _CATALOG_COURSE_IDS:
        if cid in instructions and cid not in found:
            found.append(cid)
    return found


def _instruction_reflection_leaks(instructions: str) -> list[str]:
    """Return GEPA-narrative phrases found in the instructions."""
    if not instructions:
        return []
    haystack = instructions.lower()
    return [p for p in _REFLECTION_LEAK_PHRASES if p in haystack]


def _catalog_leak_count(demos: list[dict[str, Any]]) -> int:
    """Count catalog course IDs in demo marketplace_results."""
    max_leaks = 0
    for demo in demos:
        marketplace_results = demo.get("marketplace_results", "")
        if not isinstance(marketplace_results, str):
            marketplace_results = str(marketplace_results)
        leaks = sum(
            1 for cid in _CATALOG_COURSE_IDS if cid in marketplace_results
        )
        max_leaks = max(max_leaks, leaks)
    return max_leaks


def _verdict(  # noqa: C901 — gate chain is intentionally flat
    report: dict[str, Any],
    *,
    demos: list[dict[str, Any]] | None = None,
    instructions: str | None = None,
) -> tuple[str, list[str]]:
    """Compute promotion verdict. Returns (verdict, reasons).

    Hard-stop gates force "do not promote" regardless of score:
      A: BLOAT — optimized tokens >= 2x baseline
      B: TOKEN_FACTOR — policy_token_factor < 0.50
      C: FACTOR_HIDING_GAIN — routing vs final divergence > 0.10
      D: CATALOG_LEAK — any demo embeds >= 3 catalog course IDs
      F: CATALOG_LEAK_IN_INSTRUCTIONS — any catalog/scenario course ID
         appears in the optimised instructions (training-data
         memorisation)
      G: REFLECTION_LEAK — GEPA's reflection narrative leaked into the
         optimised instructions
    Plus existing regressions and safety checks.
    """
    reasons: list[str] = []
    dev_delta = report.get("delta")
    test_delta = report.get("test_delta")

    # Gate A: BLOAT
    baseline_tokens = report.get("baseline_program_tokens", 0)
    optimized_tokens = report.get("optimized_program_tokens", 0)
    if (
        isinstance(baseline_tokens, (int, float))
        and baseline_tokens > 0
        and isinstance(optimized_tokens, (int, float))
        and optimized_tokens >= 2 * baseline_tokens
    ):
        reasons.append(
            f"BLOAT: optimized program ({int(optimized_tokens)} tok) "
            f"is >=2x baseline ({int(baseline_tokens)} tok). "
            "Promotion blocked. Reduce instruction length or accept "
            "fewer demos."
        )

    # Gate B: TOKEN_FACTOR
    factor = report.get("policy_token_factor", 1.0)
    if isinstance(factor, (int, float)) and factor < 0.5:
        reasons.append(
            f"TOKEN_FACTOR: policy_token_factor={factor:.2f} < 0.50. "
            "The token budget has eaten more than half the routing "
            "gain."
        )

    # Gate C: FACTOR_HIDING_GAIN
    routing_avg = report.get("routing_score_avg")
    final_avg = report.get("final_score_avg")
    if (
        isinstance(routing_avg, (int, float))
        and isinstance(final_avg, (int, float))
        and routing_avg - final_avg > 0.10
    ):
        reasons.append(
            f"FACTOR_HIDING_GAIN: routing {routing_avg:.4f} vs "
            f"final {final_avg:.4f}; delta of "
            f"{routing_avg - final_avg:.4f} attributable to "
            "token-budget penalty. The apparent routing gain is "
            "being absorbed by the token-cost factor."
        )

    # Gate D: CATALOG_LEAK
    if demos is not None:
        leak_count = _catalog_leak_count(demos)
        if leak_count >= 3:
            reasons.append(
                f"CATALOG_LEAK: a demo embeds {leak_count} "
                "catalog-specific course IDs; the demo will become "
                "misinformation if the catalog changes."
            )

    # Gate F: CATALOG_LEAK_IN_INSTRUCTIONS
    if instructions:
        instruction_leaks = _instruction_catalog_leaks(instructions)
        if instruction_leaks:
            reasons.append(
                "CATALOG_LEAK_IN_INSTRUCTIONS: optimised instructions "
                f"embed {len(instruction_leaks)} catalog/scenario "
                f"course ID(s): {', '.join(instruction_leaks)}. "
                "Course IDs belong in inputs, not in the rule text — "
                "this is training-data memorisation."
            )

    # Gate G: REFLECTION_LEAK
    if instructions:
        reflection_leaks = _instruction_reflection_leaks(instructions)
        if reflection_leaks:
            reasons.append(
                "REFLECTION_LEAK: optimised instructions contain "
                f"{len(reflection_leaks)} GEPA-narrative phrase(s): "
                f"{', '.join(repr(p) for p in reflection_leaks)}. "
                "The reflection lm's commentary leaked into the "
                "compiled prompt instead of a clean rule set."
            )

    # Existing regressions
    if isinstance(dev_delta, (int, float)) and dev_delta <= 0:
        reasons.append(f"dev_delta {dev_delta:+.4f} did not beat baseline")
    if isinstance(test_delta, (int, float)) and test_delta < 0:
        reasons.append(f"test_delta {test_delta:+.4f} regressed on holdout")
    safety_baseline = report.get("baseline_dev_per_suite", {}).get("safety")
    safety_opt = report.get("dev_per_suite", {}).get("safety")
    if (
        isinstance(safety_baseline, (int, float))
        and isinstance(safety_opt, (int, float))
        and safety_opt + 1e-6 < safety_baseline
    ):
        reasons.append(
            f"safety suite regressed on dev "
            f"({safety_baseline:.4f} -> {safety_opt:.4f})"
        )
    test_safety_baseline = report.get("baseline_test_per_suite", {}).get(
        "safety"
    )
    test_safety_opt = report.get("test_per_suite", {}).get("safety")
    if (
        isinstance(test_safety_baseline, (int, float))
        and isinstance(test_safety_opt, (int, float))
        and test_safety_opt + 1e-6 < test_safety_baseline
    ):
        reasons.append(
            f"safety suite regressed on test "
            f"({test_safety_baseline:.4f} -> {test_safety_opt:.4f})"
        )
    for suite, b, o in _per_suite_regressions(
        report.get("baseline_dev_per_suite", {}) or {},
        report.get("dev_per_suite", {}) or {},
        tolerance=1e-6,
    ):
        if suite == "safety":
            continue
        reasons.append(f"dev suite `{suite}` regressed ({b:.4f} -> {o:.4f})")
    return ("do not promote" if reasons else "promote", reasons)


def render_candidate(  # noqa: C901 — single-purpose packet builder
    report_path: Path,
    skill_path: Path,
    program_path: Path | None = None,
) -> str:
    """Return a Markdown review packet for the given candidate.

    The output is structured to match the phase-6.6 promotion-PR
    required fields (before/after eval, model matrix, scenario split
    hash, token budget delta, changed-instructions diff, runtime
    boilerplate) so it can be pasted directly into the PR description.
    """
    report = _load_json(report_path)

    if program_path is None:
        program_str = report.get("program_path")
        if program_str:
            program_path = Path(program_str)

    program: dict[str, Any] = {}
    if program_path is not None and program_path.is_file():
        program = _load_json(program_path)

    instructions = _extract_instructions(program) or ""
    demos = _extract_demos(program)
    current_doc = _current_signature_docstring()
    failure_counts = _failure_summary(report.get("dev_breakdown", []) or [])
    verdict, verdict_reasons = _verdict(
        report, demos=demos, instructions=instructions
    )

    skill_excerpt = ""
    if skill_path.is_file():
        text = skill_path.read_text(encoding="utf-8")
        skill_excerpt = text if len(text) <= 4000 else text[:4000] + "\n…"

    lines: list[str] = []
    lines.append("# DSPy candidate review packet")
    lines.append("")
    lines.append(
        "> Do not promote any changes to SKILL.md from this packet "
        "without explicit human review. The pipeline does not "
        "auto-write to SKILL.md."
    )
    lines.append("")

    # Verdict block — at the top so reviewers see it first.
    lines.append("## Verdict")
    lines.append("")
    if verdict == "promote":
        lines.append(
            "**Suggested verdict:** promote — score gates and per-suite "
            "checks passed. Still review the instruction diff and "
            "demos before merging."
        )
    else:
        lines.append("**Suggested verdict:** do not promote.")
        lines.append("")
        for reason in verdict_reasons:
            lines.append(f"- {reason}")
    lines.append("")

    # 1. before/after eval (the plan's first required field).
    lines.append("## 1. Before/after eval")
    lines.append("")
    lines.append("| split | baseline | optimized | delta |")
    lines.append("|---|---:|---:|---:|")
    dev_d = report.get("delta")
    test_d = report.get("test_delta")
    lines.append(
        f"| dev | {report.get('baseline_dev_score_avg', '?')} | "
        f"{report.get('dev_score_avg', '?')} | "
        f"{dev_d:+.4f} |"
        if isinstance(dev_d, (int, float))
        else "| dev | ? | ? | ? |"
    )
    lines.append(
        f"| test (holdout) | {report.get('baseline_test_score_avg', '?')} "
        f"| {report.get('test_score_avg', '?')} | "
        f"{test_d:+.4f} |"
        if isinstance(test_d, (int, float))
        else "| test (holdout) | ? | ? | ? |"
    )
    lines.append("")
    lines.append(
        f"Counts: train={report.get('train_count')}, "
        f"dev={report.get('dev_count')}, "
        f"test={report.get('test_count')}."
    )
    lines.append("")

    # Per-suite breakdown.
    lines.extend(
        _format_per_suite(
            "Dev — per-suite",
            report.get("baseline_dev_per_suite", {}) or {},
            report.get("dev_per_suite", {}) or {},
            report.get("dev_failures_per_suite", {}) or {},
        )
    )
    lines.extend(
        _format_per_suite(
            "Test — per-suite",
            report.get("baseline_test_per_suite", {}) or {},
            report.get("test_per_suite", {}) or {},
            report.get("test_failures_per_suite", {}) or {},
        )
    )

    # 2. model matrix.
    lines.append("## 2. Model matrix")
    lines.append("")
    matrix = report.get("model_matrix") or {}
    lines.append(f"- DSPY_LM: `{matrix.get('dspy_lm') or '?'}`")
    lines.append(f"- DSPY_API_BASE: `{matrix.get('dspy_api_base') or '?'}`")
    if matrix.get("dspy_reflection_lm"):
        lines.append(
            f"- DSPY_REFLECTION_LM: `{matrix.get('dspy_reflection_lm')}`"
        )
        if matrix.get("dspy_reflection_api_base"):
            lines.append(
                f"- DSPY_REFLECTION_API_BASE: "
                f"`{matrix.get('dspy_reflection_api_base')}`"
            )
    lines.append(f"- optimizer: `{matrix.get('optimizer') or '?'}`")
    lines.append(f"- seed: `{report.get('seed', '?')}`")
    optimizer_config = (
        matrix.get("optimizer_config") or report.get("optimizer_config") or {}
    )
    if optimizer_config:
        lines.append(f"- optimizer_config: `{json.dumps(optimizer_config)}`")
    lines.append("")

    # 3. scenario split hash.
    lines.append("## 3. Scenario split hash")
    lines.append("")
    lines.append(f"`{report.get('split_hash', '?')}`")
    lines.append("")
    lines.append(
        f"Catalog: `{report.get('catalog', '?')}`  "
        f"Scenarios dir: `{report.get('scenarios_dir', '?')}`"
    )
    lines.append("")

    # 4. token budget delta.
    lines.append("## 4. Token budget delta")
    lines.append("")
    baseline_tokens = report.get("baseline_program_tokens")
    optimized_tokens = report.get("optimized_program_tokens")
    token_delta = report.get("token_delta")
    lines.append(
        f"- baseline program tokens (signature docstring): "
        f"**{baseline_tokens}**"
    )
    lines.append(
        f"- optimized program tokens (instructions + demos): "
        f"**{optimized_tokens}**"
    )
    if isinstance(token_delta, int):
        lines.append(f"- token delta: **{token_delta:+d}**")
    else:
        lines.append(f"- token delta: {token_delta}")
    lines.append("")
    lines.append(
        "_Estimate uses 4 chars per token; signed delta is the cost "
        "the agent pays per decision after promotion._"
    )
    lines.append("")

    # 5. explanation of changed instructions: diff + raw text + demos.
    lines.append("## 5. Changed instructions")
    lines.append("")
    if instructions:
        diff = _instruction_diff(current_doc, instructions)
        if diff:
            lines.append(
                "### Diff vs current `DecisionPolicySignature` docstring"
            )
            lines.append("")
            lines.append("```diff")
            lines.append(diff)
            lines.append("```")
            lines.append("")
        lines.append("### Proposed instructions (full text)")
        lines.append("")
        lines.append("```")
        lines.append(instructions.rstrip())
        lines.append("```")
        lines.append("")
    else:
        lines.append(
            "_No rewritten instructions in the saved program. This is "
            "expected for `bootstrap_few_shot` (it only selects demos); "
            "use `mipro_v2` if you want instruction proposals._"
        )
        lines.append("")

    lines.append(f"### Selected few-shot demos ({len(demos)})")
    lines.append("")
    if demos:
        for idx, demo in enumerate(demos, start=1):
            lines.append(_format_demo(idx, demo))
    else:
        lines.append("_No demos selected._")
    lines.append("")

    # 6. runtime boilerplate.
    lines.append("## 6. Runtime statement")
    lines.append("")
    lines.append(
        "Runtime still does not require DSPy. DSPy remains an optional "
        "extra used only by `evals/optimizers/dspy/` for offline "
        "candidate generation; the published agent-companion wheel "
        "and `make verify` do not depend on it."
    )
    lines.append("")

    # Failure summary (aggregate) for quick scanning.
    lines.append("## Failure summary (optimized dev run)")
    lines.append("")
    if failure_counts:
        for metric_name, count in failure_counts.most_common():
            lines.append(f"- `{metric_name}`: {count} scenario(s)")
    else:
        lines.append("_No per-scenario failures recorded._")
    lines.append("")

    # Current SKILL.md excerpt for side-by-side reading.
    lines.append("## Current SKILL.md (excerpt)")
    lines.append("")
    if skill_excerpt:
        lines.append("```markdown")
        lines.append(skill_excerpt.rstrip())
        lines.append("```")
    else:
        lines.append(f"_Could not read {skill_path}_")
    lines.append("")

    lines.append("## Suggested next steps")
    lines.append("")
    lines.append(
        "1. Re-read section 1 (before/after) and the per-suite tables. "
        "If any suite — especially `safety` — regressed, do not promote."
    )
    lines.append(
        "2. Re-read section 5 (diff). Cherry-pick wording improvements "
        "that fit SKILL.md's structure; reject anything that drops the "
        "references block, YAML safety frontmatter, or implemented "
        "commands list."
    )
    lines.append(
        "3. Re-run evals (`make eval-llama-cpp`) against the proposed "
        "SKILL.md before opening a PR."
    )
    lines.append("4. Paste sections 1-6 into the PR description as evidence.")
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a DSPy candidate report + saved program into a "
            "Markdown review packet for human-driven SKILL.md updates."
        )
    )
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Path to the candidate report JSON.",
    )
    parser.add_argument(
        "--program",
        type=Path,
        help=(
            "Path to the saved program JSON. Defaults to the "
            "`program_path` field in the report."
        ),
    )
    parser.add_argument(
        "--skill",
        type=Path,
        default=Path("SKILL.md"),
        help="Path to the current SKILL.md.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Where to write the packet. Defaults to "
            "<report_stem>.review.md alongside the report."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.report.is_file():
        print(f"error: report not found: {args.report}", file=sys.stderr)
        return 2

    output_path = args.output or args.report.with_suffix("").with_suffix(
        ".review.md"
    )
    packet = render_candidate(
        report_path=args.report,
        skill_path=args.skill,
        program_path=args.program,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(packet, encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
