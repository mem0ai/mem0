from typing import Optional
from abc import ABC, abstractmethod

from mem0.configs.llms.base import BaseLlmConfig


class LLMBase(ABC):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """Initialize a base LLM class

        :param config: LLM configuration option class, defaults to None
        :type config: Optional[BaseLlmConfig], optional
        """
        if config is None:
            self.config = BaseLlmConfig()
        else:
            self.config = config

    @abstractmethod
    def generate_response(self, messages):
        """
        Generate a response based on the given messages.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.

        Returns:
            str: The generated response.
        """
        pass
