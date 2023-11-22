import ast
import json
import logging
import os
import sqlite3
import uuid

import requests
import yaml

from embedchain import Client
from embedchain.config import ChunkerConfig, PipelineConfig
from embedchain.constants import SQLITE_PATH
from embedchain.embedchain import EmbedChain
from embedchain.embedder.base import BaseEmbedder
from embedchain.embedder.openai import OpenAIEmbedder
from embedchain.factory import EmbedderFactory, LlmFactory, VectorDBFactory
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm
from embedchain.llm.openai import OpenAILlm
from embedchain.telemetry.posthog import AnonymousTelemetry
from embedchain.utils import validate_yaml_config
from embedchain.vectordb.base import BaseVectorDB
from embedchain.vectordb.chroma import ChromaDB


@register_deserializable
class Pipeline(EmbedChain):
    """
    EmbedChain pipeline lets you create a LLM powered app for your unstructured
    data by defining a pipeline with your chosen data source, embedding model,
    and vector database.
    """

    def __init__(
        self,
        id: str = None,
        name: str = None,
        config: PipelineConfig = None,
        db: BaseVectorDB = None,
        embedding_model: BaseEmbedder = None,
        llm: BaseLlm = None,
        yaml_path: str = None,
        log_level=logging.WARN,
        auto_deploy: bool = False,
        chunker: ChunkerConfig = None,
    ):
        """
        Initialize a new `App` instance.

        :param config: Configuration for the pipeline, defaults to None
        :type config: PipelineConfig, optional
        :param db: The database to use for storing and retrieving embeddings, defaults to None
        :type db: BaseVectorDB, optional
        :param embedding_model: The embedding model used to calculate embeddings, defaults to None
        :type embedding_model: BaseEmbedder, optional
        :param llm: The LLM model used to calculate embeddings, defaults to None
        :type llm: BaseLlm, optional
        :param yaml_path: Path to the YAML configuration file, defaults to None
        :type yaml_path: str, optional
        :param log_level: Log level to use, defaults to logging.WARN
        :type log_level: int, optional
        :param auto_deploy: Whether to deploy the pipeline automatically, defaults to False
        :type auto_deploy: bool, optional
        :raises Exception: If an error occurs while creating the pipeline
        """
        # Setup user directory if it doesn't exist already
        Client.setup_dir()

        if id and yaml_path:
            raise Exception("Cannot provide both id and config. Please provide only one of them.")

        if id and name:
            raise Exception("Cannot provide both id and name. Please provide only one of them.")

        if name and config:
            raise Exception("Cannot provide both name and config. Please provide only one of them.")

        logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(__name__)
        self.auto_deploy = auto_deploy
        # Store the yaml config as an attribute to be able to send it
        self.yaml_config = None
        self.client = None
        # pipeline_id from the backend
        self.id = None
        self.chunker = None
        if chunker:
            self.chunker = ChunkerConfig(**chunker)

        self.config = config or PipelineConfig()
        self.name = self.config.name
        self.config.id = self.local_id = str(uuid.uuid4()) if self.config.id is None else self.config.id

        if yaml_path:
            with open(yaml_path, "r") as file:
                config_data = yaml.safe_load(file)
                self.yaml_config = config_data

        if id is not None:
            # Init client first since user is trying to fetch the pipeline
            # details from the platform
            self._init_client()
            pipeline_details = self._get_pipeline(id)
            self.config.id = self.local_id = pipeline_details["metadata"]["local_id"]
            self.id = id

        if name is not None:
            self.name = name

        self.embedding_model = embedding_model or OpenAIEmbedder()
        self.db = db or ChromaDB()
        self.llm = llm or OpenAILlm()
        self._init_db()

        # Send anonymous telemetry
        self._telemetry_props = {"class": self.__class__.__name__}
        self.telemetry = AnonymousTelemetry(enabled=self.config.collect_metrics)

        # Establish a connection to the SQLite database
        self.connection = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
        self.cursor = self.connection.cursor()

        # Create the 'data_sources' table if it doesn't exist
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS data_sources (
                pipeline_id TEXT,
                hash TEXT,
                type TEXT,
                value TEXT,
                metadata TEXT,
                is_uploaded INTEGER DEFAULT 0,
                PRIMARY KEY (pipeline_id, hash)
            )
        """
        )
        self.connection.commit()
        # Send anonymous telemetry
        self.telemetry.capture(event_name="init", properties=self._telemetry_props)

        self.user_asks = []
        if self.auto_deploy:
            self.deploy()

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
            api_key = input(
                "🔑 Enter your Embedchain API key. You can find the API key at https://app.embedchain.ai/settings/keys/ \n"  # noqa: E501
            )
            self.client = Client(api_key=api_key)

    def _get_pipeline(self, id):
        """
        Get existing pipeline
        """
        print("🛠️ Fetching pipeline details from the platform...")
        url = f"{self.client.host}/api/v1/pipelines/{id}/cli/"
        r = requests.get(
            url,
            headers={"Authorization": f"Token {self.client.api_key}"},
        )
        if r.status_code == 404:
            raise Exception(f"❌ Pipeline with id {id} not found!")

        print(
            f"🎉 Pipeline loaded successfully! Pipeline url: https://app.embedchain.ai/pipelines/{r.json()['id']}\n"  # noqa: E501
        )
        return r.json()

    def _create_pipeline(self):
        """
        Create a pipeline on the platform.
        """
        print("🛠️ Creating pipeline on the platform...")
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
            raise Exception(f"❌ Error occurred while creating pipeline. API response: {r.text}")

        if r.status_code == 200:
            print(
                f"🎉🎉🎉 Existing pipeline found! View your pipeline: https://app.embedchain.ai/pipelines/{r.json()['id']}\n"  # noqa: E501
            )  # noqa: E501
        elif r.status_code == 201:
            print(
                f"🎉🎉🎉 Pipeline created successfully! View your pipeline: https://app.embedchain.ai/pipelines/{r.json()['id']}\n"  # noqa: E501
            )
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
        # Send anonymous telemetry
        self.telemetry.capture(event_name="search", properties=self._telemetry_props)

        # TODO: Search will call the endpoint rather than fetching the data from the db itself when deploy=True.
        if self.id is None:
            where = {"app_id": self.local_id}
            context = self.db.query(
                query,
                n_results=num_documents,
                where=where,
                skip_embedding=False,
                citations=True,
            )
            result = []
            for c in context:
                result.append(
                    {
                        "context": c[0],
                        "source": c[1],
                        "document_id": c[2],
                    }
                )
            return result
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
            print("❌ Error occurred during file upload!")
            return False

    def _upload_data_to_pipeline(self, data_type, data_value, metadata=None):
        payload = {
            "data_type": data_type,
            "data_value": data_value,
            "metadata": metadata,
        }
        try:
            self._send_api_request(f"/api/v1/pipelines/{self.id}/cli/add/", payload)
            # print the local file path if user tries to upload a local file
            printed_value = metadata.get("file_path") if metadata.get("file_path") else data_value
            print(f"✅ Data of type: {data_type}, value: {printed_value} added successfully.")
        except Exception as e:
            print(f"❌ Error occurred during data upload for type {data_type}!. Error: {str(e)}")

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
                metadata = {"file_path": data_value, "s3_key": s3_key}
                data_value = presigned_url
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
            return True
        except Exception:
            print(f"❌ Error occurred during data upload for hash {data_hash}!")
            return False

    def _mark_data_as_uploaded(self, data_hash):
        self.cursor.execute(
            "UPDATE data_sources SET is_uploaded = 1 WHERE hash = ? AND pipeline_id = ?",
            (data_hash, self.local_id),
        )
        self.connection.commit()

    def get_data_sources(self):
        db_data = self.cursor.execute("SELECT * FROM data_sources WHERE pipeline_id = ?", (self.local_id,)).fetchall()

        data_sources = []
        for data in db_data:
            data_sources.append({"data_type": data[2], "data_value": data[3], "metadata": data[4]})

        return data_sources

    def deploy(self):
        if self.client is None:
            self._init_client()

        pipeline_data = self._create_pipeline()
        self.id = pipeline_data["id"]

        results = self.cursor.execute(
            "SELECT * FROM data_sources WHERE pipeline_id = ? AND is_uploaded = 0", (self.local_id,)  # noqa:E501
        ).fetchall()

        if len(results) > 0:
            print("🛠️ Adding data to your pipeline...")
        for result in results:
            data_hash, data_type, data_value = result[1], result[2], result[3]
            self._process_and_upload_data(data_hash, data_type, data_value)

        # Send anonymous telemetry
        self.telemetry.capture(event_name="deploy", properties=self._telemetry_props)

    @classmethod
    def from_config(cls, yaml_path: str, auto_deploy: bool = False):
        """
        Instantiate a Pipeline object from a YAML configuration file.

        :param yaml_path: Path to the YAML configuration file.
        :type yaml_path: str
        :param auto_deploy: Whether to deploy the pipeline automatically, defaults to False
        :type auto_deploy: bool, optional
        :return: An instance of the Pipeline class.
        :rtype: Pipeline
        """
        # Setup user directory if it doesn't exist already
        Client.setup_dir()

        with open(yaml_path, "r") as file:
            config_data = yaml.safe_load(file)

        try:
            validate_yaml_config(config_data)
        except Exception as e:
            raise Exception(f"❌ Error occurred while validating the YAML config. Error: {str(e)}")

        pipeline_config_data = config_data.get("app", {}).get("config", {})
        db_config_data = config_data.get("vectordb", {})
        embedding_model_config_data = config_data.get("embedding_model", config_data.get("embedder", {}))
        llm_config_data = config_data.get("llm", {})
        chunker_config_data = config_data.get("chunker", {})

        pipeline_config = PipelineConfig(**pipeline_config_data)

        db_provider = db_config_data.get("provider", "chroma")
        db = VectorDBFactory.create(db_provider, db_config_data.get("config", {}))

        if llm_config_data:
            llm_provider = llm_config_data.get("provider", "openai")
            llm = LlmFactory.create(llm_provider, llm_config_data.get("config", {}))
        else:
            llm = None

        embedding_model_provider = embedding_model_config_data.get("provider", "openai")
        embedding_model = EmbedderFactory.create(
            embedding_model_provider, embedding_model_config_data.get("config", {})
        )

        # Send anonymous telemetry
        event_properties = {"init_type": "yaml_config"}
        AnonymousTelemetry().capture(event_name="init", properties=event_properties)

        return cls(
            config=pipeline_config,
            llm=llm,
            db=db,
            embedding_model=embedding_model,
            yaml_path=yaml_path,
            auto_deploy=auto_deploy,
            chunker=chunker_config_data,
        )
