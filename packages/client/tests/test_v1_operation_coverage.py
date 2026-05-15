from __future__ import annotations

import importlib
import json
from pathlib import Path

from logion.v1._generated import operations
from logion.v1._operation_map import (
    IMPLEMENTED_OPERATIONS,
    UNSUPPORTED_OPERATIONS,
)

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "openapi" / "v1.json"
)


def _collect_operation_ids() -> set[str]:
    with CONTRACT_PATH.open() as f:
        spec = json.load(f)
    ids: set[str] = set()
    for path_item in spec.get("paths", {}).values():
        for method in (
            "get",
            "post",
            "put",
            "patch",
            "delete",
        ):
            operation = path_item.get(method)
            if operation and "operationId" in operation:
                ids.add(operation["operationId"])
    return ids


def test_no_overlap_between_dicts() -> None:
    overlap = set(IMPLEMENTED_OPERATIONS) & set(UNSUPPORTED_OPERATIONS)
    assert overlap == set(), f"Operation IDs in both dicts: {overlap}"


def test_every_operation_id_is_covered() -> None:
    contract_ids = _collect_operation_ids()
    mapped_ids = set(IMPLEMENTED_OPERATIONS) | set(UNSUPPORTED_OPERATIONS)
    missing = contract_ids - mapped_ids
    assert not missing, f"Operation IDs missing from map: {missing}"
    extra = mapped_ids - contract_ids
    assert not extra, f"Operation IDs in map but not in contract: {extra}"


def test_implemented_operations_point_to_real_methods() -> None:
    for op_id, dotpath in IMPLEMENTED_OPERATIONS.items():
        parts = dotpath.split(".")
        assert len(parts) == 4, (
            f"Unexpected dotpath format for {op_id}: {dotpath}"
        )
        resource_name = parts[2]
        method_name = parts[3]
        module = importlib.import_module(
            f"logion.v1._resources.{resource_name}"
        )
        # Methods live on the *Resource class, not the module.
        class_name = f"{_pascal(resource_name)}Resource"
        assert hasattr(module, class_name), (
            f"Module logion.v1._resources.{resource_name}"
            f" has no class {class_name}"
            f" (operationId: {op_id})"
        )
        resource_cls = getattr(module, class_name)
        assert hasattr(resource_cls, method_name), (
            f"Class {class_name} has no method"
            f" {method_name}"
            f" (operationId: {op_id})"
        )


def test_every_operation_id_has_generated_operation() -> None:
    for op_id in _collect_operation_ids():
        assert hasattr(operations, op_id), (
            f"Generated operations module has no function for {op_id}"
        )


def _pascal(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(part.capitalize() for part in snake.split("_"))


def test_unsupported_operations_is_empty_or_documented() -> None:
    assert UNSUPPORTED_OPERATIONS == {}, (
        f"Unsupported operations exist: {dict(UNSUPPORTED_OPERATIONS)}"
    )
