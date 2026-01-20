"""
title: Long Term Memory Filter
author: Anton Nilsson
date: 2024-08-23
version: 1.0
license: MIT
description: A filter that processes user messages and stores them as long term memory by utilizing the mem0 framework together with qdrant and ollama
requirements: pydantic, ollama, mem0ai
"""

from typing import List, Optional
from pydantic import BaseModel
import json
from mem0 import Memory
import threading

class Pipeline:
    class Valves(BaseModel):
        pipelines: List[str] = []
        priority: int = 0

        store_cycles: int = 5 # Number of messages from the user before the data is processed and added to the memory
        mem_zero_user: str = "user" # Memories belongs to this user, only used by mem0 for internal organization of memories

        # Default values for the mem0 vector store
        vector_store_qdrant_name: str = "memories"
        vector_store_qdrant_url: str = "host.docker.internal"
        vector_store_qdrant_port: int = 6333
        vector_store_qdrant_dims: int = 768 # Need to match the vector dimensions of the embedder model

        # Default values for the mem0 language model
        ollama_llm_model: str = "llama3.1:latest" # This model need to exist in ollama
        ollama_llm_temperature: float = 0
        ollama_llm_tokens: int = 8000
        ollama_llm_url: str = "http://host.docker.internal:11434"

        # Default values for the mem0 embedding model
        ollama_embedder_model: str = "nomic-embed-text:latest" # This model need to exist in ollama
        ollama_embedder_url: str = "http://host.docker.internal:11434"

    def __init__(self):
        self.type = "filter"
        self.name = "Memory Filter"
        self.user_messages = []
        self.thread = None
        self.valves = self.Valves(
            **{
                "pipelines": ["*"],  # Connect to all pipelines
            }
        )
        self.m = self.init_mem_zero()

    async def on_startup(self):
        print(f"on_startup:{__name__}")
        pass

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")
        pass

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        print(f"pipe:{__name__}")

        user = self.valves.mem_zero_user
        store_cycles = self.valves.store_cycles

        if isinstance(body, str):
            body = json.loads(body)

        all_messages = body["messages"]
        last_message = all_messages[-1]["content"]

        self.user_messages.append(last_message)

        if len(self.user_messages) == store_cycles:

            message_text = ""
            for message in self.user_messages:
                message_text += message + " "

            if self.thread and self.thread.is_alive():
                print("Waiting for previous memory to be done")
                self.thread.join()

            self.thread = threading.Thread(target=self.m.add, kwargs={"data":message_text,"user_id":user})

            print("Text to be processed in to a memory:")
            print(message_text)

            self.thread.start()
            self.user_messages.clear()

        memories = self.m.search(last_message, user_id=user)

        if(memories):
            fetched_memory = memories[0]["memory"]
        else:
            fetched_memory = ""

        print("Memory added to the context:")
        print(fetched_memory)

        if fetched_memory:
            all_messages.insert(0, {"role":"system", "content":"This is your inner voice talking, you remember this about the person you chatting with "+str(fetched_memory)})

        print("Final body to send to the LLM:")
        print(body)

        return body

    def init_mem_zero(self):
        config = {
                "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": self.valves.vector_store_qdrant_name,
                    "host": self.valves.vector_store_qdrant_url,
                    "port": self.valves.vector_store_qdrant_port,
                    "embedding_model_dims": self.valves.vector_store_qdrant_dims,
                },
            },
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": self.valves.ollama_llm_model,
                    "temperature": self.valves.ollama_llm_temperature,
                    "max_tokens": self.valves.ollama_llm_tokens,
                    "ollama_base_url": self.valves.ollama_llm_url,
                },
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": self.valves.ollama_embedder_model,
                    "ollama_base_url": self.valves.ollama_embedder_url,
                },
            },
        }

        return Memory.from_config(config)