import logging
from typing import List

from langchain.schema import BaseMessage

from embedchain.config import ChatConfig, CustomAppConfig
from embedchain.embedchain import EmbedChain
from embedchain.models import Providers


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
        :param config: Optional. `CustomAppConfig` instance to load as configuration.
        :raises ValueError: Config must be provided for custom app
        """
        if config is None:
            raise ValueError("Config must be provided for custom app")

        self.provider = config.provider

        if config.provider == Providers.GPT4ALL:
            from embedchain import OpenSourceApp

            # Because these models run locally, they should have an instance running when the custom app is created
            self.open_source_app = OpenSourceApp(config=config.open_source_app_config)

        super().__init__(config)

    def set_llm_model(self, provider: Providers):
        self.provider = provider
        if provider == Providers.GPT4ALL:
            raise ValueError(
                "GPT4ALL needs to be instantiated with the model known, please create a new app instance instead"
            )

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        # TODO: Quitting the streaming response here for now.
        # Idea: https://gist.github.com/jvelezmagic/03ddf4c452d011aae36b2a0f73d72f68
        if config.stream:
            raise NotImplementedError(
                "Streaming responses have not been implemented for this model yet. Please disable."
            )

        try:
            if self.provider == Providers.OPENAI:
                return CustomApp._get_openai_answer(prompt, config)

            if self.provider == Providers.ANTHROPHIC:
                return CustomApp._get_athrophic_answer(prompt, config)

            if self.provider == Providers.VERTEX_AI:
                return CustomApp._get_vertex_answer(prompt, config)

            if self.provider == Providers.GPT4ALL:
                return self.open_source_app._get_gpt4all_answer(prompt, config)

        except ImportError as e:
            raise ImportError(e.msg) from None

    @staticmethod
    def _get_openai_answer(prompt: str, config: ChatConfig) -> str:
        from langchain.chat_models import ChatOpenAI

        logging.info(vars(config))

        chat = ChatOpenAI(
            temperature=config.temperature,
            model=config.model or "gpt-3.5-turbo",
            max_tokens=config.max_tokens,
            streaming=config.stream,
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
