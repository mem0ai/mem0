from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class ModelsLabConfig(BaseLlmConfig):
    """
    Configuration class for ModelsLab-specific parameters.
    Inherits from BaseLlmConfig and adds ModelsLab settings.

    ModelsLab provides an OpenAI-compatible uncensored chat API.
    API key: https://modelslab.com/account/api-key
    Docs: https://docs.modelslab.com
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        top_k: int = 1,
        enable_vision: bool = False,
        vision_details: Optional[str] = "auto",
        http_client_proxies: Optional[dict] = None,
        modelslab_base_url: Optional[str] = None,
    ):
        super().__init__(
            model=model,
            temperature=temperature,
            api_key=api_key,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            enable_vision=enable_vision,
            vision_details=vision_details,
            http_client_proxies=http_client_proxies,
        )
        self.modelslab_base_url = modelslab_base_url or "https://modelslab.com/api/uncensored-chat/v1"
