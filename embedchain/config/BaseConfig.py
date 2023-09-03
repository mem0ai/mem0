from embedchain.helper_classes.json_serializable import JSONSerializable


class BaseConfig(JSONSerializable):
    """
    Base config.
    """

    def __init__(self):
        pass

    def as_dict(self):
        return vars(self)
