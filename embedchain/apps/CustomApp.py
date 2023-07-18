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

        super().__init__(config)

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        if self.llm_model == LlmModels.OPENAI:
            from langchain.chat_models import ChatOpenAI
            from langchain.prompts.chat import (AIMessagePromptTemplate,
                                                ChatPromptTemplate,
                                                HumanMessagePromptTemplate,
                                                SystemMessagePromptTemplate)
            from langchain.schema import AIMessage, HumanMessage, SystemMessage

            chat = ChatOpenAI(temperature=config.temperature)
            messages = [
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(content=prompt),
            ]
            return chat(messages)

        # if config.stream:
        #     return self._stream_llm_model_response(response)
        # else:
        #     return response["choices"][0]["message"]["content"]
        # raise NotImplementedError("Not yet implemented for custom app")

    def _stream_llm_model_response(self, response):
        """
        This is a generator for streaming response from the OpenAI completions API
        """
        for line in response:
            chunk = line["choices"][0].get("delta", {}).get("content", "")
            yield chunk
