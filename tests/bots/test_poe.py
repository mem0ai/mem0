import argparse

import pytest
from fastapi_poe.types import ProtocolMessage, QueryRequest

from embedchain.bots.poe import PoeBot, start_command


@pytest.fixture
def poe_bot(mocker):
    bot = PoeBot()
    mocker.patch("fastapi_poe.run")
    return bot


@pytest.mark.asyncio
async def test_poe_bot_get_response(poe_bot, mocker):
    query = QueryRequest(
        version="test",
        type="query",
        query=[ProtocolMessage(role="system", content="Test content")],
        user_id="test_user_id",
        conversation_id="test_conversation_id",
        message_id="test_message_id",
    )

    mocker.patch.object(poe_bot.app.llm, "set_history")

    response_generator = poe_bot.get_response(query)

    await response_generator.__anext__()
    poe_bot.app.llm.set_history.assert_called_once()


def test_poe_bot_handle_message(poe_bot, mocker):
    mocker.patch.object(poe_bot, "ask_bot", return_value="Answer from the bot")

    response_ask = poe_bot.handle_message("What is the answer?")
    assert response_ask == "Answer from the bot"

    # TODO: This test will fail because the add_data method is commented out.
    # mocker.patch.object(poe_bot, 'add_data', return_value="Added data from: some_data")
    # response_add = poe_bot.handle_message("/add some_data")
    # assert response_add == "Added data from: some_data"


def test_start_command(mocker):
    mocker.patch("argparse.ArgumentParser.parse_args", return_value=argparse.Namespace(api_key="test_api_key"))
    mocker.patch("embedchain.bots.poe.run")

    start_command()
