from flask import Flask, render_template, jsonify
import time, threading, os

try:
    import serial
except ImportError:
    serial = None

app = Flask(__name__)

# ---- Serial setup ----
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
    "deviation": {"lower": 0, "mid": 0, "upper": 0},
    "sitting": False
}

if serial:
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to {port}")
    except Exception as e:
        print(f"⚠️ Could not open serial port {port}: {e}")
else:
    print("⚠️ pyserial not available — running in simulation mode.")

# ---- Baseline tracking ----
start_time = time.time()
baseline_window = (3, 13)
baseline_values = {"lower": [], "mid": [], "upper": []}
baseline_done = False


def read_serial():
    """Continuously read comma-separated sensor data from Arduino"""
    global sensor_data, baseline_done

    if not ser:
        print("⚠️ Serial not available. Skipping read loop.")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="ignore").strip()
                parts = line.split(",")
                if len(parts) == 4 and all(p.strip().isdigit() for p in parts):
                    seat, lower, mid, upper = map(int, parts)
                    elapsed = time.time() - start_time

                    sensor_data.update({
                        "seat": seat,
                        "lower": lower,
                        "mid": mid,
                        "upper": upper,
                        "time": round(elapsed, 2),
                        "sitting": seat > 50  # adjust threshold
                    })

                    # Record baseline if sitting during calibration window
                    if 3 <= elapsed <= 13 and sensor_data["sitting"]:
                        for k, v in zip(["lower", "mid", "upper"], [lower, mid, upper]):
                            baseline_values[k].append(v)

                    # Compute baseline once
                    if elapsed > 13 and not baseline_done and baseline_values["lower"]:
                        for k in ["lower", "mid", "upper"]:
                            sensor_data["baseline"][k] = sum(baseline_values[k]) / len(baseline_values[k])
                        baseline_done = True
                        print("✅ Baselines computed:", sensor_data["baseline"])

                    # Compute deviation from baseline (-100 to +100)
                    if baseline_done:
                        for k in ["lower", "mid", "upper"]:
                            base = sensor_data["baseline"][k]
                            val = sensor_data[k]
                            if base:
                                deviation = ((val - base) / base) * 100  # percent difference
                                deviation = max(min(deviation, 100), -100)  # clamp to [-100, 100]
                                sensor_data["deviation"][k] = round(deviation, 1)

        except Exception as e:
            print("Serial read error:", e)
            time.sleep(1)
        time.sleep(0.1)


# ---- Background thread ----
if ser:
    thread = threading.Thread(target=read_serial, daemon=True)
    thread.start()


# ---- Flask routes ----
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    return jsonify(sensor_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
