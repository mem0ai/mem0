import time
import pytest
from datetime import datetime, timedelta
from mem0.rate_limiter import RateLimiter, RateLimitExceededError, QuotaExceededError

class TestRateLimiter:
    def setup_method(self):
        """Create a fresh RateLimiter instance for each test."""
        self.limiter = RateLimiter()
        self.scope = "test_scope"
        
    def test_rate_limiting_basic(self):
        """Test basic rate limiting functionality."""
        # Set a rate limit of 2 requests per second
        self.limiter.set_rate_limit(self.scope, rate=2, window=1)
        
        # First two requests should succeed
        for _ in range(2):
            self.limiter.check_rate_limit(self.scope)
            
        # Third request should be rate limited
        with pytest.raises(RateLimitExceededError):
            self.limiter.check_rate_limit(self.scope)
            
        # After 1 second, should be able to make more requests
        time.sleep(1.1)
        self.limiter.check_rate_limit(self.scope)  # Should not raise
        
    def test_quota_enforcement(self):
        """Test that quotas are properly enforced."""
        # Set a quota of 3 requests per day
        self.limiter.set_rate_limit(self.scope, rate=10, window=1, quota=3)
        
        # First 3 requests should succeed
        for _ in range(3):
            self.limiter.check(self.scope)
            
        # Fourth request should exceed quota
        with pytest.raises(QuotaExceededError):
            self.limiter.check(self.scope)
            
    def test_quota_window(self):
        """Test that quota windows work correctly."""
        # Set a quota of 2 requests with a 1-second window
        self.limiter = RateLimiter(quota_window=1)  # 1 second window for testing
        self.limiter.set_rate_limit(self.scope, rate=10, window=1, quota=2)
        
        # Use up the quota
        self.limiter.check(self.scope)
        self.limiter.check(self.scope)
        
        # Should be over quota
        with pytest.raises(QuotaExceededError):
            self.limiter.check(self.scope)
            
        # After the window passes, should be able to make more requests
        time.sleep(1.1)
        self.limiter.check(self.scope)  # Should not raise
        
    def test_get_usage(self):
        """Test that get_usage returns correct information."""
        self.limiter.set_rate_limit(self.scope, rate=5, window=60, quota=10)
        
        # Make some requests
        for _ in range(3):
            self.limiter.check(self.scope)
            
        # Check usage
        usage = self.limiter.get_usage(self.scope)
        
        assert usage["rate_limit"]["current"] == 3
        assert usage["rate_limit"]["limit"] == 5
        assert usage["quota"]["used"] == 3
        assert usage["quota"]["limit"] == 10
        assert usage["quota"]["remaining"] == 7
