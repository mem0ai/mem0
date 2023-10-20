import threading
import uuid

import yaml

from embedchain.config import PipelineConfig
from embedchain.embedchain import EmbedChain
from embedchain.embedder.base import BaseEmbedder
from embedchain.embedder.openai import OpenAIEmbedder
from embedchain.factory import EmbedderFactory, VectorDBFactory
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB
from embedchain.vectordb.chroma import ChromaDB


@register_deserializable
class Pipeline(EmbedChain):
    """
    EmbedChain pipeline lets you create a LLM powered app for your unstructured
    data by defining a pipeline with your chosen data source, embedding model,
    and vector database.
    """

    def __init__(self, config: PipelineConfig = None, db: BaseVectorDB = None, embedding_model: BaseEmbedder = None):
        """
        Initialize a new `App` instance.

        :param config: Configuration for the pipeline, defaults to None
        :type config: PipelineConfig, optional
        :param db: The database to use for storing and retrieving embeddings, defaults to None
        :type db: BaseVectorDB, optional
        :param embedding_model: The embedding model used to calculate embeddings, defaults to None
        :type embedding_model: BaseEmbedder, optional
        """
        super().__init__()
        self.config = config or PipelineConfig()
        self.name = self.config.name
        self.id = self.config.id or str(uuid.uuid4())

        self.embedding_model = embedding_model or OpenAIEmbedder()
        self.db = db or ChromaDB()
        self._initialize_db()

        self.user_asks = []  # legacy defaults

        self.s_id = self.config.id or str(uuid.uuid4())
        self.u_id = self._load_or_generate_user_id()

        thread_telemetry = threading.Thread(target=self._send_telemetry_event, args=("pipeline_init",))
        thread_telemetry.start()

    def _initialize_db(self):
        """
        Initialize the database.
        """
        self.db._set_embedder(self.embedding_model)
        self.db._initialize()
        self.db.set_collection_name(self.name)

    def search(self, query, num_documents=3):
        """
        Search for similar documents related to the query in the vector database.
        """
        where = {"app_id": self.id}
        return self.db.query(
            query,
            n_results=num_documents,
            where=where,
            skip_embedding=False,
        )

    @classmethod
    def from_config(cls, yaml_path: str):
        """
        Instantiate a Pipeline object from a YAML configuration file.

        :param yaml_path: Path to the YAML configuration file.
        :type yaml_path: str
        :return: An instance of the Pipeline class.
        :rtype: Pipeline
        """
        with open(yaml_path, "r") as file:
            config_data = yaml.safe_load(file)

        pipeline_config_data = config_data.get("pipeline", {})
        db_config_data = config_data.get("vectordb", {})
        embedding_model_config_data = config_data.get("embedding_model", {})

        pipeline_config = PipelineConfig(**pipeline_config_data)

        db_provider = db_config_data.get("provider", "chroma")
        db = VectorDBFactory.create(db_provider, db_config_data.get("config", {}))

        embedding_model_provider = embedding_model_config_data.get("provider", "openai")
        embedding_model = EmbedderFactory.create(
            embedding_model_provider, embedding_model_config_data.get("config", {})
        )
        return cls(config=pipeline_config, db=db, embedding_model=embedding_model)
