from flask import Blueprint
from flask_sock import Sock
import json

# Create blueprint and socket
websocket_bp = Blueprint('websocket_bp', __name__)
sock = Sock()

# Keep track of connected WebSocket clients
connected_clients = []

# Ensure Sock is initialized once with the Flask app
@websocket_bp.record_once
def register_sock(state):
    sock.init_app(state.app)

# WebSocket endpoint: /ws
@sock.route('/ws')
def websocket_handler(ws):
    connected_clients.append(ws)
    print("🟢 Client connected. Total clients:", len(connected_clients))

    try:
        while True:
            message = ws.receive()
            if message is None:
                break  # Client disconnected

            print("📨 Received message:", message)

            # Broadcast message to all other clients
            for client in connected_clients:
                if client != ws:
                    try:
                        client.send(message)
                    except Exception as e:
                        print("⚠️ Failed to send message:", e)

    except Exception as e:
        print("❌ WebSocket error:", e)

    finally:
        connected_clients.remove(ws)
        print("🔴 Client disconnected. Remaining clients:", len(connected_clients))



def broadcast_update(user_id, stats):
    """
    Broadcast user stat update to all connected WebSocket clients.
    """
    message = json.dumps({
        "type": "stats_update",
        "user_id": user_id,
        "total_items": stats.get("total_items_recycled", 0),
        "accuracy": stats.get("recycle_accuracy", 0.0),
    })

    for client in connected_clients:
        try:
            client.send(message)
        except Exception as e:
            print("⚠️ Failed to send update:", e)


def broadcast_comment(post_id):
    """
    Broadcast a 'new_comment' message to all connected WebSocket clients.
    """
    message = json.dumps({
        "type": "new_comment",
        "post_id": post_id,
    })

    for client in connected_clients:
        try:
            client.send(message)
        except Exception as e:
            print(f"⚠️ Failed to send comment update: {e}")

