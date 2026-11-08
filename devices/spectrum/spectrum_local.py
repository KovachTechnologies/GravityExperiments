# PyPortal Titano local light / spectrum intensity logging
# Reads the onboard ambient light sensor (and optional STEMMA analog pins)
# and writes high-precision measurements to a CSV file on the CircuitPython
# filesystem.
#
# The primary signal is the light sensor on board.LIGHT (16-bit raw 0-65535).
# This is useful for monitoring ambient or laser-spot intensity over time.
# Optional D3/D4 analog inputs can be used for external sensors.
# MCU die temperature is also logged for reference.

import time
import board
import analogio
import microcontroller

# ---------- Configuration ----------
LOG_INTERVAL_MS = 100         # target time between log lines (ms)
LOG_FILE = "/spectrum_local.csv"  # root of CIRCUITPY drive (or remount SD here)
N_SAMPLES = 4                 # ADC readings averaged per logged sample
VOLTAGE_REF = 3.3             # nominal analog reference (V)

# ---------- Hardware setup ----------
light = analogio.AnalogIn(board.LIGHT)

# Optional external analogs on the D3 / D4 STEMMA ports.
# Set to None if not used (script will log nan).
try:
    d3 = analogio.AnalogIn(board.D3)
except Exception:
    d3 = None
try:
    d4 = analogio.AnalogIn(board.D4)
except Exception:
    d4 = None

# ---------- Helpers ----------
def read_avg(pin, n):
    """Average n raw AnalogIn readings. Returns None if pin is None."""
    if pin is None:
        return None
    total = 0
    for _ in range(n):
        total += pin.value
    return total / n

def raw_to_volts(raw):
    """Convert 16-bit raw ADC count to volts."""
    if raw is None:
        return None
    return (raw * VOLTAGE_REF) / 65536.0

# ---------- Log file ----------
start = time.monotonic()
log = open(LOG_FILE, "w")
header = ("t_ms,light_raw,light_v,"
          "d3_raw,d3_v,d4_raw,d4_v,"
          "cpu_temp_c,n_samples")
log.write(header + "\n")
log.flush()

def write_line(line):
    """Write one telemetry line to the local file."""
    log.write(line + "\n")
    # Flush occasionally so data survives an unexpected reset
    if int(time.monotonic() * 1000) % 500 < 50:
        log.flush()

print("Logging to", LOG_FILE)
print("Header:", header)
print("Light sensor ready. Optional D3/D4:",
      "yes" if d3 else "no", "/",
      "yes" if d4 else "no")

# ---------- Main loop ----------
while True:
    loop_start = time.monotonic()

    light_raw = read_avg(light, N_SAMPLES)
    d3_raw = read_avg(d3, N_SAMPLES)
    d4_raw = read_avg(d4, N_SAMPLES)

    light_v = raw_to_volts(light_raw)
    d3_v = raw_to_volts(d3_raw)
    d4_v = raw_to_volts(d4_raw)

    cpu_temp = microcontroller.cpu.temperature

    t_ms = int((time.monotonic() - start) * 1000)

    # High precision formatting
    def fmt(v, decimals=6, is_raw=False):
        if v is None:
            return "nan"
        if is_raw:
            return f"{v:.2f}"
        return f"{v:.{decimals}f}"

    parts = [
        str(t_ms),
        fmt(light_raw, is_raw=True),
        fmt(light_v, 6),
        fmt(d3_raw, is_raw=True),
        fmt(d3_v, 6),
        fmt(d4_raw, is_raw=True),
        fmt(d4_v, 6),
        f"{cpu_temp:.4f}",
        str(N_SAMPLES),
    ]
    write_line(",".join(parts))

    # Pace the loop
    elapsed_ms = (time.monotonic() - loop_start) * 1000
    sleep_ms = LOG_INTERVAL_MS - elapsed_ms
    if sleep_ms > 0:
        time.sleep(sleep_ms / 1000.0)
