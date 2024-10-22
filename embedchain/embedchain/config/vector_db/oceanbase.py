import os
from typing import Optional

from embedchain.config.vector_db.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable

DEFAULT_OCEANBASE_COLLECTION_NAME = "embedchain_vector"
DEFAULT_OCEANBASE_HOST = "localhost"
DEFAULT_OCEANBASE_PORT = "2881"
DEFAULT_OCEANBASE_USER = "root@test"
DEFAULT_OCEANBASE_PASSWORD = ""
DEFAULT_OCEANBASE_DBNAME = "test"
DEFAULT_OCEANBASE_VECTOR_METRIC_TYPE = "l2"
DEFAULT_OCEANBASE_HNSW_BUILD_PARAM = {"M": 16, "efConstruction": 256}

@register_deserializable
class OceanBaseConfig(BaseVectorDbConfig):
    pass
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: str = "db",
        host: Optional[str] = None,
        port: Optional[str] = None,
        user: Optional[str] = None,
        dbname: Optional[str] = None,
        vidx_metric_type: str = DEFAULT_OCEANBASE_VECTOR_METRIC_TYPE,
        vidx_algo_params: Optional[dict] = None,
        drop_old: bool = False,
        normalize: bool = False,
    ):
        """
        Initializes a configuration class instance for OceanBase.

        :param collection_name: Default name for the collection, defaults to None
        :type collection_name: Optional[str], optional
        :param dir: Path to the database directory, where the database is stored, defaults to "db".
            In OceanBase, this parameter is not valid.
        :type dir: str, optional
        :param host: Database connection remote host.
        :type host: Optional[str], optional
        :param port: Database connection remote port.
        :type port: Optional[str], optional
        :param user: Database user name.
        :type user: Optional[str], optional
        :param dbname: OceanBase database name
        :type dbname: Optional[str], optional
        :param vidx_metric_type: vector index metric type, 'l2' or 'inner_product'.
        :type vidx_metric_type: Optional[str], optional
        :param vidx_algo_params: vector index building params,
            refer to `DEFAULT_OCEANBASE_HNSW_BUILD_PARAM` for an example.
        :type vidx_algo_params: Optional[dict], optional
        :param drop_old: drop old table before creating.
        :type drop_old: bool
        :param normalize: normalize vector before storing into OceanBase.
        :type normalize: bool
        """
        self.collection_name = (
            collection_name or DEFAULT_OCEANBASE_COLLECTION_NAME
        )
        self.host = host or DEFAULT_OCEANBASE_HOST
        self.port = port or DEFAULT_OCEANBASE_PORT
        self.passwd = os.environ.get("OB_PASSWORD", "")
        super().__init__(
            collection_name=self.collection_name,
            dir=dir,
            host=self.host,
            port=self.port,
        )
        self.user = user or DEFAULT_OCEANBASE_USER
        self.dbname = dbname or DEFAULT_OCEANBASE_DBNAME
        self.vidx_metric_type = vidx_metric_type.lower()
        if self.vidx_metric_type not in ("l2", "inner_product"):
            raise ValueError(
                "`vidx_metric_type` should be set in `l2`/`inner_product`."
            )
        self.vidx_algo_params = (
            vidx_algo_params
            if vidx_algo_params is not None
            else DEFAULT_OCEANBASE_HNSW_BUILD_PARAM
        )
        self.drop_old = drop_old
        self.normalize = normalize
