import os
from typing import Dict, List, Optional, Union

from embedchain.config.vectordbs.BaseVectorDbConfig import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable

@register_deserializable
class LanceDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        table_name: Optional[str],
        uri: Union[str, List[str]],
        api_key: Optional[str] =None,
        region: str = 'us-west-2',
        host_override: Optional[str] = None,
    ):
        """
        Initializes a configuration class instance for an LanceDB connection.
        
        :param table_name: The name of the table
        :type table_name: Optional [str]
        :param uri: lancedb uri to be used for connection
        :type uri: Union[str, List[str]], REQUIRED
        :param api_key: If connecting to cloud or lancedb cloud
        :type api_key: Optional[str]
        :param region: the region to use lancedb cloud
        :type region: str: Defaults to 'us-west-2'
        :param: host_override: The override URL for lancedb cloud
        :type: Optional[str]: Defaults to : None

        """
        self.uri = uri
        if not self.uri:
            raise AttributeError(
                "LanceDB needs a URI attribute, "
                "this can be passed to `LanceDBConfig`"
            )
        self.region = region
        super().__init__(table_name=table_name, uri=uri)
