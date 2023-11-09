from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

from embedchain import App

app = Flask(__name__)
chat_bot = App()


@app.route("/chat", methods=["POST"])
def chat():
    incoming_message = request.values.get("Body", "").lower()
    response = handle_message(incoming_message)
    twilio_response = MessagingResponse()
    twilio_response.message(response)
    return str(twilio_response)


def handle_message(message):
    if message.startswith("add "):
        response = add_sources(message)
    else:
        response = query(message)
    return response


def add_sources(message):
    message_parts = message.split(" ", 2)
    if len(message_parts) == 3:
        data_type = message_parts[1]
        url_or_text = message_parts[2]
        try:
            chat_bot.add(data_type, url_or_text)
            response = f"Added {data_type}: {url_or_text}"
        except Exception as e:
            response = f"Failed to add {data_type}: {url_or_text}.\nError: {str(e)}"
    else:
        response = "Invalid 'add' command format.\nUse: add <data_type> <url_or_text>"
    return response


def query(message):
    try:
        response = chat_bot.chat(message)
    except Exception:
        response = "An error occurred. Please try again!"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
