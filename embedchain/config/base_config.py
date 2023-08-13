class BaseConfig:
    """
    Base config.
    """

    def __init__(self):
        pass

    def as_dict(self):
        return vars(self)
