import os
from typing import Dict, List, Optional, Union

from embedchain.config.vectordbs.BaseVectorDbConfig import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable

@register_deserializable
class LanceDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        table_name: Optional[str] = None,
        dir: Optional[str] = None,
        ld_uri: Union[str, List[str]] = None,
        **LD_EXTRA_PARAMS: Dict[str, any],
    ):
        """
        Initializes a configuration class instance for an LanceDB connection.

        :param table_name: Default name for the collection, defaults to None
        :type table_name: Optional[str], optional
        :param dir: Path to the database directory, where the database is stored, defaults to None
        :type dir: Optional[str], optional
        :param ld_url: lancedb uri to be used for connection, defaults to None
        :type ld_url: Union[str, List[str]], optional
        :param LD_EXTRA_PARAMS: extra params dict that can be passed to lancedb.
        :type LD_EXTRA_PARAMS: Dict[str, Any], optional
        """
        self.LD_URI = ld_uri or os.environ.get("LANCEDB_URI")
        if not self.LD_URI:
            raise AttributeError(
                "LanceDB needs a URI attribute, "
                "this can either be passed to `LanceDBConfig` or as `LANCEDB_URI` in `.env`"
            )
        self.LD_EXTRA_PARAMS = LD_EXTRA_PARAMS
        super().__init__(table_name=table_name, dir=dir)
