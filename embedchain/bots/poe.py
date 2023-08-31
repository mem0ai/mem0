import argparse
import logging
import os
from typing import List, Optional

from fastapi_poe import PoeBot, run

from embedchain.config import QueryConfig

from .base import BaseBot


class EcPoeBot(BaseBot, PoeBot):
    def __init__(self):
        self.history_length = 5
        super().__init__()

    async def get_response(self, query):
        last_message = query.query[-1].content
        try:
            history = (
                [f"{m.role}: {m.content}" for m in query.query[-(self.history_length + 1) : -1]]
                if len(query.query) > 0
                else None
            )
        except Exception as e:
            logging.error(f"Error when processing the chat history. Message is being sent without history. Error: {e}")
        logging.warning(history)
        answer = self.handle_message(last_message, history)
        yield self.text_event(answer)

    def handle_message(self, message, history: Optional[List[str]] = None):
        if message.startswith("/add "):
            response = self.add_data(message)
        else:
            response = self.ask_bot(message, history)
        return response

    def add_data(self, message):
        data = message.split(" ")[-1]
        try:
            self.add(data)
            response = f"Added data from: {data}"
        except Exception:
            logging.exception(f"Failed to add data {data}.")
            response = "Some error occurred while adding data."
        return response

    def ask_bot(self, message, history: List[str]):
        try:
            config = QueryConfig(history=history)
            response = self.query(message, config)
        except Exception:
            logging.exception(f"Failed to query {message}.")
            response = "An error occurred. Please try again!"
        return response


def start_command():
    parser = argparse.ArgumentParser(description="EmbedChain PoeBot command line interface")
    # parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind")
    parser.add_argument("--port", default=8080, type=int, help="Port to bind")
    parser.add_argument("--api-key", type=str, help="Poe API key")
    # parser.add_argument(
    #     "--history-length",
    #     default=5,
    #     type=int,
    #     help="Set the max size of the chat history. Multiplies cost, but improves conversation awareness.",
    # )
    args = parser.parse_args()

    # FIXME: Arguments are automatically loaded by Poebot's ArgumentParser which causes it to fail.
    # the port argument here is also just for show, it actually works because poe has the same argument.

    run(EcPoeBot(), api_key=args.api_key or os.environ.get("POE_API_KEY"))


if __name__ == "__main__":
    start_command()
