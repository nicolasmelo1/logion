"""Configuration: env vars + seed-file loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class IndexerConfig:
    """Runtime configuration loaded from env vars and seed files.

    Env vars:
        LOGION_INDEXER_GITHUB_TOKEN: GitHub API token.
        LOGION_INDEXER_API_KEY: Logion admin API key.
        LOGION_BASE_URL: Base URL for the Logion API.
    """

    github_token: str = ""
    api_key: str = ""
    base_url: str = ""
    seed_file: str = ""
    user_agent: str = "logion-indexer/0.1 (+https://logion.sh)"
    rps: float = 1.0
    dry_run: bool = False
    limit: int | None = None
    only: str | None = None

    @classmethod
    def from_env(cls, **overrides: object) -> IndexerConfig:
        """Load config from environment variables."""
        github_token = overrides.get(
            "github_token", _env("LOGION_INDEXER_GITHUB_TOKEN")
        )
        api_key = overrides.get("api_key", _env("LOGION_INDEXER_API_KEY"))
        base_url = overrides.get("base_url", _env("LOGION_BASE_URL"))
        seed_file = overrides.get(
            "seed_file", _env("LOGION_INDEXER_SEED_FILE")
        )
        return cls(
            github_token=str(github_token) if github_token else "",
            api_key=str(api_key) if api_key else "",
            base_url=str(base_url) if base_url else "",
            seed_file=str(seed_file) if seed_file else "",
        )

    @property
    def api_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")
        return "https://api.logion.sh"

    def redact(self) -> dict[str, str]:
        """Return a safe dict for logging (secrets redacted)."""
        return {
            "github_token": _redact(self.github_token),
            "api_key": _redact(self.api_key),
            "base_url": self.base_url or "(unset)",
            "seed_file": self.seed_file or "(default)",
        }


def _redact(value: str) -> str:
    if not value:
        return "(unset)"
    if len(value) <= 4:
        return "***"
    return value[:2] + "***" + value[-2:]


@dataclass
class SeedSource:
    """A single seed entry from sources.yaml."""

    adapter: str
    target: str
    mode: str | None = None
    subpath: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> SeedSource:
        return cls(
            adapter=d["adapter"],
            target=d["target"],
            mode=d.get("mode"),
            subpath=d.get("subpath"),
        )


@dataclass
class SeedFile:
    """Parsed seed file."""

    version: int
    sources: list[SeedSource] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> SeedFile:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"seed file not found: {p}")
        if yaml is None:
            raise ImportError("pyyaml required to load seed files")
        data = yaml.safe_load(p.read_text())
        if not isinstance(data, dict):
            raise TypeError(f"invalid seed file: {p}")
        version = int(data.get("version", 0))
        raw_sources = data.get("sources", [])
        sources = [SeedSource.from_dict(s) for s in raw_sources]
        return cls(version=version, sources=sources)

    @classmethod
    def default_path(cls) -> Path:
        """Default seed file shipped with the package."""
        return Path(__file__).parent / "seeds" / "sources.yaml"
