import sqlite3
from flask import Blueprint, request, jsonify
from datetime import datetime
import threading
import re
from app.users import verify_jwt
from app.websocket import broadcast_comment



forum_bp = Blueprint('forum', __name__)
DB_PATH = 'app/database.db'

def sanitize_input(text):
    # Remove HTML tags and extra whitespace
    clean = re.sub(r'<[^>]*?>', '', text)
    clean = clean.strip()
    return clean

def init_forum_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(post_id) REFERENCES posts(id)
        )
    ''')

    conn.commit()
    conn.close()

@forum_bp.route('/posts', methods=['POST'])
def create_post():
    data = request.get_json()
    username = data.get('username')
    content = sanitize_input(data.get('content', ''))
    if len(content) > 500:
        return jsonify({'status': 'error', 'message': 'Content too long (max 500 characters)'}), 400

    if not username or not content:
        return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"📬 NEW POST from {username}: {content}")

    def save_post_async(username, content, timestamp):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO posts (username, content, timestamp) VALUES (?, ?, ?)",
                       (username, content, timestamp))
        conn.commit()
        conn.close()

    threading.Thread(target=save_post_async, args=(username, content, timestamp)).start()

    return jsonify({'status': 'success'})


@forum_bp.route('/posts', methods=['GET'])
def get_posts():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, content, timestamp FROM posts ORDER BY id DESC")
        posts = cursor.fetchall()
        conn.close()

        results = []
        for p in posts:
            results.append({
                'id': p[0],
                'username': p[1],
                'content': p[2],
                'timestamp': p[3],
            })

        return jsonify(results)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@forum_bp.route('/posts/<int:post_id>/comments', methods=['POST'])
def add_comment(post_id):
    data = request.get_json()
    username = data.get('username')
    content = sanitize_input(data.get('content', ''))
    if len(content) > 300:
        return jsonify({'status': 'error', 'message': 'Comment too long (max 300 characters)'}), 400

    if not username or not content:
        return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    def save_comment_async(post_id, username, content, timestamp):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO comments (post_id, username, content, timestamp) VALUES (?, ?, ?, ?)",
            (post_id, username, content, timestamp)
        )
        conn.commit()
        conn.close()

    def after_save():
        save_comment_async(post_id, username, content, timestamp)
        broadcast_comment(post_id)

    threading.Thread(target=after_save).start()
    return jsonify({'status': 'success'})


@forum_bp.route('/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, content, timestamp FROM comments WHERE post_id = ?", (post_id,))
        comments = cursor.fetchall()
        conn.close()

        results = []
        for c in comments:
            results.append({
                'id': c[0],         # ✅ Comment ID
                'username': c[1],   # Username
                'content': c[2],    # Content
                'timestamp': c[3],  # Timestamp
            })

        return jsonify(results)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


        return jsonify(results)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@forum_bp.route('/users/<string:username>/posts', methods=['GET'])
def get_user_posts(username):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, content, timestamp FROM posts WHERE username = ? ORDER BY id DESC", (username,))
        posts = cursor.fetchall()
        conn.close()

        results = []
        for p in posts:
            results.append({
                'id': p[0],
                'username': username,
                'content': p[1],
                'timestamp': p[2],
            })

        return jsonify(results)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@forum_bp.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({'status': 'error', 'message': 'Missing token'}), 401

    user = verify_jwt(token)
    if not user:
        return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 403

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT username FROM posts WHERE id = ?", (post_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'status': 'error', 'message': 'Post not found'}), 404

        post_owner = row[0]
        cursor.execute("SELECT role FROM users WHERE username = ?", (user['username'],))
        role_row = cursor.fetchone()
        role = role_row[0] if role_row else 'user'

        if user['username'] != post_owner and role != 'admin':
            return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

        cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Post deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@forum_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({'status': 'error', 'message': 'Missing token'}), 401

    user = verify_jwt(token)
    if not user:
        return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 403

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT username FROM comments WHERE id = ?", (comment_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'status': 'error', 'message': 'Comment not found'}), 404

        comment_owner = row[0]
        cursor.execute("SELECT role FROM users WHERE username = ?", (user['username'],))
        role_row = cursor.fetchone()
        role = role_row[0] if role_row else 'user'

        if user['username'] != comment_owner and role != 'admin':
            return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

        cursor.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Comment deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


