from typing import Dict, List, Optional, Union

from embedchain.config.vectordbs.BaseVectorDbConfig import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable


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
        Initializes a configuration class instance for an Elasticsearch client.

        :param collection_name: Default name for the collection, defaults to None
        :type collection_name: Optional[str], optional
        :param dir: Path to the database directory, where the database is stored, defaults to None
        :type dir: Optional[str], optional
        :param es_url: elasticsearch url or list of nodes url to be used for connection, defaults to None
        :type es_url: Union[str, List[str]], optional
        :param ES_EXTRA_PARAMS: extra params dict that can be passed to elasticsearch.
        :type ES_EXTRA_PARAMS: Dict[str, Any], optional
        """
        # self, es_url: Union[str, List[str]] = None, **ES_EXTRA_PARAMS: Dict[str, any]):
        self.ES_URL = es_url
        self.ES_EXTRA_PARAMS = ES_EXTRA_PARAMS

        super().__init__(collection_name=collection_name, dir=dir)
