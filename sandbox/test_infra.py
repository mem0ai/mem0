import pytest


def add(memory, text, **scope):
    return memory.add(text, infer=False, **scope)


def texts(result):
    return sorted(row["memory"] for row in result["results"])


def test_get_all_is_scoped_to_the_requested_user(memory):
    add(memory, "alice likes espresso", user_id="alice")
    add(memory, "bob likes tea", user_id="bob")

    assert texts(memory.get_all(filters={"user_id": "alice"})) == ["alice likes espresso"]


def test_search_does_not_leak_across_users(memory):
    add(memory, "alice likes espresso", user_id="alice")
    add(memory, "bob likes espresso", user_id="bob")

    result = memory.search("likes espresso", filters={"user_id": "alice"}, threshold=0.0)

    assert texts(result) == ["alice likes espresso"]


def test_get_all_is_scoped_to_the_requested_run(memory):
    add(memory, "session one note", user_id="alice", run_id="r1")
    add(memory, "session two note", user_id="alice", run_id="r2")

    assert texts(memory.get_all(filters={"user_id": "alice", "run_id": "r1"})) == ["session one note"]


def test_delete_all_conjoins_entity_filters(memory):
    """Audit P1's OSS twin: a run_id matching nothing must not wipe the whole user."""
    add(memory, "alice note one", user_id="alice")
    add(memory, "alice note two", user_id="alice")

    memory.delete_all(user_id="alice", run_id="run_that_does_not_exist")

    assert len(memory.get_all(filters={"user_id": "alice"})["results"]) == 2


def test_delete_all_removes_only_the_targeted_run(memory):
    add(memory, "keep this", user_id="alice", run_id="r1")
    add(memory, "delete this", user_id="alice", run_id="r2")

    memory.delete_all(user_id="alice", run_id="r2")

    assert texts(memory.get_all(filters={"user_id": "alice"})) == ["keep this"]


def test_update_metadata_does_not_overwrite_entity_ids(memory):
    memory_id = add(memory, "alice note", user_id="alice", run_id="r1")["results"][0]["id"]

    memory.update(memory_id, metadata={"user_id": "mallory", "topic": "coffee"})

    assert memory.get(memory_id)["user_id"] == "alice"
    assert texts(memory.get_all(filters={"user_id": "alice"})) == ["alice note"]


def test_reset_clears_every_memory(memory):
    add(memory, "alice note", user_id="alice")

    memory.reset()

    assert memory.get_all(filters={"user_id": "alice"})["results"] == []


def test_metadata_operator_filters_narrow_the_result_set(memory):
    add(memory, "cheap item", user_id="alice", metadata={"price": 5})
    add(memory, "pricey item", user_id="alice", metadata={"price": 50})

    assert texts(memory.get_all(filters={"user_id": "alice", "price": {"gte": 40}})) == ["pricey item"]


def seed_colors(memory):
    add(memory, "red note", user_id="alice", metadata={"color": "red"})
    add(memory, "blue note", user_id="alice", metadata={"color": "blue"})
    add(memory, "green note", user_id="alice", metadata={"color": "green"})
    return {"user_id": "alice", "OR": [{"color": "red"}, {"color": "blue"}]}


def test_or_filter_matches_either_branch_via_search(memory):
    filters = seed_colors(memory)

    assert texts(memory.search("note", filters=filters, threshold=0.0)) == ["blue note", "red note"]


@pytest.mark.xfail(
    reason="get_all() hands raw filters to vector_store.list() without the OR->$or normalisation "
    "search() applies; qdrant self-normalises, pgvector matches nothing"
)
def test_or_filter_matches_either_branch_via_get_all(memory):
    filters = seed_colors(memory)

    assert texts(memory.get_all(filters=filters)) == ["blue note", "red note"]


@pytest.mark.xfail(reason="audit O3: icontains maps to a case-sensitive MatchText on qdrant")
def test_icontains_is_case_insensitive(memory):
    add(memory, "deadline note", user_id="alice", metadata={"deadline": "today"})

    result = memory.get_all(filters={"user_id": "alice", "deadline": {"icontains": "TODAY"}})

    assert texts(result) == ["deadline note"]


@pytest.mark.xfail(reason="audit O4: wildcard is a no-op match-all on qdrant, not an existence check")
def test_wildcard_requires_the_field_to_exist(memory):
    add(memory, "has category", user_id="alice", metadata={"category": "work"})
    add(memory, "no category", user_id="alice")

    result = memory.get_all(filters={"user_id": "alice", "category": "*"})

    assert texts(result) == ["has category"]
