import serial
import time
import paho.mqtt.client as mqtt

# ── Configuration ─────────────────────────────────────────
SERIAL_PORT   = "COM7"                # ← fixed
BAUD_RATE     = 9600
CANDIDATE     = "Kayiranga Simbi Kelia"        # ← must match Arduino
VPS_HOST      = "157.173.101.159"
VPS_PORT      = 8267
MQTT_TOPIC    = f"spees402/temperature/{CANDIDATE}"
MQTT_USER     = None
MQTT_PASS     = None

# ── MQTT callbacks ────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties):
    codes = {
        0: "Connected",
        1: "Bad protocol",
        2: "Client ID rejected",
        3: "Broker unavailable",
        4: "Bad credentials",
        5: "Not authorised",
    }
    print(f"[MQTT] {codes.get(reason_code, 'Unknown')} (code {reason_code})")

def on_publish(client, userdata, mid, reason_code, properties):
    pass

# ── MQTT setup ────────────────────────────────────────────
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_publish = on_publish

if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

print(f"[MQTT] Connecting to {VPS_HOST}:{VPS_PORT} ...")
client.connect(VPS_HOST, VPS_PORT, keepalive=60)
client.loop_start()

# ── Serial setup ──────────────────────────────────────────
print(f"[Serial] Opening {SERIAL_PORT} at {BAUD_RATE} baud ...")
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=3)
    time.sleep(2)
    ser.flushInput()
    print(f"[Serial] Port open. Listening ...\n")
except serial.SerialException as e:
    print(f"[Error] Cannot open serial port: {e}")
    print("  Check SERIAL_PORT value and that Arduino is connected.")
    exit(1)

# ── Main loop ─────────────────────────────────────────────
print(f"{'─'*40}")
print(f"  Topic : {MQTT_TOPIC}")
print(f"  Port  : {SERIAL_PORT}")
print(f"{'─'*40}\n")

try:
    while True:
        raw = ser.readline().decode("utf-8", errors="ignore").strip()

        if not raw:
            continue

        if raw.startswith("TEMP:"):
            value = raw[5:]
            timestamp = time.strftime("%H:%M:%S")

            if value == "ERR":
                print(f"[{timestamp}] Sensor read error")
            else:
                print(f"[{timestamp}] Temperature: {value} °C  →  published to {MQTT_TOPIC}")
                result = client.publish(MQTT_TOPIC, value, qos=1, retain=True)
                result.wait_for_publish()

except KeyboardInterrupt:
    print("\n[Info] Stopped by user.")
finally:
    ser.close()
    client.loop_stop()
    client.disconnect()
    print("[Info] Serial and MQTT connections closed.")