"""Regression test for Redis advanced filter translation (#6550)."""

from unittest.mock import MagicMock

from mem0.vector_stores.redis import RedisDB


class _FilterExpression:
    """Small redisvl filter stand-in that makes the generated query inspectable."""

    def __init__(self, value):
        self.value = value

    def __and__(self, other):
        return _FilterExpression(("and", self.value, other.value))

    def __or__(self, other):
        return _FilterExpression(("or", self.value, other.value))


class _Tag:
    def __init__(self, field):
        self.field = field

    def __eq__(self, value):
        return _FilterExpression(("tag_eq", self.field, value))


class _Num:
    def __init__(self, field):
        self.field = field

    def __ge__(self, value):
        return _FilterExpression(("num_gte", self.field, value))


def test_issue_6550(monkeypatch):
    """Redis search must translate operator dicts and $or instead of tag-matching them."""
    import mem0.vector_stores.redis as redis_module

    captured = {}

    class CapturingVectorQuery:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(redis_module, "Tag", _Tag)
    monkeypatch.setattr(redis_module, "Num", _Num, raising=False)
    monkeypatch.setattr(redis_module, "VectorQuery", CapturingVectorQuery)

    db = RedisDB.__new__(RedisDB)
    db.index = MagicMock()
    db.index.query.return_value = []

    assert db.search(
        "query",
        [0.1, 0.2],
        filters={
            "age": {"gte": 18},
            "$or": [{"user_id": "alice"}, {"user_id": "bob"}],
        },
    ) == []

    assert captured["filter_expression"].value == (
        "and",
        ("num_gte", "age", 18),
        ("or", ("tag_eq", "user_id", "alice"), ("tag_eq", "user_id", "bob")),
    )
