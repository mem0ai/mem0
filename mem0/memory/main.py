import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ValidationError

from mem0.llms.utils.tools import (
    ADD_MEMORY_TOOL,
    DELETE_MEMORY_TOOL,
    UPDATE_MEMORY_TOOL,
)
from mem0.configs.prompts import MEMORY_DEDUCTION_PROMPT
from mem0.memory.base import MemoryBase
from mem0.memory.setup import mem0_dir, setup_config
from mem0.memory.storage import SQLiteManager
from mem0.memory.telemetry import capture_event
from mem0.memory.utils import get_update_memory_messages
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.llms.configs import LlmConfig
from mem0.embeddings.configs import EmbedderConfig
from mem0.vector_stores.qdrant import Qdrant
from mem0.utils.factory import LlmFactory, EmbedderFactory

# Setup user config
setup_config()


class MemoryItem(BaseModel):
    id: str = Field(..., description="The unique identifier for the text data")
    text: str = Field(..., description="The text content")
    # The metadata value can be anything and not just string. Fix it
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the text data"
    )
    score: Optional[float] = Field(
        None, description="The score associated with the text data"
    )


class MemoryConfig(BaseModel):
    vector_store: VectorStoreConfig = Field(
        description="Configuration for the vector store",
        default_factory=VectorStoreConfig,
    )
    llm: LlmConfig = Field(
        description="Configuration for the language model",
        default_factory=LlmConfig,
    )
    embedder: EmbedderConfig = Field(
        description="Configuration for the embedding model",
        default_factory=EmbedderConfig,
    )
    history_db_path: str = Field(
        description="Path to the history database",
        default=os.path.join(mem0_dir, "history.db"),
    )
    collection_name: str = Field(default="mem0", description="Name of the collection")
    embedding_model_dims: int = Field(
        default=1536, description="Dimensions of the embedding model"
    )


