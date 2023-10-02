from typing import Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable


@register_deserializable
class RedisDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        db: Optional[int] = None,
        decoded_response: Optional[bool] = True,
        dir: Optional[str] = None,
        host: str = None,
        port: str = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = False,
        user_name: Optional[str] = None,
        vector_dimension: Optional[int] = 1536,
    ):
        """
        Initializes a configuration class instance for RedisDB.

        :param collection_name: Default name for the index, defaults to None
        :type collection_name: Optional[str], optional
        :param db: Number of the database
        :type db: Optional[int], optional
        :param decoded_response: Flag to decode the response of redis from bytes to text
        :type decoded_response: Optional[bool], optional
        :param dir: Path to the redis database
        :type dir: Optional[str], optional
        :param host: Database connection remote host. Use this if you run Embedchain as a client, defaults to None
        :type host: Optional[str], optional
        :param port: Database connection remote port. Use this if you run Embedchain as a client, defaults to None
        :type port: Optional[str], optional
        :param password: Password of the redis database
        :type password: Optional[bool], optional
        :param ssl: Flag to check if redis support ssl
        :type ssl: Optional[bool], optional
        :param user_name: User of the redis database
        :type user_name: Optional[str], optional
        :param vector_dimension: Dimension for the vector field
        :type vector_dimesion: Optional[int], optional
        """

        self.user_name = user_name
        self.ssl = ssl
        self.db = db
        self.dir = dir
        self.password = password
        self.decoded_response = decoded_response
        self.vector_dimension = vector_dimension
        super().__init__(host=host, port=port, dir=dir, collection_name=collection_name)
