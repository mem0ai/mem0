"""Regression tests for CWE-89 fixes on PGVector, Azure MySQL, and Neptune Analytics.

Covers issue #4875: collection_name / filter-value interpolation that previously
allowed SQL / Cypher injection. These tests verify that:

1. Pydantic config validators reject collection_name values that aren't safe
   SQL/Cypher identifiers (the entry point that guards every downstream
   f-string interpolation of ``self.collection_name``).
2. The Neptune Analytics query builders produce parameterized Cypher and
   structured node filters instead of concatenating user-controlled values.
"""

import importlib.util

import pytest
from pydantic import ValidationError

from mem0.configs.vector_stores.azure_mysql import AzureMySQLConfig
from mem0.configs.vector_stores.neptune import NeptuneAnalyticsConfig
from mem0.configs.vector_stores.pgvector import PGVectorConfig

# A sampling of real-world injection payloads from the original issue report.
INJECTION_PAYLOADS = [
    "memories; DROP TABLE users; --",
    "memories` OR 1=1; --",
    "memories:Label {prop: 'val'}) DELETE n; --",
    "valid_name OR 1=1",
    "1_starts_with_digit",
    "has space",
    "",
]


class TestPGVectorConfigCollectionNameValidation:
    def test_accepts_valid_identifier(self):
        config = PGVectorConfig(
            collection_name="valid_name",
            user="user",
            password="password",
            host="localhost",
            port=5432,
        )
        assert config.collection_name == "valid_name"

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_rejects_injection_payload(self, payload):
        with pytest.raises(ValidationError, match="Invalid collection_name"):
            PGVectorConfig(
                collection_name=payload,
                user="user",
                password="password",
                host="localhost",
                port=5432,
            )


class TestAzureMySQLConfigCollectionNameValidation:
    def test_accepts_valid_identifier(self):
        config = AzureMySQLConfig(
            collection_name="valid_name",
            host="host",
            user="user",
            database="db",
            password="pw",
        )
        assert config.collection_name == "valid_name"

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_rejects_injection_payload(self, payload):
        with pytest.raises(ValidationError, match="Invalid collection_name"):
            AzureMySQLConfig(
                collection_name=payload,
                host="host",
                user="user",
                database="db",
                password="pw",
            )


class TestNeptuneAnalyticsConfigCollectionNameValidation:
    def test_accepts_valid_identifier(self):
        config = NeptuneAnalyticsConfig(collection_name="valid_name")
        assert config.collection_name == "valid_name"

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_rejects_injection_payload(self, payload):
        with pytest.raises(ValidationError, match="Invalid collection_name"):
            NeptuneAnalyticsConfig(collection_name=payload)


# The Neptune Analytics vector store module hard-raises on missing `langchain_aws`,
# so guard the query-builder tests with a skipif when the optional dep isn't present.
_HAS_LANGCHAIN_AWS = importlib.util.find_spec("langchain_aws") is not None


@pytest.mark.skipif(not _HAS_LANGCHAIN_AWS, reason="langchain_aws package not installed")
class TestNeptuneWhereClauseParameterization:
    def test_filters_are_parameterized(self):
        from mem0.vector_stores.neptune_analytics import NeptuneAnalyticsVector

        where_clause, params = NeptuneAnalyticsVector._get_where_clause({"user_id": "123", "agent_id": "abc"})

        assert "$filter_0" in where_clause
        assert "$filter_1" in where_clause
        assert params == {"filter_0": "123", "filter_1": "abc"}

    def test_injection_value_does_not_leak_into_clause(self):
        from mem0.vector_stores.neptune_analytics import NeptuneAnalyticsVector

        payload = "x' RETURN n UNION MATCH (m) DETACH DELETE m //"
        where_clause, params = NeptuneAnalyticsVector._get_where_clause({"user_id": payload})

        assert payload not in where_clause
        assert params["filter_0"] == payload

    def test_invalid_filter_key_is_skipped(self, caplog):
        from mem0.vector_stores.neptune_analytics import NeptuneAnalyticsVector

        with caplog.at_level("WARNING"):
            where_clause, params = NeptuneAnalyticsVector._get_where_clause({"user_id' OR 1=1 --": "val"})

        assert where_clause == ""
        assert params == {}
        assert any("Skipping invalid filter key" in m for m in caplog.messages)


@pytest.mark.skipif(not _HAS_LANGCHAIN_AWS, reason="langchain_aws package not installed")
class TestNeptuneNodeFilterClause:
    def test_single_filter_returns_equals_object(self):
        from mem0.vector_stores.neptune_analytics import NeptuneAnalyticsVector

        filter_obj = NeptuneAnalyticsVector._get_node_filter_clause({"user_id": "123"})
        assert filter_obj == {"equals": {"property": "user_id", "value": "123"}}

    def test_multiple_filters_combine_with_and_all(self):
        from mem0.vector_stores.neptune_analytics import NeptuneAnalyticsVector

        filter_obj = NeptuneAnalyticsVector._get_node_filter_clause({"user_id": "123", "agent_id": "456"})
        assert "andAll" in filter_obj
        assert len(filter_obj["andAll"]) == 2

    def test_invalid_filter_key_is_skipped(self):
        from mem0.vector_stores.neptune_analytics import NeptuneAnalyticsVector

        filter_obj = NeptuneAnalyticsVector._get_node_filter_clause({"user_id' OR 1=1 --": "val"})
        assert filter_obj == {}
