import openai
import os
from embedchain.config import AppConfig, ChatConfig, ChromaDbConfig, EmbedderConfig
from embedchain.embedchain import EmbedChain
from typing import Optional
from embedchain.embedder.embedder import Embedder

from embedchain.vectordb.chroma_db import ChromaDB
try:
    from chromadb.utils import embedding_functions
except RuntimeError:
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    from chromadb.utils import embedding_functions

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
        embedder = Embedder(config=EmbedderConfig(embedding_fn=App.default_embedding_function()))

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

    @staticmethod
    def default_embedding_function():
        """
        Sets embedding function to default (`text-embedding-ada-002`).

        :raises ValueError: If the template is not valid as template should contain
        $context and $query
        :returns: The default embedding function for the app class.
        """
        if os.getenv("OPENAI_API_KEY") is None and os.getenv("OPENAI_ORGANIZATION") is None:
            raise ValueError("OPENAI_API_KEY or OPENAI_ORGANIZATION environment variables not provided")  # noqa:E501
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            organization_id=os.getenv("OPENAI_ORGANIZATION"),
            model_name="text-embedding-ada-002",
        )
