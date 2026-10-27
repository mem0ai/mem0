from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class AIHubMixConfig(BaseLlmConfig):
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        max_tokens: int = 2000,
        top_p: float = 0.1,
        top_k: int = 1,
        enable_vision: bool = False,
        vision_details: Optional[str] = "auto",
        reasoning_effort: Optional[str] = None,
        http_client_proxies=None,
        is_reasoning_model: Optional[bool] = None,
        aihubmix_base_url: Optional[str] = None,
    ):
        super().__init__(
            model=model or "gpt-6.1-terra",
            temperature=temperature,
            api_key=api_key,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            enable_vision=enable_vision,
            vision_details=vision_details,
            reasoning_effort=reasoning_effort,
            http_client_proxies=http_client_proxies,
            is_reasoning_model=is_reasoning_model,
        )
        self.aihubmix_base_url = aihubmix_base_url
