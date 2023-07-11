import os

import chromadb
from chromadb.utils import embedding_functions
from ..utils import split_connection_string

from embedchain.vectordb.base_vector_db import BaseVectorDB


class ChromaDB(BaseVectorDB):
    """Vector database using ChromaDB."""

    def __init__(self, ef=None, db_dir=None, db_server=None):
        if ef:
            self.ef = ef
        else:
            self.ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                organization_id=os.getenv("OPENAI_ORGANIZATION"),
                model_name="text-embedding-ada-002",
            )

        if db_dir is None:
            db_dir = "db"

        if db_server is None:
            self.client_settings = chromadb.config.Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=db_dir,
                anonymized_telemetry=False
            )
        else:
            _schema, host, port = split_connection_string(db_server)
            self.client_settings = chromadb.config.Settings(
                chroma_api_impl="rest",
                chroma_server_host=host,
                chroma_server_http_port=port,
                chroma_db_impl="duckdb+parquet",
                persist_directory=db_dir,
                anonymized_telemetry=False
            )
        super().__init__()

    def _get_or_create_db(self):
        """Get or create the database."""
        return chromadb.Client(self.client_settings)

    def _get_or_create_collection(self):
        """Get or create the collection."""
        return self.client.get_or_create_collection(
            "embedchain_store",
            embedding_function=self.ef,
        )
