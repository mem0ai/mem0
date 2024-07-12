import logging
import os
import re

import requests
from dotenv import load_dotenv
from slack_bolt import App as SlackApp
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv(".env")

logger = logging.getLogger(__name__)


def remove_mentions(message):
    mention_pattern = re.compile(r"<@[^>]+>")
    cleaned_message = re.sub(mention_pattern, "", message)
    cleaned_message.strip()
    return cleaned_message


class SlackBotApp:
    def __init__(self) -> None:
        logger.info("Slack Bot using Embedchain!")

    def add(self, _):
        raise ValueError("Add is not implemented yet")

    def query(self, query, citations: bool = False):
        url = os.environ["EC_APP_URL"] + "/query"
        payload = {
            "question": query,
            "citations": citations,
        }
        try:
            response = requests.request("POST", url, json=payload)
            try:
                response = response.json()
            except Exception:
                logger.error(f"Failed to parse response: {response}")
                response = {}
            return response
        except Exception:
            logger.exception(f"Failed to query {query}.")
            response = "An error occurred. Please try again!"
        return response


SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]

slack_app = SlackApp(token=SLACK_BOT_TOKEN)
slack_bot = SlackBotApp()


@slack_app.event("message")
def app_message_handler(message, say):
    pass


@slack_app.event("app_mention")
def app_mention_handler(body, say, client):
    # Get the timestamp of the original message to reply in the thread
    if "thread_ts" in body["event"]:
        # thread is already created
        thread_ts = body["event"]["thread_ts"]
        say(
            text="🧵 Currently, we don't support answering questions in threads. Could you please send your message in the channel for a swift response? Appreciate your understanding! 🚀",  # noqa: E501
            thread_ts=thread_ts,
        )
        return

    thread_ts = body["event"]["ts"]
    say(
        text="🎭 Putting on my thinking cap, brb with an epic response!",
        thread_ts=thread_ts,
    )
    query = body["event"]["text"]
    question = remove_mentions(query)
    print("Asking question: ", question)
    response = slack_bot.query(question, citations=True)
    default_answer = "Sorry, I don't know the answer to that question. Please refer to the documentation.\nhttps://nextjs.org/docs"  # noqa: E501
    answer = response.get("answer", default_answer)
    contexts = response.get("contexts", [])
    if contexts:
        sources = list(set(map(lambda x: x[1]["url"], contexts)))
        answer += "\n\n*Sources*:\n"
        for i, source in enumerate(sources):
            answer += f"- {source}\n"

    print("Sending answer: ", answer)
    result = say(text=answer, thread_ts=thread_ts)
    if result["ok"]:
        channel = result["channel"]
        timestamp = result["ts"]
        client.reactions_add(
            channel=channel,
            name="open_mouth",
            timestamp=timestamp,
        )
        client.reactions_add(
            channel=channel,
            name="thumbsup",
            timestamp=timestamp,
        )
        client.reactions_add(
            channel=channel,
            name="heart",
            timestamp=timestamp,
        )
        client.reactions_add(
            channel=channel,
            name="thumbsdown",
            timestamp=timestamp,
        )


def start_bot():
    slack_socket_mode_handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    slack_socket_mode_handler.start()


if __name__ == "__main__":
    start_bot()
