import os
import logging
from app.context import user_id_var, client_name_var

logger = logging.getLogger(__name__)

def track_tool_usage(tool_name: str, properties: dict = None):
    """
    Analytics tracking for tool usage.
    
    This function is a placeholder for a real analytics implementation (e.g., PostHog).
    It logs the event to the console for now.
    """
    # Only track if explicitly enabled via environment variable
    if not os.getenv('ENABLE_ANALYTICS', 'false').lower() == 'true':
        return
    
    try:
        from app.utils.posthog_client import get_posthog_client
        from datetime import datetime
        
        supa_uid = user_id_var.get(None)
        client_name = client_name_var.get(None)
        
        if supa_uid:
            posthog = get_posthog_client()
            
            # Create the event name
            event_name = f'mcp_core_{tool_name}' if not tool_name.startswith('chatgpt_') else f'mcp_{tool_name}'
            
            # Merge default properties with provided ones
            event_properties = {
                'tool_type': 'core_mcp',
                'source': 'mcp_server',
                'client_name': client_name,
                'timestamp': datetime.now().isoformat(),
                **(properties or {})
            }
            
            # Send to PostHog
            posthog.capture(
                user_id=supa_uid,
                event=event_name,
                properties=event_properties
            )
            
            logger.debug(f"Tracked tool usage: {event_name} for user {supa_uid}")
    except Exception:
        # Never let analytics break the main functionality
        pass 