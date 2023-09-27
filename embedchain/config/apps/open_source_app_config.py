from typing import Optional

from embedchain.helper.json_serializable import register_deserializable

from .base_app_config import BaseAppConfig


@register_deserializable
class OpenSourceAppConfig(BaseAppConfig):
    """
    Config to initialize an embedchain custom `OpenSourceApp` instance, with extra config options.
    """

    def __init__(
        self,
        log_level: str = "WARNING",
        id: Optional[str] = None,
        collect_metrics: Optional[bool] = None,
        model: str = "orca-mini-3b.ggmlv3.q4_0.bin",
        collection_name: Optional[str] = None,
    ):
        """
        Initializes a configuration class instance for an Open Source App.

        :param log_level: Debug level ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], defaults to "WARNING"
        :type log_level: str, optional
        :param id: ID of the app. Document metadata will have this id., defaults to None
        :type id: Optional[str], optional
        :param collect_metrics: Send anonymous telemetry to improve embedchain, defaults to True
        :type collect_metrics: Optional[bool], optional
        :param model: GPT4ALL uses the model to instantiate the class.
        Unlike `App`, it has to be provided before querying, defaults to "orca-mini-3b.ggmlv3.q4_0.bin"
        :type model: str, optional
        :param collection_name: Default collection name. It's recommended to use app.db.set_collection_name() instead,
        defaults to None
        :type collection_name: Optional[str], optional
        """
        self.model = model or "orca-mini-3b.ggmlv3.q4_0.bin"

        super().__init__(log_level=log_level, id=id, collect_metrics=collect_metrics, collection_name=collection_name)
