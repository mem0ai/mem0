"""Tests for the updated client utils with structured exception handling.

This module tests the api_error_handler decorator and its integration
with the new structured exception classes.
"""

import json
import pytest
from unittest.mock import Mock, patch
import httpx

from mem0.client.utils import api_error_handler, APIError
from mem0.exceptions import (
    MemoryError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    MemoryNotFoundError,
    NetworkError,
    MemoryQuotaExceededError,
)


class TestAPIErrorHandler:
    """Test the updated api_error_handler decorator."""
    
    def test_successful_request(self):
        """Test that successful requests pass through unchanged."""
        @api_error_handler
        def mock_function():
            return {"success": True}
        
        result = mock_function()
        assert result == {"success": True}
    
    def test_http_status_error_with_json_response(self):
        """Test HTTP status error with JSON response."""
        mock_request = Mock()
        mock_request.url = "https://api.mem0.ai/test"
        mock_request.method = "POST"
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = '{"detail": "Invalid request data", "field": "user_id"}'
        mock_response.headers = {"content-type": "application/json"}
        
        error = httpx.HTTPStatusError("Bad Request", request=mock_request, response=mock_response)
        
        @api_error_handler
        def mock_function():
            raise error
        
        with pytest.raises(ValidationError) as exc_info:
            mock_function()
        
        exception = exc_info.value
        assert exception.message == "Invalid request data"
        assert exception.debug_info["status_code"] == 400
        assert exception.debug_info["url"] == "https://api.mem0.ai/test"
        assert exception.debug_info["method"] == "POST"
        assert exception.details["field"] == "user_id"
    
    def test_rate_limit_error_with_retry_headers(self):
        """Test rate limit error with retry headers."""
        mock_request = Mock()
        mock_request.url = "https://api.mem0.ai/test"
        mock_request.method = "POST"
        
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_response.headers = {
            "content-type": "text/plain",
            "Retry-After": "60",
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1640995200"
        }
        
        error = httpx.HTTPStatusError("Too Many Requests", request=mock_request, response=mock_response)
        
        @api_error_handler
        def mock_function():
            raise error
        
        with pytest.raises(RateLimitError) as exc_info:
            mock_function()
        
        exception = exc_info.value
        assert exception.debug_info["retry_after"] == 60
        assert exception.debug_info["x_ratelimit_limit"] == "100"
        assert exception.debug_info["x_ratelimit_remaining"] == "0"
        assert exception.debug_info["x_ratelimit_reset"] == "1640995200"
    
    def test_timeout_error(self):
        """Test timeout error handling."""
        mock_request = Mock()
        mock_request.url = "https://api.mem0.ai/test"
        
        error = httpx.TimeoutException("Request timed out", request=mock_request)
        
        @api_error_handler
        def mock_function():
            raise error
        
        with pytest.raises(NetworkError) as exc_info:
            mock_function()
        
        exception = exc_info.value
        assert exception.error_code == "NET_TIMEOUT"
        assert "timed out" in exception.message
        assert exception.debug_info["error_type"] == "timeout"
    
    def test_connection_error(self):
        """Test connection error handling."""
        mock_request = Mock()
        mock_request.url = "https://api.mem0.ai/test"
        
        error = httpx.ConnectError("Connection failed", request=mock_request)
        
        @api_error_handler
        def mock_function():
            raise error
        
        with pytest.raises(NetworkError) as exc_info:
            mock_function()
        
        exception = exc_info.value
        assert exception.error_code == "NET_CONNECT"
        assert "Connection failed" in exception.message
        assert exception.debug_info["error_type"] == "connection"
    
    @pytest.mark.parametrize("status_code,expected_exception", [
        (400, ValidationError),
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, MemoryNotFoundError),
        (429, RateLimitError),
        (500, MemoryError),
        (502, NetworkError),
    ])
    def test_status_code_to_exception_mapping(self, status_code, expected_exception):
        """Test that different status codes map to correct exception types."""
        mock_request = Mock()
        mock_request.url = "https://api.mem0.ai/test"
        mock_request.method = "POST"
        
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.text = f"Error {status_code}"
        mock_response.headers = {"content-type": "text/plain"}
        
        error = httpx.HTTPStatusError(f"Error {status_code}", request=mock_request, response=mock_response)
        
        @api_error_handler
        def mock_function():
            raise error
        
        with pytest.raises(expected_exception):
            mock_function()


class TestBackwardCompatibility:
    """Test backward compatibility with existing APIError."""
    
    def test_api_error_still_exists(self):
        """Test that APIError class still exists for backward compatibility."""
        error = APIError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
    
    def test_api_error_docstring_indicates_deprecation(self):
        """Test that APIError docstring indicates deprecation."""
        assert "Deprecated" in APIError.__doc__
        assert "mem0.exceptions" in APIError.__doc__


class TestExamplesFromIssue:
    """Test the exact examples provided in the GitHub issue."""
    
    def test_rate_limit_example_from_issue(self):
        """Test the rate limit example exactly as shown in the GitHub issue."""
        # Create the error as it would be created by our api_error_handler
        error = RateLimitError(
            message="Rate limit exceeded",
            error_code="RATE_001",
            debug_info={"retry_after": 60}
        )
        
        # Test the exact pattern from the issue
        try:
            raise error
        except RateLimitError as e:
            # Implement exponential backoff (from the issue example)
            retry_after = e.debug_info.get('retry_after', 60)
            assert retry_after == 60
    
    def test_quota_exceeded_example_from_issue(self):
        """Test the quota exceeded example exactly as shown in the GitHub issue."""
        error = MemoryQuotaExceededError(
            message="Memory quota exceeded",
            error_code="QUOTA_001"
        )
        
        try:
            raise error
        except MemoryQuotaExceededError as e:
            # Trigger quota upgrade flow (from the issue example)
            assert e.error_code == "QUOTA_001"
    
    def test_validation_error_example_from_issue(self):
        """Test the validation error example exactly as shown in the GitHub issue."""
        error = ValidationError(
            message="Invalid input",
            error_code="VAL_001",
            suggestion="Please check your input format"
        )
        
        try:
            raise error
        except ValidationError as e:
            # Return user-friendly error (from the issue example)
            # In a real FastAPI app: raise HTTPException(400, detail=e.suggestion)
            assert e.suggestion == "Please check your input format"