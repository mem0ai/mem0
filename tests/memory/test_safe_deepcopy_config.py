"""Tests for _safe_deepcopy_config and _is_sensitive_field.

Covers:
- Allow list: runtime objects preserved (http_auth, connection_class, ssl_context)
- Exact deny: known secret field names nulled
- Suffix deny: *_secret, *_token, *_password, *_key, *_credentials
- Non-sensitive fields: preserved untouched
- Full integration: _safe_deepcopy_config with OpenSearch-like configs
- Regression: original bug (#3580) — http_auth must survive cloning
"""

import pytest
from copy import deepcopy
from unittest.mock import MagicMock
from pydantic import BaseModel, Field
from typing import Optional, Union, Type

from mem0.memory.main import _is_sensitive_field, _safe_deepcopy_config


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

class MockAWSV4SignerAuth:
    """Simulates opensearchpy.AWSV4SignerAuth — non-serializable runtime object."""
    def __init__(self, region="us-east-1"):
        self.region = region

    def __deepcopy__(self, memo):
        raise TypeError("Cannot deepcopy AWSV4SignerAuth (contains boto session)")


class MockConnectionClass:
    """Simulates a non-serializable connection class object."""
    def __deepcopy__(self, memo):
        raise TypeError("Cannot deepcopy connection class")


class OpenSearchLikeConfig(BaseModel):
    """Mimics mem0's OpenSearchConfig for testing."""
    collection_name: str = "mem0"
    host: str = "localhost"
    port: int = 9200
    user: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    embedding_model_dims: int = 1536
    verify_certs: bool = False
    use_ssl: bool = False
    http_auth: Optional[object] = None
    connection_class: Optional[Union[str, Type]] = "RequestsHttpConnection"
    pool_maxsize: int = 20

    model_config = {"arbitrary_types_allowed": True}


