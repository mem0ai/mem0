from abc import ABC
from typing import Optional

class BaseLlmConfig(ABC):
    """
    Config for LLMs.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0,
        max_tokens: int = 3000,
        top_p: float = 1
    ):
        """
        Initializes a configuration class instance for the LLM.

        :param model: Controls the OpenAI model used, defaults to None
        :type model: Optional[str], optional
        :param temperature:  Controls the randomness of the model's output.
        Higher values (closer to 1) make output more random, lower values make it more deterministic, defaults to 0
        :type temperature: float, optional
        :param max_tokens: Controls how many tokens are generated, defaults to 3000
        :type max_tokens: int, optional
        :param top_p: Controls the diversity of words. Higher values (closer to 1) make word selection more diverse,
        defaults to 1
        :type top_p: float, optional
        """
        
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p