import sqlite3
import string
import random
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import re
import jwt
from datetime import datetime, timedelta



JWT_SECRET = "my_super_secret"  # Use a better secret in real projects
JWT_EXPIRATION_MINUTES = 60


users_bp = Blueprint('users', __name__)
DB_PATH = 'app/database.db'


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')
    conn.commit()

    # Add admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        import bcrypt
        password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('''
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
        ''', ('admin', password_hash, 'admin'))
        print("✅ Admin user created with username='admin' and password='admin123'")

    conn.commit()
    conn.close()



@users_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        if len(username) < 3 or not username.isalnum():
            return jsonify({'status': 'error',
                            'message': 'Username must be at least 3 characters and contain only letters and numbers'}), 400

        if len(password) < 6 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            return jsonify({'status': 'error',
                            'message': 'Password must be at least 6 characters and contain letters and numbers'}), 400

        if len(username) > 16:
            return jsonify({'status': 'error', 'message': 'Username must be 16 characters or fewer'}), 400

        if len(password) > 16:
            return jsonify({'status': 'error', 'message': 'Password must be 16 characters or fewer'}), 400


        if not username or not password:
            return jsonify({'status': 'error', 'message': 'Missing fields'}), 400


        if len(username) < 3 or not username.isalnum():
            return jsonify({'status': 'error',
                            'message': 'Username must be at least 3 characters and contain only letters and numbers'}), 400

        if len(password) < 6 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            return jsonify({'status': 'error',
                            'message': 'Password must be at least 6 characters and contain letters and numbers'}), 400

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'Username already exists'}), 409

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_password)
        )
        conn.commit()

        user_id = cursor.lastrowid
        token = create_jwt(user_id, username, 'user')
        conn.close()

        return jsonify({
            'status': 'success',
            'message': 'User registered successfully',
            'user_id': user_id,
            'token': token,
            'role': 'user'
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@users_bp.route('/login', methods=['POST'])
def login():
    try:
        import bcrypt
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'status': 'error', 'message': 'Missing username or password'}), 400

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, password, role FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row:
            user_id, stored_password, role = row

            # Try bcrypt
            if isinstance(stored_password, bytes):
                valid = bcrypt.checkpw(password.encode('utf-8'), stored_password)
            else:
                from werkzeug.security import check_password_hash
                valid = check_password_hash(stored_password, password)

            if valid:
                token = create_jwt(user_id, username, role)  # ⚠️ update create_jwt to accept role too
                return jsonify({
                    'status': 'success',
                    'message': 'Login successful',
                    'user_id': user_id,
                    'token': token,
                    'role': role
                })

        return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@users_bp.route('/stats/<int:user_id>', methods=['GET'])
def get_user_stats(user_id):
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({'status': 'error', 'message': 'Missing token'}), 401

    user = verify_jwt(token)
    if not user or user["user_id"] != user_id:
        return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 403

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                COUNT(*) as total_items,
                MAX(upload_date) as last_date,
                AVG(confidence_score) as avg_accuracy
            FROM recycleditems
            WHERE user_id = ?
        ''', (user_id,))

        row = cursor.fetchone()
        conn.close()

        stats = {
            "total_items_recycled": row[0] or 0,
            "last_recycle_date": row[1] or "N/A",
            "recycle_accuracy": round(row[2], 2) if row[2] else 0.0
        }

        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@users_bp.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT users.username, COUNT(r.id) as total
            FROM users
            JOIN recycleditems r ON users.id = r.user_id
            GROUP BY users.username
            ORDER BY total DESC
            LIMIT 10
        ''')
        rows = cursor.fetchall()
        conn.close()

        leaderboard = [{"username": row[0], "total_items": row[1]} for row in rows]
        return jsonify({"status": "success", "leaderboard": leaderboard})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@users_bp.route('/init-db')
def run_db_setup():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT,
            password TEXT
        )
    ''')

    # Recycled items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recycleditems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            upload_date TEXT,
            confidence_score REAL
        )
    ''')

    conn.commit()
    conn.close()
    return "✅ Database initialized"

def get_user_stats_raw(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            COUNT(*) as total_items,
            MAX(upload_date) as last_date,
            AVG(confidence_score) as avg_accuracy
        FROM recycleditems
        WHERE user_id = ?
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()

    stats = {
        "total_items_recycled": row[0] or 0,
        "last_recycle_date": row[1] or "N/A",
        "recycle_accuracy": round(row[2], 2) if row[2] else 0.0
    }

    return stats

def create_jwt(user_id, username, role):
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_jwt(token):
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return decoded  # contains: user_id, username, exp
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None



@users_bp.route('/users', methods=['GET'])
def get_all_users():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users")
        users = [{'id': row[0], 'username': row[1], 'role': row[2]} for row in cursor.fetchall()]
        conn.close()
        return jsonify(users)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@users_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    token = request.headers.get("Authorization")
    user = verify_jwt(token)
    if not user:
        return jsonify({'status': 'error', 'message': 'Invalid or missing token'}), 403

    # 🚫 Prevent deleting yourself
    if user['user_id'] == user_id:
        return jsonify({'status': 'error', 'message': 'Cannot delete yourself'}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ?", (user['username'],))
    role_row = cursor.fetchone()
    if not role_row or role_row[0] != 'admin':
        conn.close()
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    try:
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'User deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
