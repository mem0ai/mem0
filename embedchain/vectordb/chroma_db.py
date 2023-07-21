import logging

import chromadb
from chromadb.config import Settings

from embedchain.vectordb.base_vector_db import BaseVectorDB


class ChromaDB(BaseVectorDB):
    """Vector database using ChromaDB."""

    def __init__(self, db_dir=None, embedding_fn=None, host=None, port=None):
        self.embedding_fn = embedding_fn

        if not hasattr(embedding_fn, "__call__"):
            raise ValueError("Embedding function is not a function")

        if host and port:
            logging.info(f"Connecting to ChromaDB server: {host}:{port}")
            self.settings = Settings(chroma_server_host=host, chroma_server_http_port=port)
            self.client = chromadb.HttpClient(self.settings)
        else:
            if db_dir is None:
                db_dir = "db"
            self.settings = Settings(anonymized_telemetry=False, allow_reset=True)
            self.client = chromadb.PersistentClient(
                path=db_dir,
                settings=self.settings,
            )
        super().__init__()

    def _get_or_create_db(self):
        """Get or create the database."""
        return self.client

    def _get_or_create_collection(self):
        """Get or create the collection."""
        return self.client.get_or_create_collection(
            "embedchain_store",
            embedding_function=self.embedding_fn,
        )
