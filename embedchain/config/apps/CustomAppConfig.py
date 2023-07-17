from .BaseAppConfig import BaseAppConfig


class CustomAppConfig(BaseAppConfig):
    """
    Config to initialize an embedchain custom `App` instance, with extra config options.
    """

    def __init__(self, log_level=None, ef=None, db=None, host=None, port=None, id=None):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param ef: Optional. Embedding function to use.
        :param db: Optional. (Vector) database to use for embeddings.
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param host: Optional. Hostname for the database server.
        :param port: Optional. Port for the database server.
        """
        super().__init__(log_level=log_level, db=db, host=host, port=port, id=id)
