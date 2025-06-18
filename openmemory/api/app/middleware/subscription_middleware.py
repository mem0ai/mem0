from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import User, SubscriptionTier
import datetime
import logging

logger = logging.getLogger(__name__)

class SubscriptionChecker:
    """Helper class to check subscription permissions"""
    
    @staticmethod
    def get_feature_benefits(feature_name: str) -> dict:
        """Get tailored messaging based on the feature being accessed"""
        feature_benefits = {
            "API key generation": {
                "title": "API Key Generation",
                "description": "Generate API keys to integrate Jean Memory into your applications and workflows.",
                "benefits": ["Unlimited API keys", "Full programmatic access", "Custom integrations", "Automated workflows"]
            },
            "API key management": {
                "title": "API Key Management",
                "description": "Create, view, and manage API keys for your applications.",
                "benefits": ["Multiple API keys", "Key management dashboard", "Security controls", "Usage monitoring"]
            },
            "metadata tagging": {
                "title": "Advanced Memory Organization", 
                "description": "Tag and categorize memories with custom metadata for better organization and retrieval.",
                "benefits": ["Custom tags & categories", "Advanced filtering", "Better organization", "Enhanced search"]
            },
            "advanced search": {
                "title": "Advanced Search",
                "description": "Search memories with advanced filters, metadata queries, and semantic understanding.",
                "benefits": ["Metadata-based filtering", "Advanced query syntax", "Faster results", "Smart categorization"]
            }
        }
        
        return feature_benefits.get(feature_name, {
            "title": "Pro Features",
            "description": f"Access {feature_name} and other advanced features with Jean Memory Pro.",
            "benefits": ["Unlimited API access", "Advanced search & filtering", "Custom metadata tagging", "Priority support"]
        })
    
    @staticmethod
    def check_pro_features(user: User, feature_name: str = "Pro feature"):
        """Check if user has access to Pro features"""
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Allow if user has Pro or Enterprise tier
        if user.subscription_tier in [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]:
            # Additional check: ensure subscription is still active
            if user.subscription_status == 'active':
                return True
            elif user.subscription_status in ['past_due']:
                # Grace period for past due
                logger.warning(f"User {user.email} accessing {feature_name} with past_due subscription")
                return True
            else:
                benefits = SubscriptionChecker.get_feature_benefits(feature_name)
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": "subscription_required",
                        "title": benefits["title"],
                        "message": f"Your subscription is {user.subscription_status}. Please reactivate your Pro subscription to continue.",
                        "description": benefits["description"],
                        "benefits": benefits["benefits"],
                        "action": {
                            "text": "Manage Subscription",
                            "url": "/pro"
                        },
                        "current_status": user.subscription_status
                    }
                )
        
        benefits = SubscriptionChecker.get_feature_benefits(feature_name)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "subscription_required",
                "title": benefits["title"],
                "message": f"This feature requires a Pro subscription.",
                "description": benefits["description"], 
                "benefits": benefits["benefits"],
                "action": {
                    "text": "Upgrade to Pro",
                    "url": "/pro"
                },
                "current_tier": user.subscription_tier.value if user.subscription_tier else "FREE"
            }
        )
    
    @staticmethod
    def check_enterprise_features(user: User, feature_name: str = "Enterprise feature"):
        """Check if user has access to Enterprise features"""
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        if user.subscription_tier != SubscriptionTier.ENTERPRISE:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "enterprise_required",
                    "title": "Enterprise Required",
                    "message": f"This feature requires an Enterprise subscription.",
                    "description": "Enterprise features include custom integrations, dedicated support, and team management.",
                    "benefits": [
                        "Unlimited API usage",
                        "Custom integrations", 
                        "Dedicated support",
                        "Team management",
                        "Custom deployment",
                        "SLA guarantees"
                    ],
                    "action": {
                        "text": "Contact Sales",
                        "url": "mailto:jonathan@jeantechnologies.com?subject=Enterprise Subscription Inquiry"
                    },
                    "current_tier": user.subscription_tier.value if user.subscription_tier else "FREE"
                }
            )
        
        return True
    
    @staticmethod
    def get_api_limits(user: User) -> dict:
        """Get API rate limits based on subscription tier"""
        if user.subscription_tier == SubscriptionTier.FREE:
            return {
                "requests_per_minute": 10,
                "requests_per_day": 100,
                "max_memories": 1000,
                "metadata_tagging": False,
                "advanced_search": False
            }
        elif user.subscription_tier == SubscriptionTier.PRO:
            return {
                "requests_per_minute": 100,
                "requests_per_day": 10000,
                "max_memories": float('inf'),
                "metadata_tagging": True,
                "advanced_search": True
            }
        else:  # Enterprise
            return {
                "requests_per_minute": float('inf'),
                "requests_per_day": float('inf'),
                "max_memories": float('inf'),
                "metadata_tagging": True,
                "advanced_search": True,
                "team_features": True
            }

# Decorator for Pro-only endpoints
def require_pro_subscription(feature_name: str = "this feature"):
    """Decorator to require Pro subscription for an endpoint"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract user from kwargs (assumes user is passed as dependency)
            user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    user = value
                    break
            
            SubscriptionChecker.check_pro_features(user, feature_name)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Decorator for Enterprise-only endpoints  
def require_enterprise_subscription(feature_name: str = "this feature"):
    """Decorator to require Enterprise subscription for an endpoint"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    user = value
                    break
            
            SubscriptionChecker.check_enterprise_features(user, feature_name)
            return func(*args, **kwargs)
        return wrapper
    return decorator 