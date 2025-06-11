from typing import Any, Optional


def merge_metadata_dict(left: Optional[dict[str, Any]], right: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """
    Merge the metadatas of two BaseMessage types.

    Args:
        left (dict[str, Any]): metadata of human message
        right (dict[str, Any]): metadata of AI message

    Returns:
        dict[str, Any]: combined metadata dict with dedup
        to be saved in db.
    """
    if not left and not right:
        return None
    elif not left:
        return right
    elif not right:
        return left

    merged = left.copy()
    for k, v in right.items():
        if k not in merged:
            merged[k] = v
        elif type(merged[k]) is not type(v):
            raise ValueError(f'additional_kwargs["{k}"] already exists in this message,' " but with a different type.")
        elif isinstance(merged[k], str):
            merged[k] += v
        elif isinstance(merged[k], dict):
            merged[k] = merge_metadata_dict(merged[k], v)
        else:
            raise ValueError(f"Additional kwargs key {k} already exists in this message.")
    return merged