class Memory(MemoryBase):
    def __init__(self, config: MemoryConfig = MemoryConfig()):
        self.config = config
        self.embedding_model = EmbedderFactory.create(self.config.embedder.provider)
        # Initialize the appropriate vector store based on the configuration
        vector_store_config = self.config.vector_store.config
        if self.config.vector_store.provider == "qdrant":
            self.vector_store = Qdrant(
                host=vector_store_config.host,
                port=vector_store_config.port,
                path=vector_store_config.path,
                url=vector_store_config.url,
                api_key=vector_store_config.api_key,
            )
        else:
            raise ValueError(
                f"Unsupported vector store type: {self.config.vector_store_type}"
            )

        self.llm = LlmFactory.create(self.config.llm.provider, self.config.llm.config)
        self.db = SQLiteManager(self.config.history_db_path)
        self.collection_name = self.config.collection_name
        self.vector_store.create_col(
            name=self.collection_name, vector_size=self.embedding_model.dims
        )
        self.vector_store.create_col(
            name=self.collection_name, vector_size=self.embedding_model.dims
        )
        capture_event("mem0.init", self)

    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]):
        try:
            config = MemoryConfig(**config_dict)
        except ValidationError as e:
            logging.error(f"Configuration validation error: {e}")
            raise
        return cls(config)

    def add(
        self,
        data,
        user_id=None,
        agent_id=None,
        run_id=None,
        metadata=None,
        filters=None,
        prompt=None,
    ):
        """
        Create a new memory.

        Args:
            data (str): Data to store in the memory.
            user_id (str, optional): ID of the user creating the memory. Defaults to None.
            agent_id (str, optional): ID of the agent creating the memory. Defaults to None.
            run_id (str, optional): ID of the run creating the memory. Defaults to None.
            metadata (dict, optional): Metadata to store with the memory. Defaults to None.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            str: ID of the created memory.
        """
        if metadata is None:
            metadata = {}
        embeddings = self.embedding_model.embed(data)

        filters = filters or {}
        if user_id:
            filters["user_id"] = metadata["user_id"] = user_id
        if agent_id:
            filters["agent_id"] = metadata["agent_id"] = agent_id
        if run_id:
            filters["run_id"] = metadata["run_id"] = run_id

        if not prompt:
            prompt = MEMORY_DEDUCTION_PROMPT.format(user_input=data, metadata=metadata)
        extracted_memories = self.llm.generate_response(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at deducing facts, preferences and memories from unstructured text.",
                },
                {"role": "user", "content": prompt},
            ]
        )
        existing_memories = self.vector_store.search(
            name=self.collection_name,
            query=embeddings,
            limit=5,
            filters=filters,
        )
        existing_memories = [
            MemoryItem(
                id=mem.id,
                score=mem.score,
                metadata=mem.payload,
                text=mem.payload["data"],
            )
            for mem in existing_memories
        ]
        serialized_existing_memories = [
            item.model_dump(include={"id", "text", "score"})
            for item in existing_memories
        ]
        logging.info(f"Total existing memories: {len(existing_memories)}")
        messages = get_update_memory_messages(
            serialized_existing_memories, extracted_memories
        )
        # Add tools for noop, add, update, delete memory.
        tools = [ADD_MEMORY_TOOL, UPDATE_MEMORY_TOOL, DELETE_MEMORY_TOOL]
        response = self.llm.generate_response(messages=messages, tools=tools)
        tool_calls = response["tool_calls"]

        response = []
        if tool_calls:
            # Create a new memory
            available_functions = {
                "add_memory": self._create_memory_tool,
                "update_memory": self._update_memory_tool,
                "delete_memory": self._delete_memory_tool,
            }
            for tool_call in tool_calls:
                function_name = tool_call["name"]
                function_to_call = available_functions[function_name]
                function_args = tool_call["arguments"]
                logging.info(
                    f"[openai_func] func: {function_name}, args: {function_args}"
                )

                # Pass metadata to the function if it requires it
                if function_name in ["add_memory", "update_memory"]:
                    function_args["metadata"] = metadata

                function_result = function_to_call(**function_args)
                # Fetch the memory_id from the response
                response.append(
                    {
                        "id": function_result,
                        "event": function_name.replace("_memory", ""),
                        "data": function_args.get("data"),
                    }
                )
                capture_event(
                    "mem0.add.function_call",
                    self,
                    {"memory_id": function_result, "function_name": function_name},
                )
        capture_event("mem0.add", self)
        return response

    def get(self, memory_id):
        """
        Retrieve a memory by ID.

        Args:
            memory_id (str): ID of the memory to retrieve.

        Returns:
            dict: Retrieved memory.
        """
        capture_event("mem0.get", self, {"memory_id": memory_id})
        memory = self.vector_store.get(name=self.collection_name, vector_id=memory_id)
        if not memory:
            return None
        return MemoryItem(
            id=memory.id,
            metadata=memory.payload,
            text=memory.payload["data"],
        ).model_dump(exclude={"score"})

    def get_all(self, user_id=None, agent_id=None, run_id=None, limit=100):
        """
        List all memories.

        Returns:
            list: List of all memories.
        """
        filters = {}
        if user_id:
            filters["user_id"] = user_id
        if agent_id:
            filters["agent_id"] = agent_id
        if run_id:
            filters["run_id"] = run_id

        capture_event("mem0.get_all", self, {"filters": len(filters), "limit": limit})
        memories = self.vector_store.list(
            name=self.collection_name, filters=filters, limit=limit
        )
        return [
            MemoryItem(
                id=mem.id,
                metadata=mem.payload,
                text=mem.payload["data"],
            ).model_dump(exclude={"score"})
            for mem in memories[0]
        ]

    def search(
        self, query, user_id=None, agent_id=None, run_id=None, limit=100, filters=None
    ):
        """
        Search for memories.

        Args:
            query (str): Query to search for.
            user_id (str, optional): ID of the user to search for. Defaults to None.
            agent_id (str, optional): ID of the agent to search for. Defaults to None.
            run_id (str, optional): ID of the run to search for. Defaults to None.
            limit (int, optional): Limit the number of results. Defaults to 100.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: List of search results.
        """
        filters = filters or {}
        if user_id:
            filters["user_id"] = user_id
        if agent_id:
            filters["agent_id"] = agent_id
        if run_id:
            filters["run_id"] = run_id

        capture_event("mem0.search", self, {"filters": len(filters), "limit": limit})
        embeddings = self.embedding_model.embed(query)
        memories = self.vector_store.search(
            name=self.collection_name, query=embeddings, limit=limit, filters=filters
        )
        return [
            MemoryItem(
                id=mem.id,
                metadata=mem.payload,
                score=mem.score,
                text=mem.payload["data"],
            ).model_dump()
            for mem in memories
        ]

    def update(self, memory_id, data):
        """
        Update a memory by ID.

        Args:
            memory_id (str): ID of the memory to update.
            data (dict): Data to update the memory with.

        Returns:
            dict: Updated memory.
        """
        capture_event("mem0.get_all", self, {"memory_id": memory_id})
        self._update_memory_tool(memory_id, data)

    def delete(self, memory_id):
        """
        Delete a memory by ID.

        Args:
            memory_id (str): ID of the memory to delete.
        """
        capture_event("mem0.delete", self, {"memory_id": memory_id})
        self._delete_memory_tool(memory_id)

    def delete_all(self, user_id=None, agent_id=None, run_id=None):
        """
        Delete all memories.

        Args:
            user_id (str, optional): ID of the user to delete memories for. Defaults to None.
            agent_id (str, optional): ID of the agent to delete memories for. Defaults to None.
            run_id (str, optional): ID of the run to delete memories for. Defaults to None.
        """
        filters = {}
        if user_id:
            filters["user_id"] = user_id
        if agent_id:
            filters["agent_id"] = agent_id
        if run_id:
            filters["run_id"] = run_id

        if not filters:
            raise ValueError(
                "At least one filter is required to delete all memories. If you want to delete all memories, use the `reset()` method."
            )

        capture_event("mem0.delete_all", self, {"filters": len(filters)})
        memories = self.vector_store.list(name=self.collection_name, filters=filters)[0]
        for memory in memories:
            self._delete_memory_tool(memory.id)

    def history(self, memory_id):
        """
        Get the history of changes for a memory by ID.

        Args:
            memory_id (str): ID of the memory to get history for.

        Returns:
            list: List of changes for the memory.
        """
        capture_event("mem0.history", self, {"memory_id": memory_id})
        return self.db.get_history(memory_id)

    def _create_memory_tool(self, data, metadata=None):
        logging.info(f"Creating memory with {data=}")
        embeddings = self.embedding_model.embed(data)
        memory_id = str(uuid.uuid4())
        metadata = metadata or {}
        metadata["data"] = data
        metadata["created_at"] = int(time.time())

        self.vector_store.insert(
            name=self.collection_name,
            vectors=[embeddings],
            ids=[memory_id],
            payloads=[metadata],
        )
        self.db.add_history(memory_id, None, data, "add")
        return memory_id

    def _update_memory_tool(self, memory_id, data, metadata=None):
        existing_memory = self.vector_store.get(
            name=self.collection_name, vector_id=memory_id
        )
        prev_value = existing_memory.payload.get("data")

        new_metadata = metadata or {}
        new_metadata["data"] = data
        new_metadata["updated_at"] = int(time.time())
        embeddings = self.embedding_model.embed(data)
        self.vector_store.update(
            name=self.collection_name,
            vector_id=memory_id,
            vector=embeddings,
            payload=new_metadata,
        )
        logging.info(f"Updating memory with ID {memory_id=} with {data=}")
        self.db.add_history(memory_id, prev_value, data, "update")

    def _delete_memory_tool(self, memory_id):
        logging.info(f"Deleting memory with {memory_id=}")
        existing_memory = self.vector_store.get(
            name=self.collection_name, vector_id=memory_id
        )
        prev_value = existing_memory.payload["data"]
        self.vector_store.delete(name=self.collection_name, vector_id=memory_id)
        self.db.add_history(memory_id, prev_value, None, "delete", is_deleted=1)

    def reset(self):
        """
        Reset the memory store.
        """
        self.vector_store.delete_col(name=self.collection_name)
        self.db.reset()
        capture_event("mem0.reset", self)

    def chat(self, query):
        raise NotImplementedError("Chat function not implemented yet.")
