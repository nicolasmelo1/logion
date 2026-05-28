"""Render a DSPy candidate report + saved program into a review packet.

The packet is a single Markdown file a human reads before deciding
whether to translate the optimizer's output into a ``SKILL.md`` change.
Nothing here writes to ``SKILL.md`` directly — promotion remains a
manual PR per the policy in ``README.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_instructions(program: dict[str, Any]) -> str | None:
    """Pull the rewritten signature instructions from a saved program.

    DSPy's ``Module.save`` writes a JSON whose exact shape varies by
    version. The instructions live under one of a few known keys; we
    search for the first match. Returns ``None`` if not found.
    """
    candidate_keys = (
        "predictor.signature.instructions",
        "predict.signature.instructions",
        "signature.instructions",
    )
    for key in candidate_keys:
        value = program.get(key)
        if isinstance(value, str) and value.strip():
            return value

    # Some DSPy versions nest the signature under a "predictors" list.
    predictors = program.get("predictors")
    if isinstance(predictors, list):
        for item in predictors:
            sig = (
                (item or {}).get("signature")
                if isinstance(item, dict)
                else None
            )
            instructions = (
                (sig or {}).get("instructions")
                if isinstance(sig, dict)
                else None
            )
            if isinstance(instructions, str) and instructions.strip():
                return instructions
    return None


def _extract_demos(program: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull selected few-shot demos from a saved program."""
    for key in ("predictor.demos", "predict.demos", "demos"):
        value = program.get(key)
        if isinstance(value, list):
            return [d for d in value if isinstance(d, dict)]

    predictors = program.get("predictors")
    if isinstance(predictors, list):
        for item in predictors:
            demos = (
                (item or {}).get("demos") if isinstance(item, dict) else None
            )
            if isinstance(demos, list):
                return [d for d in demos if isinstance(d, dict)]
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


def render_candidate(
    report_path: Path,
    skill_path: Path,
    program_path: Path | None = None,
) -> str:
    """Return a Markdown review packet for the given candidate."""
    report = _load_json(report_path)

    if program_path is None:
        program_str = report.get("program_path")
        if program_str:
            program_path = Path(program_str)

    program: dict[str, Any] = {}
    if program_path is not None and program_path.is_file():
        program = _load_json(program_path)

    instructions = _extract_instructions(program)
    demos = _extract_demos(program)
    failure_counts = _failure_summary(report.get("dev_breakdown", []) or [])

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
    lines.append("## Scores")
    lines.append("")
    lines.append(f"- optimizer: `{report.get('optimizer', '?')}`")
    lines.append(
        f"- baseline dev avg: **{report.get('baseline_dev_score_avg', '?')}**"
    )
    lines.append(
        f"- optimized dev avg: **{report.get('dev_score_avg', '?')}**"
    )
    delta = report.get("delta")
    lines.append(
        f"- delta: **{delta:+.4f}**"
        if isinstance(delta, (int, float))
        else f"- delta: {delta}"
    )
    lines.append(
        f"- train={report.get('train_count')} "
        f"dev={report.get('dev_count')} "
        f"test={report.get('test_count')} "
        f"split_hash=`{report.get('split_hash')}`"
    )
    lines.append("")
    if isinstance(delta, (int, float)) and delta <= 0:
        lines.append(
            "**Verdict suggestion:** delta ≤ 0 — the optimizer did not "
            "beat the baseline on this run. Do not promote."
        )
        lines.append("")

    lines.append("## Failure summary (optimized run)")
    lines.append("")
    if failure_counts:
        for metric_name, count in failure_counts.most_common():
            lines.append(f"- `{metric_name}`: {count} scenario(s)")
    else:
        lines.append("_No per-scenario failures recorded._")
    lines.append("")

    lines.append("## Rewritten signature instructions")
    lines.append("")
    if instructions:
        lines.append("```")
        lines.append(instructions.rstrip())
        lines.append("```")
    else:
        lines.append(
            "_No rewritten instructions in the saved program. This is "
            "expected for `bootstrap_few_shot` (it only selects demos); "
            "use `mipro_v2` if you want instruction proposals._"
        )
    lines.append("")

    lines.append(f"## Selected few-shot demos ({len(demos)})")
    lines.append("")
    if demos:
        for idx, demo in enumerate(demos, start=1):
            lines.append(_format_demo(idx, demo))
    else:
        lines.append("_No demos selected._")
    lines.append("")

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
        "1. Read the failure summary. If `safety` dominates, the "
        "candidate is unsafe — do not promote regardless of delta."
    )
    lines.append(
        "2. If delta > 0 and no safety failures remain, hand-translate "
        "the rewritten instructions into the matching section of "
        "SKILL.md. Keep prose style consistent."
    )
    lines.append(
        "3. Re-run evals (`make eval-llama-cpp`) against the proposed "
        "SKILL.md before opening a PR."
    )
    lines.append(
        "4. Include this packet in the PR description so reviewers see "
        "the same evidence."
    )
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
