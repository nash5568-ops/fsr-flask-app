from flask import Flask, render_template, jsonify
import time, threading

try:
    import serial
except ImportError:
    serial = None

app = Flask(__name__)

# ---------------------------------------------------------
# Global state
# ---------------------------------------------------------
sensor_data = {
    "seat": 0,
    "lower": 0,
    "mid": 0,
    "upper": 0,
    "time": 0,
    "baseline": {"lower": None, "mid": None, "upper": None},
    "deviation": {"lower": 0, "mid": 0, "upper": 0},
    "sitting": False,
    "connected": False
}

# calibration control
baseline_values = {"lower": [], "mid": [], "upper": []}
baseline_done = False
calibrate_requested = False

# ---------------------------------------------------------
# Serial setup
# ---------------------------------------------------------
port = "COM4"
baud = 9600
ser = None

if serial:
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)
        print(f" Connected to {port}")
        sensor_data["connected"] = True
    except Exception as e:
        print(f"⚠️ Could not open serial port {port}: {e}")
        sensor_data["connected"] = False
else:
    print("⚠️ pyserial not available — simulation mode.")
    sensor_data["connected"] = False

# ---------------------------------------------------------
# Serial reader thread
# ---------------------------------------------------------
def read_serial():
    global baseline_done, baseline_values, calibrate_requested

    if not ser:
        print(" Serial not available. No reading.")
        return

    while True:
        try:
            # read a single line
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="ignore").strip()
                parts = line.split(",")

                if len(parts) == 4 and all(p.strip().lstrip('-').isdigit() for p in parts):
                    seat, lower, mid, upper = map(int, parts)
                    # update readings
                    sensor_data.update({
                        "seat": seat,
                        "lower": lower,
                        "mid": mid,
                        "upper": upper,
                        "time": round(time.time(), 2),
                        "sitting": seat > 50
                    })

                    # If a manual calibrate was requested, collect a burst of samples
                    if calibrate_requested:
                        # collect N valid samples into baseline_values
                        N = 50
                        # reset temporary lists
                        baseline_values = {"lower": [], "mid": [], "upper": []}
                        collected = 0
                        print("🔁 Calibration requested — collecting samples...")
                        while collected < N:
                            # try to read next valid line
                            if ser.in_waiting > 0:
                                ln = ser.readline().decode(errors="ignore").strip()
                                vals = ln.split(",")
                                if len(vals) == 4 and all(v.strip().lstrip('-').isdigit() for v in vals):
                                    _, l, m, u = map(int, vals)
                                    baseline_values["lower"].append(l)
                                    baseline_values["mid"].append(m)
                                    baseline_values["upper"].append(u)
                                    collected += 1
                            else:
                                time.sleep(0.05)
                        # compute baseline averages
                        for key in ["lower", "mid", "upper"]:
                            sensor_data["baseline"][key] = sum(baseline_values[key]) / len(baseline_values[key])
                        baseline_done = True
                        calibrate_requested = False
                        print("✅ Manual calibration complete:", sensor_data["baseline"])

                    # If baseline already done, compute deviation
                    if baseline_done:
                        for key in ["lower", "mid", "upper"]:
                            base = sensor_data["baseline"][key]
                            val = sensor_data[key]
                            if base and base != 0:
                                deviation = ((val - base) / base) * 100
                                deviation = max(min(deviation, 100), -100)
                                sensor_data["deviation"][key] = round(deviation, 1)
                            else:
                                sensor_data["deviation"][key] = 0

        except Exception as e:
            print("Serial read error:", e)
            sensor_data["connected"] = False
            time.sleep(0.5)

        time.sleep(0.02)  # small pause to avoid busy loop

# start thread
if ser:
    thread = threading.Thread(target=read_serial, daemon=True)
    thread.start()

# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/data")
def data():
    return jsonify(sensor_data)


@app.route("/reset_calibration")
def reset_calibration():
    global calibrate_requested, baseline_done, baseline_values
    calibrate_requested = True
    baseline_done = False
    baseline_values = {"lower": [], "mid": [], "upper": []}
    print("🔄 Calibration endpoint called — will recalibrate on next sample burst.")
    return jsonify({"status": "calibration started"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
