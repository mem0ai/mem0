from typing import Dict, List, Union

from embedchain.config.BaseConfig import BaseConfig


class ElasticsearchDBConfig(BaseConfig):
    """
    Config to initialize an elasticsearch client.
    :param es_url. elasticsearch url or list of nodes url to be used for connection
    :param ES_EXTRA_PARAMS: extra params dict that can be passed to elasticsearch.
    """

    def __init__(self, es_url: Union[str, List[str]] = None, **ES_EXTRA_PARAMS: Dict[str, any]):
        self.ES_URL = es_url
        self.ES_EXTRA_PARAMS = ES_EXTRA_PARAMS
