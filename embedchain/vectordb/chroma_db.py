import chromadb
import os

from chromadb.utils import embedding_functions
from ..utils import split_connection_string

from embedchain.vectordb.base_vector_db import BaseVectorDB

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-ada-002"
)

class ChromaDB(BaseVectorDB):
    def __init__(self, db_dir=None, server=None):
        if db_dir is None:
            db_dir = "db"

        if server is None:
            self.client_settings = chromadb.config.Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=db_dir,
                anonymized_telemetry=False
            )
        else:
            _schema, host, port = split_connection_string(server)
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
        return chromadb.Client(self.client_settings)

    def _get_or_create_collection(self):
        return self.client.get_or_create_collection(
            'embedchain_store', embedding_function=openai_ef,
        )