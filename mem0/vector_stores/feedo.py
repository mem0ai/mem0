import logging
import asyncio
from typing import Any, List, Optional

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

class Feedo(VectorStoreBase):
    """
    Feedo Protocol integration for mem0.
    Feedo is a decentralized long-term memory network providing encrypted-at-rest storage.
    """

    def __init__(self, usage_key: str, did: str, namespace: str = ""):
        """
        Initialize the Feedo vector store.

        Args:
            usage_key (str): The Feedo usage key for authentication.
            did (str): The decentralized identity (DID) for the agent.
            namespace (str, optional): Tenant isolation namespace (e.g., room_id or user_id).
        """
        try:
            from feedo.router import NodeRouter
            from feedo.modules.search import SearchModule
        except ImportError:
            raise ImportError(
                "Could not import feedo python package. "
                "Please install it with `pip install feedo-sdk`."
            )

        router = NodeRouter()
        self.client = SearchModule(router=router, usage_key=usage_key, did=did)
        self.namespace = namespace

    def create_col(self, name, vector_size, distance):
        """Feedo handles dynamic schema internally."""
        pass

    def insert(self, vectors, payloads=None, ids=None):
        """
        Insert vectors into a collection.
        Currently Feedo handles vectorization on the node side.
        We extract the raw text from the payload to securely transmit and index.
        """
        logger.info(f"Inserting {len(vectors)} memories into Feedo network")
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for i, payload in enumerate(payloads or []):
            text = payload.get("data", "")
            doc_id = ids[i] if ids else f"doc_{i}"
            
            loop.run_until_complete(
                self.client.index_private_document(
                    hash_id=doc_id,
                    plaintext=text,
                    metadata=payload,
                    namespace=self.namespace
                )
            )

    def search(self, query: str, vectors: list, top_k: int = 5, filters: dict = None) -> list:
        """Search for similar vectors."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        response = loop.run_until_complete(
            self.client.search(
                query=query,
                limit=top_k,
                namespace=self.namespace
            )
        )
        
        docs = response.get("documents", []) or response.get("data", []) or response.get("results", [])
        
        # Mem0 expects results formatted with payload, score, etc.
        # Qdrant integration returns objects with .id, .payload, .score
        # Mem0 internal format: we can return dicts or objects depending on what mem0 expects, 
        # but let's look at `base.py` or just return dicts.
        
        class Hit:
            def __init__(self, id, payload, score):
                self.id = id
                self.payload = payload
                self.score = score
        
        hits = []
        for doc in docs:
            score = float(doc.get("score", 0.0))
            metadata = doc.get("metadata", {})
            doc_id = doc.get("hash_id") or metadata.get("id") or "unknown"
            
            hits.append(Hit(id=doc_id, payload=metadata, score=score))
            
        return hits

    def delete(self, vector_id):
        raise NotImplementedError("Delete by vector_id not natively supported by Feedo yet.")

    def update(self, vector_id, vector=None, payload=None):
        raise NotImplementedError("Update not natively supported by Feedo yet.")

    def get(self, vector_id):
        raise NotImplementedError("Get by vector_id not natively supported by Feedo yet.")

    def list_cols(self):
        return [self.namespace]

    def delete_col(self):
        pass

    def col_info(self):
        return {"name": self.namespace}

    def list(self):
        raise NotImplementedError("List not natively supported by Feedo yet.")
