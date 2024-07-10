import os

import requests
from dotenv import load_dotenv
from flask import Flask, request

from embedchain import App

app = Flask(__name__)
load_dotenv()
bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_bot = App()


@app.route("/", methods=["POST"])
def telegram_webhook():
    data = request.json
    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message["text"]
    if text.startswith("/start"):
        response_text = (
            "Welcome to Embedchain Bot! Try the following commands to use the bot:\n"
            "For adding data sources:\n /add <data_type> <url_or_text>\n"
            "For asking queries:\n /query <question>"
        )
    elif text.startswith("/add"):
        _, data_type, url_or_text = text.split(maxsplit=2)
        response_text = add_to_chat_bot(data_type, url_or_text)
    elif text.startswith("/query"):
        _, question = text.split(maxsplit=1)
        response_text = query_chat_bot(question)
    else:
        response_text = "Invalid command. Please refer to the documentation for correct syntax."
    send_message(chat_id, response_text)
    return "OK"


def add_to_chat_bot(data_type, url_or_text):
    try:
        chat_bot.add(data_type, url_or_text)
        response_text = f"Added {data_type} : {url_or_text}"
    except Exception as e:
        response_text = f"Failed to add {data_type} : {url_or_text}"
        print("Error occurred during 'add' command:", e)
    return response_text


def query_chat_bot(question):
    try:
        response = chat_bot.chat(question)
        response_text = response
    except Exception as e:
        response_text = "An error occurred. Please try again!"
        print("Error occurred during 'query' command:", e)
    return response_text


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, json=data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
