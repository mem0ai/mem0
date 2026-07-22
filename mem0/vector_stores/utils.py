from typing import Any


def normalize_list_result(result: Any) -> list:
    """Normalize vector-store list results without discarding pagination metadata at the adapter boundary."""
    if result is None:
        return []
    if not isinstance(result, (list, tuple)):
        raise TypeError(f"Unsupported vector-store list result type: {type(result).__name__}")
    if not result:
        return []

    first = result[0]
    if isinstance(first, (list, tuple)):
        if len(result) > 2:
            raise TypeError(f"Malformed vector-store list result container: {type(result).__name__}")
        return list(first)

    if isinstance(result, tuple):
        raise TypeError("Malformed vector-store list result container: tuple")
    return list(result)
