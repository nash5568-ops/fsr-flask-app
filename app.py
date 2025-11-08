from flask import Flask, render_template, jsonify
import serial
import time
import threading

app = Flask(__name__)

# ---- Arduino Setup ----
port = 'COM4'    # 🔹 Change this if your Arduino uses another port
baud = 9600

# Try to connect safely
try:
    ser = serial.Serial(port, baud, timeout=1)
    time.sleep(2)
    print(f"✅ Connected to {port}")
except Exception as e:
    ser = None
    print(f"⚠️ Could not open serial port {port}: {e}")

fsr_data = []  # store latest readings


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
        time.sleep(0.05)  # slight delay to prevent CPU overload


# Start the thread safely
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


if __name__ == '__main__':
    # Run WITHOUT auto-reload (prevents COM port locking issues)
    app.run(host='10.200.193.152', port=5000, debug=False)
