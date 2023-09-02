from typing import Optional

from dotenv import load_dotenv

from embedchain.models import EmbeddingFunctions, Providers, VectorDimensions

from .BaseAppConfig import BaseAppConfig

load_dotenv()


class CustomAppConfig(BaseAppConfig):
    """
    Config to initialize an embedchain custom `App` instance, with extra config options.
    """

    def __init__(
        self,
        log_level=None,
        db=None,
        id=None,
        provider: Providers = None,
        open_source_app_config=None,
        collect_metrics: Optional[bool] = None,
    ):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param db: Optional. (Vector) database to use for embeddings.
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param provider: Optional. (Providers): LLM Provider to use.
        :param open_source_app_config: Optional. Config instance needed for open source apps.
        :param collect_metrics: Defaults to True. Send anonymous telemetry to improve embedchain.
        """
        if provider:
            self.provider = provider
        else:
            raise ValueError("CustomApp must have a provider assigned.")

        self.open_source_app_config = open_source_app_config

        super().__init__(
            log_level=log_level,
            db=db,
            id=id,
            collect_metrics=collect_metrics,
        )
