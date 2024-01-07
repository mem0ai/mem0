from dotenv import load_dotenv

from embedchain import App
from embedchain.models.data_type import DataType

from .slack_chunker import SlackChunker
from .slack_loader import SlackLoader

load_dotenv(".env")

loader = SlackLoader()
chunker = SlackChunker()
chunker.set_data_type(DataType.SLACK)

app_config = {
    "app": {
        "config": {
            "id": "eaf8717e-ad3f-4963-a6ae-9bfce5829a0b",
            "name": "slack-app",
        }
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-3.5-turbo-1106",
        },
    },
}

app = App.from_config(config=app_config)
