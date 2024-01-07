from embedchain.helpers.json_serializable import JSONSerializable


class BaseLoader(JSONSerializable):
    def __init__(self):
        pass

    def load_data(self, url):
        """
        Implemented by child classes
        """
        pass
