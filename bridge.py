"""
bridge.py  –  MQTT → WebSocket relay  (compatible with websockets v14+/v16)
─────────────────────────────────────────────────────────────────────────────
Run:   python bridge.py
Then open dashboard.html in your browser.

FIXES in v3:
  • ws_handler now uses await websocket.wait_closed() instead of
    "async for _ in websocket" — in websockets v16 the for-loop exits
    instantly when the browser sends no messages, causing immediate disconnect.
  • on_connect handles paho VERSION2 ReasonCode objects correctly.
  • All prints use flush=True so output appears immediately.
"""

import asyncio
import threading
import time
import paho.mqtt.client as mqtt

# ── detect websockets API version ──────────────────────────────
try:
    from websockets.asyncio.server import serve   # v14 / v16 new API
    WS_NEW_API = True
except ImportError:
    import websockets                             # v13 and older
    WS_NEW_API = False

try:
    import serial.tools.list_ports as lp
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# ── Configuration (mirror of weather.py) ──────────────────────
VPS_HOST   = "157.173.101.159"
VPS_PORT   = 8267
CANDIDATE  = "Kayiranga Simbi Kelia"
MQTT_TOPIC = f"spees402/temperature/{CANDIDATE}"
WS_HOST    = "localhost"
WS_PORT    = 8765

# ── Shared state ───────────────────────────────────────────────
connected_browsers: set = set()
main_loop: asyncio.AbstractEventLoop = None

# ── COM port helper ────────────────────────────────────────────
def print_com_ports():
    print("\n┌─────────────────────────────────────────────────┐")
    print("│           Available Serial / COM Ports           │")
    print("├─────────────────────────────────────────────────┤")
    if HAS_SERIAL:
        ports = list(lp.comports())
        if ports:
            for p in ports:
                line = f"  {p.device:<10} {p.description:<35}"
                print(f"│ {line:<49}│")
        else:
            print("│  No serial ports found – plug in the Arduino.   │")
    else:
        print("│  pyserial not found, cannot list ports.          │")
    print("└─────────────────────────────────────────────────┘\n")

# ── broadcast to all browser tabs ─────────────────────────────
async def broadcast(payload: str):
    dead = set()
    for ws in list(connected_browsers):
        try:
            await ws.send(payload)
        except Exception:
            dead.add(ws)
    connected_browsers.difference_update(dead)

# ── WebSocket handler ──────────────────────────────────────────
async def ws_handler(websocket):
    addr = getattr(websocket, "remote_address", "?")
    count = len(connected_browsers) + 1
    print(f"[WS]  Browser connected  {addr}  (total: {count})", flush=True)
    connected_browsers.add(websocket)
    try:
        # ✅ FIX: use wait_closed() to keep connection alive.
        # "async for _ in websocket" exits immediately in websockets v16
        # when the client sends no data, dropping the connection at once.
        await websocket.wait_closed()
    except Exception:
        pass
    finally:
        connected_browsers.discard(websocket)
        print(f"[WS]  Browser disconnected  (total: {len(connected_browsers)})", flush=True)

# ── WebSocket server ───────────────────────────────────────────
async def run_ws_server():
    global main_loop
    main_loop = asyncio.get_running_loop()

    if WS_NEW_API:
        # websockets >= v14
        async with serve(ws_handler, WS_HOST, WS_PORT) as server:
            print(f"[WS]  Listening on ws://{WS_HOST}:{WS_PORT}  (websockets v14+ API)", flush=True)
            print("[WS]  Open dashboard.html in your browser now.\n", flush=True)
            await server.serve_forever()
    else:
        # websockets <= v13
        async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
            print(f"[WS]  Listening on ws://{WS_HOST}:{WS_PORT}  (websockets legacy API)", flush=True)
            print("[WS]  Open dashboard.html in your browser now.\n", flush=True)
            await asyncio.Future()

# ── MQTT callbacks ─────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties=None):
    # paho VERSION2 passes a ReasonCode object — convert safely
    try:
        rc_val = int(reason_code)
    except Exception:
        rc_val = -1

    if rc_val == 0:
        print(f"[MQTT] ✓ Connected OK!", flush=True)
        client.subscribe(MQTT_TOPIC, qos=1)
        print(f"[MQTT] Subscribed → {MQTT_TOPIC}\n", flush=True)
    else:
        print(f"[MQTT] ✗ Connection refused (code={reason_code})", flush=True)

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="ignore").strip()
    print(f"[MQTT] ← {payload} °C  ({len(connected_browsers)} browser(s))", flush=True)
    if main_loop and connected_browsers:
        asyncio.run_coroutine_threadsafe(broadcast(payload), main_loop)

# ── MQTT thread ────────────────────────────────────────────────
def mqtt_thread():
    while True:
        try:
            try:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            except Exception:
                client = mqtt.Client()
            client.on_connect = on_connect
            client.on_message = on_message
            print(f"[MQTT] Connecting to {VPS_HOST}:{VPS_PORT} …")
            client.connect(VPS_HOST, VPS_PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            print(f"[MQTT] Error: {e}  – retrying in 8 s …")
            time.sleep(8)

# ── Entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 52)
    print("   SPEES-402  –  MQTT → WebSocket Bridge  v2")
    print("=" * 52)
    print_com_ports()

    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()

    try:
        asyncio.run(run_ws_server())
    except KeyboardInterrupt:
        print("\n[Info] Bridge stopped.")
