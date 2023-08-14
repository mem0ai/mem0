import os

from dotenv import load_dotenv
from flask import Flask
from slack_sdk import WebClient
from slackeventsapi import SlackEventAdapter

from embedchain import App

load_dotenv()
app = Flask(__name__)

slack_signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/chat", app)

slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
client = WebClient(token=slack_bot_token)

chat_bot = App()
recent_message = {"ts": 0, "channel": ""}


@slack_events_adapter.on("message")
def handle_message(event_data):
    message = event_data["event"]
    if "text" in message and message.get("subtype") != "bot_message":
        text = message["text"]
        if float(message.get("ts")) > float(recent_message["ts"]):
            recent_message["ts"] = message["ts"]
            recent_message["channel"] = message["channel"]
            if text.startswith("query"):
                _, question = text.split(" ", 1)
                try:
                    response = chat_bot.chat(question)
                    send_slack_message(message["channel"], response)
                    print("Query answered successfully!")
                except Exception as e:
                    send_slack_message(message["channel"], "An error occurred. Please try again!")
                    print("Error occurred during 'query' command:", e)
            elif text.startswith("add"):
                _, data_type, url_or_text = text.split(" ", 2)
                if url_or_text.startswith("<") and url_or_text.endswith(">"):
                    url_or_text = url_or_text[1:-1]
                try:
                    chat_bot.add(data_type, url_or_text)
                    send_slack_message(message["channel"], f"Added {data_type} : {url_or_text}")
                except Exception as e:
                    send_slack_message(message["channel"], f"Failed to add {data_type} : {url_or_text}")
                    print("Error occurred during 'add' command:", e)


def send_slack_message(channel, message):
    response = client.chat_postMessage(channel=channel, text=message)
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
