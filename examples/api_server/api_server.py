from flask import Flask, jsonify, request

from embedchain import App

app = Flask(__name__)


def initialize_chat_bot():
    global chat_bot
    chat_bot = App()


@app.route("/add", methods=["POST"])
def add():
    data = request.get_json()
    data_type = data.get("data_type")
    url_or_text = data.get("url_or_text")
    if data_type and url_or_text:
        try:
            chat_bot.add(data_type, url_or_text)
            return jsonify({"data": f"Added {data_type}: {url_or_text}"}), 200
        except Exception:
            return jsonify({"error": f"Failed to add {data_type}: {url_or_text}"}), 500
    return jsonify({"error": "Invalid request. Please provide 'data_type' and 'url_or_text' in JSON format."}), 400


@app.route("/query", methods=["POST"])
def query():
    data = request.get_json()
    question = data.get("question")
    if question:
        try:
            response = chat_bot.chat(question)
            return jsonify({"data": response}), 200
        except Exception:
            return jsonify({"error": "An error occurred. Please try again!"}), 500
    return jsonify({"error": "Invalid request. Please provide 'question' in JSON format."}), 400


if __name__ == "__main__":
    initialize_chat_bot()
    app.run(host="0.0.0.0", port=5000, debug=False)
