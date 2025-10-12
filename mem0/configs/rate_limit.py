"""
Rate limiting configuration and constants.
"""
from enum import Enum, auto
from typing import Any, Dict, Optional

class RateLimitScope(str, Enum):
    """Scopes for rate limiting.
    
    These scopes can be used to apply different rate limits to different
    types of operations or users.
    """
    # Global API rate limits
    API = "api"
    
    # Per-user rate limits
    USER = "user:{user_id}"  # Format with user_id
    
    # Per-project rate limits
    PROJECT = "project:{project_id}"  # Format with project_id
    
    # Specific operation rate limits
    MEMORY_ADD = "memory:add"
    MEMORY_GET = "memory:get"
    MEMORY_UPDATE = "memory:update"
    MEMORY_DELETE = "memory:delete"
    MEMORY_SEARCH = "memory:search"
    
    # Webhook specific limits
    WEBHOOK = "webhook:{webhook_id}"  # Format with webhook_id
    
    def format(self, **kwargs: Any) -> str:
        """Format the rate limit scope with the given parameters.
        
        Args:
            **kwargs: Parameters to format into the scope string
            
        Returns:
            Formatted scope string
        """
        return self.value.format(**kwargs)


class RateLimitTier(str, Enum):
    """Rate limit tiers for different user/plan levels."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# Default rate limits (requests per minute)
DEFAULT_RATE_LIMITS: Dict[RateLimitTier, Dict[RateLimitScope, int]] = {
    RateLimitTier.FREE: {
        RateLimitScope.API: 60,  # 60 RPM
        RateLimitScope.MEMORY_ADD: 30,
        RateLimitScope.MEMORY_GET: 120,
        RateLimitScope.MEMORY_UPDATE: 30,
        RateLimitScope.MEMORY_DELETE: 30,
        RateLimitScope.MEMORY_SEARCH: 60,
        RateLimitScope.WEBHOOK: 10,
    },
    RateLimitTier.BASIC: {
        RateLimitScope.API: 120,
        RateLimitScope.MEMORY_ADD: 60,
        RateLimitScope.MEMORY_GET: 240,
        RateLimitScope.MEMORY_UPDATE: 60,
        RateLimitScope.MEMORY_DELETE: 60,
        RateLimitScope.MEMORY_SEARCH: 120,
        RateLimitScope.WEBHOOK: 30,
    },
    RateLimitTier.PRO: {
        RateLimitScope.API: 300,
        RateLimitScope.MEMORY_ADD: 150,
        RateLimitScope.MEMORY_GET: 600,
        RateLimitScope.MEMORY_UPDATE: 150,
        RateLimitScope.MEMORY_DELETE: 150,
        RateLimitScope.MEMORY_SEARCH: 300,
        RateLimitScope.WEBHOOK: 100,
    },
    RateLimitTier.ENTERPRISE: {
        # Enterprise has very high limits by default
        RateLimitScope.API: 1000,
        RateLimitScope.MEMORY_ADD: 500,
        RateLimitScope.MEMORY_GET: 2000,
        RateLimitScope.MEMORY_UPDATE: 500,
        RateLimitScope.MEMORY_DELETE: 500,
        RateLimitScope.MEMORY_SEARCH: 1000,
        RateLimitScope.WEBHOOK: 500,
    },
}

# Default quotas (per day)
DEFAULT_QUOTAS: Dict[RateLimitTier, Dict[RateLimitScope, int]] = {
    RateLimitTier.FREE: {
        RateLimitScope.MEMORY_ADD: 1000,
        RateLimitScope.MEMORY_UPDATE: 1000,
        RateLimitScope.MEMORY_DELETE: 1000,
        RateLimitScope.MEMORY_SEARCH: 10000,
    },
    RateLimitTier.BASIC: {
        RateLimitScope.MEMORY_ADD: 10000,
        RateLimitScope.MEMORY_UPDATE: 10000,
        RateLimitScope.MEMORY_DELETE: 10000,
        RateLimitScope.MEMORY_SEARCH: 100000,
    },
    RateLimitTier.PRO: {
        RateLimitScope.MEMORY_ADD: 100000,
        RateLimitScope.MEMORY_UPDATE: 100000,
        RateLimitScope.MEMORY_DELETE: 100000,
        RateLimitScope.MEMORY_SEARCH: 1000000,
    },
    # Enterprise has no quotas by default
    RateLimitTier.ENTERPRISE: {},
}

def get_rate_limits(tier: RateLimitTier) -> Dict[RateLimitScope, int]:
    """Get rate limits for a specific tier.
    
    Args:
        tier: The rate limit tier
        
    Returns:
        Dictionary of rate limits for the tier
    """
    return DEFAULT_RATE_LIMITS.get(tier, DEFAULT_RATE_LIMITS[RateLimitTier.FREE])


def get_quota(tier: RateLimitTier, scope: RateLimitScope) -> Optional[int]:
    """Get quota for a specific tier and scope.
    
    Args:
        tier: The rate limit tier
        scope: The scope to get quota for
        
    Returns:
        Quota value or None if no quota is set
    """
    return DEFAULT_QUOTAS.get(tier, {}).get(scope)
