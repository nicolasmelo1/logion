"""Regression tests for phase-16.1 role checks."""

from agent_proving_ground.assertions.evals import _check


def _fact(value: object) -> dict[str, object]:
    return {"ok": True, "value": value}


def test_role_scoped_expected_value_is_checked_per_role() -> None:
    facts: dict[str, object] = {
        "terminal_status": _fact({
            "run_one": "succeeded",
            "run_two": "succeeded",
        })
    }

    passed, _, errors = _check(
        facts,
        ("terminal_status",),
        {"terminal_status": "succeeded"},
        ("run_one", "run_two"),
    )

    assert passed is True
    assert errors == ""


def test_role_scoped_expected_value_rejects_one_bad_role() -> None:
    facts: dict[str, object] = {"http_status": _fact({"one": 422, "two": 500})}

    passed, _, errors = _check(
        facts, ("http_status",), {"http_status": 422}, ("one", "two")
    )

    assert passed is False
    assert errors == "http_status"
