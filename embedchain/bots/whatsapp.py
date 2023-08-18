from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from .base import BaseBot

import argparse
import logging
import signal
import sys


class WhatsAppBot(BaseBot):
    def __init__(self):
        super().__init__()

    def handle_message(self, message):
        if message.startswith("add "):
            response = self.add_sources(message)
        else:
            response = self.query(message)
        return response

    def add_source(self, message):
        data = message.split(" ", 1)
        try:
            self.add(data)
            response = f"Added {data}"
        except Exception as e:
            response = f"Failed to add {data}.\nError: {str(e)}"
        return response

    def query(self, message):
        try:
            response = self.query(message)
        except Exception:
            response = "An error occurred. Please try again!"
        return response

    def start(self, host="0.0.0.0", port=5000, debug=True):
        app = Flask(__name__)

        def signal_handler(sig, frame):
            logging.info("\nGracefully shutting down the WhatsAppBot...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        @app.route("/chat", methods=["POST"])
        def chat():
            incoming_message = request.values.get("Body", "").lower()
            response = self.handle_message(incoming_message)
            response = MessagingResponse()
            response.message(response)
            return str(response)

        app.run(host=host, port=port, debug=debug)


def start_command():
    parser = argparse.ArgumentParser(description="EmbedChain WhatsAppBot Command Line Interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind")
    parser.add_argument("--port", default=5000, type=int, help="Port to bind")
    args = parser.parse_args()

    whatsapp_bot = WhatsAppBot()
    whatsapp_bot.start(host=args.host, port=args.port)


if __name__ == "__main__":
    start_command()