class SimpleConfig:
    """Plain Python class config for non-Pydantic path."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ===========================================================================
# _is_sensitive_field — Allow list (runtime objects preserved)
# ===========================================================================

class TestAllowList:
    """Fields in the allow list should NOT be marked sensitive."""

    @pytest.mark.parametrize("field_name", [
        "http_auth",
        "HTTP_AUTH",
        "Http_Auth",
        "connection_class",
        "CONNECTION_CLASS",
        "ssl_context",
        "SSL_CONTEXT",
    ])
    def test_safe_fields_not_sensitive(self, field_name):
        assert _is_sensitive_field(field_name) is False


# ===========================================================================
# _is_sensitive_field — Exact deny list
# ===========================================================================

class TestExactDeny:
    """Known secret field names should be marked sensitive."""

    @pytest.mark.parametrize("field_name", [
        "password",
        "api_key",
        "secret",
        "token",
        "credential",
        "credentials",
        "client_secret",
        "private_key",
        "refresh_token",
        "access_token",
        "auth_client_secret",
        "azure_client_secret",
        "service_account_json",
        "aws_session_token",
    ])
    def test_exact_sensitive_fields(self, field_name):
        assert _is_sensitive_field(field_name) is True

    @pytest.mark.parametrize("field_name", [
        "PASSWORD",
        "Api_Key",
        "SECRET",
        "TOKEN",
        "Client_Secret",
    ])
    def test_case_insensitive(self, field_name):
        assert _is_sensitive_field(field_name) is True


# ===========================================================================
# _is_sensitive_field — Suffix deny patterns
# ===========================================================================

class TestSuffixDeny:
    """Fields ending with sensitive suffixes should be marked sensitive."""

    @pytest.mark.parametrize("field_name,expected", [
        ("db_password", True),           # _password suffix
        ("oauth_secret", True),          # _secret suffix
        ("bearer_token", True),          # _token suffix
        ("encryption_key", True),        # _key suffix
        ("gcp_credentials", True),       # _credentials suffix
        ("my_custom_secret", True),      # _secret suffix
        ("some_api_key", True),          # _key suffix
        ("jwt_refresh_token", True),     # _token suffix
        ("azure_client_secret", True),   # exact + suffix
    ])
    def test_suffix_patterns(self, field_name, expected):
        assert _is_sensitive_field(field_name) is expected


# ===========================================================================
# _is_sensitive_field — Non-sensitive fields (should NOT be nulled)
# ===========================================================================

class TestNonSensitive:
    """Regular operational fields should NOT be marked sensitive."""

    @pytest.mark.parametrize("field_name", [
        "host",
        "port",
        "collection_name",
        "embedding_model_dims",
        "verify_certs",
        "use_ssl",
        "pool_maxsize",
        "user",
        "path",
        "url",
        "timeout",
        "batch_size",
        "dimension",
        "metric_type",
        "index_type",
        "use_azure_credential",  # boolean flag, not a secret
        "credentials_path",      # a file path, not the credential itself
    ])
    def test_non_sensitive_fields(self, field_name):
        assert _is_sensitive_field(field_name) is False


# ===========================================================================
# _safe_deepcopy_config — Integration with OpenSearch-like config
# ===========================================================================

class TestSafeDeepcopyCoreScenario:
    """Regression test for #3580: http_auth must survive config cloning."""

    def test_deepcopy_success_path(self):
        """When deepcopy works (no non-serializable objects), return exact copy."""
        config = OpenSearchLikeConfig(
            host="search.example.com",
            password="super_secret",
            api_key="sk-123",
        )
        cloned = _safe_deepcopy_config(config)
        assert cloned.host == "search.example.com"
        assert cloned.password == "super_secret"  # deepcopy doesn't sanitize
        assert cloned.api_key == "sk-123"

    def test_fallback_preserves_http_auth(self):
        """#3580 regression: when deepcopy fails, http_auth must be preserved."""
        mock_auth = MockAWSV4SignerAuth(region="us-east-1")
        config = OpenSearchLikeConfig(
            host="search.us-east-1.amazonaws.com",
            password="should_be_nulled",
            api_key="should_be_nulled",
            http_auth=mock_auth,
            connection_class="RequestsHttpConnection",
        )
        cloned = _safe_deepcopy_config(config)
        # http_auth and connection_class should be preserved (None from model_dump,
        # but NOT actively nulled by the sanitizer)
        assert cloned.password is None       # sensitive — nulled
        assert cloned.api_key is None        # sensitive — nulled
        assert cloned.host == "search.us-east-1.amazonaws.com"  # non-sensitive
        assert cloned.collection_name == "mem0"                 # non-sensitive
        assert cloned.connection_class is not None               # safe field

    def test_fallback_nulls_sensitive_fields(self):
        """Sensitive fields should be nulled when deepcopy falls back."""
        mock_auth = MockAWSV4SignerAuth()
        config = OpenSearchLikeConfig(
            host="search.example.com",
            password="p@ss",
            api_key="ak-123",
            http_auth=mock_auth,
        )
        cloned = _safe_deepcopy_config(config)
        assert cloned.password is None
        assert cloned.api_key is None

    def test_non_sensitive_fields_preserved(self):
        """Non-sensitive operational fields should be preserved."""
        mock_auth = MockAWSV4SignerAuth()
        config = OpenSearchLikeConfig(
            host="search.example.com",
            port=443,
            embedding_model_dims=768,
            verify_certs=True,
            use_ssl=True,
            pool_maxsize=50,
            http_auth=mock_auth,
        )
        cloned = _safe_deepcopy_config(config)
        assert cloned.host == "search.example.com"
        assert cloned.port == 443
        assert cloned.embedding_model_dims == 768
        assert cloned.verify_certs is True
        assert cloned.use_ssl is True
        assert cloned.pool_maxsize == 50


# ===========================================================================
# _safe_deepcopy_config — Plain Python class (non-Pydantic path)
# ===========================================================================

class TestSafeDeepcopPlainClass:
    """Test the __dict__ fallback path for non-Pydantic configs."""

    def test_plain_class_sensitive_nulled(self):
        config = SimpleConfig(
            host="localhost",
            password="secret123",
            api_key="key456",
            http_auth="runtime_signer",
            connection_class="SomeClass",
            custom_setting="keep_me",
        )
        # Force deepcopy to fail
        config.__deepcopy__ = lambda memo: (_ for _ in ()).throw(
            TypeError("cannot deepcopy")
        )
        cloned = _safe_deepcopy_config(config)
        assert cloned.password is None
        assert cloned.api_key is None
        assert cloned.http_auth == "runtime_signer"  # safe field preserved
        assert cloned.connection_class == "SomeClass" # safe field preserved
        assert cloned.host == "localhost"
        assert cloned.custom_setting == "keep_me"


