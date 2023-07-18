import logging
from typing import List, Iterable, Union

from langchain.schema import BaseMessage

from embedchain.config import ChatConfig, CustomAppConfig
from embedchain.embedchain import EmbedChain
from embedchain.models import LlmModels


class CustomApp(EmbedChain):
    """
    The custom EmbedChain app.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    dry_run(query): test your prompt without consuming tokens.
    """

    def __init__(self, config: CustomAppConfig = None):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        :raises ValueError: Config must be provided for custom app
        """
        if config is None:
            raise ValueError("Config must be provided for custom app")

        self.llm_model = config.llm_model

        self.gpt4all_model = None

        super().__init__(config)

    def set_llm_model(self, llm_model: LlmModels):
        self.llm_model = llm_model

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        # TODO: Quitting the streaming response here for now.
        # Idea: https://gist.github.com/jvelezmagic/03ddf4c452d011aae36b2a0f73d72f68
        if config.stream:
            raise NotImplementedError(
                "Streaming responses have not been implemented for this model yet. Please disable."
            )

        try:
            if self.llm_model == LlmModels.OPENAI:
                return CustomApp._get_openai_answer(prompt, config)

            if self.llm_model == LlmModels.ANTHROPHIC:
                return CustomApp._get_athrophic_answer(prompt, config)

            if self.llm_model == LlmModels.VERTEX_AI:
                return CustomApp._get_vertex_answer(prompt, config)
            
            if self.llm_model == LlmModels.GPT4ALL:
                return self._get_gpt4all_answer(prompt, config)

        except ImportError as e:
            raise ImportError(e.msg) from None

    @staticmethod
    def _get_openai_answer(prompt: str, config: ChatConfig) -> str:
        from langchain.callbacks import AsyncIteratorCallbackHandler
        from langchain.chat_models import ChatOpenAI

        callback_handler = AsyncIteratorCallbackHandler() if config.stream else None

        chat = ChatOpenAI(
            temperature=config.temperature,
            model=config.model,
            max_tokens=config.max_tokens,
            streaming=config.stream,
            callbacks=[callback_handler],
        )

        if config.top_p and config.top_p != 1:
            logging.warning("Config option `top_p` is not supported by this model.")

        messages = CustomApp._get_messages(prompt)

        return chat(messages).content

    @staticmethod
    def _get_athrophic_answer(prompt: str, config: ChatConfig) -> str:
        from langchain.chat_models import ChatAnthropic

        chat = ChatAnthropic(temperature=config.temperature, model=config.model)

        if config.max_tokens and config.max_tokens != 1000:
            logging.warning("Config option `max_tokens` is not supported by this model.")

        messages = CustomApp._get_messages(prompt)

        return chat(messages).content

    @staticmethod
    def _get_vertex_answer(prompt: str, config: ChatConfig) -> str:
        from langchain.chat_models import ChatVertexAI

        chat = ChatVertexAI(temperature=config.temperature, model=config.model, max_output_tokens=config.max_tokens)

        if config.top_p and config.top_p != 1:
            logging.warning("Config option `top_p` is not supported by this model.")

        messages = CustomApp._get_messages(prompt)

        return chat(messages).content
    
    def _get_gpt4all_answer(self, prompt: str, config: ChatConfig) -> Union[str, Iterable]:
        from gpt4all import GPT4All

        if self.gpt4all_model is None:
            self.gpt4all_model = GPT4All(config.model or "orca-mini-3b.ggmlv3.q4_0.bin")
        response = self.gpt4all_model.generate(prompt=prompt, streaming=config.stream)
        return response

    @staticmethod
    def _get_messages(prompt: str) -> List[BaseMessage]:
        from langchain.schema import HumanMessage, SystemMessage

        return [SystemMessage(content="You are a helpful assistant."), HumanMessage(content=prompt)]

    def _stream_llm_model_response(self, response):
        """
        This is a generator for streaming response from the OpenAI completions API
        """
        for line in response:
            chunk = line["choices"][0].get("delta", {}).get("content", "")
            yield chunk
