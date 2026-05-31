"""Phase 6.11: tests for the reference-routing signature, metric,
scenarios, and renderer gates."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from evals.optimizers.dspy.reference_routing_inventory import (
    REFERENCE_NAMES,
)
from evals.optimizers.dspy.reference_routing_metric import (
    ReferenceRoutingFinding,
    ReferenceRoutingMetric,
    _classify,
    _resolve_reference,
    aggregate_rates,
)
from evals.optimizers.dspy.render_candidate import _verdict

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_PATH = (
    PACKAGE_ROOT
    / "evals"
    / "scenarios"
    / "reference_routing"
    / "scenarios.yaml"
)


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------


class TestSignatureInventory:
    def test_enum_has_nine_classes(self) -> None:
        assert len(REFERENCE_NAMES) == 9
        assert REFERENCE_NAMES[0] == "none"

    def test_signature_docstring_under_250_chars(self) -> None:
        """The ReferenceRoutingSignature docstring is a thin pointer to
        SKILL.md.  It must stay under 250 chars."""
        pytest.importorskip("dspy")
        from evals.optimizers.dspy.reference_routing import (
            ReferenceRoutingSignature,
        )

        doc = ReferenceRoutingSignature.__doc__ or ""
        assert "SKILL.md" in doc or "Reference" in doc
        assert len(doc) <= 250, f"docstring is {len(doc)} chars"

    def test_canonical_inventory_matches_references_dir(self) -> None:
        refs_dir = PACKAGE_ROOT / "references"
        actual = {p.stem for p in refs_dir.glob("*.md")}
        canonical = set(REFERENCE_NAMES) - {"none"}
        assert actual == canonical, (
            f"references/ inventory drifted from REFERENCE_NAMES; "
            f"only in references/: {actual - canonical}, "
            f"only in REFERENCE_NAMES: {canonical - actual}"
        )


# ---------------------------------------------------------------------------
# Metric primitives
# ---------------------------------------------------------------------------


class TestResolveReference:
    def test_valid_reference_passes_through(self) -> None:
        assert _resolve_reference("bounties") == "bounties"

    def test_none_passes_through(self) -> None:
        assert _resolve_reference("none") == "none"

    def test_unknown_string_becomes_empty(self) -> None:
        assert _resolve_reference("creator-flow") == ""

    def test_strips_trailing_period(self) -> None:
        assert _resolve_reference("bounties.") == "bounties"

    def test_non_string_becomes_empty(self) -> None:
        assert _resolve_reference(None) == ""
        assert _resolve_reference(42) == ""


class TestClassify:
    def test_exact_match(self) -> None:
        f = _classify("none", "none")
        assert f.kind == ReferenceRoutingFinding.EXACT

    def test_false_positive(self) -> None:
        f = _classify("none", "admin-operations")
        assert f.kind == ReferenceRoutingFinding.FALSE_POSITIVE
        assert "none" in f.message

    def test_false_negative(self) -> None:
        f = _classify("bounties", "none")
        assert f.kind == ReferenceRoutingFinding.FALSE_NEGATIVE
        assert "bounties" in f.message

    def test_wrong_named(self) -> None:
        f = _classify("bounties", "admin-operations")
        assert f.kind == ReferenceRoutingFinding.WRONG_NAMED

    def test_invalid_prediction(self) -> None:
        f = _classify("bounties", "")
        assert f.kind == ReferenceRoutingFinding.INVALID


# ---------------------------------------------------------------------------
# Metric scoring
# ---------------------------------------------------------------------------


def _example(reference: str) -> SimpleNamespace:
    return SimpleNamespace(reference=reference)


def _prediction(reference: str) -> SimpleNamespace:
    return SimpleNamespace(reference=reference)


class TestReferenceRoutingMetricScoring:
    def test_exact_match_perfect_score(self) -> None:
        m = ReferenceRoutingMetric()
        gold = _example("bounties")
        pred = _prediction("bounties")
        score, finding = m.evaluate_with_finding(gold, pred)
        assert score == 1.0
        assert finding.kind == ReferenceRoutingFinding.EXACT

    def test_false_positive_scores_zero(self) -> None:
        m = ReferenceRoutingMetric()
        score, _ = m.evaluate_with_finding(
            _example("none"), _prediction("admin-operations")
        )
        assert score == 0.0

    def test_false_negative_scores_zero(self) -> None:
        m = ReferenceRoutingMetric()
        score, _ = m.evaluate_with_finding(
            _example("bounties"), _prediction("none")
        )
        assert score == 0.0

    def test_wrong_named_scores_partial(self) -> None:
        m = ReferenceRoutingMetric()
        score, _ = m.evaluate_with_finding(
            _example("bounties"), _prediction("admin-operations")
        )
        assert score == pytest.approx(0.2)

    def test_default_factor_is_one(self) -> None:
        m = ReferenceRoutingMetric()
        assert m._policy_token_factor == 1.0

    def test_token_factor_drops_with_bloated_instructions(self) -> None:
        m = ReferenceRoutingMetric(program_instructions="x" * 10000)
        # 10000 chars / 4 = 2500 tokens >> ceiling 1800.
        assert m._policy_token_factor == 0.0

    def test_token_factor_multiplies_final_score(self) -> None:
        m = ReferenceRoutingMetric(program_instructions="x" * 4000)
        # 4000 / 4 = 1000 tok; between target=800 and ceiling=1800.
        assert 0.0 < m._policy_token_factor < 1.0
        final = m(_example("bounties"), _prediction("bounties"), trace=None)
        assert isinstance(final, float)
        assert final == pytest.approx(m._policy_token_factor)

    def test_gepa_signature_returns_score_with_feedback(self) -> None:
        m = ReferenceRoutingMetric()
        out = m(
            _example("none"),
            _prediction("admin-operations"),
            trace=None,
            pred_name="predictor",
            pred_trace=None,
        )
        assert isinstance(out, dict)
        assert {"score", "feedback"} <= out.keys()
        assert out["score"] == 0.0
        assert "admin-operations" in out["feedback"]


# ---------------------------------------------------------------------------
# Aggregate rates
# ---------------------------------------------------------------------------


class TestAggregateRates:
    def _findings(
        self, pairs: list[tuple[str, str]]
    ) -> list[ReferenceRoutingFinding]:
        return [_classify(g, p) for g, p in pairs]

    def test_empty_none_class_gives_zero_fp(self) -> None:
        rates = aggregate_rates(self._findings([("bounties", "bounties")]))
        assert rates["false_positive_rate_on_none"] == 0.0

    def test_fp_rate_on_none(self) -> None:
        rates = aggregate_rates(
            self._findings([
                ("none", "none"),
                ("none", "admin-operations"),
                ("none", "none"),
                ("none", "bounties"),
            ])
        )
        assert rates["false_positive_rate_on_none"] == 0.5

    def test_fn_rate_on_named(self) -> None:
        rates = aggregate_rates(
            self._findings([
                ("bounties", "bounties"),
                ("bounties", "none"),
                ("admin-operations", "none"),
                ("admin-operations", "admin-operations"),
            ])
        )
        assert rates["false_negative_rate_on_named"] == 0.5

    def test_per_class_accuracy(self) -> None:
        rates = aggregate_rates(
            self._findings([
                ("none", "none"),
                ("none", "bounties"),
                ("bounties", "bounties"),
                ("bounties", "bounties"),
            ])
        )
        assert rates["per_class_accuracy"]["none"] == 0.5
        assert rates["per_class_accuracy"]["bounties"] == 1.0


# ---------------------------------------------------------------------------
# Scenarios YAML
# ---------------------------------------------------------------------------


def _load_scenarios() -> list[dict[str, Any]]:
    data = yaml.safe_load(SCENARIOS_PATH.read_text(encoding="utf-8"))
    return data["scenarios"]


class TestScenarioInventory:
    def test_yaml_parses(self) -> None:
        scenarios = _load_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) >= 36

    def test_every_gold_reference_is_canonical(self) -> None:
        for s in _load_scenarios():
            assert s["gold_reference"] in REFERENCE_NAMES, (
                f"{s['id']}: gold_reference={s['gold_reference']!r} "
                "is not in canonical inventory"
            )

    def test_every_id_is_unique(self) -> None:
        ids = [s["id"] for s in _load_scenarios()]
        assert len(ids) == len(set(ids))

    def test_distribution_per_class_meets_minimum(self) -> None:
        scenarios = _load_scenarios()
        counts: dict[str, int] = {}
        for s in scenarios:
            counts[s["gold_reference"]] = (
                counts.get(s["gold_reference"], 0) + 1
            )
        # Per plan §6: every named class has >= 3 scenarios, none has >= 10.
        assert counts.get("none", 0) >= 10
        for name in REFERENCE_NAMES:
            if name == "none":
                continue
            assert counts.get(name, 0) >= 3, (
                f"class {name!r} has fewer than 3 scenarios"
            )

    def test_every_recall_band_is_canonical(self) -> None:
        valid = {"HIGH", "MEDIUM", "LOW", "NONE"}
        for s in _load_scenarios():
            band = s.get("current_recall_band", "NONE")
            assert band in valid, f"{s['id']}: band {band!r} invalid"


# ---------------------------------------------------------------------------
# Renderer gates H, I, J
# ---------------------------------------------------------------------------


class TestRendererGateNoneFloor:
    def test_blocks_above_25pct_false_positive(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "false_positive_rate_on_none_avg": 0.40,
        }
        verdict, reasons = _verdict(report)
        assert verdict == "do not promote"
        assert any("NONE_FLOOR" in r for r in reasons)

    def test_does_not_block_at_25pct(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "false_positive_rate_on_none_avg": 0.25,
        }
        _, reasons = _verdict(report)
        assert not any("NONE_FLOOR" in r for r in reasons)

    def test_does_not_fire_for_decision_policy_signature(self) -> None:
        # Decision-policy reports never carry this field; gate must not fire.
        report = {
            "delta": 0.1,
            "false_positive_rate_on_none_avg": 0.99,
        }
        _, reasons = _verdict(report)
        assert not any("NONE_FLOOR" in r for r in reasons)


class TestRendererGateSpecificityRegression:
    def test_blocks_on_growth_over_10pct(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "false_negative_rate_on_named_avg": 0.40,
            "baseline_false_negative_rate_on_named_avg": 0.20,
        }
        _, reasons = _verdict(report)
        assert any("SPECIFICITY_REGRESSION" in r for r in reasons)

    def test_does_not_block_on_improvement(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "false_negative_rate_on_named_avg": 0.10,
            "baseline_false_negative_rate_on_named_avg": 0.20,
        }
        _, reasons = _verdict(report)
        assert not any("SPECIFICITY_REGRESSION" in r for r in reasons)


class TestRendererGateInventoryMismatch:
    def test_blocks_on_invented_class(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": ["creator-flow"],
            "invalid_predictions": 1,
        }
        _, reasons = _verdict(report)
        assert any("REFERENCE_INVENTORY_MISMATCH" in r for r in reasons)

    def test_blocks_on_invalid_predictions_count(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": [],
            "invalid_predictions": 3,
        }
        _, reasons = _verdict(report)
        assert any("REFERENCE_INVENTORY_MISMATCH" in r for r in reasons)

    def test_does_not_block_when_clean(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": [],
            "invalid_predictions": 0,
        }
        _, reasons = _verdict(report)
        assert not any("REFERENCE_INVENTORY_MISMATCH" in r for r in reasons)


class TestRendererPromoteVerdictForReferenceRouting:
    def test_promotes_with_clean_report(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.05,
            "test_delta": 0.03,
            "baseline_program_tokens": 200,
            "optimized_program_tokens": 250,
            "policy_token_factor": 0.95,
            "routing_score_avg": 0.85,
            "final_score_avg": 0.82,
            "false_positive_rate_on_none_avg": 0.10,
            "false_negative_rate_on_named_avg": 0.10,
            "baseline_false_negative_rate_on_named_avg": 0.12,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": [],
            "invalid_predictions": 0,
        }
        verdict, reasons = _verdict(report)
        assert verdict == "promote", reasons


class TestRendererGateInventedReferenceName:
    """Gate K — instructions claim a reference that does not exist
    in the canonical inventory.  Catches the iter-N May 2026 GEPA
    failure where the proposal mentioned "the ``email`` reference"
    and "the ``video`` reference" — neither of which is a file
    under references/.
    """

    def test_blocks_on_backticked_invented_reference(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": [],
            "invalid_predictions": 0,
        }
        instructions = (
            "If the user is asking about inbox or emails, load the "
            "``email`` reference if the primary path does not cover it."
        )
        verdict, reasons = _verdict(report, instructions=instructions)
        assert verdict == "do not promote"
        assert any("INVENTED_REFERENCE_NAME" in r for r in reasons)
        assert any("'email'" in r for r in reasons)

    def test_blocks_on_iter_n_real_world_email_and_video(self) -> None:
        """Regression: the actual iter-N candidate text."""
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": [],
            "invalid_predictions": 0,
        }
        instructions = (
            "If the request is about email management and the "
            "installed capabilities include functions like reading, "
            "sending, or organizing emails, the ``email`` reference "
            "should be considered if the primary path does not "
            "cover these functions.\n"
            "If the request is about video editing or related "
            "capabilities, check if the installed capabilities "
            "include relevant functions. If they do, the primary "
            "path likely covers it; otherwise, consider loading "
            "the ``video`` reference."
        )
        verdict, reasons = _verdict(report, instructions=instructions)
        assert verdict == "do not promote"
        gate_reasons = [r for r in reasons if "INVENTED_REFERENCE_NAME" in r]
        assert len(gate_reasons) == 1
        # Both 'email' and 'video' should be reported.
        assert "'email'" in gate_reasons[0]
        assert "'video'" in gate_reasons[0]

    def test_does_not_block_on_canonical_reference_name(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": [],
            "invalid_predictions": 0,
        }
        instructions = (
            "If the user asks about admin operations, load the "
            "``admin-operations`` reference."
        )
        _, reasons = _verdict(report, instructions=instructions)
        assert not any("INVENTED_REFERENCE_NAME" in r for r in reasons)

    def test_handles_references_md_path(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": [],
            "invalid_predictions": 0,
        }
        instructions = (
            "Consider loading references/safety-and-approval.md "
            "for confirmation flows."
        )
        _, reasons = _verdict(report, instructions=instructions)
        assert any("INVENTED_REFERENCE_NAME" in r for r in reasons)
        assert any("'safety-and-approval'" in r for r in reasons)

    def test_does_not_fire_for_decision_policy_signature(self) -> None:
        # The decision-policy signature doesn't carry a
        # ``canonical_reference_names`` field; Gate K must not fire.
        report = {
            "delta": 0.1,
        }
        instructions = "Load the ``email`` reference when appropriate."
        _, reasons = _verdict(report, instructions=instructions)
        assert not any("INVENTED_REFERENCE_NAME" in r for r in reasons)

    def test_does_not_block_when_instructions_empty(self) -> None:
        report = {
            "signature": "reference_routing",
            "delta": 0.1,
            "canonical_reference_names": list(REFERENCE_NAMES),
            "invalid_classes": [],
            "invalid_predictions": 0,
        }
        _, reasons = _verdict(report, instructions="")
        assert not any("INVENTED_REFERENCE_NAME" in r for r in reasons)
