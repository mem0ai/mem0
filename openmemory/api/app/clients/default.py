from .claude import ClaudeProfile


class DefaultProfile(ClaudeProfile):
    """
    Default client profile for unknown or unspecified clients.
    Inherits from the ClaudeProfile to provide a safe, backward-compatible default.
    """
    pass 