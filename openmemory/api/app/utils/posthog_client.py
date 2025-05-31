"""
PostHog client for backend analytics tracking
"""
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from posthog import Posthog
    POSTHOG_AVAILABLE = True
except ImportError:
    POSTHOG_AVAILABLE = False

class PostHogClient:
    def __init__(self):
        self.posthog = None
        if POSTHOG_AVAILABLE:
            api_key = os.getenv('POSTHOG_API_KEY') or os.getenv('NEXT_PUBLIC_POSTHOG_KEY')
            host = os.getenv('POSTHOG_HOST') or os.getenv('NEXT_PUBLIC_POSTHOG_HOST', 'https://us.i.posthog.com')
            
            if api_key:
                self.posthog = Posthog(
                    project_api_key=api_key,
                    host=host
                )
                logger.info("PostHog client initialized successfully")
            else:
                logger.warning("PostHog API key not found in environment variables")
        else:
            logger.warning("PostHog package not installed, analytics tracking disabled")

    def capture(self, user_id: str, event: str, properties: Optional[Dict[str, Any]] = None):
        """Capture an event for analytics tracking"""
        if not self.posthog:
            return
        
        try:
            self.posthog.capture(
                distinct_id=user_id,
                event=event,
                properties=properties or {}
            )
        except Exception as e:
            logger.error(f"Failed to track event '{event}': {e}")

    def shutdown(self):
        """Shutdown the PostHog client"""
        if self.posthog:
            try:
                self.posthog.shutdown()
            except Exception as e:
                logger.error(f"Failed to shutdown PostHog client: {e}")

# Global instance
_posthog_client = None

def get_posthog_client() -> PostHogClient:
    """Get or create the global PostHog client instance"""
    global _posthog_client
    if _posthog_client is None:
        _posthog_client = PostHogClient()
    return _posthog_client 