#!/usr/bin/env python3
"""Multi-device USB serial aggregator for Raspberry Pi.

Discovers OpenMV camera, OpenScale-IoT, and PyPortal Titano devices by
enumerating serial ports (pyserial list_ports) and confirming with a
READY self-identification handshake. Sends a common START command, then
records all incoming telemetry as JSON Lines with host receipt timestamps
and device IDs. On clean exit (KeyboardInterrupt) sends STOP to each device.
"""

import json
import sys
import time
from datetime import datetime, timezone

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Missing dependency: pyserial.  Install with:  pip install pyserial", file=sys.stderr)
    sys.exit(1)

# ---------- Configuration ----------
BAUD = 115200
TIMEOUT = 0.1                 # non-blocking-ish read timeout (seconds)
DISCOVERY_TIMEOUT = 3.0       # seconds to wait for READY lines per port
PROBE_INTERVAL = 0.5          # how often to re-check during discovery
START_TOKEN = "START"
STOP_TOKEN = "STOP"
READY_PREFIX = "READY:"       # devices emit "READY:camera", "READY:scale", etc.

# Known USB VID:PID pairs (decimal). Used as a first filter; handshake is authoritative.
# OpenMV Cam (common): 0x1209:0xABD1
# Adafruit CircuitPython boards (PyPortal family): 0x239A:*
# ESP32 / USB-UART bridges vary; handshake covers them.
KNOWN_VIDS = {
    0x1209,   # OpenMV / pid.codes
    0x239A,   # Adafruit
    0x10C4,   # Silicon Labs CP210x (common on ESP32 boards)
    0x1A86,   # QinHeng CH340 (common on ESP32 boards)
    0x303A,   # Espressif native USB
}

EXPECTED_DEVICES = {"camera", "scale", "spectrum"}

# ---------- Helpers ----------
def host_timestamp():
    """High-resolution host timestamp (Unix seconds with fractional part)."""
    return time.time()

def iso_now():
    """ISO-8601 timestamp in UTC for filenames and logs."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def list_candidate_ports():
    """Return serial ports that look like our devices (by VID or by being ACM/USB)."""
    candidates = []
    for p in serial.tools.list_ports.comports():
        # Prefer ports with a known VID; also accept any ttyACM/ttyUSB on Linux
        vid_ok = p.vid in KNOWN_VIDS if p.vid is not None else False
        name_ok = any(x in (p.device or "").lower() for x in ("ttyacm", "ttyusb", "usbmodem", "usbserial"))
        if vid_ok or name_ok:
            candidates.append(p)
    return candidates

def probe_port(port_info, timeout=DISCOVERY_TIMEOUT):
    """
    Open port briefly, look for a READY:device line.
    Returns the device name (str) or None.
    """
    try:
        ser = serial.Serial(port_info.device, BAUD, timeout=TIMEOUT)
    except (serial.SerialException, OSError) as e:
        print(f"  [skip] {port_info.device}: {e}")
        return None

    device = None
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            raw = ser.readline()
            if not raw:
                time.sleep(PROBE_INTERVAL)
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            if line.startswith(READY_PREFIX):
                device = line[len(READY_PREFIX):].strip().lower()
                if device in EXPECTED_DEVICES:
                    print(f"  [found] {port_info.device} → {device}")
                    break
                else:
                    print(f"  [unknown device] {port_info.device}: {line}")
    finally:
        ser.close()
    return device

def discover_devices():
    """Scan ports and return {device_name: serial.Serial} for those that respond."""
    print("Enumerating USB serial ports ...")
    candidates = list_candidate_ports()
    if not candidates:
        print("No candidate serial ports found.")
        return {}

    print(f"Found {len(candidates)} candidate port(s). Probing for READY handshake ...")
    found = {}
    for p in candidates:
        print(f"  probing {p.device} (VID={p.vid:#06x} PID={p.pid:#06x})" if p.vid else f"  probing {p.device}")
        device = probe_port(p)
        if device and device not in found:
            # Re-open for the long-running session
            try:
                ser = serial.Serial(p.device, BAUD, timeout=TIMEOUT)
                found[device] = ser
            except (serial.SerialException, OSError) as e:
                print(f"  [reopen failed] {p.device}: {e}")
    return found

def send_command(ser, token):
    """Send a command token followed by newline."""
    try:
        ser.write((token + "\n").encode("utf-8"))
        ser.flush()
    except (serial.SerialException, OSError):
        pass

def parse_line(line, device):
    """
    Turn a raw line into a dict. Prefer JSON; otherwise wrap as raw.
    Always inject host timestamp and device id.
    """
    obj = {
        "host_ts": host_timestamp(),
        "device": device,
    }
    line = line.strip()
    if not line:
        return None
    if line.startswith("{"):
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                obj.update(payload)
                return obj
        except json.JSONDecodeError:
            pass
    # Fallback: keep the raw line (useful while devices still emit CSV)
    obj["raw"] = line
    return obj

# ---------- Main ----------
def main():
    stamp = iso_now()
    out_path = f"aggregated_{stamp}.jsonl"
    print(f"Aggregator starting. Output → {out_path}")
    print("Press Ctrl-C to stop and send STOP to devices.\n")

    devices = discover_devices()
    if not devices:
        print("No devices responded with READY. Exiting.")
        sys.exit(1)

    missing = EXPECTED_DEVICES - set(devices.keys())
    if missing:
        print(f"Warning: missing devices: {', '.join(sorted(missing))}")
    print(f"Ready devices: {', '.join(sorted(devices.keys()))}")

    # Send START to all discovered devices
    print("Sending START ...")
    for name, ser in devices.items():
        send_command(ser, START_TOKEN)
        print(f"  START → {name}")

    print("Listening ...\n")

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            while True:
                for name, ser in list(devices.items()):
                    try:
                        raw = ser.readline()
                    except (serial.SerialException, OSError) as e:
                        print(f"[{name}] serial error: {e}")
                        continue
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line or line.startswith(READY_PREFIX):
                        continue  # ignore late READY lines
                    record = parse_line(line, name)
                    if record is None:
                        continue
                    f.write(json.dumps(record, separators=(",", ":")) + "\n")
                    f.flush()
                    # Light console feedback (truncate long lines)
                    preview = line if len(line) < 120 else line[:117] + "..."
                    print(f"[{name}] {preview}")
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Sending STOP ...")
    finally:
        for name, ser in devices.items():
            send_command(ser, STOP_TOKEN)
            print(f"  STOP → {name}")
            try:
                ser.close()
            except Exception:
                pass
        print(f"Closed all ports. Data saved to {out_path}")

if __name__ == "__main__":
    main()
