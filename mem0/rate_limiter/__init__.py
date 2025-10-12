"""
Rate limiting and quota management for Mem0 API.

This module provides rate limiting functionality to control the rate of API requests
and enforce quotas for different types of operations.
"""
from __future__ import annotations

__all__ = [
    'RateLimiter',
    'RateLimitExceededError',
    'QuotaExceededError',
    'rate_limiter',
]

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from mem0.configs.rate_limit import RateLimitScope, RateLimitTier, get_rate_limits, get_quota


class RateLimitExceededError(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: float, limit: int, scope: str):
        self.retry_after = retry_after
        self.limit = limit
        self.scope = scope
        super().__init__(
            f"Rate limit exceeded for {scope}. Try again in {retry_after:.2f} seconds. Limit: {limit} requests per minute"
        )


class QuotaExceededError(Exception):
    """Exception raised when quota is exceeded."""

    def __init__(self, quota_type: str, limit: int, used: int, reset_time: datetime):
        self.quota_type = quota_type
        self.limit = limit
        self.used = used
        self.reset_time = reset_time
        super().__init__(
            f"{quota_type} quota exceeded. Used {used}/{limit}. Resets at {reset_time.isoformat()}"
        )


class RateLimiter:
    """Implements token bucket algorithm for rate limiting."""

    def __init__(
        self,
        default_rate: int = 60,  # requests per minute
        default_window: int = 60,  # seconds
        default_quota: Optional[int] = None,  # None means no quota
        quota_window: int = 86400,  # 24 hours in seconds
    ):
        """Initialize the rate limiter.

        Args:
            default_rate: Default number of requests allowed per window
            default_window: Default time window in seconds
            default_quota: Default quota (None for no quota)
            quota_window: Quota window in seconds (default: 24 hours)
        """
        self.default_rate = default_rate
        self.default_window = default_window
        self.default_quota = default_quota
        self.quota_window = quota_window

        # Track rate limits per scope
        self.rate_limits: Dict[str, List[float]] = defaultdict(list)
        # Track quotas per scope and window
        self.quotas: Dict[Tuple[str, int], Dict[str, int]] = {}
        # Rate limit configurations per scope
        self.rate_configs: Dict[str, Dict[str, int]] = {}
        # Quota configurations per scope
        self.quota_configs: Dict[str, Dict[str, int]] = {}

    def set_rate_limit(
        self, scope: str, rate: int, window: int = 60, quota: Optional[int] = None
    ) -> None:
        """Set rate limit configuration for a specific scope.

        Args:
            scope: Scope to apply rate limiting (e.g., 'api', 'user:123', 'project:456')
            rate: Number of requests allowed per window
            window: Time window in seconds
            quota: Optional quota (None for no quota)
        """
        self.rate_configs[scope] = {"rate": rate, "window": window}
        if quota is not None:
            self.quota_configs[scope] = {"quota": quota, "window": self.quota_window}

    def _get_rate_limit(self, scope: str) -> Tuple[int, int]:
        """Get rate limit configuration for a scope with fallback to default.

        Args:
            scope: Scope to get rate limit for

        Returns:
            Tuple of (rate, window)
        """
        if scope in self.rate_configs:
            config = self.rate_configs[scope]
            return config["rate"], config["window"]
        return self.default_rate, self.default_window

    def _get_quota(self, scope: str) -> Optional[int]:
        """Get quota configuration for a scope with fallback to default.

        Args:
            scope: Scope to get quota for

        Returns:
            Quota value or None if no quota
        """
        if scope in self.quota_configs:
            return self.quota_configs[scope]["quota"]
        return self.default_quota

    def _get_quota_window(self, scope: str) -> int:
        """Get quota window for a scope with fallback to default.

        Args:
            scope: Scope to get quota window for

        Returns:
            Quota window in seconds
        """
        if scope in self.quota_configs:
            return self.quota_configs[scope]["window"]
        return self.quota_window

    def _get_quota_key(self, scope: str) -> Tuple[str, int]:
        """Get the quota tracking key for a scope.

        Args:
            scope: Scope to get quota key for

        Returns:
            Tuple of (scope, window_start)
        """
        window_size = self._get_quota_window(scope)
        window_start = int(time.time() // window_size) * window_size
        return scope, window_start

    def check_rate_limit(self, scope: str) -> None:
        """Check if the request is allowed based on rate limits.

        Args:
            scope: Scope to check rate limit for

        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        rate, window = self._get_rate_limit(scope)
        now = time.time()
        
        # Clean up old timestamps
        self.rate_limits[scope] = [t for t in self.rate_limits[scope] if t > now - window]
        
        if len(self.rate_limits[scope]) >= rate:
            retry_after = (self.rate_limits[scope][0] + window) - now
            raise RateLimitExceededError(
                retry_after=retry_after,
                limit=rate,
                scope=scope,
            )
        
        self.rate_limits[scope].append(now)

    def check_quota(self, scope: str, amount: int = 1) -> None:
        """Check if the request is allowed based on quotas.

        Args:
            scope: Scope to check quota for
            amount: Amount to consume from quota (default: 1)

        Raises:
            QuotaExceededError: If quota is exceeded
        """
        quota = self._get_quota(scope)
        if quota is None:
            return  # No quota set for this scope

        key = self._get_quota_key(scope)
        if key not in self.quotas:
            self.quotas[key] = {"used": 0, "reset_time": datetime.fromtimestamp(key[1] + self._get_quota_window(scope))}
        
        if self.quotas[key]["used"] + amount > quota:
            raise QuotaExceededError(
                quota_type=scope,
                limit=quota,
                used=self.quotas[key]["used"],
                reset_time=self.quotas[key]["reset_time"],
            )
        
        self.quotas[key]["used"] += amount

    def check(self, scope: str, amount: int = 1) -> None:
        """Check both rate limit and quota for a scope.

        Args:
            scope: Scope to check
            amount: Amount to consume from quota (default: 1)

        Raises:
            RateLimitExceededError: If rate limit is exceeded
            QuotaExceededError: If quota is exceeded
        """
        self.check_rate_limit(scope)
        self.check_quota(scope, amount)

    def get_usage(self, scope: str) -> Dict[str, Any]:
        """Get current usage information for a scope.

        Args:
            scope: Scope to get usage for

        Returns:
            Dictionary with usage information
        """
        rate, window = self._get_rate_limit(scope)
        quota = self._get_quota(scope)
        
        now = time.time()
        current_rate = len([t for t in self.rate_limits.get(scope, []) if t > now - window])
        
        result = {
            "rate_limit": {
                "current": current_rate,
                "limit": rate,
                "window_seconds": window,
                "reset_in": (self.rate_limits[scope][0] + window - now) if self.rate_limits.get(scope) else 0,
            }
        }
        
        if quota is not None:
            key = self._get_quota_key(scope)
            used = self.quotas.get(key, {}).get("used", 0)
            reset_time = self.quotas.get(key, {}).get("reset_time", datetime.now() + timedelta(seconds=self.quota_window))
            
            result["quota"] = {
                "used": used,
                "limit": quota,
                "remaining": max(0, quota - used),
                "reset_time": reset_time.isoformat(),
                "reset_in": (reset_time - datetime.now()).total_seconds(),
            }
        
        return result
        
    def reset(self) -> None:
        """Reset all rate limit and quota tracking."""
        self.rate_limits.clear()
        self.quotas.clear()


# Global rate limiter instance
rate_limiter = RateLimiter()
