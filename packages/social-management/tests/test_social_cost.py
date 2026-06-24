"""Tests for cost estimation + spend ledger."""

from __future__ import annotations

import pytest

from social_management.core.errors import BudgetExceededError
from social_management.cost.constants import (
    POST_COST_CENTS,
    POST_WITH_LINK_COST_CENTS,
)
from social_management.cost.estimator import CostEstimator
from social_management.cost.ledger import SpendLedger
from social_management.x.models import CostEstimate


def test_estimate_no_link_is_post_cost() -> None:
    est = CostEstimator.estimate("hello world")
    assert est.cents == POST_COST_CENTS
    assert est.cents == 2
    assert est.has_link is False


def test_estimate_with_https_link_is_link_tax() -> None:
    est = CostEstimator.estimate("see https://logion.sh")
    assert est.cents == POST_WITH_LINK_COST_CENTS
    assert est.cents == 20
    assert est.has_link is True


def test_estimate_bare_domain_detected_as_link() -> None:
    est = CostEstimator.estimate("grab it at logion.sh today")
    assert est.has_link is True


def test_has_link_false_for_plain_text() -> None:
    assert CostEstimator.has_link("no urls here at all") is False


def test_ledger_records_and_accumulates(
    tmp_ledger: SpendLedger,
) -> None:
    tmp_ledger.record(CostEstimate(cents=2, has_link=False, reason="x"))
    tmp_ledger.record(CostEstimate(cents=2, has_link=False, reason="y"))
    assert tmp_ledger.month_to_date_cents() == 4


def test_budget_gate_raises_when_exceeded(
    tmp_ledger: SpendLedger,
) -> None:
    tmp_ledger.record(CostEstimate(cents=2, has_link=False, reason="seed"))
    estimate = CostEstimate(cents=20, has_link=True, reason="link post")
    with pytest.raises(BudgetExceededError) as exc_info:
        tmp_ledger.check_and_reserve(estimate, budget_cents=10)
    assert exc_info.value.budget_cents == 10
    assert exc_info.value.estimate_cents == 20


def test_budget_gate_passes_under_cap(
    tmp_ledger: SpendLedger,
) -> None:
    estimate = CostEstimate(cents=2, has_link=False, reason="cheap")
    # Should not raise.
    tmp_ledger.check_and_reserve(estimate, budget_cents=100)
