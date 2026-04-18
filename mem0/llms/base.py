import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union

from mem0.configs.llms.base import BaseLlmConfig

# Reasoning models (OpenAI o-series and GPT-5 family) reject parameters like
# temperature. A substring check ("gpt-5" in name) misfires on model names
# such as "gpt-5.4-mini" that happen to share a prefix but support the full
# chat-completion parameter set. Match explicitly:
#   o1, o3, o4, o5 (with optional "-suffix" like -preview, -mini, -pro)
#   gpt-5 exactly, or gpt-5 followed by an alphabetic suffix (gpt-5o),
#     each optionally followed by "-suffix" (gpt-5-mini, gpt-5o-mini).
# A digit or "." after the core identifier breaks the match, so gpt-5.4-mini,
# gpt-5.5, etc. are treated as regular chat models.
_REASONING_MODEL_PATTERN = re.compile(
    r"^(?:o[1-9])(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?$"
    r"|^gpt-5[a-z]*(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?$"
)


class LLMBase(ABC):
    """
    Base class for all LLM providers.
    Handles common functionality and delegates provider-specific logic to subclasses.
    """

    def __init__(self, config: Optional[Union[BaseLlmConfig, Dict]] = None):
        """Initialize a base LLM class

        :param config: LLM configuration option class or dict, defaults to None
        :type config: Optional[Union[BaseLlmConfig, Dict]], optional
        """
        if config is None:
            self.config = BaseLlmConfig()
        elif isinstance(config, dict):
            # Handle dict-based configuration (backward compatibility)
            self.config = BaseLlmConfig(**config)
        else:
            self.config = config

        # Validate configuration
        self._validate_config()

    def _validate_config(self):
        """
        Validate the configuration.
        Override in subclasses to add provider-specific validation.
        """
        if not hasattr(self.config, "model"):
            raise ValueError("Configuration must have a 'model' attribute")

        if not hasattr(self.config, "api_key") and not hasattr(self.config, "api_key"):
            # Check if API key is available via environment variable
            # This will be handled by individual providers
            pass

    def _is_reasoning_model(self, model: str) -> bool:
        """
        Check if the model is a reasoning model or GPT-5 series that doesn't support certain parameters.

        Args:
            model: The model name to check

        Returns:
            bool: True if the model is a reasoning model or GPT-5 series
        """
        return bool(_REASONING_MODEL_PATTERN.match(model.lower()))

    def _get_supported_params(self, **kwargs) -> Dict:
        """
        Get parameters that are supported by the current model.
        Filters out unsupported parameters for reasoning models and GPT-5 series.
        
        Args:
            **kwargs: Additional parameters to include
            
        Returns:
            Dict: Filtered parameters dictionary
        """
        model = getattr(self.config, 'model', '')
        
        if self._is_reasoning_model(model):
            supported_params = {}
            
            if "messages" in kwargs:
                supported_params["messages"] = kwargs["messages"]
            if "response_format" in kwargs:
                supported_params["response_format"] = kwargs["response_format"]
            if "tools" in kwargs:
                supported_params["tools"] = kwargs["tools"]
            if "tool_choice" in kwargs:
                supported_params["tool_choice"] = kwargs["tool_choice"]

            # Add reasoning_effort if configured
            reasoning_effort = getattr(self.config, 'reasoning_effort', None)
            if reasoning_effort:
                supported_params["reasoning_effort"] = reasoning_effort

            return supported_params
        else:
            # For regular models, include all common parameters
            return self._get_common_params(**kwargs)

    @abstractmethod
    def generate_response(
        self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None, tool_choice: str = "auto", **kwargs
    ):
        """
        Generate a response based on the given messages.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional provider-specific parameters.

        Returns:
            str or dict: The generated response.
        """
        pass

    def _get_common_params(self, **kwargs) -> Dict:
        """
        Get common parameters that most providers use.

        Returns:
            Dict: Common parameters dictionary.
        """
        params = {
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        # Add provider-specific parameters from kwargs
        params.update(kwargs)

        return params
