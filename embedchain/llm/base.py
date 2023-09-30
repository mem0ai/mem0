import logging
from typing import Any, Dict, Generator, List, Optional

from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage

from embedchain.config import BaseLlmConfig
from embedchain.config.llm.base_llm_config import (
    DEFAULT_PROMPT, DEFAULT_PROMPT_WITH_HISTORY_TEMPLATE,
    DOCS_SITE_PROMPT_TEMPLATE)
from embedchain.helper.json_serializable import JSONSerializable


class BaseLlm(JSONSerializable):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """Initialize a base LLM class

        :param config: LLM configuration option class, defaults to None
        :type config: Optional[BaseLlmConfig], optional
        """
        if config is None:
            self.config = BaseLlmConfig()
        else:
            self.config = config

        self.memory = ConversationBufferMemory()
        self.is_docs_site_instance = False
        self.online = False
        self.history: Any = None

    def get_llm_model_answer(self):
        """
        Usually implemented by child class
        """
        raise NotImplementedError

    def set_history(self, history: Any):
        """
        Provide your own history.
        Especially interesting for the query method, which does not internally manage conversation history.

        :param history: History to set
        :type history: Any
        """
        self.history = history

    def update_history(self):
        """Update class history attribute with history in memory (for chat method)"""
        chat_history = self.memory.load_memory_variables({})["history"]
        if chat_history:
            self.set_history(chat_history)

    def generate_prompt(self, input_query: str, contexts: List[str], **kwargs: Dict[str, Any]) -> str:
        """
        Generates a prompt based on the given query and context, ready to be
        passed to an LLM

        :param input_query: The query to use.
        :type input_query: str
        :param contexts: List of similar documents to the query used as context.
        :type contexts: List[str]
        :return: The prompt
        :rtype: str
        """
        context_string = (" | ").join(contexts)
        web_search_result = kwargs.get("web_search_result", "")
        if web_search_result:
            context_string = self._append_search_and_context(context_string, web_search_result)

        template_contains_history = self.config._validate_template_history(self.config.template)
        if template_contains_history:
            # Template contains history
            # If there is no history yet, we insert `- no history -`
            prompt = self.config.template.substitute(
                context=context_string, query=input_query, history=self.history or "- no history -"
            )
        elif self.history and not template_contains_history:
            # History is present, but not included in the template.
            # check if it's the default template without history
            if (
                not self.config._validate_template_history(self.config.template)
                and self.config.template.template == DEFAULT_PROMPT
            ):
                # swap in the template with history
                prompt = DEFAULT_PROMPT_WITH_HISTORY_TEMPLATE.substitute(
                    context=context_string, query=input_query, history=self.history
                )
            else:
                # If we can't swap in the default, we still proceed but tell users that the history is ignored.
                logging.warning(
                    "Your bot contains a history, but template does not include `$history` key. History is ignored."
                )
                prompt = self.config.template.substitute(context=context_string, query=input_query)
        else:
            # basic use case, no history.
            prompt = self.config.template.substitute(context=context_string, query=input_query)
        return prompt

    def _append_search_and_context(self, context: str, web_search_result: str) -> str:
        """Append web search context to existing context

        :param context: Existing context
        :type context: str
        :param web_search_result: Web search result
        :type web_search_result: str
        :return: Concatenated web search result
        :rtype: str
        """
        return f"{context}\nWeb Search Result: {web_search_result}"

    def get_answer_from_llm(self, prompt: str):
        """
        Gets an answer based on the given query and context by passing it
        to an LLM.

        :param prompt: Gets an answer based on the given query and context by passing it to an LLM.
        :type prompt: str
        :return: The answer.
        :rtype: _type_
        """
        return self.get_llm_model_answer(prompt)

    def access_search_and_get_results(self, input_query: str):
        """
        Search the internet for additional context

        :param input_query: search query
        :type input_query: str
        :return: Search results
        :rtype: Unknown
        """
        from langchain.tools import DuckDuckGoSearchRun

        search = DuckDuckGoSearchRun()
        logging.info(f"Access search to get answers for {input_query}")
        return search.run(input_query)

    def _stream_query_response(self, answer: Any) -> Generator[Any, Any, None]:
        """Generator to be used as streaming response

        :param answer: Answer chunk from llm
        :type answer: Any
        :yield: Answer chunk from llm
        :rtype: Generator[Any, Any, None]
        """
        streamed_answer = ""
        for chunk in answer:
            streamed_answer = streamed_answer + chunk
            yield chunk
        logging.info(f"Answer: {streamed_answer}")

    def _stream_chat_response(self, answer: Any) -> Generator[Any, Any, None]:
        """Generator to be used as streaming response

        :param answer: Answer chunk from llm
        :type answer: Any
        :yield: Answer chunk from llm
        :rtype: Generator[Any, Any, None]
        """
        streamed_answer = ""
        for chunk in answer:
            streamed_answer = streamed_answer + chunk
            yield chunk
        self.memory.chat_memory.add_ai_message(streamed_answer)
        logging.info(f"Answer: {streamed_answer}")

    def query(self, input_query: str, contexts: List[str], config: BaseLlmConfig = None, dry_run=False):
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        :param input_query: The query to use.
        :type input_query: str
        :param contexts: Embeddings retrieved from the database to be used as context.
        :type contexts: List[str]
        :param config: The `LlmConfig` instance to use as configuration options. This is used for one method call.
        To persistently use a config, declare it during app init., defaults to None
        :type config: Optional[BaseLlmConfig], optional
        :param dry_run: A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response., defaults to False
        :type dry_run: bool, optional
        :return: The answer to the query or the dry run result
        :rtype: str
        """
        try:
            if config:
                # A config instance passed to this method will only be applied temporarily, for one call.
                # So we will save the previous config and restore it at the end of the execution.
                # For this we use the serializer.
                prev_config = self.config.serialize()
                self.config = config

            if config is not None and config.query_type == "Images":
                return contexts

            if self.is_docs_site_instance:
                self.config.template = DOCS_SITE_PROMPT_TEMPLATE
                self.config.number_documents = 5
            k = {}
            if self.online:
                k["web_search_result"] = self.access_search_and_get_results(input_query)
            prompt = self.generate_prompt(input_query, contexts, **k)
            logging.info(f"Prompt: {prompt}")

            if dry_run:
                return prompt

            answer = self.get_answer_from_llm(prompt)

            if isinstance(answer, str):
                logging.info(f"Answer: {answer}")
                return answer
            else:
                return self._stream_query_response(answer)
        finally:
            if config:
                # Restore previous config
                self.config: BaseLlmConfig = BaseLlmConfig.deserialize(prev_config)

    def chat(self, input_query: str, contexts: List[str], config: BaseLlmConfig = None, dry_run=False):
        """
        Queries the vector database on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        Maintains the whole conversation in memory.

        :param input_query: The query to use.
        :type input_query: str
        :param contexts: Embeddings retrieved from the database to be used as context.
        :type contexts: List[str]
        :param config: The `LlmConfig` instance to use as configuration options. This is used for one method call.
        To persistently use a config, declare it during app init., defaults to None
        :type config: Optional[BaseLlmConfig], optional
        :param dry_run: A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response., defaults to False
        :type dry_run: bool, optional
        :return: The answer to the query or the dry run result
        :rtype: str
        """
        try:
            if config:
                # A config instance passed to this method will only be applied temporarily, for one call.
                # So we will save the previous config and restore it at the end of the execution.
                # For this we use the serializer.
                prev_config = self.config.serialize()
                self.config = config

            if self.is_docs_site_instance:
                self.config.template = DOCS_SITE_PROMPT_TEMPLATE
                self.config.number_documents = 5
            k = {}
            if self.online:
                k["web_search_result"] = self.access_search_and_get_results(input_query)

            self.update_history()

            prompt = self.generate_prompt(input_query, contexts, **k)
            logging.info(f"Prompt: {prompt}")

            if dry_run:
                return prompt

            answer = self.get_answer_from_llm(prompt)

            self.memory.chat_memory.add_user_message(input_query)

            if isinstance(answer, str):
                self.memory.chat_memory.add_ai_message(answer)
                logging.info(f"Answer: {answer}")

                # NOTE: Adding to history before and after. This could be seen as redundant.
                # If we change it, we have to change the tests (no big deal).
                self.update_history()

                return answer
            else:
                # this is a streamed response and needs to be handled differently.
                return self._stream_chat_response(answer)
        finally:
            if config:
                # Restore previous config
                self.config: BaseLlmConfig = BaseLlmConfig.deserialize(prev_config)

    @staticmethod
    def _get_messages(prompt: str, system_prompt: Optional[str] = None) -> List[BaseMessage]:
        """
        Construct a list of langchain messages

        :param prompt: User prompt
        :type prompt: str
        :param system_prompt: System prompt, defaults to None
        :type system_prompt: Optional[str], optional
        :return: List of messages
        :rtype: List[BaseMessage]
        """
        from langchain.schema import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return messages
