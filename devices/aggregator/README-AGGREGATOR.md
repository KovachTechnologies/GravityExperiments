# Multi-Device USB Serial Aggregator

This note covers the host-side aggregator that runs on a Raspberry Pi (or any Linux host) and collects telemetry from three USB-connected devices:

- OpenMV Cam (camera / beam COM)
- SparkFun OpenScale-IoT (scale / weight)
- Adafruit PyPortal Titano (spectrum / light intensity)

The aggregator discovers the devices automatically, synchronizes their start with a common `START` command, records all data as JSON Lines with host receipt timestamps, and cleanly stops them with `STOP` on exit.

Companion device scripts (streaming versions that wait for `START` and emit `READY:` lines) will be added separately. Local-only loggers (`*_local.py`) remain available for offline runs.

## 1. Prerequisites

### Hardware
- Raspberry Pi (or other Linux host) with enough USB ports (or a powered hub).
- The three boards listed above, each running a script that:
  - sits idle waiting for a `START` command,
  - periodically emits a `READY:<device>` line while waiting,
  - begins streaming telemetry after receiving `START`,
  - stops cleanly on `STOP`.
- USB cables that support data.

### Software
- Python 3.8+ on the host.
- `pyserial` (see Packages below).
- User must have permission to open serial ports (on Raspberry Pi OS, membership in the `dialout` group is normally sufficient).

### Firmware
Each board must be running its streaming script (not the pure local-logger versions) before the aggregator is launched.

## 2. Packages needed

### On the host (Raspberry Pi)
```bash
pip install pyserial
```
That is the only external dependency.

## 3. Engineering details

### Port discovery
The aggregator does **not** require hard-coded port names (`/dev/ttyACM0`, etc.). On startup it:

1. Enumerates all serial ports via `serial.tools.list_ports`.
2. Filters to likely candidates (known USB VID/PID values or names containing `ttyACM`/`ttyUSB`).
3. Opens each candidate briefly and listens for a self-identification line of the form:
   ```
   READY:camera
   READY:scale
   READY:spectrum
   ```
4. Builds a map of device name → open serial port for every board that responds.

This combination of hardware IDs and an explicit handshake tolerates plug-order changes and ignores unrelated serial devices.

### Protocol
- **READY:** emitted by a device while it is waiting (before `START`).
- **START:** sent by the aggregator to every discovered device. Devices reset their internal timers and begin sampling/streaming.
- **STOP:** sent by the aggregator on clean exit (KeyboardInterrupt). Devices halt their measurement loops.
- **Telemetry:** each device streams one line per sample. Preferred format is a JSON object; the aggregator also accepts raw/CSV lines and wraps them. Every recorded record receives:
  - `host_ts` — high-resolution Unix timestamp of receipt on the aggregator
  - `device` — `"camera"`, `"scale"`, or `"spectrum"`

### Output
A single JSON Lines file named `aggregated_<UTC-timestamp>.jsonl`. Each line is a self-contained JSON object, so fields can be added or changed later without breaking older logs.

Example line:
```json
{"host_ts":1731091234.567,"device":"scale","t_ms":1234,"weight_g":12.345678}
```

### Timing and synchronization
Because `START` is issued by the same process that stamps every arrival with `host_ts`, the three streams share a common origin to within serial latency (typically a few milliseconds). The host timestamps remain the authoritative reference for later alignment even if device-side clocks differ.

## 4. Running the code

1. Power on all three devices and confirm their streaming scripts are running (they should be emitting occasional `READY:` lines).
2. On the Raspberry Pi:
   ```bash
   python3 aggregator.py
   ```
3. The script prints the discovery results, sends `START`, then streams incoming data to the console and to the JSONL file.
4. Press Ctrl-C to stop. The aggregator sends `STOP` to every device, closes the ports, and exits.

If one or more devices are missing, a warning is printed and the aggregator continues with the devices that responded.

## 5. Relationship to other files

| File                  | Role                                      |
|-----------------------|-------------------------------------------|
| `aggregator.py`       | This multi-device listener (Raspberry Pi) |
| `camera.py`           | OpenMV streaming script (to be updated)   |
| `scale.py`            | OpenScale streaming script (future)       |
| `spectrum.py`         | PyPortal streaming script (future)        |
| `*_local.py`          | Offline CSV loggers (current fallback)    |
| `server.py`           | Legacy single-device camera listener      |

## 6. Notes and future work

- Device scripts must be updated to implement the `READY` / `START` / `STOP` behavior and to emit JSON (or structured) telemetry. Until then the aggregator will wrap raw lines.
- Sample rates differ across devices; the JSONL stream preserves arrival order and host timestamps so downstream analysis can resample or interpolate as needed.
- The aggregator is intentionally single-process and single-threaded for simplicity. At the data rates of these sensors this is more than adequate.
