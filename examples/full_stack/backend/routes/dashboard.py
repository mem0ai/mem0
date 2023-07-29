import os 
import shutil
from flask import Blueprint, request, jsonify, make_response

from models import db, APIKey, BotList
from paths import DB_DIRECTORY_OPEN_AI, DB_DIRECTORY_OPEN_SOURCE

dashboard_bp = Blueprint('dashboard', __name__)


# Set Open AI Key
@dashboard_bp.route('/api/set_key', methods=['POST'])
def set_key():
    data = request.get_json()
    api_key = data['openAIKey']
    existing_key = APIKey.query.first()
    if existing_key:
        existing_key.key = api_key
    else:
        new_key = APIKey(key=api_key)
        db.session.add(new_key)
    db.session.commit()
    return make_response(jsonify(message='API key saved successfully'), 200)


# Check OpenAI Key
@dashboard_bp.route('/api/check_key', methods=['GET'])
def check_key():
    existing_key = APIKey.query.first()
    if existing_key:
        return make_response(jsonify(status="ok", message='OpenAI Key exists'), 200)
    else:
        return make_response(jsonify(status="fail", message='No OpenAI Key present'), 200)


# Create a bot
@dashboard_bp.route('/api/create_bot', methods=['POST'])
def create_bot():
    data = request.get_json()
    name = data['name']
    # persona = data['persona']
    slug = name.lower().replace(' ', '_')
    existing_bot = BotList.query.filter_by(slug=slug).first()
    if existing_bot:
        return make_response(jsonify(message='Bot already exists'), 400),
    # new_bot = BotList(name=name, persona=persona, slug=slug)
    new_bot = BotList(name=name, slug=slug)
    db.session.add(new_bot)
    db.session.commit()
    return make_response(jsonify(message='Bot created successfully'), 200)


# Delete a bot
@dashboard_bp.route("/api/delete_bot", methods=["POST"])
def delete_bot():
    data = request.get_json()
    slug = data.get("slug")
    bot = BotList.query.filter_by(slug=slug).first()
    if bot:
        db.session.delete(bot)
        db.session.commit()
        return make_response(jsonify(message='Bot deleted successfully'), 200)
    return make_response(jsonify(message='Bot not found'), 400)


# Get the list of bots
@dashboard_bp.route('/api/get_bots', methods=['GET'])
def get_bots():
    bots = BotList.query.all()
    bot_list = []
    for bot in bots:
        bot_list.append({
            'name': bot.name,
            'slug': bot.slug,
            # 'persona': bot.persona
        })
    return jsonify(bot_list)


# Purge the vector DBs
# @dashboard_bp.route("/api/purge_db", methods=["POST"])
# def purge_db():
#     try:
#         shutil.rmtree(os.path.join(DB_DIRECTORY_OPEN_AI,'db'))
#         shutil.rmtree(os.path.join(DB_DIRECTORY_OPEN_SOURCE,'db'))
#         return make_response(jsonify(message='Database purged successfully'), 200)
#     except Exception as e:
#         return make_response(jsonify({"error": str(e)}), 400)