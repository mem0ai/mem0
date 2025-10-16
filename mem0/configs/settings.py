"""
Settings module for mem0 configuration management.
"""

from typing import Any, Dict

from mem0.configs.base import MemoryConfig


class Settings:
    """Settings class to manage configuration."""

    def __init__(self):
        """Initialize settings with default configuration."""
        self.config = {}
        self._memory_config = MemoryConfig()

    def configure(self, config: Dict[str, Any]) -> None:
        """
        Configure settings with provided configuration.

        Args:
            config: Dictionary containing configuration settings
        """
        self.config.update(config)

    @property
    def memory_config(self) -> MemoryConfig:
        """Get the memory configuration."""
        return self._memory_config

    @memory_config.setter
    def memory_config(self, config: MemoryConfig) -> None:
        """
        Set the memory configuration.

        Args:
            config: MemoryConfig instance
        """
        self._memory_config = config


# Create a singleton instance
settings = Settings()
