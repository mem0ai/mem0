"""Tests for _safe_deepcopy_config and _is_sensitive_field (Issue #3580).

Validates that runtime auth objects (http_auth, connection_class, etc.) are
preserved while genuinely sensitive fields (password, api_key, etc.) are
redacted during config cloning for telemetry.
"""

import threading
from dataclasses import dataclass

import pytest

from mem0.memory.main import _is_sensitive_field, _safe_deepcopy_config


# ---------------------------------------------------------------------------
# _is_sensitive_field tests
# ---------------------------------------------------------------------------


class TestRuntimeFieldsPreserved:
    """Runtime/allowlist fields must NOT be considered sensitive."""

    @pytest.mark.parametrize("field", [
        "http_auth",
        "auth",
        "connection_class",
        "ssl_context",
    ])
    def test_runtime_fields_are_not_sensitive(self, field):
        assert _is_sensitive_field(field) is False

    def test_runtime_fields_case_insensitive(self):
        assert _is_sensitive_field("HTTP_AUTH") is False
        assert _is_sensitive_field("Connection_Class") is False


class TestExactDenyList:
    """Known secret field names must be redacted."""

    @pytest.mark.parametrize("field", [
        "api_key",
        "secret_key",
        "private_key",
        "access_key",
        "password",
        "credentials",
        "credential",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "session_token",
        "client_secret",
        "auth_client_secret",
        "azure_client_secret",
        "service_account_json",
        "aws_session_token",
    ])
    def test_exact_sensitive_fields(self, field):
        assert _is_sensitive_field(field) is True

    def test_exact_fields_case_insensitive(self):
        assert _is_sensitive_field("API_KEY") is True
        assert _is_sensitive_field("Password") is True


class TestSuffixDenyList:
    """Fields ending with sensitive suffixes must be redacted."""

    @pytest.mark.parametrize("field", [
        "db_password",
        "user_password",
        "redis_password",
        "app_secret",
        "client_secret",
        "oauth_token",
        "bearer_token",
        "aws_credential",
        "gcp_credentials",
    ])
    def test_suffix_matches(self, field):
        assert _is_sensitive_field(field) is True


class TestNonSensitiveFields:
    """Common config fields that must NOT be redacted."""

    @pytest.mark.parametrize("field", [
        "host",
        "port",
        "collection_name",
        "embedding_model_dims",
        "use_ssl",
        "verify_certs",
        "index_name",
        "dimension",
        "metric",
        "path",
        "url",
        "timeout",
        "pool_maxsize",
    ])
    def test_common_config_fields(self, field):
        assert _is_sensitive_field(field) is False


class TestOverMatchingPrevention:
    """Fields that previously matched due to broad substring matching
    but should NOT be redacted."""

    @pytest.mark.parametrize("field", [
        "primary_key",       # contains "key" but is a DB concept
        "partition_key",     # contains "key" but is a DB concept
        "shard_key",         # contains "key" but is a DB concept
        "token_type",        # contains "token" but is metadata
        "token_count",       # contains "token" but is a count
        "tokenizer",         # contains "token" but is a tool name
        "key_space",         # contains "key" but is a namespace
        "keyboard",          # contains "key" but is unrelated
        "monkey",            # contains "key" but is unrelated
        "authenticate",      # contains "auth" but is a verb
        "authorization_url", # contains "auth" but is a URL
        "credentials_path",  # contains "credential" but is a file path
        "secret_agent_name", # contains "secret" but is not a suffix match
    ])
    def test_no_over_matching(self, field):
        assert _is_sensitive_field(field) is False


class TestEdgeCases:
    def test_empty_string(self):
        assert _is_sensitive_field("") is False

    def test_whitespace_stripped(self):
        assert _is_sensitive_field("  api_key  ") is True
        assert _is_sensitive_field("  http_auth  ") is False


class TestRealWorldFieldCoverage:
    """Verify behavior for actual field names from mem0 vector store configs."""

    @pytest.mark.parametrize("field,expected", [
        # OpenSearch
        ("password", True),
        ("api_key", True),
        ("http_auth", False),
        ("connection_class", False),
        ("host", False),
        ("port", False),
        ("verify_certs", False),
        ("use_ssl", False),
        ("pool_maxsize", False),
        # Weaviate
        ("auth_client_secret", True),
        # Databricks
        ("access_token", True),
        ("client_secret", True),
        ("azure_client_secret", True),
        # Upstash / Milvus
        ("token", True),
        # Vertex AI
        ("service_account_json", True),
        ("credentials_path", False),
        # AWS
        ("aws_session_token", True),
        # Azure MySQL
        ("use_azure_credential", True),
        # General non-sensitive
        ("collection_name", False),
        ("embedding_model_dims", False),
        ("user", False),
        ("path", False),
        ("url", False),
        ("dimension", False),
        ("metric_type", False),
        ("batch_size", False),
        ("index_type", False),
    ])
    def test_field_sensitivity(self, field, expected):
        assert _is_sensitive_field(field) is expected


