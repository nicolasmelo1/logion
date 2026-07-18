"""Tests for the bundled indexer source registry."""

from logion_indexer.cli import _get_adapter
from logion_indexer.config import SeedFile
from logion_indexer.rate_limit import RateLimiter
from logion_indexer.transport import FakeTransport


def test_default_seed_uses_registered_catalog_adapters() -> None:
    seed = SeedFile.load(SeedFile.default_path())
    adapter_names = {source.adapter for source in seed.sources}

    assert {"skillsmp", "smithery"} <= adapter_names
    assert "hermes_docs" not in adapter_names

    transport = FakeTransport()
    limiter = RateLimiter(default_rps=0)
    for adapter_name in adapter_names:
        assert _get_adapter(adapter_name, transport, limiter) is not None
