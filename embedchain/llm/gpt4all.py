from typing import Iterable, Optional, Union

from embedchain.config import BaseLlmConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class GPT4ALLLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if self.config.model is None:
            self.config.model = "orca-mini-3b.ggmlv3.q4_0.bin"
        self.instance = GPT4ALLLlm._get_instance(self.config.model)

    def get_llm_model_answer(self, prompt):
        return self._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_instance(model):
        try:
            from gpt4all import GPT4All
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The GPT4All python package is not installed. Please install it with `pip install --upgrade embedchain[opensource]`"  # noqa E501
            ) from None

        return GPT4All(model_name=model)

    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> Union[str, Iterable]:
        if config.model and config.model != self.config.model:
            raise RuntimeError(
                "OpenSourceApp does not support switching models at runtime. Please create a new app instance."
            )

        if config.system_prompt:
            raise ValueError("OpenSourceApp does not support `system_prompt`")

        response = self.instance.generate(
            prompt=prompt,
            streaming=config.stream,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            temp=config.temperature,
        )
        return response
