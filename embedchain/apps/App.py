import openai
import os
from embedchain.config import AppConfig, ChatConfig, ChromaDbConfig, BaseEmbedderConfig
from embedchain.embedchain import EmbedChain
from typing import Optional
from embedchain.embedder.OpenAiEmbedder import OpenAiEmbedder

from embedchain.vectordb.chroma_db import ChromaDB

class App(EmbedChain):
    """
    The EmbedChain app.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    dry_run(query): test your prompt without consuming tokens.
    """

    def __init__(self, config: AppConfig = None, chromadb_config: Optional[ChromaDbConfig] = None):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        """
        if config is None:
            config = AppConfig()

        database = ChromaDB(config=chromadb_config)
        embedder = OpenAiEmbedder(config=BaseEmbedderConfig(model="text-embedding-ada-002"))

        super().__init__(config, db=database, embedder=embedder)

    def get_llm_model_answer(self, prompt, config: ChatConfig):
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
