import os

from flask import Flask
from models import db
from paths import DB_DIRECTORY_OPEN_AI, ROOT_DIRECTORY
from routes.chat_response import chat_response_bp
from routes.dashboard import dashboard_bp
from routes.sources import sources_bp

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(ROOT_DIRECTORY, "database", "user_data.db")
app.register_blueprint(dashboard_bp)
app.register_blueprint(sources_bp)
app.register_blueprint(chat_response_bp)


# Initialize the app on startup
def load_app():
    os.makedirs(DB_DIRECTORY_OPEN_AI, exist_ok=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    load_app()
    app.run(host="0.0.0.0", debug=True, port=8000)
