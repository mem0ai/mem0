import itertools

from mem0.memory.main import _build_session_scope, _escape_scope_value

DELIMITER_VALUES = [
    "u1",
    "r1",
    "a1",
    "%",
    "&",
    "=",
    "%25",
    "%26",
    "%3D",
    "a==",
    "a1&run_id=r1",
    "a1&user_id=u1",
    "r1&user_id=u1",
    "a1&run_id=r1&user_id=u1",
]


class TestBuildSessionScope:
    """Tests that _build_session_scope produces a unique key per id combination."""

    def test_ordinary_ids_produce_unchanged_scope_keys(self):
        """Ids without delimiter characters keep producing the pre-fix key format."""
        cases = [
            ({"user_id": "550e8400-e29b-41d4-a716-446655440000"}, "user_id=550e8400-e29b-41d4-a716-446655440000"),
            ({"agent_id": "agent.assistant:v2"}, "agent_id=agent.assistant:v2"),
            ({"run_id": "12345"}, "run_id=12345"),
            (
                {"user_id": "user@example.com", "agent_id": "support-bot"},
                "agent_id=support-bot&user_id=user@example.com",
            ),
            (
                {"user_id": "u1", "agent_id": "a1", "run_id": "r1"},
                "agent_id=a1&run_id=r1&user_id=u1",
            ),
        ]
        for filters, expected in cases:
            assert _build_session_scope(filters) == expected

    def test_ids_containing_delimiters_do_not_collide(self):
        """A value that embeds the join syntax no longer maps to the same key as the equivalent split filters."""
        collapsed_run = {"run_id": "proj-x&user_id=u1"}
        split_run = {"user_id": "u1", "run_id": "proj-x"}
        assert _build_session_scope(collapsed_run) != _build_session_scope(split_run)
        assert _build_session_scope(collapsed_run) == "run_id=proj-x%26user_id%3Du1"

        collapsed_agent = {"run_id": "proj-y&agent_id=a1"}
        split_agent = {"agent_id": "a1", "run_id": "proj-y"}
        assert _build_session_scope(collapsed_agent) != _build_session_scope(split_agent)

    def test_scope_keys_are_unique_per_filter_combination(self):
        """Every distinct filter dict built from delimiter-heavy id values maps to a distinct scope key."""
        keys = ["user_id", "agent_id", "run_id"]
        seen = {}
        for size in range(1, len(keys) + 1):
            for key_subset in itertools.combinations(keys, size):
                for combo in itertools.product(DELIMITER_VALUES, repeat=size):
                    filters = dict(zip(key_subset, combo))
                    scope = _build_session_scope(filters)
                    if scope in seen:
                        assert seen[scope] == filters, f"{seen[scope]} and {filters} both map to {scope!r}"
                    else:
                        seen[scope] = filters


class TestEscapeScopeValue:
    """Tests for the low-level per-value escaping helper."""

    def test_non_string_input_is_stringified(self):
        assert _escape_scope_value(42) == "42"

    def test_percent_is_escaped_before_other_delimiters(self):
        assert _escape_scope_value("%26") == "%2526"
        assert _escape_scope_value("%26") != "%26"

    def test_each_delimiter_is_escaped(self):
        assert _escape_scope_value("%") == "%25"
        assert _escape_scope_value("&") == "%26"
        assert _escape_scope_value("=") == "%3D"
