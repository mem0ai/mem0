import chromadb
import os

from chromadb.utils import embedding_functions

from embedchain.vectordb.base_vector_db import BaseVectorDB

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    organization_id=os.getenv("OPENAI_ORGANIZATION"),
    model_name="text-embedding-ada-002"
)

class ChromaDB(BaseVectorDB):
    def __init__(self, db_dir=None, ef=None):
        self.ef = ef if ef is not None else openai_ef
        if db_dir is None:
            db_dir = "db"
        self.client_settings = chromadb.config.Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=db_dir,
            anonymized_telemetry=False
        )
        super().__init__()

    def _get_or_create_db(self):
        return chromadb.Client(self.client_settings)

    def _get_or_create_collection(self):
        return self.client.get_or_create_collection(
            'embedchain_store', embedding_function=self.ef,
        )