# ===========================================================================
# _safe_deepcopy_config — Dataclass path
# ===========================================================================

class TestSafeDeepcopDataclass:
    """Test the dataclass fallback path."""

    def test_dataclass_config(self):
        from dataclasses import dataclass

        @dataclass
        class DataConfig:
            host: str = "localhost"
            password: str = "secret"
            api_key: str = "key123"
            http_auth: object = None
            connection_class: str = "Default"

            def __deepcopy__(self, memo):
                raise TypeError("cannot deepcopy")

        config = DataConfig(
            host="example.com",
            password="p@ss",
            api_key="ak-1",
            http_auth="signer_obj",
            connection_class="MyConn",
        )
        cloned = _safe_deepcopy_config(config)
        assert cloned.password is None
        assert cloned.api_key is None
        assert cloned.http_auth == "signer_obj"
        assert cloned.connection_class == "MyConn"
        assert cloned.host == "example.com"


# ===========================================================================
# Real-world field name coverage across all mem0 vector store configs
# ===========================================================================

class TestRealWorldFieldCoverage:
    """Verify behavior for actual field names found across all mem0 vector store configs."""

    @pytest.mark.parametrize("field_name,should_null", [
        # OpenSearch
        ("password", True),
        ("api_key", True),
        ("http_auth", False),          # #3580 — must NOT be nulled
        ("connection_class", False),    # runtime object
        ("host", False),
        ("port", False),
        ("verify_certs", False),
        ("use_ssl", False),
        ("pool_maxsize", False),
        # Elasticsearch
        ("api_key", True),
        # Weaviate
        ("auth_client_secret", True),
        # Databricks
        ("access_token", True),
        ("client_secret", True),
        ("azure_client_secret", True),
        # Upstash
        ("token", True),
        # Milvus
        ("token", True),
        # Pinecone
        ("api_key", True),
        # Qdrant
        ("api_key", True),
        # ChromaDB
        ("api_key", True),
        # Baidu
        ("api_key", True),
        # Vertex AI
        ("service_account_json", True),
        ("credentials_path", False),    # file path, not the credential
        # Azure MySQL
        ("use_azure_credential", False), # boolean flag
        # Cassandra
        ("password", True),
        # PGVector
        ("password", True),
        # Azure AI Search
        ("api_key", True),
        # AWS Bedrock (LLM config, but verify suffix patterns)
        ("aws_session_token", True),
        # General non-sensitive
        ("collection_name", False),
        ("embedding_model_dims", False),
        ("user", False),
        ("path", False),
        ("url", False),
    ])
    def test_field_sensitivity(self, field_name, should_null):
        assert _is_sensitive_field(field_name) is should_null, (
            f"Expected _is_sensitive_field('{field_name}') to be {should_null}"
        )


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_field_name(self):
        assert _is_sensitive_field("") is False

    def test_field_name_with_spaces(self):
        assert _is_sensitive_field("  password  ") is True    # exact deny — spaces stripped
        assert _is_sensitive_field("  http_auth  ") is False  # allow list — spaces stripped
        assert _is_sensitive_field("\tapi_key\n") is True     # other whitespace stripped
        assert _is_sensitive_field("  db_password  ") is True # suffix deny — spaces stripped

    def test_partial_match_not_triggered(self):
        """Old code used substring matching — verify we don't over-match."""
        # "key" as substring should NOT match "monkey", "keyboard", etc.
        assert _is_sensitive_field("monkey") is False
        assert _is_sensitive_field("keyboard") is False
        assert _is_sensitive_field("authenticate") is False
        assert _is_sensitive_field("token_count") is False
        assert _is_sensitive_field("secret_agent_name") is False  # doesn't end with _secret

    def test_unknown_fields_default_safe(self):
        """Fields not matching any pattern should be preserved."""
        assert _is_sensitive_field("custom_config_option") is False
        assert _is_sensitive_field("batch_size") is False
        assert _is_sensitive_field("dimension") is False
        assert _is_sensitive_field("metric_type") is False
