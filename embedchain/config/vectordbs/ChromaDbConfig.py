from embedchain.config.vectordbs.BaseVectorDbConfig import BaseVectorDbConfig
from typing import Optional

class ChromaDbConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[str] = None,
    ):
        