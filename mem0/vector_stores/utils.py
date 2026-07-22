from typing import Any
from uuid import UUID


def _is_supported_scroll_offset(offset: Any) -> bool:
    if offset is None or (isinstance(offset, (str, int, UUID)) and not isinstance(offset, bool)):
        return True

    descriptor = getattr(type(offset), "DESCRIPTOR", None)
    return getattr(descriptor, "full_name", None) == "qdrant.PointId"


def normalize_list_result(result: Any) -> list:
    """Normalize vector-store list results without discarding pagination metadata at the adapter boundary."""
    if result is None:
        return []
    if not isinstance(result, (list, tuple)):
        raise TypeError(f"Unsupported vector-store list result type: {type(result).__name__}")
    if not result:
        return []

    if isinstance(result, tuple):
        if len(result) == 1 and isinstance(result[0], (list, tuple)):
            return list(result[0])
        if len(result) == 2 and isinstance(result[0], (list, tuple)):
            offset = result[1]
            if _is_supported_scroll_offset(offset):
                return list(result[0])
        raise TypeError("Malformed vector-store list result container: tuple")

    if len(result) == 1 and isinstance(result[0], (list, tuple)):
        return list(result[0])
    if any(isinstance(item, (list, tuple)) for item in result):
        raise TypeError("Malformed vector-store list result container: list")
    return list(result)
