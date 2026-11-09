# PyPortal Titano spectrum / light intensity streaming (aggregator mode)
# Waits for a START command from the host aggregator, then streams
# high-precision light (and optional analog) measurements as JSON lines
# over USB serial. Implements the READY / START / STOP handshake used
# by aggregator.py.
#
# Companion local-only logger: spectrum_local.py (does not change).
# Primary signal is the onboard light sensor (board.LIGHT).

import time
import board
import analogio
import microcontroller
import json
import sys
import supervisor

# ---------- Configuration ----------
LOG_INTERVAL_MS = 100         # target time between samples (ms)
N_SAMPLES = 4                 # ADC readings averaged per sample
VOLTAGE_REF = 3.3             # nominal analog reference (V)
DEVICE_NAME = "spectrum"
READY_INTERVAL = 1.0          # seconds between READY lines while waiting
BAUD_NOTE = 115200            # host aggregator uses this baud (USB CDC ignores it)

# ---------- Hardware setup ----------
light = analogio.AnalogIn(board.LIGHT)

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

def check_command():
    """
    Non-blocking read of one line from the USB serial console.
    Returns the stripped line or None.
    """
    if not supervisor.runtime.serial_bytes_available:
        return None
    try:
        # input() / readline() consume a full line (triggered by \r or \n)
        line = sys.stdin.readline()
        if line:
            return line.strip()
    except Exception:
        pass
    return None

def emit_json(obj):
    """Send one JSON line over USB serial (print goes to the console CDC)."""
    print(json.dumps(obj, separators=(",", ":")))

# ---------- Main state machine ----------
print(f"READY:{DEVICE_NAME}")  # immediate first READY for fast discovery

while True:
    # ---------- Waiting for START ----------
    started = False
    last_ready = time.monotonic()
    while not started:
        cmd = check_command()
        if cmd == "START":
            started = True
            break
        elif cmd == "STOP":
            # ignore STOP while already idle
            pass
        # Periodic READY heartbeat
        now = time.monotonic()
        if now - last_ready >= READY_INTERVAL:
            print(f"READY:{DEVICE_NAME}")
            last_ready = now
        time.sleep(0.05)

    # ---------- Running (streaming) ----------
    start = time.monotonic()
    running = True
    while running:
        loop_start = time.monotonic()

        # Check for STOP (or another START which restarts the timer)
        cmd = check_command()
        if cmd == "STOP":
            running = False
            break
        elif cmd == "START":
            start = time.monotonic()  # reset device timer

        light_raw = read_avg(light, N_SAMPLES)
        d3_raw = read_avg(d3, N_SAMPLES)
        d4_raw = read_avg(d4, N_SAMPLES)

        light_v = raw_to_volts(light_raw)
        d3_v = raw_to_volts(d3_raw)
        d4_v = raw_to_volts(d4_raw)

        cpu_temp = microcontroller.cpu.temperature
        t_ms = int((time.monotonic() - start) * 1000)

        record = {
            "t_ms": t_ms,
            "light_raw": None if light_raw is None else round(light_raw, 2),
            "light_v": None if light_v is None else round(light_v, 6),
            "d3_raw": None if d3_raw is None else round(d3_raw, 2),
            "d3_v": None if d3_v is None else round(d3_v, 6),
            "d4_raw": None if d4_raw is None else round(d4_raw, 2),
            "d4_v": None if d4_v is None else round(d4_v, 6),
            "cpu_temp_c": round(cpu_temp, 4),
            "n_samples": N_SAMPLES,
        }
        emit_json(record)

        # Pace the loop
        elapsed_ms = (time.monotonic() - loop_start) * 1000
        sleep_ms = LOG_INTERVAL_MS - elapsed_ms
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)

    # After STOP, fall back to the outer loop and resume READY heartbeats
    print(f"READY:{DEVICE_NAME}")
