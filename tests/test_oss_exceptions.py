"""Tests for OSS-specific structured exception classes.

This module tests the OSS-specific exception classes that extend the base
MemoryError for local memory operations, vector stores, graph stores, etc.
"""

import pytest

from mem0.exceptions import (
    VectorStoreError,
    GraphStoreError,
    EmbeddingError,
    LLMError,
    DatabaseError,
    DependencyError,
)


class TestOSSSpecificExceptions:
    """Test OSS-specific exception classes."""

    def test_vector_store_error(self):
        """Test VectorStoreError initialization and attributes."""
        error = VectorStoreError(
            message="Vector search failed",
            error_code="VECTOR_001",
            details={"operation": "search", "collection": "memories"},
            suggestion="Check your vector store configuration"
        )
        
        assert error.message == "Vector search failed"
        assert error.error_code == "VECTOR_001"
        assert error.details == {"operation": "search", "collection": "memories"}
        assert error.suggestion == "Check your vector store configuration"
        assert error.debug_info == {}

    def test_graph_store_error(self):
        """Test GraphStoreError initialization and attributes."""
        error = GraphStoreError(
            message="Graph relationship creation failed",
            error_code="GRAPH_001",
            details={"entity": "user_123", "relationship": "CONNECTED_TO"},
            suggestion="Check your graph store connection"
        )
        
        assert error.message == "Graph relationship creation failed"
        assert error.error_code == "GRAPH_001"
        assert error.details == {"entity": "user_123", "relationship": "CONNECTED_TO"}
        assert error.suggestion == "Check your graph store connection"

    def test_embedding_error(self):
        """Test EmbeddingError initialization and attributes."""
        error = EmbeddingError(
            message="Embedding generation failed",
            error_code="EMBED_001",
            details={"text_length": 1000, "model": "openai"},
            suggestion="Check your embedding model configuration"
        )
        
        assert error.message == "Embedding generation failed"
        assert error.error_code == "EMBED_001"
        assert error.details == {"text_length": 1000, "model": "openai"}
        assert error.suggestion == "Check your embedding model configuration"

    def test_llm_error(self):
        """Test LLMError initialization and attributes."""
        error = LLMError(
            message="LLM completion failed",
            error_code="LLM_001",
            details={"model": "gpt-4", "prompt_length": 500},
            suggestion="Check your LLM configuration and API key"
        )
        
        assert error.message == "LLM completion failed"
        assert error.error_code == "LLM_001"
        assert error.details == {"model": "gpt-4", "prompt_length": 500}
        assert error.suggestion == "Check your LLM configuration and API key"

    def test_database_error(self):
        """Test DatabaseError initialization and attributes."""
        error = DatabaseError(
            message="Database insert failed",
            error_code="DB_001",
            details={"operation": "insert", "table": "memories"},
            suggestion="Check your database configuration and connection"
        )
        
        assert error.message == "Database insert failed"
        assert error.error_code == "DB_001"
        assert error.details == {"operation": "insert", "table": "memories"}
        assert error.suggestion == "Check your database configuration and connection"

    def test_dependency_error(self):
        """Test DependencyError initialization and attributes."""
        error = DependencyError(
            message="Required dependency missing",
            error_code="DEPS_001",
            details={"package": "kuzu", "feature": "graph_store"},
            suggestion="Please install the required dependencies: pip install kuzu"
        )
        
        assert error.message == "Required dependency missing"
        assert error.error_code == "DEPS_001"
        assert error.details == {"package": "kuzu", "feature": "graph_store"}
        assert error.suggestion == "Please install the required dependencies: pip install kuzu"

    def test_oss_exception_inheritance(self):
        """Test that OSS exceptions inherit from MemoryError."""
        from mem0.exceptions import MemoryError
        
        exceptions = [
            VectorStoreError("test"),
            GraphStoreError("test"),
            EmbeddingError("test"),
            LLMError("test"),
            DatabaseError("test"),
            DependencyError("test"),
        ]
        
        for exc in exceptions:
            assert isinstance(exc, MemoryError)
            assert isinstance(exc, Exception)

    def test_oss_exception_repr(self):
        """Test string representation of OSS exceptions."""
        error = VectorStoreError(
            message="Test error",
            error_code="VECTOR_001",
            details={"test": "data"},
            suggestion="Test suggestion"
        )
        
        repr_str = repr(error)
        assert "VectorStoreError" in repr_str
        assert "Test error" in repr_str
        assert "VECTOR_001" in repr_str
        assert "Test suggestion" in repr_str


class TestOSSUsageExamples:
    """Test OSS exception usage examples from real scenarios."""

    def test_vector_store_search_failure(self):
        """Test vector store search failure scenario."""
        try:
            # Simulate vector store search failure
            raise VectorStoreError(
                message="Vector similarity search failed",
                error_code="VECTOR_SEARCH_001",
                details={
                    "operation": "search",
                    "collection": "memories",
                    "query_vector_dim": 1536,
                    "top_k": 10
                },
                suggestion="Check your vector store connection and collection exists",
                debug_info={"provider": "qdrant", "host": "localhost:6333"}
            )
        except VectorStoreError as e:
            assert e.error_code == "VECTOR_SEARCH_001"
            assert "similarity search" in e.message
            assert e.details["operation"] == "search"
            assert "connection" in e.suggestion

    def test_embedding_generation_failure(self):
        """Test embedding generation failure scenario."""
        try:
            # Simulate embedding generation failure
            raise EmbeddingError(
                message="Failed to generate embeddings for text",
                error_code="EMBED_GEN_001",
                details={
                    "text_length": 5000,
                    "model": "text-embedding-ada-002",
                    "provider": "openai"
                },
                suggestion="Check your OpenAI API key and model availability",
                debug_info={"rate_limit": False, "model_status": "active"}
            )
        except EmbeddingError as e:
            assert e.error_code == "EMBED_GEN_001"
            assert "embeddings" in e.message
            assert e.details["text_length"] == 5000
            assert "API key" in e.suggestion

    def test_dependency_missing_scenario(self):
        """Test missing dependency scenario."""
        try:
            # Simulate missing dependency
            raise DependencyError(
                message="Required package 'kuzu' is not installed",
                error_code="DEPS_MISSING_001",
                details={
                    "package": "kuzu",
                    "feature": "graph_store",
                    "required_version": ">=0.11.0"
                },
                suggestion="Install with: pip install kuzu>=0.11.0",
                debug_info={"installed_packages": ["mem0", "qdrant-client"]}
            )
        except DependencyError as e:
            assert e.error_code == "DEPS_MISSING_001"
            assert "kuzu" in e.message
            assert e.details["package"] == "kuzu"
            assert "pip install" in e.suggestion
