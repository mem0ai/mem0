import hashlib
import importlib.metadata
import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from langchain.docstore.document import Document
from tenacity import retry, stop_after_attempt, wait_fixed

from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config import AddConfig, BaseLlmConfig
from embedchain.config.apps.BaseAppConfig import BaseAppConfig
from embedchain.data_formatter import DataFormatter
from embedchain.embedder.base import BaseEmbedder
from embedchain.helper.json_serializable import JSONSerializable
from embedchain.llm.base import BaseLlm
from embedchain.loaders.base_loader import BaseLoader
from embedchain.models.data_type import DataType
from embedchain.utils import detect_datatype
from embedchain.vectordb.base import BaseVectorDB

load_dotenv()

ABS_PATH = os.getcwd()
HOME_DIR = str(Path.home())
CONFIG_DIR = os.path.join(HOME_DIR, ".embedchain")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


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

        # Add subclasses
        ## Llm
        self.llm = llm
        ## Database
        # Database has support for config assignment for backwards compatibility
        if db is None and (not hasattr(self.config, "db") or self.config.db is None):
            raise ValueError("App requires Database.")
        self.db = db or self.config.db
        ## Embedder
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

        # Attributes that aren't subclass related.
        self.user_asks = []

        # Send anonymous telemetry
        self.s_id = self.config.id if self.config.id else str(uuid.uuid4())
        self.u_id = self._load_or_generate_user_id()
        # NOTE: Uncomment the next two lines when running tests to see if any test fires a telemetry event.
        # if (self.config.collect_metrics):
        #     raise ConnectionRefusedError("Collection of metrics should not be allowed.")
        thread_telemetry = threading.Thread(target=self._send_telemetry_event, args=("init",))
        thread_telemetry.start()

    def _load_or_generate_user_id(self) -> str:
        """
        Loads the user id from the config file if it exists, otherwise generates a new
        one and saves it to the config file.

        :return: user id
        :rtype: str
        """
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)

        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                if "user_id" in data:
                    return data["user_id"]

        u_id = str(uuid.uuid4())
        with open(CONFIG_FILE, "w") as f:
            json.dump({"user_id": u_id}, f)

        return u_id

    def add(
        self,
        source: Any,
        data_type: Optional[DataType] = None,
        metadata: Optional[Dict[str, Any]] = None,
        config: Optional[AddConfig] = None,
        dry_run=False,
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
        :type metadata: Optional[Dict[str, Any]], optional
        :param config: The `AddConfig` instance to use as configuration options., defaults to None
        :type config: Optional[AddConfig], optional
        :raises ValueError: Invalid data type
        :param dry_run: Optional. A dry run displays the chunks to ensure that the loader and chunker work as intended.
        deafaults to False
        :return: source_id, a md5-hash of the source, in hexadecimal representation.
        :rtype: str
        """
        if config is None:
            config = AddConfig()

        try:
            DataType(source)
            logging.warning(
                f"""Starting from version v0.0.40, Embedchain can automatically detect the data type. So, in the `add` method, the argument order has changed. You no longer need to specify '{source}' for the `source` argument. So the code snippet will be `.add("{data_type}", "{source}")`"""  # noqa #E501
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
        self.user_asks.append([source, data_type.value, metadata])
        documents, metadatas, _ids, new_chunks = self.load_and_embed_v2(
            data_formatter.loader, data_formatter.chunker, source, metadata, source_id, dry_run
        )
        if data_type in {DataType.DOCS_SITE}:
            self.is_docs_site_instance = True

        if dry_run:
            data_chunks_info = {"chunks": documents, "metadata": metadatas, "count": len(documents), "type": data_type}
            logging.debug(f"Dry run info : {data_chunks_info}")
            return data_chunks_info

        # Send anonymous telemetry
        if self.config.collect_metrics:
            # it's quicker to check the variable twice than to count words when they won't be submitted.
            word_count = sum([len(document.split(" ")) for document in documents])

            extra_metadata = {"data_type": data_type.value, "word_count": word_count, "chunks_count": new_chunks}
            thread_telemetry = threading.Thread(target=self._send_telemetry_event, args=("add", extra_metadata))
            thread_telemetry.start()

        return source_id

    def add_local(
        self,
        source: Any,
        data_type: Optional[DataType] = None,
        metadata: Optional[Dict[str, Any]] = None,
        config: Optional[AddConfig] = None,
    ):
        """
        Adds the data from the given URL to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        Warning:
            This method is deprecated and will be removed in future versions. Use `add` instead.

        :param source: The data to embed, can be a URL, local file or raw content, depending on the data type.
        :type source: Any
        :param data_type: Automatically detected, but can be forced with this argument. The type of the data to add,
        defaults to None
        :type data_type: Optional[DataType], optional
        :param metadata: Metadata associated with the data source., defaults to None
        :type metadata: Optional[Dict[str, Any]], optional
        :param config: The `AddConfig` instance to use as configuration options., defaults to None
        :type config: Optional[AddConfig], optional
        :raises ValueError: Invalid data type
        :return: source_id, a md5-hash of the source, in hexadecimal representation.
        :rtype: str
        """
        logging.warning(
            "The `add_local` method is deprecated and will be removed in future versions. Please use the `add` method for both local and remote files."  # noqa: E501
        )
        return self.add(source=source, data_type=data_type, metadata=metadata, config=config)

    def load_and_embed(
        self,
        loader: BaseLoader,
        chunker: BaseChunker,
        src: Any,
        metadata: Optional[Dict[str, Any]] = None,
        source_id: Optional[str] = None,
        dry_run=False,
    ) -> Tuple[List[str], Dict[str, Any], List[str], int]:
        """The loader to use to load the data.

        :param loader: The loader to use to load the data.
        :type loader: BaseLoader
        :param chunker: The chunker to use to chunk the data.
        :type chunker: BaseChunker
        :param src: The data to be handled by the loader.
        Can be a URL for remote sources or local content for local loaders.
        :type src: Any
        :param metadata: Metadata associated with the data source., defaults to None
        :type metadata: Dict[str, Any], optional
        :param source_id: Hexadecimal hash of the source., defaults to None
        :type source_id: str, optional
        :param dry_run: Optional. A dry run returns chunks and doesn't update DB.
        :type dry_run: bool, defaults to False
        :return: (List) documents (embedded text), (List) metadata, (list) ids, (int) number of chunks
        :rtype: Tuple[List[str], Dict[str, Any], List[str], int]
        """
        embeddings_data = chunker.create_chunks(loader, src)

        # spread chunking results
        documents = embeddings_data["documents"]
        metadatas = embeddings_data["metadatas"]
        ids = embeddings_data["ids"]

        # get existing ids, and discard doc if any common id exist.
        where = {"app_id": self.config.id} if self.config.id is not None else {}
        # where={"url": src}
        db_result = self.db.get(
            ids=ids,
            where=where,  # optional filter
        )
        existing_ids = set(db_result["ids"])

        if len(existing_ids):
            data_dict = {id: (doc, meta) for id, doc, meta in zip(ids, documents, metadatas)}
            data_dict = {id: value for id, value in data_dict.items() if id not in existing_ids}

            if not data_dict:
                print(f"All data from {src} already exists in the database.")
                # Make sure to return a matching return type
                return [], [], [], 0

            ids = list(data_dict.keys())
            documents, metadatas = zip(*data_dict.values())

        if dry_run:
            return list(documents), metadatas, ids, 0

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
        chunks_before_addition = self.db.count()

        self.db.add(documents=documents, metadatas=metadatas, ids=ids)
        count_new_chunks = self.db.count() - chunks_before_addition
        print((f"Successfully saved {src} ({chunker.data_type}). New chunks count: {count_new_chunks}"))
        return list(documents), metadatas, ids, count_new_chunks

    def load_and_embed_v2(
        self,
        loader: BaseLoader,
        chunker: BaseChunker,
        src: Any,
        metadata: Optional[Dict[str, Any]] = None,
        source_id: Optional[str] = None,
        dry_run=False,
    ):
        """
        Loads the data from the given URL, chunks it, and adds it to database.

        :param loader: The loader to use to load the data.
        :param chunker: The chunker to use to chunk the data.
        :param src: The data to be handled by the loader. Can be a URL for
        remote sources or local content for local loaders.
        :param metadata: Optional. Metadata associated with the data source.
        :param source_id: Hexadecimal hash of the source.
        :return: (List) documents (embedded text), (List) metadata, (list) ids, (int) number of chunks
        """
        existing_embeddings_data = self.db.get(
            where={
                "url": src,
            },
            limit=1,
        )
        try:
            existing_doc_id = existing_embeddings_data.get("metadatas", [])[0]["doc_id"]
        except Exception:
            existing_doc_id = None
        embeddings_data = chunker.create_chunks(loader, src)

        # spread chunking results
        documents = embeddings_data["documents"]
        metadatas = embeddings_data["metadatas"]
        ids = embeddings_data["ids"]
        new_doc_id = embeddings_data["doc_id"]

        if existing_doc_id and existing_doc_id == new_doc_id:
            print("Doc content has not changed. Skipping creating chunks and embeddings")
            return [], [], [], 0

        # this means that doc content has changed.
        if existing_doc_id and existing_doc_id != new_doc_id:
            print("Doc content has changed. Recomputing chunks and embeddings intelligently.")
            self.db.delete({"doc_id": existing_doc_id})

        # get existing ids, and discard doc if any common id exist.
        where = {"app_id": self.config.id} if self.config.id is not None else {}
        # where={"url": src}
        db_result = self.db.get(
            ids=ids,
            where=where,  # optional filter
        )
        existing_ids = set(db_result["ids"])

        if len(existing_ids):
            data_dict = {id: (doc, meta) for id, doc, meta in zip(ids, documents, metadatas)}
            data_dict = {id: value for id, value in data_dict.items() if id not in existing_ids}

            if not data_dict:
                print(f"All data from {src} already exists in the database.")
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
        count_new_chunks = self.count() - chunks_before_addition
        print((f"Successfully saved {src} ({chunker.data_type}). New chunks count: {count_new_chunks}"))
        return list(documents), metadatas, ids, count_new_chunks

    def _format_result(self, results):
        return [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def retrieve_from_database(self, input_query: str, config: Optional[BaseLlmConfig] = None, where=None) -> List[str]:
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query

        :param input_query: The query to use.
        :type input_query: str
        :param config: The query configuration, defaults to None
        :type config: Optional[BaseLlmConfig], optional
        :param where: A dictionary of key-value pairs to filter the database results, defaults to None
        :type where: _type_, optional
        :return: List of contents of the document that matched your query
        :rtype: List[str]
        """
        query_config = config or self.llm.config

        if where is not None:
            where = where
        elif query_config is not None and query_config.where is not None:
            where = query_config.where
        else:
            where = {}

        if self.config.id is not None:
            where.update({"app_id": self.config.id})

        contents = self.db.query(
            input_query=input_query,
            n_results=query_config.number_documents,
            where=where,
        )

        return contents

    def query(self, input_query: str, config: BaseLlmConfig = None, dry_run=False, where: Optional[Dict] = None) -> str:
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        :param input_query: The query to use.
        :type input_query: str
        :param config: The `LlmConfig` instance to use as configuration options. This is used for one method call.
        To persistently use a config, declare it during app init., defaults to None
        :type config: Optional[BaseLlmConfig], optional
        :param dry_run: A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response., defaults to False
        :type dry_run: bool, optional
        :param where: A dictionary of key-value pairs to filter the database results., defaults to None
        :type where: Optional[Dict[str, str]], optional
        :return: The answer to the query or the dry run result
        :rtype: str
        """
        contexts = self.retrieve_from_database(input_query=input_query, config=config, where=where)
        answer = self.llm.query(input_query=input_query, contexts=contexts, config=config, dry_run=dry_run)

        # Send anonymous telemetry
        thread_telemetry = threading.Thread(target=self._send_telemetry_event, args=("query",))
        thread_telemetry.start()

        return answer

    def chat(
        self,
        input_query: str,
        config: Optional[BaseLlmConfig] = None,
        dry_run=False,
        where: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Queries the vector database on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        Maintains the whole conversation in memory.

        :param input_query: The query to use.
        :type input_query: str
        :param config: The `LlmConfig` instance to use as configuration options. This is used for one method call.
        To persistently use a config, declare it during app init., defaults to None
        :type config: Optional[BaseLlmConfig], optional
        :param dry_run: A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response., defaults to False
        :type dry_run: bool, optional
        :param where: A dictionary of key-value pairs to filter the database results., defaults to None
        :type where: Optional[Dict[str, str]], optional
        :return: The answer to the query or the dry run result
        :rtype: str
        """
        contexts = self.retrieve_from_database(input_query=input_query, config=config, where=where)
        answer = self.llm.chat(input_query=input_query, contexts=contexts, config=config, dry_run=dry_run)

        # Send anonymous telemetry
        thread_telemetry = threading.Thread(target=self._send_telemetry_event, args=("chat",))
        thread_telemetry.start()

        return answer

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

    def count(self) -> int:
        """
        Count the number of embeddings.

        DEPRECATED IN FAVOR OF `db.count()`

        :return: The number of embeddings.
        :rtype: int
        """
        logging.warning("DEPRECATION WARNING: Please use `app.db.count()` instead of `app.count()`.")
        return self.db.count()

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        `App` does not have to be reinitialized after using this method.

        DEPRECATED IN FAVOR OF `db.reset()`
        """
        # Send anonymous telemetry
        thread_telemetry = threading.Thread(target=self._send_telemetry_event, args=("reset",))
        thread_telemetry.start()

        logging.warning("DEPRECATION WARNING: Please use `app.db.reset()` instead of `App.reset()`.")
        self.db.reset()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def _send_telemetry_event(self, method: str, extra_metadata: Optional[dict] = None):
        """
        Send telemetry event to the embedchain server. This is anonymous. It can be toggled off in `AppConfig`.
        """
        if not self.config.collect_metrics:
            return

        with threading.Lock():
            url = "https://api.embedchain.ai/api/v1/telemetry/"
            metadata = {
                "s_id": self.s_id,
                "version": importlib.metadata.version(__package__ or __name__),
                "method": method,
                "language": "py",
                "u_id": self.u_id,
            }
            if extra_metadata:
                metadata.update(extra_metadata)

            response = requests.post(url, json={"metadata": metadata})
            if response.status_code != 200:
                logging.warning(f"Telemetry event failed with status code {response.status_code}")
