# OpenScale-IoT weight streaming (aggregator mode)
# Waits for a START command from the host aggregator, then streams
# high-precision weight measurements as JSON lines over USB serial.
# Implements the READY / START / STOP handshake used by aggregator.py.
#
# Companion local-only logger: scale_local.py (does not change).
# On startup the script tares (zeroes) the scale.

import time
import json
import sys
import select
from machine import Pin, I2C

# ---------- Configuration ----------
DOUT_PIN = 25                 # HX711 DOUT (from OpenScale-IoT schematic)
SCK_PIN  = 26                 # HX711 PD_SCK
GAIN = 128                    # 128, 64 (ch A) or 32 (ch B)

# Calibration: grams per raw unit.  Determine once with a known weight
# after tare:  SCALE_FACTOR = known_grams / (raw - tare_offset)
# Leave as 1.0 to stream raw-proportional values only.
SCALE_FACTOR = 1.0

TARE_SAMPLES = 15             # readings averaged for the startup zero
READ_SAMPLES = 3              # readings averaged per streamed sample
LOG_INTERVAL_MS = 100         # target time between samples (HX711 is 10 or 80 SPS)

DEVICE_NAME = "scale"
READY_INTERVAL = 1.0          # seconds between READY lines while waiting
BAUD_NOTE = 115200            # host aggregator uses this baud (USB CDC ignores it)

# Optional onboard TMP102 (address 0x49).  Set I2C pins if you know them;
# leave None to skip temperature.
I2C_SDA = None                # e.g. 21
I2C_SCL = None                # e.g. 22
TMP102_ADDR = 0x49

# ---------- Minimal HX711 driver (self-contained) ----------
class HX711:
    def __init__(self, dout, sck, gain=128):
        self.dout = Pin(dout, Pin.IN)
        self.sck  = Pin(sck, Pin.OUT, value=0)
        self.set_gain(gain)

    def set_gain(self, gain):
        if gain == 128:
            self._gain_pulses = 1
        elif gain == 64:
            self._gain_pulses = 3
        elif gain == 32:
            self._gain_pulses = 2
        else:
            raise ValueError("gain must be 128, 64 or 32")
        # Dummy read to set the gain for the next conversion
        self.read_raw()

    def is_ready(self):
        return self.dout.value() == 0

    def read_raw(self):
        """Return a single signed 24-bit reading.  Blocks until ready."""
        # Wait for data ready (DOUT goes low)
        timeout = time.ticks_add(time.ticks_ms(), 1000)
        while not self.is_ready():
            if time.ticks_diff(timeout, time.ticks_ms()) < 0:
                raise RuntimeError("HX711 timeout")
        # Clock out 24 data bits, MSB first
        value = 0
        for _ in range(24):
            self.sck.value(1)
            value = (value << 1) | self.dout.value()
            self.sck.value(0)
        # Extra pulses set channel/gain for next conversion
        for _ in range(self._gain_pulses):
            self.sck.value(1)
            self.sck.value(0)
        # Convert from two's complement
        if value & 0x800000:
            value -= 0x1000000
        return value

    def read_average(self, n=1):
        if n < 1:
            n = 1
        total = 0
        for _ in range(n):
            total += self.read_raw()
        return total / n

# ---------- Optional temperature ----------
def read_temp_c(i2c):
    """Read TMP102 temperature in Celsius.  Returns None on failure."""
    try:
        # Temperature register is 0x00, 2 bytes, 12-bit left-aligned
        raw = i2c.readfrom_mem(TMP102_ADDR, 0x00, 2)
        val = (raw[0] << 4) | (raw[1] >> 4)
        if val & 0x800:
            val -= 0x1000
        return val * 0.0625
    except Exception:
        return None

# ---------- Serial helpers (USB CDC) ----------
def check_command():
    """
    Non-blocking read of one line from the USB serial console.
    Returns the stripped line or None.
    """
    # select works on recent MicroPython ESP32 builds for sys.stdin
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
    except Exception:
        ready = []
    if not ready:
        return None
    try:
        line = sys.stdin.readline()
        if line:
            return line.strip()
    except Exception:
        pass
    return None

def emit_json(obj):
    """Send one JSON line over USB serial (print goes to the console CDC)."""
    print(json.dumps(obj, separators=(",", ":")))

# ---------- Hardware setup ----------
hx = HX711(DOUT_PIN, SCK_PIN, GAIN)

# Give the HX711 a moment to stabilize after power-up / gain set
time.sleep_ms(500)

# Startup tare (zero).  Assumes the scale is unloaded (or at the
# desired zero condition) when the script starts.
print("Taring scale...")
tare_offset = hx.read_average(TARE_SAMPLES)
print("Tare offset:", tare_offset)

i2c = None
if I2C_SDA is not None and I2C_SCL is not None:
    try:
        i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400000)
    except Exception as e:
        print("I2C init failed:", e)
        i2c = None

# ---------- Main state machine ----------
print(f"READY:{DEVICE_NAME}")  # immediate first READY for fast discovery

while True:
    # ---------- Waiting for START ----------
    started = False
    last_ready = time.time()
    while not started:
        cmd = check_command()
        if cmd == "START":
            started = True
            break
        elif cmd == "STOP":
            # ignore STOP while already idle
            pass
        # Periodic READY heartbeat
        now = time.time()
        if now - last_ready >= READY_INTERVAL:
            print(f"READY:{DEVICE_NAME}")
            last_ready = now
        time.sleep_ms(50)

    # ---------- Running (streaming) ----------
    start_ms = time.ticks_ms()
    running = True
    while running:
        loop_start = time.ticks_ms()

        # Check for STOP (or another START which restarts the timer)
        cmd = check_command()
        if cmd == "STOP":
            running = False
            break
        elif cmd == "START":
            start_ms = time.ticks_ms()  # reset device timer

        try:
            raw = hx.read_average(READ_SAMPLES)
        except Exception as e:
            print(json.dumps({"error": str(e)}, separators=(",", ":")))
            time.sleep_ms(100)
            continue

        # weight = (raw - offset) / scale_factor
        # With SCALE_FACTOR=1.0 this is simply the zeroed raw value.
        weight_g = (raw - tare_offset) / SCALE_FACTOR

        temp_c = read_temp_c(i2c) if i2c else None
        t_ms = time.ticks_diff(time.ticks_ms(), start_ms)

        record = {
            "t_ms": t_ms,
            "weight_g": round(weight_g, 8),
            "raw": round(raw, 2),
            "tare_offset": round(tare_offset, 2),
            "scale_factor": SCALE_FACTOR,
            "temp_c": None if temp_c is None else round(temp_c, 4),
            "n_samples": READ_SAMPLES,
        }
        emit_json(record)

        # Pace the loop
        elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
        sleep_ms = LOG_INTERVAL_MS - elapsed
        if sleep_ms > 0:
            time.sleep_ms(sleep_ms)

    # After STOP, fall back to the outer loop and resume READY heartbeats
    print(f"READY:{DEVICE_NAME}")
