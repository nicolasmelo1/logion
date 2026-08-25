# SPDX-License-Identifier: MIT
"""Unit tests for the generated-model postprocessor.

``test_generated_model_extras.py`` checks the committed output. It cannot
catch a transform that fails on generator output we do not have yet, which
is how a closed request body carrying a class docstring got through: the
contract that introduced one lives in another repository, so the break
surfaced in the private sync job instead of here.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "postprocess_models.py"
)
_spec = importlib.util.spec_from_file_location("postprocess_models", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
postprocess_models = importlib.util.module_from_spec(_spec)
sys.modules["postprocess_models"] = postprocess_models
_spec.loader.exec_module(postprocess_models)

forbid_extra = postprocess_models.forbid_extra
_closed_request_models = postprocess_models._closed_request_models


def _model(
    name: str, *, docstring: str | None = None, quote: str = '"'
) -> str:
    body = f'    """\n    {docstring}\n    """\n\n' if docstring else ""
    return (
        f"class {name}(BaseModel):\n"
        f"{body}"
        f"    model_config = ConfigDict(\n"
        f"        extra={quote}allow{quote},\n"
        f"    )\n"
        f"    field: str\n"
    )


def test_rewrites_a_model_without_a_docstring() -> None:
    out = forbid_extra(_model("Closed"), {"Closed"})
    assert 'extra="forbid"' in out


def test_rewrites_a_model_with_a_docstring() -> None:
    """``--use-schema-description`` pushes ``model_config`` down the body."""
    out = forbid_extra(_model("Closed", docstring="Explained."), {"Closed"})
    assert 'extra="forbid"' in out


def test_rewrites_a_model_emitted_with_single_quotes() -> None:
    out = forbid_extra(_model("Closed", quote="'"), {"Closed"})
    assert "extra='forbid'" in out


def test_leaves_models_outside_the_closed_set_alone() -> None:
    source = _model("Closed") + "\n\n" + _model("Open")
    out = forbid_extra(source, {"Closed"})
    assert out.count('extra="forbid"') == 1
    assert out.count('extra="allow"') == 1


def test_fails_loudly_rather_than_rewriting_the_next_class() -> None:
    """The guard on the docstring skip.

    A model with no ``model_config`` must raise, not silently close the
    following model. An unbounded skip matches the next class instead and
    reports a successful rewrite of the wrong one.
    """
    source = "class Closed(BaseModel):\n    field: str\n\n\n" + _model("Other")
    with pytest.raises(SystemExit, match="found 0"):
        forbid_extra(source, {"Closed"})


def test_closed_request_models_reads_only_request_bodies(
    tmp_path: Path,
) -> None:
    """A closed *response* schema stays permissive in the client."""

    def body(name: str) -> dict:
        ref = {"$ref": f"#/components/schemas/{name}"}
        return {"content": {"application/json": {"schema": ref}}}

    spec = {
        "paths": {
            "/thing": {
                "post": {
                    "requestBody": body("ClosedReq"),
                    "responses": {"200": body("ClosedRes")},
                }
            }
        },
        "components": {
            "schemas": {
                "ClosedReq": {"additionalProperties": False},
                "ClosedRes": {"additionalProperties": False},
                "OpenReq": {"additionalProperties": True},
            }
        },
    }
    path = tmp_path / "v1.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    assert _closed_request_models(path) == {"ClosedReq"}
