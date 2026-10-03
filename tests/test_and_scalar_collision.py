"""Regression tests for scalar key collisions in AND filters (#7529).

`merge_filters` deep-merges when both sides are operator dicts (fixed in #4853) and
silently overwrites otherwise. So an `AND` condition naming a key that also appears as a
top-level scalar replaced it, and which value survived depended on dict insertion order:

    {"user_id": "alice", "category": "work", "AND": [{"category": "personal"}]}
      -> {"user_id": "alice", "category": "personal"}

    {"user_id": "alice", "AND": [{"category": "personal"}], "category": "work"}
      -> {"user_id": "alice", "category": "work"}

Same logical filter, two answers. The fix routes the collision into the `AND` list so every
condition reaches the vector store, which builds one `must` clause each.

Both `Memory` and `AsyncMemory` carry their own copy of the helper, so both are covered.
"""

from __future__ import annotations

import pytest

from mem0.memory.main import AsyncMemory, Memory


SCALAR_COLLISION = {
    "user_id": "alice",
    "category": "work",
    "AND": [{"category": "personal"}],
}
SCALAR_COLLISION_REVERSED = {
    "user_id": "alice",
    "AND": [{"category": "personal"}],
    "category": "work",
}


def _memory() -> Memory:
    """A Memory with no store: _process_metadata_filters never touches one."""
    return Memory.__new__(Memory)


def _async_memory() -> AsyncMemory:
    return AsyncMemory.__new__(AsyncMemory)


@pytest.mark.parametrize("owner", [_memory, _async_memory])
def test_and_condition_does_not_overwrite_a_sibling_scalar(owner):
    """Both conditions survive, instead of one replacing the other."""
    processed = owner()._process_metadata_filters(SCALAR_COLLISION)

    # The scalar no longer sits at the top level: both values move into $and, which the
    # vector store expands into one `must` clause each. Neither is lost.
    assert "category" not in processed
    assert processed["$and"] == [{"category": "work"}, {"category": "personal"}]
    assert processed["user_id"] == "alice"


@pytest.mark.parametrize("owner", [_memory, _async_memory])
def test_the_surviving_value_does_not_depend_on_dict_order(owner):
    """The same logical filter gives the same answer whichever order it was written in."""
    forward = owner()._process_metadata_filters(SCALAR_COLLISION)
    reversed_ = owner()._process_metadata_filters(SCALAR_COLLISION_REVERSED)

    # Both conditions are present in both orders; only their sequence differs, and a
    # conjunction is order-independent.
    assert sorted(map(str, forward["$and"])) == sorted(map(str, reversed_["$and"]))
    assert forward["user_id"] == reversed_["user_id"] == "alice"


@pytest.mark.parametrize("owner", [_memory, _async_memory])
def test_operator_dicts_still_deep_merge(owner):
    """#4853's operator-dict merge is unchanged — this fix only touches scalars."""
    processed = owner()._process_metadata_filters(
        {"user_id": "alice", "price": {"gt": 10}, "AND": [{"price": {"lt": 20}}]}
    )

    assert processed["price"] == {"gt": 10, "lt": 20}


@pytest.mark.parametrize("owner", [_memory, _async_memory])
def test_a_key_present_only_in_one_place_is_untouched(owner):
    """The common case must not grow a redundant $and wrapper."""
    processed = owner()._process_metadata_filters(
        {"user_id": "alice", "category": "work", "AND": [{"priority": {"gt": 3}}]}
    )

    assert processed["category"] == "work"
    assert "$and" not in processed
    assert processed["priority"] == {"gt": 3}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
