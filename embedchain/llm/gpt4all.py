from typing import Iterable, Optional, Union

from langchain.callbacks.stdout import StdOutCallbackHandler
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class GPT4ALLLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if self.config.model is None:
            self.config.model = "orca-mini-3b-gguf2-q4_0.gguf"
        self.instance = GPT4ALLLlm._get_instance(self.config.model)
        self.instance.streaming = self.config.stream

    def get_llm_model_answer(self, prompt):
        return self._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_instance(model):
        try:
            from langchain.llms.gpt4all import GPT4All as LangchainGPT4All
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The GPT4All python package is not installed. Please install it with `pip install --upgrade embedchain[opensource]`"  # noqa E501
            ) from None

        return LangchainGPT4All(model=model, allow_download=True)

    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> Union[str, Iterable]:
        if config.model and config.model != self.config.model:
            raise RuntimeError(
                "GPT4ALLLlm does not support switching models at runtime. Please create a new app instance."
            )

        messages = []
        if config.system_prompt:
            messages.append(config.system_prompt)
        messages.append(prompt)
        kwargs = {
            "temp": config.temperature,
            "max_tokens": config.max_tokens,
        }
        if config.top_p:
            kwargs["top_p"] = config.top_p

        callbacks = [StreamingStdOutCallbackHandler()] if config.stream else [StdOutCallbackHandler()]

        response = self.instance.generate(prompts=messages, callbacks=callbacks, **kwargs)
        answer = ""
        for generations in response.generations:
            answer += " ".join(map(lambda generation: generation.text, generations))
        return answer
