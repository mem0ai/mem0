import logging

from langchain.memory import ConversationBufferMemory

from embedchain.config import ChatConfig, QueryConfig
from embedchain.config.QueryConfig import DOCS_SITE_PROMPT_TEMPLATE


class BaseLlm:
    def __init__(self):
        self.memory = ConversationBufferMemory()
        self.is_docs_site_instance = False
        self.online = False

    def get_llm_model_answer(self):
        """
        Usually implemented by child class
        """
        raise NotImplementedError

    def generate_prompt(self, input_query, contexts, config: QueryConfig, **kwargs):
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
        if not config.history:
            prompt = config.template.substitute(context=context_string, query=input_query)
        else:
            prompt = config.template.substitute(context=context_string, query=input_query, history=config.history)
        return prompt

    def _append_search_and_context(self, context, web_search_result):
        return f"{context}\nWeb Search Result: {web_search_result}"

    def get_answer_from_llm(self, prompt, config: ChatConfig):
        """
        Gets an answer based on the given query and context by passing it
        to an LLM.

        :param query: The query to use.
        :param context: Similar documents to the query used as context.
        :return: The answer.
        """

        return self.get_llm_model_answer(prompt, config)

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

    def query(self, input_query, contexts, config: QueryConfig = None, dry_run=False):
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        :param input_query: The query to use.
        :param config: Optional. The `QueryConfig` instance to use as
        configuration options.
        :param dry_run: Optional. A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response.
        You can use it to test your prompt, including the context provided
        by the vector database's doc retrieval.
        The only thing the dry run does not consider is the cut-off due to
        the `max_tokens` parameter.
        :return: The answer to the query.
        """
        if config is None:
            config = QueryConfig()
        if self.is_docs_site_instance:
            config.template = DOCS_SITE_PROMPT_TEMPLATE
            config.number_documents = 5
        k = {}
        if self.online:
            k["web_search_result"] = self.access_search_and_get_results(input_query)
        prompt = self.generate_prompt(input_query, contexts, config, **k)
        logging.info(f"Prompt: {prompt}")

        if dry_run:
            return prompt

        answer = self.get_answer_from_llm(prompt, config)

        if isinstance(answer, str):
            logging.info(f"Answer: {answer}")
            return answer
        else:
            return self._stream_query_response(answer)

    def chat(self, input_query, contexts, config: ChatConfig = None, dry_run=False):
        """
        Queries the vector database on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        Maintains the whole conversation in memory.
        :param input_query: The query to use.
        :param config: Optional. The `QueryConfig` instance to use as
        configuration options.
        :param dry_run: Optional. A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response.
        You can use it to test your prompt, including the context provided
        by the vector database's doc retrieval.
        The only thing the dry run does not consider is the cut-off due to
        the `max_tokens` parameter.
        :return: The answer to the query.
        """
        if config is None:
            config = ChatConfig()
        if self.is_docs_site_instance:
            config.template = DOCS_SITE_PROMPT_TEMPLATE
            config.number_documents = 5
        k = {}
        if self.online:
            k["web_search_result"] = self.access_search_and_get_results(input_query)

        chat_history = self.memory.load_memory_variables({})["history"]

        if chat_history:
            config.set_history(chat_history)

        prompt = self.generate_prompt(input_query, contexts, config, **k)
        logging.info(f"Prompt: {prompt}")

        if dry_run:
            return prompt

        answer = self.get_answer_from_llm(prompt, config)

        self.memory.chat_memory.add_user_message(input_query)

        if isinstance(answer, str):
            self.memory.chat_memory.add_ai_message(answer)
            logging.info(f"Answer: {answer}")
            return answer
        else:
            # this is a streamed response and needs to be handled differently.
            return self._stream_chat_response(answer)
