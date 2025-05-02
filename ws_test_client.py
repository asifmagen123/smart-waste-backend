import websocket
import threading

def on_message(ws, message):
    print("📡 Received:", message)

def on_error(ws, error):
    print("❌ Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("🔌 Disconnected from WebSocket")

def on_open(ws):
    print("🟢 Connected to WebSocket")

def run_ws_client():
    ws_url = "ws://127.0.0.1:5000/ws"
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

if __name__ == "__main__":
    threading.Thread(target=run_ws_client).start()
