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


def test_seed_only_prepares_non_secret_consumer_inputs(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        module, "_compose", lambda _repo, *args: calls.append(args)
    )

    module._seed(tmp_path, module.REPO_ROOT)

    prepared = tmp_path / "prepared"
    assert (prepared / "contract.json").is_file()
    assert (prepared / "subject.json").is_file()
    launcher = (prepared / "run-eval-flow.sh").read_text(encoding="utf-8")
    fixture = (
        module.REPO_ROOT
        / "packages/agent-proving-ground/scripts/eval_flow_launcher.sh"
    ).read_text(encoding="utf-8")
    assert launcher == fixture
    assert "logion-node eval validate" in launcher
    assert launcher.count("logion-node eval run") == 2
    assert "logion-node eval compare" in launcher
    assert "LOGION_PROVING_GROUND_ROLE_KEYS_FILE" not in launcher
    assert calls[0][:4] == ("exec", "-T", "consumer", "sh")
    assert calls[1][0] == "cp"
