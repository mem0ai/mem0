import pytest
from mem0.vector_stores.qdrant import Qdrant
from qdrant_client.http import models as rest

class MockQdrant(Qdrant):
    def __init__(self):
        # Bypass init to test _create_filter directly
        pass

@pytest.fixture
def qdrant_store():
    return MockQdrant()

def test_simple_kv_filter(qdrant_store):
    filters = {"user_id": "alice"}
    q_filter = qdrant_store._create_filter(filters)
    
    assert isinstance(q_filter, rest.Filter)
    assert len(q_filter.must) == 1
    assert q_filter.must[0].key == "user_id"
    assert q_filter.must[0].match.value == "alice"

def test_operator_eq(qdrant_store):
    filters = {"user_id": {"eq": "alice"}}
    q_filter = qdrant_store._create_filter(filters)
    
    assert len(q_filter.must) == 1
    assert q_filter.must[0].key == "user_id"
    assert q_filter.must[0].match.value == "alice"

def test_operator_ne(qdrant_store):
    filters = {"status": {"ne": "deleted"}}
    q_filter = qdrant_store._create_filter(filters)
    
    # "ne" usually maps to must_not match
    assert q_filter.must_not is not None
    assert len(q_filter.must_not) == 1
    assert q_filter.must_not[0].key == "status"
    assert q_filter.must_not[0].match.value == "deleted"

def test_operator_range(qdrant_store):
    filters = {"age": {"gt": 18, "lte": 30}}
    q_filter = qdrant_store._create_filter(filters)
    
    assert len(q_filter.must) == 1
    range_cond = qdrant_store._create_filter({"age": {"gt": 18}}).must[0].range
    # Note: Structure might vary depending on implementation (one Range object vs multiple)
    # Assuming standard behavior: separate conditions or unified range
    # Let's verify at least one range condition exists
    cond = q_filter.must[0]
    assert cond.key == "age"
    assert cond.range.gt == 18
    assert cond.range.lte == 30

def test_operator_in(qdrant_store):
    filters = {"tags": {"in": ["ai", "python"]}}
    q_filter = qdrant_store._create_filter(filters)
    
    assert len(q_filter.must) == 1
    assert q_filter.must[0].key == "tags"
    assert q_filter.must[0].match.any == ["ai", "python"]

def test_operator_nin(qdrant_store):
    filters = {"tags": {"nin": ["spam", "ads"]}}
    q_filter = qdrant_store._create_filter(filters)
    
    assert len(q_filter.must_not) == 1
    assert q_filter.must_not[0].key == "tags"
    assert q_filter.must_not[0].match.any == ["spam", "ads"]

def test_logical_or(qdrant_store):
    # OR: [{"role": "admin"}, {"status": "active"}]
    # Mem0 defined format for OR might be implicit list or strict key "$or" or "OR"
    # Based on memory/main.py logic, it might modify keys. 
    # But usually vector store receives filters directly. 
    # Assuming Mem0 convention for explicit OR is key "OR" or similar?
    # Wait, looking at memory/main.py _process_metadata_filters:
    # it maps standard operators but structure is passed.
    # Let's test standard Qdrant/Mongo style if applicable, or just assume input is what's passed.
    
    # According to `mem0/vector_stores/qdrant.py` current impl, it iterates `.items()`.
    # Let's implement support for a special key "OR" that takes a list of conditions.
    filters = {
        "OR": [
            {"role": "admin"},
            {"role": "editor"}
        ]
    }
    q_filter = qdrant_store._create_filter(filters)
    
    assert q_filter.should is not None
    assert len(q_filter.should) == 2
    # Since _create_filter returns a Filter object, the list contains nested Filters
    # Each nested Filter wraps the condition in its 'must' list
    assert isinstance(q_filter.should[0], rest.Filter)
    assert q_filter.should[0].must[0].key == "role"
    assert q_filter.should[0].must[0].match.value == "admin"
