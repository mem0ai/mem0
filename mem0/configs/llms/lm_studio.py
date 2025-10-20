from mem0.configs.llms.base import BaseLlmConfig


class LMStudioConfig(BaseLlmConfig):
    def __init__(self, model: str = "gpt-4", temperature: float = 0.1, max_tokens: int = 4000, top_p: float = 1.0, base_url: str = "http://localhost:1234/v1", api_key: str = "lm-studio"):
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        self.base_url = base_url
        self.api_key = api_key
