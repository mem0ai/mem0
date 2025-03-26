from abc import ABC, abstractmethod
from typing import Dict, List, Optional

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
    def generate_response(self, messages, tools: Optional[List[Dict]] = None, tool_choice: str = "auto"):
        """
        Generate a response based on the given messages.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        pass
