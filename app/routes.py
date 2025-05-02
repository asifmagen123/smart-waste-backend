# Defines all REST API endpoints for prediction and user account management.

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import uuid
from .model import predict
from .logger import log_prediction
from .websocket import broadcast_update
from flask import g



api_bp = Blueprint("api", __name__)
@api_bp.route("/predict", methods=["POST"])
def predict():
    try:
        if "image" not in request.files:
            return jsonify({"success": False, "message": "No image uploaded"}), 400

        file = request.files["image"]
        filename = secure_filename(file.filename)
        image_id = f"{uuid.uuid4()}_{filename}"
        upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], image_id)

        file.save(upload_path)
        g.user_id = int(request.form.get("user_id"))
        predicted_class, confidence = predict_class(upload_path)
        log_prediction(image_id, predicted_class, confidence)

        result = {
            "class": predicted_class,
            "confidence": round(confidence * 100, 2)
        }
        return jsonify({"success": True, "prediction": result})

    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@api_bp.route("/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.json
    success, message = register_user(data.get("username"), data.get("password"))
    status = 200 if success else 409
    return jsonify({"success": success, "message": message}), status

@api_bp.route("/login", methods=["POST"])
def login():
    """Authenticate a user."""
    data = request.json
    success, message = login_user(data.get("username"), data.get("password"))
    status = 200 if success else 401
    return jsonify({"success": success, "message": message}), status

@api_bp.route("/delete", methods=["POST"])
def delete():
    """Delete a user account."""
    data = request.json
    success, message = delete_user(data.get("username"), data.get("password"))
    status = 200 if success else 401
    return jsonify({"success": success, "message": message}), status


@api_bp.route("/test-broadcast")
def test_broadcast():
    broadcast_update(user_id=999, stats={
        "total_items_recycled": 99,
        "recycle_accuracy": 0.95
    })
    return "✅ Broadcast sent"

