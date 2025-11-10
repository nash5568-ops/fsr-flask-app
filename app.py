from flask import Flask, render_template, jsonify
import time, threading, os

try:
    import serial
except ImportError:
    serial = None

app = Flask(__name__)

port = 'COM4'
baud = 9600
ser = None
sensor_data = {
    "seat": 0,
    "lower": 0,
    "mid": 0,
    "upper": 0,
    "time": 0,
    "baseline": {"lower": None, "mid": None, "upper": None},
    "fill": {"lower": 0, "mid": 0, "upper": 0},
    "sitting": False
}

if serial and os.environ.get("RENDER") != "true":
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to {port}")
    except Exception as e:
        print(f"⚠️ Could not open serial port {port}: {e}")

# ---- Variables for baseline tracking ----
start_time = time.time()
baseline_window = [3, 13]
baseline_values = {"lower": [], "mid": [], "upper": []}
baseline_done = False

def read_serial():
    global sensor_data, baseline_done
    if not ser:
        print("⚠️ Serial not available.")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="ignore").strip()
                parts = line.split(",")
                if len(parts) == 4 and all(p.isdigit() for p in parts):
                    seat, lower, mid, upper = map(int, parts)
                    elapsed = time.time() - start_time
                    sensor_data["seat"] = seat
                    sensor_data["lower"] = lower
                    sensor_data["mid"] = mid
                    sensor_data["upper"] = upper
                    sensor_data["time"] = round(elapsed, 2)

                    # Detect if sitting
                    sensor_data["sitting"] = seat > 50  # adjust threshold

                    # Record baseline during [3, 13] seconds
                    if 3 <= elapsed <= 13 and sensor_data["sitting"]:
                        baseline_values["lower"].append(lower)
                        baseline_values["mid"].append(mid)
                        baseline_values["upper"].append(upper)

                    # Compute baseline averages once
                    if elapsed > 13 and not baseline_done and len(baseline_values["lower"]) > 0:
                        sensor_data["baseline"]["lower"] = sum(baseline_values["lower"]) / len(baseline_values["lower"])
                        sensor_data["baseline"]["mid"] = sum(baseline_values["mid"]) / len(baseline_values["mid"])
                        sensor_data["baseline"]["upper"] = sum(baseline_values["upper"]) / len(baseline_values["upper"])
                        baseline_done = True
                        print("✅ Baselines computed:", sensor_data["baseline"])

                    # Compute fill ratios
                    if baseline_done:
                        for key in ["lower", "mid", "upper"]:
                            base = sensor_data["baseline"][key]
                            val = sensor_data[key]
                            ratio = min(val / base, 1.0) if base else 0
                            sensor_data["fill"][key] = round(ratio * 100, 1)
        except Exception as e:
            print("Serial read error:", e)
        time.sleep(0.1)

if ser:
    t = threading.Thread(target=read_serial, daemon=True)
    t.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    return jsonify(sensor_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
