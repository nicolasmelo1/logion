"""The 16.1 clean-workspace facts come from interpreter provenance."""

import importlib.util
from pathlib import Path


def _module():
    script = Path(__file__).parents[2] / "scripts" / "run_eval_evidence.py"
    spec = importlib.util.spec_from_file_location("run_eval_evidence", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checkout_visibility_uses_probe_paths(tmp_path: Path) -> None:
    module = _module()
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    assert module._checkout_visible(
        {"sys_path": [str(checkout / "package")]}, checkout
    )
    assert not module._checkout_visible(
        {"sys_path": [str(tmp_path / "venv")]}, checkout
    )
