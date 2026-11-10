# Multi-Device Sensing Platform

Real-time multi-sensor data acquisition for laboratory experiments. This repository organizes the host-side aggregator and the three USB-connected measurement devices used to capture synchronized streams of:

- **Optical beam tracking** (OpenMV Cam) — laser-spot center-of-mass and multi-lobe geometry
- **Weight / force** (SparkFun OpenScale-IoT) — high-resolution load-cell measurements
- **Light / spectrum intensity** (Adafruit PyPortal Titano) — ambient light sensor and optional analog channels

All devices share a common handshake (`READY` / `START` / `STOP`) so the aggregator can discover them, start them together, and stamp every sample with a host receipt timestamp. Local-only CSV loggers are also provided for offline runs.

This setup supports the broader Computational Theory of Gravity (CTG) laboratory work; see the companion notes in the parent lab notebook for campaign-level protocol and results.

## Directory layout

```
.
├── aggregator/          # Host-side multi-device collector (Raspberry Pi)
│   ├── aggregator.py
│   └── README-AGGREGATOR.md
├── camera/              # OpenMV Cam beam tracker
│   ├── camera.py            # Streaming (aggregator) version
│   ├── camera_local.py      # Local CSV logger
│   ├── server.py            # Legacy single-device listener
│   ├── requirements.txt
│   └── README-CAMERA.md
├── scale/               # OpenScale-IoT weight logger
│   ├── scale.py             # Streaming (aggregator) version
│   ├── scale_local.py       # Local CSV logger
│   └── README-SCALE.md
├── spectrum/            # PyPortal Titano light/spectrum logger
│   ├── spectrum.py          # Streaming (aggregator) version
│   ├── spectrum_local.py    # Local CSV logger
│   └── README-SPECTRUM.md
└── README.md            # This file
```

## Prerequisites

### Hardware
- Raspberry Pi (or other Linux host) with sufficient USB ports (or a powered hub)
- OpenMV Cam (H7 / H7 Plus / RT1062 or later)
- SparkFun OpenScale-IoT with load cell
- Adafruit PyPortal Titano
- USB data cables for all boards

### Software
- Python 3.8+ on the host
- `pyserial` on the host (`pip install pyserial` or `pip install -r camera/requirements.txt`)
- Membership in the `dialout` group (or equivalent) so the host user can open serial ports
- Device firmware:
  - OpenMV: recent MicroPython firmware (via OpenMV IDE)
  - OpenScale-IoT: MicroPython for ESP32
  - PyPortal Titano: CircuitPython

Detailed hardware, pinouts, calibration, and firmware-flashing notes live in the per-device READMEs.

## Installation

1. Clone or copy this repository onto the Raspberry Pi (or host).
2. Install the only host dependency:
   ```bash
   pip install pyserial
   ```
   or
   ```bash
   pip install -r camera/requirements.txt
   ```
3. Flash the appropriate firmware on each board and upload the corresponding streaming script (`camera.py`, `scale.py`, `spectrum.py`).  
   - On OpenMV, use the OpenMV IDE or save the script as `main.py`.  
   - On the ESP32 (OpenScale) and PyPortal, use Thonny, mpremote, or the CIRCUITPY drive workflow.
4. Confirm each device enumerates as a serial port and is emitting occasional `READY:<device>` lines.

## Running the system

1. Power on and connect all three devices. Verify they are running their streaming scripts (they should emit `READY:camera`, `READY:scale`, and `READY:spectrum`).
2. On the host:
   ```bash
   cd aggregator
   python3 aggregator.py
   ```
3. The aggregator discovers the devices by the `READY:` handshake, sends a common `START`, and begins writing a timestamped JSON Lines file (`aggregated_<UTC-timestamp>.jsonl`) while also printing to the console.
4. Press Ctrl-C to stop. The aggregator sends `STOP` to every device, closes the ports, and exits cleanly.

If one or more devices are absent, a warning is printed and the aggregator continues with the devices that responded.

### Local-only mode
Each device also has a `*_local.py` script that writes CSV directly to the board’s filesystem (or microSD). Use these when no host is attached. See the individual READMEs for file names and copy-off procedures.

### Legacy single-device path
`camera/server.py` remains available for a simple host-side CSV logger that talks only to the camera. The preferred multi-device path is `aggregator.py`.

## Protocol overview

| Direction       | Token / format     | Meaning                                      |
|-----------------|--------------------|----------------------------------------------|
| Device → host   | `READY:<device>`   | Idle heartbeat / self-identification         |
| Host → device   | `START`            | Begin sampling; reset device timer           |
| Host → device   | `STOP`             | Halt sampling; return to READY state         |
| Device → host   | JSON line          | One telemetry record per sample              |

Every record written by the aggregator receives:
- `host_ts` — high-resolution Unix timestamp of receipt on the host
- `device` — `"camera"`, `"scale"`, or `"spectrum"`

Example aggregated line:
```json
{"host_ts":1731091234.567,"device":"scale","t_ms":1234,"weight_g":12.345678}
```

Sample rates differ across devices. The JSONL stream preserves arrival order and host timestamps so downstream analysis can resample or interpolate as needed.

## Component summaries

### Aggregator (`aggregator/`)
Host-side collector that dynamically discovers USB serial devices, synchronizes their start, and records all telemetry as JSON Lines. See `aggregator/README-AGGREGATOR.md`.

### Camera (`camera/`)
OpenMV Cam script that tracks up to three bright laser lobes (e.g., from conductive-tape refraction), computes per-lobe and overall center-of-mass, and streams JSON. Local CSV variant and legacy server are also included. See `camera/README-CAMERA.md`.

### Scale (`scale/`)
OpenScale-IoT (ESP32 + HX711) script that tares on startup and streams high-precision weight (and optional temperature). Local CSV variant included. See `scale/README-SCALE.md`.

### Spectrum (`spectrum/`)
PyPortal Titano CircuitPython script that logs ambient light intensity (and optional STEMMA analog channels) plus MCU temperature. Local CSV variant included. See `spectrum/README-SPECTRUM.md`.

## Output and analysis

The aggregator writes a single self-contained JSON Lines file. Each line is an independent JSON object, so fields can evolve without breaking older logs. Downstream analysis can:

- Align streams using the common `host_ts`
- Resample to a uniform time base
- Extract device-specific metrics (COM coordinates, weight, light counts, etc.)

Per-device local CSV files use a simpler tabular format documented in each README.

## Notes

- The aggregator is intentionally single-process and single-threaded; the data rates of these sensors make that more than adequate.
- Baud rate is conventionally 115200; USB CDC devices ignore the baud setting.
- Device scripts must be the streaming versions (`*.py`, not `*_local.py`) for aggregator use.
- For calibration, pinouts, sample-rate trade-offs, and firmware details, refer to the individual component READMEs.

## License / status

Laboratory software for internal experimental use. Scripts are self-contained and rely only on built-in device modules plus `pyserial` on the host.
