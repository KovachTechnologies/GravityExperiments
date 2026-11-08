#!/usr/bin/env python3
"""Host-side reader for OpenMV camera telemetry.

Listens on a serial port for CSV lines from camera.py and logs them to a
timestamped file while printing to stdout.
"""

import csv
import sys
from datetime import datetime

try:
    import serial
except ImportError:
    print("Missing dependency: pyserial.  Install with:  pip install pyserial", file=sys.stderr)
    sys.exit(1)

# ---------- Configuration ----------
PORT = "COM3"          # Windows: COM3, COM4, ...
                       # Linux:   /dev/ttyACM0  (USB VCP) or /dev/ttyUSB0 (USB-UART adapter)
                       # macOS:   /dev/tty.usbmodem... or /dev/cu.usbmodem...
BAUD = 115200
TIMEOUT = 1.0          # seconds

def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"beam_telemetry_{stamp}.csv"

    print(f"Opening {PORT} at {BAUD} baud ...")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=TIMEOUT)
    except serial.SerialException as e:
        print(f"Failed to open serial port: {e}", file=sys.stderr)
        print("Check the port name, cable, and that the OpenMV is powered and running.", file=sys.stderr)
        sys.exit(1)

    print(f"Logging to {out_path}")
    print("Press Ctrl-C to stop.\n")

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        header_written = False

        try:
            while True:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Skip or capture the header that camera.py may emit
                if line.startswith("t_ms"):
                    if not header_written:
                        writer.writerow(line.split(","))
                        header_written = True
                    continue

                parts = line.split(",")
                if len(parts) < 11:
                    print(f"[skip] {line}")
                    continue

                writer.writerow(parts)
                f.flush()
                print(line)
        except KeyboardInterrupt:
            print("\nStopped by user.")
        finally:
            ser.close()
            print(f"Closed {PORT}. Data saved to {out_path}")

if __name__ == "__main__":
    main()
