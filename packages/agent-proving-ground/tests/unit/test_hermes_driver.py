"""Unit tests for HermesDriver model/provider config."""

from __future__ import annotations

from logion_agent_proving_ground.drivers.hermes import HermesDriver


class TestHermesDriverEffectiveArgs:
    """Model and provider config in driver_config.hermes are forwarded as
    --model/--provider flags to the hermes CLI."""

    def test_model_and_provider_in_args(self) -> None:
        driver = HermesDriver(
            driver_config={
                "hermes": {
                    "model": "glm-5.1",
                    "provider": "ollama-cloud",
                }
            }
        )
        args = driver._effective_args()
        assert "--model" in args
        idx = args.index("--model")
        assert args[idx + 1] == "glm-5.1"
        assert "--provider" in args
        pidx = args.index("--provider")
        assert args[pidx + 1] == "ollama-cloud"

    def test_model_only(self) -> None:
        driver = HermesDriver(
            driver_config={"hermes": {"model": "anthropic/claude-sonnet-4"}}
        )
        args = driver._effective_args()
        assert "--model" in args
        assert "anthropic/claude-sonnet-4" in args
        assert "--provider" not in args

    def test_no_model_no_provider(self) -> None:
        driver = HermesDriver(driver_config={})
        args = driver._effective_args()
        assert "--model" not in args
        assert "--provider" not in args

    def test_extra_args_combined_with_model(self) -> None:
        driver = HermesDriver(
            driver_config={
                "hermes": {
                    "model": "glm-5.1",
                    "extra_args": [
                        "--skills",
                        "logion-agent-proving-ground-workflow",
                    ],
                }
            }
        )
        args = driver._effective_args()
        assert "--model" in args
        assert "glm-5.1" in args
        assert "--skills" in args

    def test_default_args_preserved_when_config_empty(self) -> None:
        driver = HermesDriver(driver_config={})
        args = driver._effective_args()
        assert "chat" in args
        assert "--cli" in args
        assert "--max-turns" in args
