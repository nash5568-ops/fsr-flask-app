from flask import Flask, render_template, jsonify
import time
import threading
import os

# Only import serial when running locally
try:
    import serial
except ImportError:
    serial = None

app = Flask(__name__)

# ---- Arduino Setup ----
port = 'COM4'    # Change this if your Arduino uses another port
baud = 9600

ser = None
fsr_data = []  # store latest readings

# Only try to connect if running locally and pyserial is available
if serial and os.environ.get("RENDER") != "true":
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to {port}")
    except Exception as e:
        print(f"⚠️ Could not open serial port {port}: {e}")


# ---- Background thread to read from Arduino ----
def read_serial():
    global fsr_data
    if not ser:
        print("⚠️ Serial port not available, skipping read loop.")
        return

    start_time = time.time()
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors='ignore').strip()
                if line.isdigit():
                    elapsed = round(time.time() - start_time, 3)
                    value = int(line)
                    fsr_data.append({"time": elapsed, "value": value})
                    fsr_data = fsr_data[-200:]  # keep last 200 points
        except Exception as e:
            print(f"Serial read error: {e}")
        time.sleep(0.05)  # small delay


# Start background serial thread (only locally)
if ser:
    thread = threading.Thread(target=read_serial)
    thread.daemon = True
    thread.start()


# ---- Flask Routes ----
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    return jsonify(fsr_data)

@app.route('/reset')
def reset_data():
    global fsr_data
    fsr_data = []  # clear data
    print("🔄 Data reset")
    return "Data reset!", 200


# ---- Run App ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
