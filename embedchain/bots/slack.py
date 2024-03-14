import argparse
import logging
import os
import signal
import sys

from embedchain import App
from embedchain.helpers.json_serializable import register_deserializable

from .base import BaseBot

try:
    from flask import Flask, request
    from slack_sdk import WebClient
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "The required dependencies for Slack are not installed."
        'Please install with `pip install --upgrade "embedchain[slack]"`'
    ) from None


logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")


@register_deserializable
class SlackBot(BaseBot):
    def __init__(self):
        self.client = WebClient(token=SLACK_BOT_TOKEN)
        self.chat_bot = App()
        self.recent_message = {"ts": 0, "channel": ""}
        super().__init__()

    def handle_message(self, event_data):
        message = event_data.get("event")
        if message and "text" in message and message.get("subtype") != "bot_message":
            text: str = message["text"]
            if float(message.get("ts")) > float(self.recent_message["ts"]):
                self.recent_message["ts"] = message["ts"]
                self.recent_message["channel"] = message["channel"]
                if text.startswith("query"):
                    _, question = text.split(" ", 1)
                    try:
                        response = self.chat_bot.chat(question)
                        self.send_slack_message(message["channel"], response)
                        logger.info("Query answered successfully!")
                    except Exception as e:
                        self.send_slack_message(message["channel"], "An error occurred. Please try again!")
                        logger.error("Error occurred during 'query' command:", e)
                elif text.startswith("add"):
                    _, data_type, url_or_text = text.split(" ", 2)
                    if url_or_text.startswith("<") and url_or_text.endswith(">"):
                        url_or_text = url_or_text[1:-1]
                    try:
                        self.chat_bot.add(url_or_text, data_type)
                        self.send_slack_message(message["channel"], f"Added {data_type} : {url_or_text}")
                    except ValueError as e:
                        self.send_slack_message(message["channel"], f"Error: {str(e)}")
                        logger.error("Error occurred during 'add' command:", e)
                    except Exception as e:
                        self.send_slack_message(message["channel"], f"Failed to add {data_type} : {url_or_text}")
                        logger.error("Error occurred during 'add' command:", e)

    def send_slack_message(self, channel, message):
        response = self.client.chat_postMessage(channel=channel, text=message)
        return response

    def start(self, host="0.0.0.0", port=5000, debug=True):
        app = Flask(__name__)

        def signal_handler(sig, frame):
            logger.info("\nGracefully shutting down the SlackBot...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        @app.route("/", methods=["POST"])
        def chat():
            # Check if the request is a verification request
            if request.json.get("challenge"):
                return str(request.json.get("challenge"))

            response = self.handle_message(request.json)
            return str(response)

        app.run(host=host, port=port, debug=debug)


def start_command():
    parser = argparse.ArgumentParser(description="EmbedChain SlackBot command line interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind")
    parser.add_argument("--port", default=5000, type=int, help="Port to bind")
    args = parser.parse_args()

    slack_bot = SlackBot()
    slack_bot.start(host=args.host, port=args.port)


if __name__ == "__main__":
    start_command()
