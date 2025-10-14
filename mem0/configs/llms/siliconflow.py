from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class SiliconflowConfig(BaseLlmConfig):
    """
    Configuration for the Siliconflow LLM.
    """

    def __init__(
        self,
        model: Optional[str] = "tencent/Hunyuan-MT-7B", # Free model for local testing
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize Siliconflow configuration.

        Args:
            model: The model to use. Defaults to "tencent/Hunyuan-MT-7B".
            api_key: API key for authentication. Defaults to None.
            base_url: Base URL for the Siliconflow API. Defaults to None.
            **kwargs: Additional keyword arguments for BaseLlmConfig.
        """
        super().__init__(model=model, api_key=api_key, **kwargs)
        self.siliconflow_base_url = base_url
