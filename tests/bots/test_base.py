import os
from unittest.mock import patch

import pytest

from embedchain.bots.base import BaseBot
from embedchain.config import AddConfig, BaseLlmConfig


@pytest.fixture
def base_bot():
    os.environ["OPENAI_API_KEY"] = "test_api_key"  # needed by App
    return BaseBot()


def test_add(base_bot):
    data = "Test data"
    config = AddConfig()

    with patch.object(base_bot.app, "add") as mock_add:
        base_bot.add(data, config)
        mock_add.assert_called_with(data, config=config)


def test_query(base_bot):
    query = "Test query"
    config = BaseLlmConfig()

    with patch.object(base_bot.app, "query") as mock_query:
        mock_query.return_value = "Query result"

        result = base_bot.query(query, config)

    assert isinstance(result, str)
    assert result == "Query result"


def test_start():
    class TestBot(BaseBot):
        def start(self):
            return "Bot started"

    bot = TestBot()
    result = bot.start()
    assert result == "Bot started"


def test_start_not_implemented():
    bot = BaseBot()
    with pytest.raises(NotImplementedError):
        bot.start()