# ---------------------------------------------------------------------------
# _safe_deepcopy_config integration tests
# ---------------------------------------------------------------------------


class MockNonCopyableAuth:
    """Simulates AWSV4SignerAuth which cannot be deep-copied due to thread locks."""

    def __init__(self):
        self._lock = threading.Lock()
        self.region = "us-east-1"

    def __deepcopy__(self, memo):
        raise TypeError("cannot pickle '_thread.lock' object")


class MockConnectionClass:

    def __init__(self):
        self._state = {"connected": False}

    def __deepcopy__(self, memo):
        raise TypeError("cannot pickle connection state")


class PlainConfig:
    """Config object using plain attributes (not Pydantic)."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestSafeDeepcopyClonesNormally:
    """When deepcopy succeeds, config is returned as-is (no sanitization)."""

    def test_deepcopy_success_returns_clone(self):
        config = PlainConfig(host="localhost", port=9200, password="super_secret")
        result = _safe_deepcopy_config(config)

        assert result is not config
        assert result.host == "localhost"
        assert result.port == 9200
        # deepcopy success path does not sanitize
        assert result.password == "super_secret"


class TestSafeDeepcopyCopiesWithAuth:
    """When deepcopy fails (auth objects), fallback preserves auth and redacts secrets."""

    def test_preserves_http_auth_and_connection_class(self):
        auth = MockNonCopyableAuth()
        conn = MockConnectionClass()
        config = PlainConfig(
            host="localhost",
            port=9200,
            http_auth=auth,
            connection_class=conn,
            api_key="secret123",
            password="hunter2",
            collection_name="test",
        )

        result = _safe_deepcopy_config(config)

        # Runtime objects preserved (not None)
        assert result.http_auth is not None
        assert result.connection_class is not None
        # Sensitive fields redacted
        assert result.api_key is None
        assert result.password is None
        # Normal fields preserved
        assert result.host == "localhost"
        assert result.port == 9200
        assert result.collection_name == "test"

    def test_preserves_auth_field(self):
        auth = MockNonCopyableAuth()
        config = PlainConfig(
            host="localhost",
            auth=auth,
            credentials={"key": "val"},
        )

        result = _safe_deepcopy_config(config)

        assert result.auth is not None
        assert result.credentials is None


class TestSafeDeepcopyWithPydantic:
    """Test fallback path with Pydantic-like model_dump objects."""

    def test_pydantic_like_config(self):
        class PydanticLikeConfig:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

            def model_dump(self, mode=None):
                return {k: v for k, v in self.__dict__.items()
                        if not k.startswith("_")}

            def __deepcopy__(self, memo):
                raise TypeError("cannot deepcopy")

        config = PydanticLikeConfig(
            host="localhost",
            api_key="secret",
            http_auth="signer_obj",
        )

        result = _safe_deepcopy_config(config)
        assert result.host == "localhost"
        assert result.api_key is None
        assert result.http_auth is not None


class TestSafeDeepcopyWithRealPydanticModel:
    """Test with real Pydantic BaseModel matching the OpenSearch config pattern.

    This validates the model_dump() path (without mode='json') preserves
    actual auth objects rather than losing them to JSON serialization.
    """

    def test_real_pydantic_model_preserves_auth_objects(self):
        from pydantic import BaseModel, Field
        from typing import Optional

        class OpenSearchLikeConfig(BaseModel):
            host: str = "localhost"
            port: int = 9200
            collection_name: str = "test"
            password: Optional[str] = None
            api_key: Optional[str] = None
            http_auth: Optional[object] = Field(None)
            connection_class: Optional[object] = Field(None)

        auth = MockNonCopyableAuth()
        conn = MockConnectionClass()
        config = OpenSearchLikeConfig(
            host="myhost",
            password="hunter2",
            api_key="sk-secret",
            http_auth=auth,
            connection_class=conn,
        )

        result = _safe_deepcopy_config(config)

        # Auth objects must be the actual objects, not string representations
        assert result.http_auth is auth
        assert result.connection_class is conn
        # Sensitive fields must be redacted
        assert result.password is None
        assert result.api_key is None
        # Normal fields preserved
        assert result.host == "myhost"
        assert result.port == 9200


class TestSafeDeepcopyWithDataclass:
    """Test fallback path with dataclasses."""

    def test_dataclass_config(self):
        @dataclass
        class DCConfig:
            host: str = "localhost"
            api_key: str = None
            db_password: str = None
            http_auth: object = None

            def __deepcopy__(self, memo):
                raise TypeError("cannot deepcopy")

        config = DCConfig(
            host="myhost",
            api_key="secret",
            db_password="pass123",
            http_auth="auth_obj",
        )

        result = _safe_deepcopy_config(config)
        assert result.host == "myhost"
        assert result.api_key is None
        assert result.db_password is None
        assert result.http_auth is not None
