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
            from langchain.llms import GPT4All
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The GPT4All python package is not installed. Please install it with `pip install --upgrade embedchain[opensource]`"  # noqa E501
            ) from None

        return GPT4All(
            temp=BaseLlmConfig().temperature,
            allow_download=True,
            model=model,
            n_threads=8,
            max_tokens=BaseLlmConfig().max_tokens,
            n_parts=8,
            backend="llama",
            seed=0,
            f16_kv=False,
            n_batch=8,
            embedding=False,
            logits_all=False,
            vocab_only=False,
            use_mlock=False,
        )

    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> Union[str, Iterable]:
        if config.model and config.model != self.config.model:
            raise RuntimeError(
                "OpenSourceApp does not support switching models at runtime. Please create a new app instance."
            )

        if config.system_prompt:
            raise ValueError("OpenSourceApp does not support `system_prompt`")

        response = self.get_answer_from_llm(prompt=prompt)
        return response
