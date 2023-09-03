from typing import Optional

import openai

from embedchain.config import BaseLlmConfig
from embedchain.llm.base_llm import BaseLlm


class OpenAiLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)

    # NOTE: This class does not use langchain. One reason is that `top_p` is not supported.

    def get_llm_model_answer(self, prompt, config: BaseLlmConfig):
        messages = []
        if config.system_prompt:
            messages.append({"role": "system", "content": config.system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = openai.ChatCompletion.create(
            model=config.model or "gpt-3.5-turbo-0613",
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            stream=config.stream,
        )

        if config.stream:
            return self._stream_llm_model_response(response)
        else:
            return response["choices"][0]["message"]["content"]

    def _stream_llm_model_response(self, response):
        """
        This is a generator for streaming response from the OpenAI completions API
        """
        for line in response:
            chunk = line["choices"][0].get("delta", {}).get("content", "")
            yield chunk
