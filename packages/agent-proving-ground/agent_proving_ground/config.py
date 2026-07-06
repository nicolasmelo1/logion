from __future__ import annotations

from pathlib import Path

DEFAULT_RUNS_ROOT = Path(".runs/proving-ground")
BUILTIN_SCENARIOS_ROOT = Path(__file__).parent / "scenarios" / "builtin"
SAFE_NAME_RE = r"^[a-zA-Z0-9_.-]+$"


class ProvingGroundError(Exception):
    pass


class InconclusiveRun(ProvingGroundError):
    pass


class AssertionFailure(ProvingGroundError):
    pass


class ValidationFailure(ProvingGroundError):
    pass
