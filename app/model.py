import os
import sqlite3
import numpy as np
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from tensorflow.keras.models import load_model
from app.websocket import broadcast_update
from .predictor import Predictor
import threading
from hashlib import sha256
from datetime import datetime
from app.users import verify_jwt, get_user_stats_raw

model_bp = Blueprint('model', __name__)
MODEL_PATH = r'best_model.keras'
DB_PATH = 'app/database.db'

CLASS_NAMES = [
    'Cardboard', 'Organic', 'Textile Trash',
    'electronic_waste', 'glass', 'metal', 'paper', 'plastic'
]
IMG_SIZE = (160, 160)

# Load model + predictor
model = load_model(MODEL_PATH)
predictor = Predictor(model=model, class_names=CLASS_NAMES, img_size=IMG_SIZE)

@model_bp.route('/predict', methods=['POST'])
def predict():
    file = request.files['image']

    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Empty filename'}), 400
    # Validate file type
    allowed_extensions = ('.jpg', '.jpeg', '.png')
    if not file.filename.lower().endswith(allowed_extensions):
        return jsonify({'status': 'error', 'message': 'Only .jpg, .jpeg, and .png files are allowed'}), 400

    # Check file extension
    if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return jsonify({'status': 'error', 'message': 'Only image files are allowed'}), 400

    try:
        raw_name = secure_filename(file.filename)
        hashed_name = sha256(f"{raw_name}{datetime.now()}".encode()).hexdigest() + ".jpg"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], hashed_name)
        file.save(filepath)

        token = request.headers.get("Authorization")
        if not token:
            return jsonify({'status': 'error', 'message': 'Missing token'}), 401

        user = verify_jwt(token)
        if not user:
            return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 403

        user_id = user["user_id"]

        try:
            predicted_class, confidence = predictor.predict_image(filepath)
        except Exception as e:
            print("❌ Prediction error:", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500

        print("✅ Image received, predicting:", filepath)
        threading.Thread(
            target=log_prediction,
            args=(user_id, hashed_name, predicted_class, confidence)
        ).start()

        return jsonify({
            'status': 'success',
            'prediction': {
                'class': predicted_class,
                'confidence': round(confidence * 100, 2)
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def log_prediction(user_id, image_id, predicted_class, confidence):
    print(f"📊 Logging for user_id={user_id}, class={predicted_class}, conf={confidence}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO recycleditems (user_id, upload_date, confidence_score)
        VALUES (?, datetime('now'), ?)
    ''', (user_id, confidence))
    conn.commit()
    conn.close()

    stats = get_user_stats_raw(user_id)
    broadcast_update(user_id, stats)
