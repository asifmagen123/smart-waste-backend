from flask import Flask
from flask_cors import CORS
import os

from .users import users_bp, init_db
from .model import model_bp
from .websocket import websocket_bp, sock
from .forum import forum_bp, init_forum_db
from .routes import api_bp


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config['SECRET_KEY'] = 'replace-this-key'
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'app', 'uploads')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    init_db()
    init_forum_db()

    register_blueprints(app)
    return app



def register_blueprints(app):
    app.register_blueprint(users_bp)
    app.register_blueprint(model_bp)
    app.register_blueprint(websocket_bp)
    app.register_blueprint(forum_bp)
    app.register_blueprint(api_bp)

