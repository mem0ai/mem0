import hashlib
import logging
import os

from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.memory import ConversationBufferMemory

from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config import AddConfig, ChatConfig, QueryConfig
from embedchain.config.apps.BaseAppConfig import BaseAppConfig
from embedchain.config.QueryConfig import DOCS_SITE_PROMPT_TEMPLATE
from embedchain.data_formatter import DataFormatter
from embedchain.loaders.base_loader import BaseLoader
from embedchain.models.data_type import DataType
from embedchain.utils import detect_datatype

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
        self.collection = self.config.db._get_or_create_collection(self.config.collection_name)
        self.db = self.config.db
        self.user_asks = []
        self.is_docs_site_instance = False
        self.online = False

    def add(self, source, data_type=None, metadata=None, config: AddConfig = None):
        """
        Adds the data from the given URL to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param source: The data to embed, can be a URL, local file or raw content, depending on the data type.
        :param data_type: Optional. Automatically detected, but can be forced with this argument.
        The type of the data to add.
        :param metadata: Optional. Metadata associated with the data source.
        :param config: Optional. The `AddConfig` instance to use as configuration
        options.
        :return: source_id, a md5-hash of the source, in hexadecimal representation.
        """
        if config is None:
            config = AddConfig()

        try:
            DataType(source)
            logging.warning(
                f"It looks like you used '{source}', a data_type, as the `source` argument. Since v0.0.35, Embedchain is able to detect the data_type automatically, so the arguments of the `add` method switched places."  # noqa #E501
            )
            logging.warning(
                "Embedchain is swapping the arguments for you. This functionality might be deprecated in the future, so please adjust your code."  # noqa #E501
            )
            source, data_type = data_type, source
        except ValueError:
            pass

        if data_type:
            try:
                data_type = DataType(data_type)
            except ValueError:
                raise ValueError(
                    f"Invalid data_type: '{data_type}'.",
                    f"Please use one of the following: {[data_type.value for data_type in DataType]}",
                ) from None
        if not data_type:
            data_type = detect_datatype(source)

        # `source_id` is the hash of the source argument
        hash_object = hashlib.md5(str(source).encode("utf-8"))
        source_id = hash_object.hexdigest()

        data_formatter = DataFormatter(data_type, config)
        self.user_asks.append([source, data_type, metadata])
        self.load_and_embed(data_formatter.loader, data_formatter.chunker, source, metadata, source_id)
        if data_type in {DataType.DOCS_SITE}:
            self.is_docs_site_instance = True

        return source_id

    def add_local(self, source, data_type=None, metadata=None, config: AddConfig = None):
        """
        Warning:
            This method is deprecated and will be removed in future versions. Use `add` instead.

        Adds the data from the given URL to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param source: The data to embed, can be a URL, local file or raw content, depending on the data type.
        :param data_type: Optional. Automatically detected, but can be forced with this argument.
        The type of the data to add.
        :param metadata: Optional. Metadata associated with the data source.
        :param config: Optional. The `AddConfig` instance to use as configuration
        options.
        :return: md5-hash of the source, in hexadecimal representation.
        """
        logging.warning(
            "The `add_local` method is deprecated and will be removed in future versions. Please use the `add` method for both local and remote files."  # noqa: E501
        )
        return self.add(source=source, data_type=data_type, metadata=metadata, config=config)

    def load_and_embed(self, loader: BaseLoader, chunker: BaseChunker, src, metadata=None, source_id=None):
        """
        Loads the data from the given URL, chunks it, and adds it to database.

        :param loader: The loader to use to load the data.
        :param chunker: The chunker to use to chunk the data.
        :param src: The data to be handled by the loader. Can be a URL for
        remote sources or local content for local loaders.
        :param metadata: Optional. Metadata associated with the data source.
        :param source_id: Hexadecimal hash of the source.
        """
        embeddings_data = chunker.create_chunks(loader, src)

        # spread chunking results
        documents = embeddings_data["documents"]
        metadatas = embeddings_data["metadatas"]
        ids = embeddings_data["ids"]

        # get existing ids, and discard doc if any common id exist.
        where = {"app_id": self.config.id} if self.config.id is not None else {}
        # where={"url": src}
        existing_ids = self.db.get(
            ids=ids,
            where=where,  # optional filter
        )

        if len(existing_ids):
            data_dict = {id: (doc, meta) for id, doc, meta in zip(ids, documents, metadatas)}
            data_dict = {id: value for id, value in data_dict.items() if id not in existing_ids}

            if not data_dict:
                print(f"All data from {src} already exists in the database.")
                return

            ids = list(data_dict.keys())
            documents, metadatas = zip(*data_dict.values())

        # Loop though all metadatas and add extras.
        new_metadatas = []
        for m in metadatas:
            # Add app id in metadatas so that they can be queried on later
            if self.config.id:
                m["app_id"] = self.config.id

            # Add hashed source
            m["hash"] = source_id

            # Note: Metadata is the function argument
            if metadata:
                # Spread whatever is in metadata into the new object.
                m.update(metadata)

            new_metadatas.append(m)
        metadatas = new_metadatas

        # Count before, to calculate a delta in the end.
        chunks_before_addition = self.count()

        self.db.add(documents=documents, metadatas=metadatas, ids=ids)
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
        where = {"app_id": self.config.id} if self.config.id is not None else {}  # optional filter
        contents = self.db.query(
            input_query=input_query,
            n_results=config.number_documents,
            where=where,
        )

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

    def set_collection(self, collection_name):
        """
        Set the collection to use.

        :param collection_name: The name of the collection to use.
        """
        self.collection = self.config.db._get_or_create_collection(collection_name)

    def count(self):
        """
        Count the number of embeddings.

        :return: The number of embeddings.
        """
        return self.db.count()

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        `App` has to be reinitialized after using this method.
        """
        self.db.reset()
