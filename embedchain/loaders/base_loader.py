from embedchain.helper.json_serializable import JSONSerializable
from embedchain.config.add_config import LoaderConfig

class BaseLoader(JSONSerializable):
    def __init__(self,config:LoaderConfig):
        self.config = config

    def load_data():
        """
        Implemented by child classes
        """
        pass
