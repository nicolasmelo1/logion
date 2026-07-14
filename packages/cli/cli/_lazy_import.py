# SPDX-License-Identifier: MIT
"""Lazy module proxy for startup-sensitive imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any


class LazyModule:
    """Resolve module attributes only when first used."""

    def __init__(self, module_name: str) -> None:
        self._module_name = module_name

    def __getattr__(self, name: str) -> Any:
        module = import_module(self._module_name)
        return getattr(module, name)
