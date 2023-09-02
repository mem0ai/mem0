from typing import Any, Optional

from dotenv import load_dotenv

from embedchain.models import (EmbeddingFunctions, Providers,
                               VectorDimensions)

from .BaseAppConfig import BaseAppConfig

load_dotenv()


class CustomAppConfig(BaseAppConfig):
    """
    Config to initialize an embedchain custom `App` instance, with extra config options.
    """

    def __init__(
        self,
        log_level=None,
        embedding_fn: EmbeddingFunctions = None,
        embedding_fn_model=None,
        db=None,
        id=None,
        provider: Providers = None,
        open_source_app_config=None,
        deployment_name=None,
        collect_metrics: Optional[bool] = None,
    ):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param embedding_fn: Optional. Embedding function to use.
        :param embedding_fn_model: Optional. Model name to use for embedding function.
        :param db: Optional. (Vector) database to use for embeddings.
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param provider: Optional. (Providers): LLM Provider to use.
        :param open_source_app_config: Optional. Config instance needed for open source apps.
        :param collect_metrics: Defaults to True. Send anonymous telemetry to improve embedchain.
        :param db_type: Optional. type of Vector database to use.
        :param es_config: Optional. elasticsearch database config to be used for connection
        """
        if provider:
            self.provider = provider
        else:
            raise ValueError("CustomApp must have a provider assigned.")

        self.open_source_app_config = open_source_app_config

        super().__init__(
            log_level=log_level,
            embedding_fn=CustomAppConfig.embedding_function(
                embedding_function=embedding_fn, model=embedding_fn_model, deployment_name=deployment_name
            ),
            db=db,
            id=id,
            collect_metrics=collect_metrics,
        )



    @staticmethod
    def get_vector_dimension(embedding_function: EmbeddingFunctions):
        if not isinstance(embedding_function, EmbeddingFunctions):
            raise ValueError(f"Invalid option: '{embedding_function}'.")

        if embedding_function == EmbeddingFunctions.OPENAI:
            return VectorDimensions.OPENAI.value

        elif embedding_function == EmbeddingFunctions.HUGGING_FACE:
            return VectorDimensions.HUGGING_FACE.value

        elif embedding_function == EmbeddingFunctions.VERTEX_AI:
            return VectorDimensions.VERTEX_AI.value

        elif embedding_function == EmbeddingFunctions.GPT4ALL:
            return VectorDimensions.GPT4ALL.value
