import ast
import json
import logging
import os
import sqlite3
import uuid

import requests
import yaml
from fastapi import FastAPI, HTTPException

from embedchain import Client
from embedchain.config import PipelineConfig
from embedchain.embedchain import CONFIG_DIR, EmbedChain
from embedchain.embedder.base import BaseEmbedder
from embedchain.embedder.openai import OpenAIEmbedder
from embedchain.factory import EmbedderFactory, VectorDBFactory
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm
from embedchain.vectordb.base import BaseVectorDB
from embedchain.vectordb.chroma import ChromaDB

SQLITE_PATH = os.path.join(CONFIG_DIR, "embedchain.db")


@register_deserializable
class Pipeline(EmbedChain):
    """
    EmbedChain pipeline lets you create a LLM powered app for your unstructured
    data by defining a pipeline with your chosen data source, embedding model,
    and vector database.
    """

    def __init__(
        self,
        config: PipelineConfig = None,
        db: BaseVectorDB = None,
        embedding_model: BaseEmbedder = None,
        llm: BaseLlm = None,
        yaml_path: str = None,
        log_level=logging.INFO,
    ):
        """
        Initialize a new `App` instance.

        :param config: Configuration for the pipeline, defaults to None
        :type config: PipelineConfig, optional
        :param db: The database to use for storing and retrieving embeddings, defaults to None
        :type db: BaseVectorDB, optional
        :param embedding_model: The embedding model used to calculate embeddings, defaults to None
        :type embedding_model: BaseEmbedder, optional
        """
        logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(__name__)
        # Store the yaml config as an attribute to be able to send it
        self.yaml_config = None
        self.client = None
        if yaml_path:
            with open(yaml_path, "r") as file:
                config_data = yaml.safe_load(file)
                self.yaml_config = config_data

        self.config = config or PipelineConfig()
        self.name = self.config.name
        self.local_id = self.config.id or str(uuid.uuid4())

        self.embedding_model = embedding_model or OpenAIEmbedder()
        self.db = db or ChromaDB()
        self.llm = llm or None
        self._init_db()

        # setup user id and directory
        self.u_id = self._load_or_generate_user_id()

        # Establish a connection to the SQLite database
        self.connection = sqlite3.connect(SQLITE_PATH)
        self.cursor = self.connection.cursor()

        # Create the 'data_sources' table if it doesn't exist
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS data_sources (
                pipeline_id TEXT,
                hash TEXT,
                type TEXT,
                value TEXT,
                metadata TEXT
                is_uploaded INTEGER DEFAULT 0,
                PRIMARY KEY (pipeline_id, hash)
            )
        """
        )
        self.connection.commit()

        self.user_asks = []  # legacy defaults

    def _init_db(self):
        """
        Initialize the database.
        """
        self.db._set_embedder(self.embedding_model)
        self.db._initialize()
        self.db.set_collection_name(self.db.config.collection_name)

    def _init_client(self):
        """
        Initialize the client.
        """
        config = Client.load_config()
        if config.get("api_key"):
            self.client = Client()
        else:
            api_key = input("Enter API key. You can find the API key at https://app.embedchain.ai/settings/keys/ \n")
            self.client = Client(api_key=api_key)

    def _create_pipeline(self):
        """
        Create a pipeline on the platform.
        """
        print("Creating pipeline on the platform...")
        # self.yaml_config is a dict. Pass it inside the key 'yaml_config' to the backend
        payload = {
            "yaml_config": json.dumps(self.yaml_config),
            "name": self.name,
            "local_id": self.local_id,
        }
        url = f"{self.client.host}/api/v1/pipelines/cli/create/"
        r = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Token {self.client.api_key}"},
        )
        if r.status_code not in [200, 201]:
            raise Exception(f"Error occurred while creating pipeline. Response from API: {r.text}")

        print(f"Pipeline created. link: https://app.embedchain.ai/pipelines/{r.json()['id']}")
        return r.json()

    def _get_presigned_url(self, data_type, data_value):
        payload = {"data_type": data_type, "data_value": data_value}
        r = requests.post(
            f"{self.client.host}/api/v1/pipelines/{self.id}/cli/presigned_url/",
            json=payload,
            headers={"Authorization": f"Token {self.client.api_key}"},
        )
        r.raise_for_status()
        return r.json()

    def search(self, query, num_documents=3):
        """
        Search for similar documents related to the query in the vector database.
        """
        # TODO: Search will call the endpoint rather than fetching the data from the db itself when deploy=True.
        if self.deploy is False:
            where = {"app_id": self.local_id}
            return self.db.query(
                query,
                n_results=num_documents,
                where=where,
                skip_embedding=False,
            )
        else:
            # Make API call to the backend to get the results
            NotImplementedError("Search is not implemented yet for the prod mode.")

    def _upload_file_to_presigned_url(self, presigned_url, file_path):
        try:
            with open(file_path, "rb") as file:
                response = requests.put(presigned_url, data=file)
                response.raise_for_status()
                return response.status_code == 200
        except Exception as e:
            self.logger.exception(f"Error occurred during file upload: {str(e)}")
            return False

    def _upload_data_to_pipeline(self, data_type, data_value, metadata=None):
        payload = {
            "data_type": data_type,
            "data_value": data_value,
            "metadata": metadata,
        }
        return self._send_api_request(f"/api/v1/pipelines/{self.id}/cli/add/", payload)

    def _send_api_request(self, endpoint, payload):
        url = f"{self.client.host}{endpoint}"
        headers = {"Authorization": f"Token {self.client.api_key}"}
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response

    def _process_and_upload_data(self, data_hash, data_type, data_value):
        if os.path.isabs(data_value):
            presigned_url_data = self._get_presigned_url(data_type, data_value)
            presigned_url = presigned_url_data["presigned_url"]
            s3_key = presigned_url_data["s3_key"]
            if self._upload_file_to_presigned_url(presigned_url, file_path=data_value):
                data_value = presigned_url
                metadata = {"file_path": data_value, "s3_key": s3_key}
            else:
                self.logger.error(f"File upload failed for hash: {data_hash}")
                return False
        else:
            if data_type == "qna_pair":
                data_value = list(ast.literal_eval(data_value))
            metadata = {}

        try:
            self._upload_data_to_pipeline(data_type, data_value, metadata)
            self._mark_data_as_uploaded(data_hash)
            self.logger.info(f"Data of type {data_type} uploaded successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Error occurred during data upload: {str(e)}")
            return False

    def _mark_data_as_uploaded(self, data_hash):
        self.cursor.execute(
            "UPDATE data_sources SET is_uploaded = 1 WHERE hash = ? AND pipeline_id = ? AND is_uploaded = 0",
            (data_hash, self.local_id),
        )
        self.connection.commit()

    def deploy(self):
        try:
            if self.client is None:
                self._init_client()

            pipeline_data = self._create_pipeline()
            self.id = pipeline_data["id"]

            results = self.cursor.execute(
                "SELECT * FROM data_sources WHERE pipeline_id = ? AND is_uploaded = 0", (self.local_id,)
            ).fetchall()

            for result in results:
                data_hash, data_type, data_value = result[0], result[2], result[3]
                if self._process_and_upload_data(data_hash, data_type, data_value):
                    self.logger.info(f"Data with hash {data_hash} uploaded successfully.")

        except Exception as e:
            self.logger.exception(f"Error occurred during deployment: {str(e)}")
            raise HTTPException(status_code=500, detail="Error occurred during deployment.")

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

        pipeline_config_data = config_data.get("pipeline", {}).get("config", {})
        db_config_data = config_data.get("vectordb", {})
        embedding_model_config_data = config_data.get("embedding_model", {})

        pipeline_config = PipelineConfig(**pipeline_config_data)

        db_provider = db_config_data.get("provider", "chroma")
        db = VectorDBFactory.create(db_provider, db_config_data.get("config", {}))

        embedding_model_provider = embedding_model_config_data.get("provider", "openai")
        embedding_model = EmbedderFactory.create(
            embedding_model_provider, embedding_model_config_data.get("config", {})
        )
        return cls(
            config=pipeline_config,
            db=db,
            embedding_model=embedding_model,
            yaml_path=yaml_path,
        )

    def start(self, host="0.0.0.0", port=8000):
        app = FastAPI()

        @app.post("/add")
        async def add_document(data_value: str, data_type: str = None):
            """
            Add a document to the pipeline.
            """
            try:
                document = {"data_value": data_value, "data_type": data_type}
                self.add(document)
                return {"message": "Document added successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/query")
        async def query_documents(query: str, num_documents: int = 3):
            """
            Query for similar documents in the pipeline.
            """
            try:
                results = self.search(query, num_documents)
                return results
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        import uvicorn

        uvicorn.run(app, host=host, port=port)
