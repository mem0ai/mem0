import os 
from flask import Blueprint, request, jsonify, make_response
from embedchain import App, PersonApp, OpenSourceApp, PersonOpenSourceApp

from models import APIKey
from paths import DB_DIRECTORY_OPEN_AI, DB_DIRECTORY_OPEN_SOURCE

chat_response_bp = Blueprint('chat_response', __name__)


# Chat Response for user query
@chat_response_bp.route("/api/get_answer", methods=["POST"])
def get_answer():
    try:
        data = request.get_json()
        query = data.get("query")
        embedding_model = data.get("embedding_model")
        app_type = data.get("app_type")
        # persona = data.get("persona")

        if embedding_model == "open_ai":
            os.chdir(DB_DIRECTORY_OPEN_AI)
            api_key = APIKey.query.first().key
            os.environ["OPENAI_API_KEY"] = api_key
            if app_type == "app":
                chat_bot = App()
            # elif app_type == "p_app":
            #     chat_bot = PersonApp(persona)
        # elif embedding_model == "open_source":
        #     os.chdir(DB_DIRECTORY_OPEN_SOURCE)
        #     if app_type == "os_app":
        #         chat_bot = OpenSourceApp()
            # elif app_type == "pos_app":
            #     chat_bot = PersonOpenSourceApp(persona)

        response = chat_bot.chat(query)
        return make_response(jsonify({"response": response}), 200)
        
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 400)