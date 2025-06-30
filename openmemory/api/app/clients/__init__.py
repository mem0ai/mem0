from .base import BaseClientProfile
from .claude import ClaudeProfile
from .chatgpt import ChatGPTProfile
from .api import APIProfile
from .chorus import ChorusProfile
from .default import DefaultProfile

# Client profile mapping
_client_profiles = {
    "claude": ClaudeProfile(),
    "chatgpt": ChatGPTProfile(),
    "api": APIProfile(),
    "chorus": ChorusProfile(),
    "default": DefaultProfile(),
}

def get_client_name(client_name_from_header: str, is_api_key_path: bool) -> str:
    """Determines the profile to use based on client name and auth method."""
    if is_api_key_path:
        return "api"
    
    # Normalize client names for robustness
    normalized_client = client_name_from_header.lower()
    
    if "claude" in normalized_client:
        return "claude"
    if "chatgpt" in normalized_client:
        return "chatgpt"
    if "chorus" in normalized_client:
        return "chorus"

    return "default"


def get_client_profile(client_name_key: str) -> BaseClientProfile:
    """Factory function to get the correct client profile instance."""
    return _client_profiles.get(client_name_key, _client_profiles["default"]) 