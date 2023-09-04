from typing import Optional

import openai

from embedchain.config import AppConfig, ChatConfig
from embedchain.embedchain import EmbedChain
from embedchain.helper_classes.json_serializable import register_deserializable


@register_deserializable
class App(EmbedChain):
    """
    The EmbedChain app.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    dry_run(query): test your prompt without consuming tokens.
    """

    def __init__(self, config: AppConfig = None, system_prompt: Optional[str] = None):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        :param system_prompt: System prompt string. Optional.
        """
        if config is None:
            config = AppConfig()

        super().__init__(config, system_prompt)

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        messages = []
        system_prompt = (
            self.system_prompt
            if self.system_prompt is not None
            else config.system_prompt
            if config.system_prompt is not None
            else None
        )
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
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
