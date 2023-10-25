import pathlib
from typing import Dict, Optional, Union

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable


@register_deserializable
class DeeplakeDBConfig(BaseVectorDbConfig):
    """
    Config to initialize a deeplake client.
    """

    def __init__(
        self,
        path: Union[str, pathlib.Path] = "/tmp/deeplake",
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        **extra_params: Dict[str, any],
    ):
        """
        Initializes a configuration class instance for a deeplake client.
        path : - The full path for storing to the Deep Lake Vector Store. It can be:
                - a Deep Lake cloud path of the form ``hub://org_id/dataset_name``. Requires registration with
                Deep Lake.
                - an s3 path of the form ``s3://bucketname/path/to/dataset``. Credentials are required in the
                environment
                - a local file system path of the form ``./path/to/dataset`` or ``~/path/to/dataset``
                or ``path/to/dataset``.
                - a memory path of the form ``mem://path/to/dataset`` which doesn't save the dataset but keeps it in
                memory instead. Should be used only for testing as it does not persist.
        :type path: Union[str, pathlib.Path]
        :param collection_name: Default name for the collection, defaults to None.
        :type collection_name: Optional[str], optional
        :param dir: Path to the database directory, where the database is stored, defaults to None
        :type dir: Optional[str], optional
        """
        self.path = path
        self.extra_params = extra_params

        # We are fixing this to python because deeplake currently supports filtering support on metadata only with this
        # config
        self.exec_option = "python"
        super().__init__(collection_name=collection_name, dir=dir)
