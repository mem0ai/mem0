from embedchain import CustomApp
from embedchain.config import AddConfig, CustomAppConfig, QueryConfig
from embedchain.models import EmbeddingFunctions, Providers


class BaseBot:
    def __init__(self, app_config=None):
        if app_config is None:
            app_config = CustomAppConfig(embedding_fn=EmbeddingFunctions.OPENAI, provider=Providers.OPENAI)
        self.app_config = app_config
        self.app = CustomApp(config=self.app_config)

    def add(self, data, config: AddConfig = None):
        """Add data to the bot"""
        config = config if config else AddConfig()
        self.app.add(data, config=config)

    def query(self, query, config: QueryConfig = None):
        """Query bot"""
        config = config if config else QueryConfig()
        return self.app.query(query, config=config)

    def start(self):
        """Start the bot's functionality."""
        raise NotImplementedError("Subclasses must implement the start method.")
