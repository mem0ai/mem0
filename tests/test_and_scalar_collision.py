import pytest

from mem0.memory.main import AsyncMemory, Memory


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
def test_and_scalar_collision_preserves_both_values(memory_cls):
    memory = memory_cls.__new__(memory_cls)

    processed = memory._process_metadata_filters(
        {
            "user_id": "alice",
            "AND": [{"user_id": "bob"}],
        }
    )

    assert processed["$and"] == [
        {"user_id": "alice"},
        {"user_id": "bob"},
    ]


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
def test_and_scalar_collision_is_order_independent(memory_cls):
    memory = memory_cls.__new__(memory_cls)

    forward = memory._process_metadata_filters(
        {
            "user_id": "alice",
            "AND": [{"user_id": "bob"}],
        }
    )

    reversed_ = memory._process_metadata_filters(
        {
            "AND": [{"user_id": "bob"}],
            "user_id": "alice",
        }
    )

    assert forward == reversed_


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
def test_multiple_and_scalar_collisions_preserve_all_values(memory_cls):
    memory = memory_cls.__new__(memory_cls)

    processed = memory._process_metadata_filters(
        {
            "user_id": "alice",
            "AND": [
                {"user_id": "bob"},
                {"user_id": "charlie"},
            ],
        }
    )

    assert processed["$and"] == [
        {"user_id": "alice"},
        {"user_id": "bob"},
        {"user_id": "charlie"},
    ]


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
def test_operator_dicts_still_merge(memory_cls):
    memory = memory_cls.__new__(memory_cls)

    processed = memory._process_metadata_filters(
        {
            "price": {"gt": 10},
            "AND": [{"price": {"lt": 20}}],
        }
    )

    assert processed["price"] == {
        "gt": 10,
        "lt": 20,
    }


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
def test_non_colliding_and_filters_are_unchanged(memory_cls):
    memory = memory_cls.__new__(memory_cls)

    processed = memory._process_metadata_filters(
        {
            "user_id": "alice",
            "AND": [{"category": "work"}],
        }
    )

    assert processed == {
        "user_id": "alice",
        "category": "work",
    }
