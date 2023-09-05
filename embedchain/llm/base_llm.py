import logging
from typing import List, Optional

from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage

from embedchain.config import BaseLlmConfig
from embedchain.config.llm.base_llm_config import (
    DEFAULT_PROMPT, DEFAULT_PROMPT_WITH_HISTORY_TEMPLATE,
    DOCS_SITE_PROMPT_TEMPLATE)
from embedchain.helper_classes.json_serializable import JSONSerializable


class BaseLlm(JSONSerializable):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if config is None:
            self.config = BaseLlmConfig()
        else:
            self.config = config

        self.memory = ConversationBufferMemory()
        self.is_docs_site_instance = False
        self.online = False
        self.history: any = None

    def get_llm_model_answer(self):
        """
        Usually implemented by child class
        """
        raise NotImplementedError

    def set_history(self, history: any):
        self.history = history

    def update_history(self):
        chat_history = self.memory.load_memory_variables({})["history"]
        if chat_history:
            self.set_history(chat_history)

    def generate_prompt(self, input_query, contexts, **kwargs):
        """
        Generates a prompt based on the given query and context, ready to be
        passed to an LLM

        :param input_query: The query to use.
        :param contexts: List of similar documents to the query used as context.
        :param config: Optional. The `QueryConfig` instance to use as
        configuration options.
        :return: The prompt
        """
        context_string = (" | ").join(contexts)
        web_search_result = kwargs.get("web_search_result", "")
        if web_search_result:
            context_string = self._append_search_and_context(context_string, web_search_result)
        if not self.history:
            prompt = self.config.template.substitute(context=context_string, query=input_query)
        else:
            # check if it's the default template without history
            if (
                not self.config._validate_template_history(self.config.template)
                and self.config.template.template == DEFAULT_PROMPT
            ):
                # swap in the template with history
                prompt = DEFAULT_PROMPT_WITH_HISTORY_TEMPLATE.substitute(
                    context=context_string, query=input_query, history=self.history
                )
            elif not self.config._validate_template_history(self.config.template):
                logging.warning("Template does not include `$history` key. History is not included in prompt.")
                prompt = self.config.template.substitute(context=context_string, query=input_query)
            else:
                prompt = self.config.template.substitute(
                    context=context_string, query=input_query, history=self.history
                )
        return prompt

    def _append_search_and_context(self, context, web_search_result):
        return f"{context}\nWeb Search Result: {web_search_result}"

    def get_answer_from_llm(self, prompt):
        """
        Gets an answer based on the given query and context by passing it
        to an LLM.

        :param query: The query to use.
        :param context: Similar documents to the query used as context.
        :return: The answer.
        """

        return self.get_llm_model_answer(prompt)

    def access_search_and_get_results(self, input_query):
        from langchain.tools import DuckDuckGoSearchRun

        search = DuckDuckGoSearchRun()
        logging.info(f"Access search to get answers for {input_query}")
        return search.run(input_query)

    def _stream_query_response(self, answer):
        streamed_answer = ""
        for chunk in answer:
            streamed_answer = streamed_answer + chunk
            yield chunk
        logging.info(f"Answer: {streamed_answer}")

    def _stream_chat_response(self, answer):
        streamed_answer = ""
        for chunk in answer:
            streamed_answer = streamed_answer + chunk
            yield chunk
        self.memory.chat_memory.add_ai_message(streamed_answer)
        logging.info(f"Answer: {streamed_answer}")

    def query(self, input_query, contexts, config: BaseLlmConfig = None, dry_run=False, where=None):
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        :param input_query: The query to use.
        :param config: Optional. The `LlmConfig` instance to use as configuration options.
        This is used for one method call. To persistently use a config, declare it during app init.
        :param dry_run: Optional. A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response.
        You can use it to test your prompt, including the context provided
        by the vector database's doc retrieval.
        The only thing the dry run does not consider is the cut-off due to
        the `max_tokens` parameter.
        :param where: Optional. A dictionary of key-value pairs to filter the database results.
        :return: The answer to the query.
        """
        query_config = config or self.config

        if self.is_docs_site_instance:
            query_config.template = DOCS_SITE_PROMPT_TEMPLATE
            query_config.number_documents = 5
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

    def chat(self, input_query, contexts, config: BaseLlmConfig = None, dry_run=False, where=None):
        """
        Queries the vector database on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        Maintains the whole conversation in memory.
        :param input_query: The query to use.
        :param config: Optional. The `LlmConfig` instance to use as configuration options.
        This is used for one method call. To persistently use a config, declare it during app init.
        :param dry_run: Optional. A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response.
        You can use it to test your prompt, including the context provided
        by the vector database's doc retrieval.
        The only thing the dry run does not consider is the cut-off due to
        the `max_tokens` parameter.
        :param where: Optional. A dictionary of key-value pairs to filter the database results.
        :return: The answer to the query.
        """
        query_config = config or self.config

        if self.is_docs_site_instance:
            query_config.template = DOCS_SITE_PROMPT_TEMPLATE
            query_config.number_documents = 5
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

    @staticmethod
    def _get_messages(prompt: str, system_prompt: Optional[str] = None) -> List[BaseMessage]:
        from langchain.schema import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return messages
