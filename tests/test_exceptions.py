"""Tests for the structured exception classes in mem0.exceptions.

This module provides comprehensive tests for all exception classes,
including their attributes, inheritance, and the HTTP response mapping functionality.
"""

import json
import pytest
from unittest.mock import Mock

from mem0.exceptions import (
    MemoryError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    MemoryNotFoundError,
    NetworkError,
    ConfigurationError,
    MemoryQuotaExceededError,
    MemoryCorruptionError,
    VectorSearchError,
    CacheError,
    HTTP_STATUS_TO_EXCEPTION,
    create_exception_from_response,
)


class TestMemoryError:
    """Test the base MemoryError exception class."""
    
    def test_basic_initialization(self):
        """Test basic exception initialization."""
        error = MemoryError("Test message", "TEST_001")
        
        assert error.message == "Test message"
        assert error.error_code == "TEST_001"
        assert error.details == {}
        assert error.suggestion is None
        assert error.debug_info == {}
        assert str(error) == "Test message"
    
    def test_full_initialization(self):
        """Test exception initialization with all parameters."""
        details = {"user_id": "user123", "operation": "add"}
        debug_info = {"request_id": "req456", "timestamp": "2024-01-01"}
        
        error = MemoryError(
            message="Test message",
            error_code="TEST_001",
            details=details,
            suggestion="Please try again",
            debug_info=debug_info,
        )
        
        assert error.message == "Test message"
        assert error.error_code == "TEST_001"
        assert error.details == details
        assert error.suggestion == "Please try again"
        assert error.debug_info == debug_info
    
    def test_repr(self):
        """Test string representation."""
        error = MemoryError("Test", "TEST_001", {"key": "value"})
        repr_str = repr(error)
        
        assert "MemoryError" in repr_str
        assert "Test" in repr_str
        assert "TEST_001" in repr_str
        assert "key" in repr_str
    
    def test_inheritance(self):
        """Test that MemoryError inherits from Exception."""
        error = MemoryError("Test", "TEST_001")
        assert isinstance(error, Exception)


class TestSpecificExceptions:
    """Test all specific exception subclasses."""
    
    @pytest.mark.parametrize("exception_class", [
        AuthenticationError,
        RateLimitError,
        ValidationError,
        MemoryNotFoundError,
        NetworkError,
        ConfigurationError,
        MemoryQuotaExceededError,
        MemoryCorruptionError,
        VectorSearchError,
        CacheError,
    ])
    def test_exception_inheritance(self, exception_class):
        """Test that all specific exceptions inherit from MemoryError."""
        error = exception_class("Test message", "TEST_001")
        assert isinstance(error, MemoryError)
        assert isinstance(error, Exception)
    
    def test_authentication_error(self):
        """Test AuthenticationError specific functionality."""
        error = AuthenticationError(
            message="Invalid API key",
            error_code="AUTH_001",
            suggestion="Please check your API key"
        )
        
        assert error.message == "Invalid API key"
        assert error.error_code == "AUTH_001"
        assert error.suggestion == "Please check your API key"
    
    def test_rate_limit_error_with_retry_info(self):
        """Test RateLimitError with retry information."""
        debug_info = {
            "retry_after": 60,
            "limit": 100,
            "remaining": 0,
            "reset_time": "2024-01-01T01:00:00Z"
        }
        
        error = RateLimitError(
            message="Rate limit exceeded",
            error_code="RATE_001",
            debug_info=debug_info
        )
        
        assert error.debug_info["retry_after"] == 60
        assert error.debug_info["limit"] == 100
        assert error.debug_info["remaining"] == 0
    
    def test_validation_error_with_field_info(self):
        """Test ValidationError with field information."""
        details = {
            "field": "user_id",
            "value": "",
            "expected": "non-empty string"
        }
        
        error = ValidationError(
            message="Invalid user_id",
            error_code="VAL_001",
            details=details
        )
        
        assert error.details["field"] == "user_id"
        assert error.details["value"] == ""
        assert error.details["expected"] == "non-empty string"


