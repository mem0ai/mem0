from typing import Dict, List, Optional, Union

from embedchain.config.vectordbs.BaseVectorDbConfig import BaseVectorDbConfig
from embedchain.helper_classes.json_serializable import register_deserializable


@register_deserializable
class ElasticsearchDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        es_url: Union[str, List[str]] = None,
        **ES_EXTRA_PARAMS: Dict[str, any],
    ):
        """
        Config to initialize an elasticsearch client.
        :param es_url. elasticsearch url or list of nodes url to be used for connection
        :param ES_EXTRA_PARAMS: extra params dict that can be passed to elasticsearch.
        """
        # self, es_url: Union[str, List[str]] = None, **ES_EXTRA_PARAMS: Dict[str, any]):
        self.ES_URL = es_url
        self.ES_EXTRA_PARAMS = ES_EXTRA_PARAMS

        super().__init__(collection_name=collection_name, dir=dir)
