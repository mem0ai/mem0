from typing import Dict, Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable


@register_deserializable
class DeeplakeDBConfig(BaseVectorDbConfig):
    """
    Config to initialize an qdrant client.
    :param url. deeplake url or list of nodes url to be used for connection
    """

    def __init__(
        self,
        path: Optional[str] = None,
        exec_option: Optional[str] = "python",
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        **extra_params: Dict[str, any],
    ):
        """
        Initializes a configuration class instance for a qdrant client.


        :param collection_name: Default name for the collection, defaults to None
        :type collection_name: Optional[str], optional

        exec_option (Optional[str]): Method for search execution. It could be either ``"python"``, ``"compute_engine"`` or ``"tensor_db"``. Defaults to ``None``, which inherits the option from the Vector Store initialization.

            - ``python`` - Pure-python implementation that runs on the client and can be used for data stored anywhere. WARNING: using this option with big datasets is discouraged because it can lead to memory issues.
            - ``compute_engine`` - Performant C++ implementation of the Deep Lake Compute Engine that runs on the client and can be used for any data stored in or connected to Deep Lake. It cannot be used with in-memory or local datasets.
            - ``tensor_db`` - Performant and fully-hosted Managed Tensor Database that is responsible for storage and query execution. Only available for data stored in the Deep Lake Managed Database. Store datasets in this database by specifying runtime = {"tensor_db": True} during dataset creation.

        :param dir: Path to the database directory, where the database is stored, defaults to None
        :type dir: Optional[str], optional
        :param hnsw_config: Params for HNSW index
        :type hnsw_config: Optional[Dict[str, any]], defaults to None
        :param quantization_config: Params for quantization, if None - quantization will be disabled
        :type quantization_config: Optional[Dict[str, any]], defaults to None
        :param on_disk: If true - point`s payload will not be stored in memory.
                It will be read from the disk every time it is requested.
                This setting saves RAM by (slightly) increasing the response time.
                Note: those payload values that are involved in filtering and are indexed - remain in RAM.
        :type on_disk: bool, optional, defaults to None
        """
        self.path = path
        self.extra_params = extra_params
        self.exec_option = exec_option
        super().__init__(collection_name=collection_name, dir=dir)
