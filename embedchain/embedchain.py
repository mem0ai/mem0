import logging
import os

from chromadb.errors import InvalidDimensionException
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.memory import ConversationBufferMemory

from embedchain.config import AddConfig, ChatConfig, QueryConfig
from embedchain.config.apps.BaseAppConfig import BaseAppConfig
from embedchain.config.QueryConfig import DOCS_SITE_PROMPT_TEMPLATE
from embedchain.data_formatter import DataFormatter

load_dotenv()

ABS_PATH = os.getcwd()
DB_DIR = os.path.join(ABS_PATH, "db")

memory = ConversationBufferMemory()


class EmbedChain:
    def __init__(self, config: BaseAppConfig):
        """
        Initializes the EmbedChain instance, sets up a vector DB client and
        creates a collection.

        :param config: BaseAppConfig instance to load as configuration.
        """

        self.config = config
        self.db_client = self.config.db.client
        self.collection = self.config.db.collection
        self.user_asks = []
        self.is_docs_site_instance = False
        self.online = False

    def add(self, data_type, url, metadata=None, config: AddConfig = None):
        """
        Adds the data from the given URL to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param data_type: The type of the data to add.
        :param url: The URL where the data is located.
        :param metadata: Optional. Metadata associated with the data source.
        :param config: Optional. The `AddConfig` instance to use as configuration
        options.
        """
        if config is None:
            config = AddConfig()

        data_formatter = DataFormatter(data_type, config)
        self.user_asks.append([data_type, url, metadata])
        self.load_and_embed(data_formatter.loader, data_formatter.chunker, url, metadata)
        if data_type in ("docs_site",):
            self.is_docs_site_instance = True

    def add_local(self, data_type, content, metadata=None, config: AddConfig = None):
        """
        Adds the data you supply to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param data_type: The type of the data to add.
        :param content: The local data. Refer to the `README` for formatting.
        :param metadata: Optional. Metadata associated with the data source.
        :param config: Optional. The `AddConfig` instance to use as
        configuration options.
        """
        if config is None:
            config = AddConfig()

        data_formatter = DataFormatter(data_type, config)
        self.user_asks.append([data_type, content])
        self.load_and_embed(
            data_formatter.loader,
            data_formatter.chunker,
            content,
            metadata,
        )

    def load_and_embed(self, loader, chunker, src, metadata=None):
        """
        Loads the data from the given URL, chunks it, and adds it to database.

        :param loader: The loader to use to load the data.
        :param chunker: The chunker to use to chunk the data.
        :param src: The data to be handled by the loader. Can be a URL for
        remote sources or local content for local loaders.
        :param metadata: Optional. Metadata associated with the data source.
        """
        embeddings_data = chunker.create_chunks(loader, src)
        documents = embeddings_data["documents"]
        metadatas = embeddings_data["metadatas"]
        ids = embeddings_data["ids"]
        # get existing ids, and discard doc if any common id exist.
        where = {"app_id": self.config.id} if self.config.id is not None else {}
        # where={"url": src}
        existing_docs = self.collection.get(
            ids=ids,
            where=where,  # optional filter
        )
        existing_ids = set(existing_docs["ids"])

        if len(existing_ids):
            data_dict = {id: (doc, meta) for id, doc, meta in zip(ids, documents, metadatas)}
            data_dict = {id: value for id, value in data_dict.items() if id not in existing_ids}

            if not data_dict:
                print(f"All data from {src} already exists in the database.")
                return

            ids = list(data_dict.keys())
            documents, metadatas = zip(*data_dict.values())

        # Add app id in metadatas so that they can be queried on later
        if self.config.id is not None:
            metadatas = [{**m, "app_id": self.config.id} for m in metadatas]

        # FIXME: Fix the error handling logic when metadatas or metadata is None
        metadatas = metadatas if metadatas else []
        metadata = metadata if metadata else {}
        chunks_before_addition = self.count()

        # Add metadata to each document
        metadatas_with_metadata = [{**meta, **metadata} for meta in metadatas]

        self.collection.add(documents=documents, metadatas=list(metadatas_with_metadata), ids=ids)
        print((f"Successfully saved {src}. New chunks count: " f"{self.count() - chunks_before_addition}"))

    def _format_result(self, results):
        return [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def get_llm_model_answer(self):
        """
        Usually implemented by child class
        """
        raise NotImplementedError

    def retrieve_from_database(self, input_query, config: QueryConfig):
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query

        :param input_query: The query to use.
        :param config: The query configuration.
        :return: The content of the document that matched your query.
        """
        try:
            where = {"app_id": self.config.id} if self.config.id is not None else {}  # optional filter
            result = self.collection.query(
                query_texts=[
                    input_query,
                ],
                n_results=config.number_documents,
                where=where,
            )
        except InvalidDimensionException as e:
            raise InvalidDimensionException(
                e.message()
                + ". This is commonly a side-effect when an embedding function, different from the one used to add the embeddings, is used to retrieve an embedding from the database."  # noqa E501
            ) from None

        results_formatted = self._format_result(result)
        contents = [result[0].page_content for result in results_formatted]
        return contents

    def _append_search_and_context(self, context, web_search_result):
        return f"{context}\nWeb Search Result: {web_search_result}"

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

    def query(self, input_query, config: QueryConfig = None, dry_run=False):
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
        contexts = self.retrieve_from_database(input_query, config)
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

    def _stream_query_response(self, answer):
        streamed_answer = ""
        for chunk in answer:
            streamed_answer = streamed_answer + chunk
            yield chunk
        logging.info(f"Answer: {streamed_answer}")

    def chat(self, input_query, config: ChatConfig = None, dry_run=False):
        """
        Queries the vector database on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        Maintains the whole conversation in memory.
        :param input_query: The query to use.
        :param config: Optional. The `ChatConfig` instance to use as
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
        contexts = self.retrieve_from_database(input_query, config)

        global memory
        chat_history = memory.load_memory_variables({})["history"]

        if chat_history:
            config.set_history(chat_history)

        prompt = self.generate_prompt(input_query, contexts, config, **k)
        logging.info(f"Prompt: {prompt}")

        if dry_run:
            return prompt

        answer = self.get_answer_from_llm(prompt, config)

        memory.chat_memory.add_user_message(input_query)

        if isinstance(answer, str):
            memory.chat_memory.add_ai_message(answer)
            logging.info(f"Answer: {answer}")
            return answer
        else:
            # this is a streamed response and needs to be handled differently.
            return self._stream_chat_response(answer)

    def _stream_chat_response(self, answer):
        streamed_answer = ""
        for chunk in answer:
            streamed_answer = streamed_answer + chunk
            yield chunk
        memory.chat_memory.add_ai_message(streamed_answer)
        logging.info(f"Answer: {streamed_answer}")

    def count(self):
        """
        Count the number of embeddings.

        :return: The number of embeddings.
        """
        return self.collection.count()

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        `App` has to be reinitialized after using this method.
        """
        self.db_client.reset()
