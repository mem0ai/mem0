import argparse
import logging
import os

from fastapi_poe import PoeBot, run

from .base import BaseBot


class PoeBot(BaseBot, PoeBot):
    def __init__(self):
        super().__init__()

    async def get_response(self, query):
        last_message = query.query[-1].content
        answer = self.handle_message(last_message)
        yield self.text_event(answer)

    def handle_message(self, message):
        if message.startswith("/add "):
            response = self.add_data(message)
        else:
            response = self.ask_bot(message)
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

    def ask_bot(self, message):
        try:
            response = self.query(message)
        except Exception:
            logging.exception(f"Failed to query {message}.")
            response = "An error occurred. Please try again!"
        return response


def start_command():
    parser = argparse.ArgumentParser(description="EmbedChain PoeBot command line interface")
    # parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind")
    # parser.add_argument("--port", default=5000, type=int, help="Port to bind")
    parser.add_argument("--apikey", type=str, help="Poe API key")
    args = parser.parse_args()

    run(PoeBot(), api_key=args.apikey or os.environ.get("POE_API_KEY"))


if __name__ == "__main__":
    start_command()