class TestHTTPStatusMapping:
    """Test HTTP status code to exception mapping."""
    
    def test_http_status_mapping_exists(self):
        """Test that HTTP_STATUS_TO_EXCEPTION mapping exists and is complete."""
        expected_mappings = {
            400: ValidationError,
            401: AuthenticationError,
            403: AuthenticationError,
            404: MemoryNotFoundError,
            408: NetworkError,
            409: ValidationError,
            413: MemoryQuotaExceededError,
            422: ValidationError,
            429: RateLimitError,
            500: MemoryError,
            502: NetworkError,
            503: NetworkError,
            504: NetworkError,
        }
        
        assert HTTP_STATUS_TO_EXCEPTION == expected_mappings
    
    @pytest.mark.parametrize("status_code,expected_exception", [
        (400, ValidationError),
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, MemoryNotFoundError),
        (408, NetworkError),
        (409, ValidationError),
        (413, MemoryQuotaExceededError),
        (422, ValidationError),
        (429, RateLimitError),
        (500, MemoryError),
        (502, NetworkError),
        (503, NetworkError),
        (504, NetworkError),
    ])
    def test_individual_status_mappings(self, status_code, expected_exception):
        """Test individual status code mappings."""
        assert HTTP_STATUS_TO_EXCEPTION[status_code] == expected_exception


class TestCreateExceptionFromResponse:
    """Test the create_exception_from_response function."""
    
    def test_create_exception_basic(self):
        """Test basic exception creation from response."""
        exception = create_exception_from_response(
            status_code=404,
            response_text="Memory not found"
        )
        
        assert isinstance(exception, MemoryNotFoundError)
        assert exception.message == "Memory not found"
        assert exception.error_code == "HTTP_404"
        assert "not found" in exception.suggestion
    
    def test_create_exception_with_custom_error_code(self):
        """Test exception creation with custom error code."""
        exception = create_exception_from_response(
            status_code=429,
            response_text="Rate limit exceeded",
            error_code="CUSTOM_RATE_001"
        )
        
        assert isinstance(exception, RateLimitError)
        assert exception.error_code == "CUSTOM_RATE_001"
    
    def test_create_exception_with_details_and_debug_info(self):
        """Test exception creation with additional details."""
        details = {"user_id": "user123"}
        debug_info = {"retry_after": 60}
        
        exception = create_exception_from_response(
            status_code=429,
            response_text="Rate limit exceeded",
            details=details,
            debug_info=debug_info
        )
        
        assert exception.details == details
        assert exception.debug_info == debug_info
    
    def test_create_exception_unknown_status_code(self):
        """Test exception creation for unknown status codes."""
        exception = create_exception_from_response(
            status_code=418,  # I'm a teapot
            response_text="I'm a teapot"
        )
        
        assert isinstance(exception, MemoryError)
        assert exception.error_code == "HTTP_418"
        assert "try again later" in exception.suggestion


class TestExceptionUsageExamples:
    """Test realistic usage examples of the exception classes."""
    
    def test_rate_limit_handling_example(self):
        """Test the rate limit handling example from the module docstring."""
        # Simulate a rate limit error as shown in the GitHub issue
        error = RateLimitError(
            message="Rate limit exceeded",
            error_code="RATE_001",
            debug_info={"retry_after": 60}
        )
        
        # Test the usage pattern from the issue
        retry_after = error.debug_info.get("retry_after", 60)
        assert retry_after == 60
    
    def test_quota_exceeded_handling_example(self):
        """Test the quota exceeded handling example from the GitHub issue."""
        error = MemoryQuotaExceededError(
            message="Memory quota exceeded",
            error_code="QUOTA_001",
            debug_info={"current_usage": 1000, "quota_limit": 1000}
        )
        
        # Test logging the error code as shown in the issue
        assert error.error_code == "QUOTA_001"
    
    def test_validation_error_handling_example(self):
        """Test the validation error handling example from the GitHub issue."""
        error = ValidationError(
            message="Invalid input",
            error_code="VAL_001",
            suggestion="Please check your input format"
        )
        
        # Test using the suggestion for HTTP responses as shown in the issue
        assert error.suggestion == "Please check your input format"


class TestBackwardCompatibility:
    """Test backward compatibility considerations."""
    
    def test_memory_error_can_be_caught_as_exception(self):
        """Test that MemoryError can be caught as a generic Exception."""
        error = MemoryError("Test", "TEST_001")
        
        try:
            raise error
        except Exception as e:
            assert isinstance(e, MemoryError)
            assert e.message == "Test"
    
    def test_specific_exceptions_can_be_caught_as_memory_error(self):
        """Test that specific exceptions can be caught as MemoryError."""
        error = ValidationError("Test", "VAL_001")
        
        try:
            raise error
        except MemoryError as e:
            assert isinstance(e, ValidationError)
            assert e.error_code == "VAL_001"