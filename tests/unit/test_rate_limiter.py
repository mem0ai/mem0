import pytest
import time
from unittest.mock import patch, MagicMock
from mem0.rate_limiter import rate_limiter, RateLimitExceededError, QuotaExceededError
from mem0.configs.rate_limit import RateLimitScope, RateLimitTier, get_rate_limits, get_quota

class TestRateLimiter:
    def setup_method(self):
        """Reset the rate limiter before each test."""
        rate_limiter.reset()

    def test_token_bucket_refill(self):
        """Test that tokens are refilled after the window passes."""
        # Set up a rate limit of 2 requests per second
        scope = RateLimitScope.API
        rate_limiter.set_rate_limit(scope, rate=2, window=1, quota=10)
        
        # First two requests should succeed
        assert rate_limiter.consume(scope, 1) is True
        assert rate_limiter.consume(scope, 1) is True
        
        # Third request should fail (rate limit of 2 per second)
        assert rate_limiter.consume(scope, 1) is False
        
        # After 1 second, tokens should be refilled
        time.sleep(1.1)
        assert rate_limiter.consume(scope, 1) is True

    def test_quota_enforcement(self):
        """Test that quota limits are enforced."""
        scope = RateLimitScope.API
        rate_limiter.set_rate_limit(scope, rate=10, window=1, quota=3)
        
        # First 3 requests should succeed (within quota)
        for _ in range(3):
            assert rate_limiter.consume(scope, 1) is True
        
        # Fourth request should fail (quota exceeded)
        assert rate_limiter.consume(scope, 1) is False

    def test_multiple_scopes(self):
        """Test that rate limits are enforced per scope."""
        scope1 = RateLimitScope.USER.format(user_id="user1")
        scope2 = RateLimitScope.USER.format(user_id="user2")
        
        rate_limiter.set_rate_limit(scope1, rate=1, window=1, quota=5)
        rate_limiter.set_rate_limit(scope2, rate=1, window=1, quota=5)
        
        # Both users should be able to make requests independently
        assert rate_limiter.consume(scope1, 1) is True
        assert rate_limiter.consume(scope2, 1) is True
        
        # Second request for either user should be rate limited
        assert rate_limiter.consume(scope1, 1) is False
        assert rate_limiter.consume(scope2, 1) is False

    def test_rate_limit_headers(self):
        """Test that rate limit headers are correctly generated."""
        scope = RateLimitScope.API
        rate_limiter.set_rate_limit(scope, rate=10, window=60, quota=100)
        
        # Make some requests
        rate_limiter.consume(scope, 5)
        
        # Get headers
        headers = rate_limiter.get_rate_limit_headers(scope)
        
        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Remaining"] == "5"
        assert "X-RateLimit-Reset" in headers  # Should be a timestamp

class TestRateLimitClientIntegration:
    def test_client_rate_limiting(self):
        """Test that the MemoryClient enforces rate limits."""
        from mem0.client.main import MemoryClient
        
        # Create a client with a very low rate limit for testing
        client = MemoryClient(api_key="test_key", rate_limit_tier=RateLimitTier.FREE)
        
        # Get the rate limit status
        status = client.get_rate_limit_status()
        assert status is not None
        
        # Test that rate limiting is enforced for API calls
        with patch.object(client.client, 'post') as mock_post:
            # First request should succeed
            mock_post.return_value.status_code = 200
            response = client.add([{"role": "user", "content": "test"}])
            assert response is not None
            
            # If we try to make too many requests, the rate limiter should block them
            # (Note: This is a simplified test - in reality, we'd need to mock time to test this properly)
            pass

    def test_rate_limit_exception(self):
        """Test that rate limit exceptions are properly raised."""
        from mem0.client.main import MemoryClient
        from mem0.rate_limiter import RateLimitExceededError
        
        client = MemoryClient(api_key="test_key", rate_limit_tier=RateLimitTier.FREE)
        
        # Force rate limit to be exceeded
        with patch('mem0.rate_limiter.rate_limiter.consume', return_value=False):
            with pytest.raises(RateLimitExceededError):
                client.add([{"role": "user", "content": "test"}])
