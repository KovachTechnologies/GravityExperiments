# OpenScale-IoT local weight logging
# Reads the onboard HX711 load-cell ADC and writes high-precision
# weight measurements to a CSV file on the ESP32 filesystem.
#
# On startup the script performs a tare (zero) of the scale.
# Calibration factor must be set for your specific load cell.

import time
from machine import Pin, I2C

# ---------- Configuration ----------
DOUT_PIN = 25                 # HX711 DOUT (from OpenScale-IoT schematic)
SCK_PIN  = 26                 # HX711 PD_SCK
GAIN = 128                    # 128, 64 (ch A) or 32 (ch B)

# Calibration: grams per raw unit.  Determine once with a known weight
# after tare:  SCALE_FACTOR = known_grams / (raw - tare_offset)
# Leave as 1.0 to log raw-proportional values only.
SCALE_FACTOR = 1.0

TARE_SAMPLES = 15             # readings averaged for the startup zero
READ_SAMPLES = 3              # readings averaged per logged sample
LOG_INTERVAL_MS = 100         # target time between log lines (HX711 is 10 or 80 SPS)
LOG_FILE = "scale_local.csv"  # written to the ESP32 filesystem

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

# ---------- Log file ----------
start_ms = time.ticks_ms()
log = open(LOG_FILE, "w")
header = ("t_ms,weight_g,raw,tare_offset,scale_factor,temp_c,n_samples")
log.write(header + "\n")
log.flush()

def write_line(line):
    """Write one telemetry line to the local file."""
    log.write(line + "\n")
    # Flush occasionally so data survives an unexpected reset
    if time.ticks_ms() % 500 < 50:
        log.flush()

print("Logging to", LOG_FILE)
print("Header:", header)

# ---------- Main loop ----------
while True:
    loop_start = time.ticks_ms()

    try:
        raw = hx.read_average(READ_SAMPLES)
    except Exception as e:
        print("Read error:", e)
        time.sleep_ms(100)
        continue

    # weight = (raw - offset) / scale_factor
    # With SCALE_FACTOR=1.0 this is simply the zeroed raw value.
    weight_g = (raw - tare_offset) / SCALE_FACTOR

    temp_c = read_temp_c(i2c) if i2c else None
    temp_str = f"{temp_c:.4f}" if temp_c is not None else "nan"

    t_ms = time.ticks_diff(time.ticks_ms(), start_ms)

    # High precision: raw is integer, weight printed with many decimals
    parts = [
        str(t_ms),
        f"{weight_g:.8f}",
        f"{raw:.2f}",
        f"{tare_offset:.2f}",
        f"{SCALE_FACTOR:.8f}",
        temp_str,
        str(READ_SAMPLES),
    ]
    write_line(",".join(parts))

    # Pace the loop
    elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
    sleep_ms = LOG_INTERVAL_MS - elapsed
    if sleep_ms > 0:
        time.sleep_ms(sleep_ms)
