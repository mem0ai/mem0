import hashlib
import json
import logging
from typing import Any, Optional, Union

from dotenv import load_dotenv
from langchain.docstore.document import Document

from embedchain.cache import (adapt, get_gptcache_session,
                              gptcache_data_convert,
                              gptcache_update_cache_callback)
from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config import AddConfig, BaseLlmConfig, ChunkerConfig
from embedchain.config.base_app_config import BaseAppConfig
from embedchain.core.db.models import ChatHistory, DataSource
from embedchain.data_formatter import DataFormatter
from embedchain.embedder.base import BaseEmbedder
from embedchain.helpers.json_serializable import JSONSerializable
from embedchain.llm.base import BaseLlm
from embedchain.loaders.base_loader import BaseLoader
from embedchain.models.data_type import (DataType, DirectDataType,
                                         IndirectDataType, SpecialDataType)
from embedchain.utils.misc import detect_datatype, is_valid_json_string
from embedchain.vectordb.base import BaseVectorDB

load_dotenv()

logger = logging.getLogger(__name__)


class EmbedChain(JSONSerializable):
    def __init__(
        self,
        config: BaseAppConfig,
        llm: BaseLlm,
        db: BaseVectorDB = None,
        embedder: BaseEmbedder = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Initializes the EmbedChain instance, sets up a vector DB client and
        creates a collection.

        :param config: Configuration just for the app, not the db or llm or embedder.
        :type config: BaseAppConfig
        :param llm: Instance of the LLM you want to use.
        :type llm: BaseLlm
        :param db: Instance of the Database to use, defaults to None
        :type db: BaseVectorDB, optional
        :param embedder: instance of the embedder to use, defaults to None
        :type embedder: BaseEmbedder, optional
        :param system_prompt: System prompt to use in the llm query, defaults to None
        :type system_prompt: Optional[str], optional
        :raises ValueError: No database or embedder provided.
        """
        self.config = config
        self.cache_config = None
        # Llm
        self.llm = llm
        # Database has support for config assignment for backwards compatibility
        if db is None and (not hasattr(self.config, "db") or self.config.db is None):
            raise ValueError("App requires Database.")
        self.db = db or self.config.db
        # Embedder
        if embedder is None:
            raise ValueError("App requires Embedder.")
        self.embedder = embedder

        # Initialize database
        self.db._set_embedder(self.embedder)
        self.db._initialize()
        # Set collection name from app config for backwards compatibility.
        if config.collection_name:
            self.db.set_collection_name(config.collection_name)

        # Add variables that are "shortcuts"
        if system_prompt:
            self.llm.config.system_prompt = system_prompt

        # Fetch the history from the database if exists
        self.llm.update_history(app_id=self.config.id)

        # Attributes that aren't subclass related.
        self.user_asks = []

        self.chunker: Optional[ChunkerConfig] = None

    @property
    def collect_metrics(self):
        return self.config.collect_metrics

    @collect_metrics.setter
    def collect_metrics(self, value):
        if not isinstance(value, bool):
            raise ValueError(f"Boolean value expected but got {type(value)}.")
        self.config.collect_metrics = value

    @property
    def online(self):
        return self.llm.online

    @online.setter
    def online(self, value):
        if not isinstance(value, bool):
            raise ValueError(f"Boolean value expected but got {type(value)}.")
        self.llm.online = value

    def add(
        self,
        source: Any,
        data_type: Optional[DataType] = None,
        metadata: Optional[dict[str, Any]] = None,
        config: Optional[AddConfig] = None,
        dry_run=False,
        loader: Optional[BaseLoader] = None,
        chunker: Optional[BaseChunker] = None,
        **kwargs: Optional[dict[str, Any]],
    ):
        """
        Adds the data from the given URL to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param source: The data to embed, can be a URL, local file or raw content, depending on the data type.
        :type source: Any
        :param data_type: Automatically detected, but can be forced with this argument. The type of the data to add,
        defaults to None
        :type data_type: Optional[DataType], optional
        :param metadata: Metadata associated with the data source., defaults to None
        :type metadata: Optional[dict[str, Any]], optional
        :param config: The `AddConfig` instance to use as configuration options., defaults to None
        :type config: Optional[AddConfig], optional
        :raises ValueError: Invalid data type
        :param dry_run: Optional. A dry run displays the chunks to ensure that the loader and chunker work as intended.
        deafaults to False
        :return: source_hash, a md5-hash of the source, in hexadecimal representation.
        :rtype: str
        """
        if config is not None:
            pass
        elif self.chunker is not None:
            config = AddConfig(chunker=self.chunker)
        else:
            config = AddConfig()

        try:
            DataType(source)
            logger.warning(
                f"""Starting from version v0.0.40, Embedchain can automatically detect the data type. So, in the `add` method, the argument order has changed. You no longer need to specify '{source}' for the `source` argument. So the code snippet will be `.add("{data_type}", "{source}")`"""  # noqa #E501
            )
            logger.warning(
                "Embedchain is swapping the arguments for you. This functionality might be deprecated in the future, so please adjust your code."  # noqa #E501
            )
            source, data_type = data_type, source
        except ValueError:
            pass

        if data_type:
            try:
                data_type = DataType(data_type)
            except ValueError:
                logger.info(
                    f"Invalid data_type: '{data_type}', using `custom` instead.\n Check docs to pass the valid data type: `https://docs.embedchain.ai/data-sources/overview`"  # noqa: E501
                )
                data_type = DataType.CUSTOM

        if not data_type:
            data_type = detect_datatype(source)

        # `source_hash` is the md5 hash of the source argument
        source_hash = hashlib.md5(str(source).encode("utf-8")).hexdigest()

        self.user_asks.append([source, data_type.value, metadata])

        data_formatter = DataFormatter(data_type, config, loader, chunker)
        documents, metadatas, _ids, new_chunks = self._load_and_embed(
            data_formatter.loader, data_formatter.chunker, source, metadata, source_hash, config, dry_run, **kwargs
        )
        if data_type in {DataType.DOCS_SITE}:
            self.is_docs_site_instance = True

        # Convert the source to a string if it is not already
        if not isinstance(source, str):
            source = str(source)

        # Insert the data into the 'ec_data_sources' table
        self.db_session.add(
            DataSource(
                hash=source_hash,
                app_id=self.config.id,
                type=data_type.value,
                value=source,
                metadata=json.dumps(metadata),
            )
        )
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error adding data source: {e}")
            self.db_session.rollback()

        if dry_run:
            data_chunks_info = {"chunks": documents, "metadata": metadatas, "count": len(documents), "type": data_type}
            logger.debug(f"Dry run info : {data_chunks_info}")
            return data_chunks_info

        # Send anonymous telemetry
        if self.config.collect_metrics:
            # it's quicker to check the variable twice than to count words when they won't be submitted.
            word_count = data_formatter.chunker.get_word_count(documents)

            # Send anonymous telemetry
            event_properties = {
                **self._telemetry_props,
                "data_type": data_type.value,
                "word_count": word_count,
                "chunks_count": new_chunks,
            }
            self.telemetry.capture(event_name="add", properties=event_properties)

        return source_hash

    def _get_existing_doc_id(self, chunker: BaseChunker, src: Any):
        """
        Get id of existing document for a given source, based on the data type
        """
        # Find existing embeddings for the source
        # Depending on the data type, existing embeddings are checked for.
        if chunker.data_type.value in [item.value for item in DirectDataType]:
            # DirectDataTypes can't be updated.
            # Think of a text:
            #   Either it's the same, then it won't change, so it's not an update.
            #   Or it's different, then it will be added as a new text.
            return None
        elif chunker.data_type.value in [item.value for item in IndirectDataType]:
            # These types have an indirect source reference
            # As long as the reference is the same, they can be updated.
            where = {"url": src}
            if chunker.data_type == DataType.JSON and is_valid_json_string(src):
                url = hashlib.sha256((src).encode("utf-8")).hexdigest()
                where = {"url": url}

            if self.config.id is not None:
                where.update({"app_id": self.config.id})

            existing_embeddings = self.db.get(
                where=where,
                limit=1,
            )
            if len(existing_embeddings.get("metadatas", [])) > 0:
                return existing_embeddings["metadatas"][0]["doc_id"]
            else:
                return None
        elif chunker.data_type.value in [item.value for item in SpecialDataType]:
            # These types don't contain indirect references.
            # Through custom logic, they can be attributed to a source and be updated.
            if chunker.data_type == DataType.QNA_PAIR:
                # QNA_PAIRs update the answer if the question already exists.
                where = {"question": src[0]}
                if self.config.id is not None:
                    where.update({"app_id": self.config.id})

                existing_embeddings = self.db.get(
                    where=where,
                    limit=1,
                )
                if len(existing_embeddings.get("metadatas", [])) > 0:
                    return existing_embeddings["metadatas"][0]["doc_id"]
                else:
                    return None
            else:
                raise NotImplementedError(
                    f"SpecialDataType {chunker.data_type} must have a custom logic to check for existing data"
                )
        else:
            raise TypeError(
                f"{chunker.data_type} is type {type(chunker.data_type)}. "
                "When it should be  DirectDataType, IndirectDataType or SpecialDataType."
            )

    def _load_and_embed(
        self,
        loader: BaseLoader,
        chunker: BaseChunker,
        src: Any,
        metadata: Optional[dict[str, Any]] = None,
        source_hash: Optional[str] = None,
        add_config: Optional[AddConfig] = None,
        dry_run=False,
        **kwargs: Optional[dict[str, Any]],
    ):
        """
        Loads the data from the given URL, chunks it, and adds it to database.

        :param loader: The loader to use to load the data.
        :param chunker: The chunker to use to chunk the data.
        :param src: The data to be handled by the loader. Can be a URL for
        remote sources or local content for local loaders.
        :param metadata: Optional. Metadata associated with the data source.
        :param source_hash: Hexadecimal hash of the source.
        :param dry_run: Optional. A dry run returns chunks and doesn't update DB.
        :type dry_run: bool, defaults to False
        :return: (list) documents (embedded text), (list) metadata, (list) ids, (int) number of chunks
        """
        existing_doc_id = self._get_existing_doc_id(chunker=chunker, src=src)
        app_id = self.config.id if self.config is not None else None

        # Create chunks
        embeddings_data = chunker.create_chunks(loader, src, app_id=app_id, config=add_config.chunker)
        # spread chunking results
        documents = embeddings_data["documents"]
        metadatas = embeddings_data["metadatas"]
        ids = embeddings_data["ids"]
        new_doc_id = embeddings_data["doc_id"]

        if existing_doc_id and existing_doc_id == new_doc_id:
            logger.info("Doc content has not changed. Skipping creating chunks and embeddings")
            return [], [], [], 0

        # this means that doc content has changed.
        if existing_doc_id and existing_doc_id != new_doc_id:
            logger.info("Doc content has changed. Recomputing chunks and embeddings intelligently.")
            self.db.delete({"doc_id": existing_doc_id})

        # get existing ids, and discard doc if any common id exist.
        where = {"url": src}
        if chunker.data_type == DataType.JSON and is_valid_json_string(src):
            url = hashlib.sha256((src).encode("utf-8")).hexdigest()
            where = {"url": url}

        # if data type is qna_pair, we check for question
        if chunker.data_type == DataType.QNA_PAIR:
            where = {"question": src[0]}

        if self.config.id is not None:
            where["app_id"] = self.config.id

        db_result = self.db.get(ids=ids, where=where)  # optional filter
        existing_ids = set(db_result["ids"])
        if len(existing_ids):
            data_dict = {id: (doc, meta) for id, doc, meta in zip(ids, documents, metadatas)}
            data_dict = {id: value for id, value in data_dict.items() if id not in existing_ids}

            if not data_dict:
                src_copy = src
                if len(src_copy) > 50:
                    src_copy = src[:50] + "..."
                logger.info(f"All data from {src_copy} already exists in the database.")
                # Make sure to return a matching return type
                return [], [], [], 0

            ids = list(data_dict.keys())
            documents, metadatas = zip(*data_dict.values())

        # Loop though all metadatas and add extras.
        new_metadatas = []
        for m in metadatas:
            # Add app id in metadatas so that they can be queried on later
            if self.config.id:
                m["app_id"] = self.config.id

            # Add hashed source
            m["hash"] = source_hash

            # Note: Metadata is the function argument
            if metadata:
                # Spread whatever is in metadata into the new object.
                m.update(metadata)

            new_metadatas.append(m)
        metadatas = new_metadatas

        if dry_run:
            return list(documents), metadatas, ids, 0

        # Count before, to calculate a delta in the end.
        chunks_before_addition = self.db.count()

        # Filter out empty documents and ensure they meet the API requirements
        valid_documents = [doc for doc in documents if doc and isinstance(doc, str)]

        documents = valid_documents

        # Chunk documents into batches of 2048 and handle each batch
        # helps wigth large loads of embeddings  that hit OpenAI limits
        document_batches = [documents[i : i + 2048] for i in range(0, len(documents), 2048)]
        metadata_batches = [metadatas[i : i + 2048] for i in range(0, len(metadatas), 2048)]
        id_batches = [ids[i : i + 2048] for i in range(0, len(ids), 2048)]
        for batch_docs, batch_meta, batch_ids in zip(document_batches, metadata_batches, id_batches):
            try:
                # Add only valid batches
                if batch_docs:
                    self.db.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids, **kwargs)
            except Exception as e:
                logger.info(f"Failed to add batch due to a bad request: {e}")
                # Handle the error, e.g., by logging, retrying, or skipping
                pass

        count_new_chunks = self.db.count() - chunks_before_addition
        logger.info(f"Successfully saved {str(src)[:100]} ({chunker.data_type}). New chunks count: {count_new_chunks}")

        return list(documents), metadatas, ids, count_new_chunks

    @staticmethod
    def _format_result(results):
        return [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def _retrieve_from_database(
        self,
        input_query: str,
        config: Optional[BaseLlmConfig] = None,
        where=None,
        citations: bool = False,
        **kwargs: Optional[dict[str, Any]],
    ) -> Union[list[tuple[str, str, str]], list[str]]:
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query

        :param input_query: The query to use.
        :type input_query: str
        :param config: The query configuration, defaults to None
        :type config: Optional[BaseLlmConfig], optional
        :param where: A dictionary of key-value pairs to filter the database results, defaults to None
        :type where: _type_, optional
        :param citations: A boolean to indicate if db should fetch citation source
        :type citations: bool
        :return: List of contents of the document that matched your query
        :rtype: list[str]
        """
        query_config = config or self.llm.config
        if where is not None:
            where = where
        else:
            where = {}
            if query_config is not None and query_config.where is not None:
                where = query_config.where

            if self.config.id is not None:
                where.update({"app_id": self.config.id})

        contexts = self.db.query(
            input_query=input_query,
            n_results=query_config.number_documents,
            where=where,
            citations=citations,
            **kwargs,
        )

        return contexts

    def query(
        self,
        input_query: str,
        config: BaseLlmConfig = None,
        dry_run=False,
        where: Optional[dict] = None,
        citations: bool = False,
        **kwargs: dict[str, Any],
    ) -> Union[tuple[str, list[tuple[str, dict]]], str]:
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        :param input_query: The query to use.
        :type input_query: str
        :param config: The `BaseLlmConfig` instance to use as configuration options. This is used for one method call.
        To persistently use a config, declare it during app init., defaults to None
        :type config: Optional[BaseLlmConfig], optional
        :param dry_run: A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response., defaults to False
        :type dry_run: bool, optional
        :param where: A dictionary of key-value pairs to filter the database results., defaults to None
        :type where: Optional[dict[str, str]], optional
        :param kwargs: To read more params for the query function. Ex. we use citations boolean
        param to return context along with the answer
        :type kwargs: dict[str, Any]
        :return: The answer to the query, with citations if the citation flag is True
        or the dry run result
        :rtype: str, if citations is False, otherwise tuple[str, list[tuple[str,str,str]]]
        """
        contexts = self._retrieve_from_database(
            input_query=input_query, config=config, where=where, citations=citations, **kwargs
        )
        if citations and len(contexts) > 0 and isinstance(contexts[0], tuple):
            contexts_data_for_llm_query = list(map(lambda x: x[0], contexts))
        else:
            contexts_data_for_llm_query = contexts

        if self.cache_config is not None:
            logger.info("Cache enabled. Checking cache...")
            answer = adapt(
                llm_handler=self.llm.query,
                cache_data_convert=gptcache_data_convert,
                update_cache_callback=gptcache_update_cache_callback,
                session=get_gptcache_session(session_id=self.config.id),
                input_query=input_query,
                contexts=contexts_data_for_llm_query,
                config=config,
                dry_run=dry_run,
            )
        else:
            answer = self.llm.query(
                input_query=input_query, contexts=contexts_data_for_llm_query, config=config, dry_run=dry_run
            )

        # Send anonymous telemetry
        self.telemetry.capture(event_name="query", properties=self._telemetry_props)

        if citations:
            return answer, contexts
        else:
            return answer

    def chat(
        self,
        input_query: str,
        config: Optional[BaseLlmConfig] = None,
        dry_run=False,
        session_id: str = "default",
        where: Optional[dict[str, str]] = None,
        citations: bool = False,
        **kwargs: dict[str, Any],
    ) -> Union[tuple[str, list[tuple[str, dict]]], str]:
        """
        Queries the vector database on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        Maintains the whole conversation in memory.

        :param input_query: The query to use.
        :type input_query: str
        :param config: The `BaseLlmConfig` instance to use as configuration options. This is used for one method call.
        To persistently use a config, declare it during app init., defaults to None
        :type config: Optional[BaseLlmConfig], optional
        :param dry_run: A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response., defaults to False
        :type dry_run: bool, optional
        :param session_id: The session id to use for chat history, defaults to 'default'.
        :type session_id: Optional[str], optional
        :param where: A dictionary of key-value pairs to filter the database results., defaults to None
        :type where: Optional[dict[str, str]], optional
        :param kwargs: To read more params for the query function. Ex. we use citations boolean
        param to return context along with the answer
        :type kwargs: dict[str, Any]
        :return: The answer to the query, with citations if the citation flag is True
        or the dry run result
        :rtype: str, if citations is False, otherwise tuple[str, list[tuple[str,str,str]]]
        """
        contexts = self._retrieve_from_database(
            input_query=input_query, config=config, where=where, citations=citations, **kwargs
        )
        if citations and len(contexts) > 0 and isinstance(contexts[0], tuple):
            contexts_data_for_llm_query = list(map(lambda x: x[0], contexts))
        else:
            contexts_data_for_llm_query = contexts

        # Update the history beforehand so that we can handle multiple chat sessions in the same python session
        self.llm.update_history(app_id=self.config.id, session_id=session_id)

        if self.cache_config is not None:
            logger.debug("Cache enabled. Checking cache...")
            cache_id = f"{session_id}--{self.config.id}"
            answer = adapt(
                llm_handler=self.llm.chat,
                cache_data_convert=gptcache_data_convert,
                update_cache_callback=gptcache_update_cache_callback,
                session=get_gptcache_session(session_id=cache_id),
                input_query=input_query,
                contexts=contexts_data_for_llm_query,
                config=config,
                dry_run=dry_run,
            )
        else:
            logger.debug("Cache disabled. Running chat without cache.")
            answer = self.llm.chat(
                input_query=input_query, contexts=contexts_data_for_llm_query, config=config, dry_run=dry_run
            )

        # add conversation in memory
        self.llm.add_history(self.config.id, input_query, answer, session_id=session_id)

        # Send anonymous telemetry
        self.telemetry.capture(event_name="chat", properties=self._telemetry_props)

        if citations:
            return answer, contexts
        else:
            return answer

    def search(self, query, num_documents=3, where=None, raw_filter=None, namespace=None):
        """
        Search for similar documents related to the query in the vector database.

        Args:
            query (str): The query to use.
            num_documents (int, optional): Number of similar documents to fetch. Defaults to 3.
            where (dict[str, any], optional): Filter criteria for the search.
            raw_filter (dict[str, any], optional): Advanced raw filter criteria for the search.
            namespace (str, optional): The namespace to search in. Defaults to None.

        Raises:
            ValueError: If both `raw_filter` and `where` are used simultaneously.

        Returns:
            list[dict]: A list of dictionaries, each containing the 'context' and 'metadata' of a document.
        """
        # Send anonymous telemetry
        self.telemetry.capture(event_name="search", properties=self._telemetry_props)

        if raw_filter and where:
            raise ValueError("You can't use both `raw_filter` and `where` together.")

        filter_type = "raw_filter" if raw_filter else "where"
        filter_criteria = raw_filter if raw_filter else where

        params = {
            "input_query": query,
            "n_results": num_documents,
            "citations": True,
            "app_id": self.config.id,
            "namespace": namespace,
            filter_type: filter_criteria,
        }

        return [{"context": c[0], "metadata": c[1]} for c in self.db.query(**params)]

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        Using `app.db.set_collection_name` method is preferred to this.

        :param name: Name of the collection.
        :type name: str
        """
        self.db.set_collection_name(name)
        # Create the collection if it does not exist
        self.db._get_or_create_collection(name)
        # TODO: Check whether it is necessary to assign to the `self.collection` attribute,
        # since the main purpose is the creation.

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        `App` does not have to be reinitialized after using this method.
        """
        try:
            self.db_session.query(DataSource).filter_by(app_id=self.config.id).delete()
            self.db_session.query(ChatHistory).filter_by(app_id=self.config.id).delete()
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error deleting data sources: {e}")
            self.db_session.rollback()
            return None
        self.db.reset()
        self.delete_all_chat_history(app_id=self.config.id)
        # Send anonymous telemetry
        self.telemetry.capture(event_name="reset", properties=self._telemetry_props)

    def get_history(
        self,
        num_rounds: int = 10,
        display_format: bool = True,
        session_id: Optional[str] = "default",
        fetch_all: bool = False,
    ):
        history = self.llm.memory.get(
            app_id=self.config.id,
            session_id=session_id,
            num_rounds=num_rounds,
            display_format=display_format,
            fetch_all=fetch_all,
        )
        return history

    def delete_session_chat_history(self, session_id: str = "default"):
        self.llm.memory.delete(app_id=self.config.id, session_id=session_id)
        self.llm.update_history(app_id=self.config.id)

    def delete_all_chat_history(self, app_id: str):
        self.llm.memory.delete(app_id=app_id)
        self.llm.update_history(app_id=app_id)

    def delete(self, source_id: str):
        """
        Deletes the data from the database.
        :param source_hash: The hash of the source.
        :type source_hash: str
        """
        try:
            self.db_session.query(DataSource).filter_by(hash=source_id, app_id=self.config.id).delete()
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error deleting data sources: {e}")
            self.db_session.rollback()
            return None
        self.db.delete(where={"hash": source_id})
        logger.info(f"Successfully deleted {source_id}")
        # Send anonymous telemetry
        if self.config.collect_metrics:
            self.telemetry.capture(event_name="delete", properties=self._telemetry_props)
