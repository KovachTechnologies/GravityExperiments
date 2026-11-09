# OpenMV Camera Real-Time Beam Analytics

This note covers the real-time laser-spot tracking setup that runs on an OpenMV Cam. It is the live counterpart to the offline analysis in `analyze_beam.py`.

- **`camera.py`** — MicroPython script that runs on the OpenMV Cam. It captures frames, finds the bright laser lobes (up to three overlapping dots caused by tape refraction), computes each lobe’s center of mass plus a weighted overall COM, and streams one JSON line per frame over USB serial. Implements the `READY:camera` / `START` / `STOP` handshake used by `aggregator.py`.
- **`camera_local.py`** — Identical center-of-mass logic to `camera.py`, but writes the CSV lines to a local file (`beam_local.csv`) on the OpenMV filesystem instead of streaming. Use this when no host computer is connected during the run. **Not modified** by the aggregator integration.
- **`aggregator.py`** — Host-side multi-device collector (Raspberry Pi). Discovers the camera (and other devices), sends a common `START`, and records all telemetry as JSON Lines. See `README-AGGREGATOR.md`.
- **`server.py`** — Legacy single-device camera listener (still functional for raw lines, but the preferred path is now `aggregator.py`).

The board is an OpenMV Cam (red PCB with the OpenMV logo). It supports MicroPython, a full image-processing library, and TensorFlow Lite. Serial is the preferred transport; the USB cable already appears as a virtual COM port on the host.

## 1. Prerequisites

### Hardware
- OpenMV Cam (H7, H7 Plus, RT1062, or later). The photo shows a standard red OpenMV board.
- USB cable that supports data (not charge-only).
- Optional: OpenMV CAN/RS232 Shield if you want true RS-232 levels instead of USB serial. The shield maps UART to P4 (TX) and P5 (RX).
- Optional: USB-to-TTL adapter if you prefer a hardware UART link without the shield.
- Host computer (Windows, macOS, or Linux) with a free USB port.
- Stable mount so the camera points at the laser-on-backdrop scene.

### Software
- **OpenMV IDE** (recommended for development and flashing). Download from [openmv.io](https://openmv.io). It installs the necessary drivers and gives you a live frame buffer, serial terminal, and one-click script upload.
- Python 3.8+ on the host for `server.py`.
- `pyserial` on the host (see Packages below).

### Firmware
The OpenMV should be running a recent firmware (v4.x or later). The IDE can update the firmware automatically when you connect the camera.

## 2. Packages needed

### On the host (for `server.py`)
```bash
pip install pyserial
```
That is the only external dependency. The rest of the standard library is sufficient.

### On the OpenMV (for `camera.py` or `camera_local.py`)
Nothing extra. The scripts use only the built-in modules:
- `sensor` — camera control
- `image` — find_blobs, drawing
- `time` — timestamps
- `json` — structured telemetry
- `pyb.USB_VCP` — USB virtual COM port (in `camera.py` for the aggregator handshake)

`camera_local.py` writes to the OpenMV’s internal filesystem (or the root of an inserted microSD card). No additional packages are required.

## 3. Engineering details — connecting the camera

### Recommended path: USB virtual COM port + aggregator
`camera.py` is designed to work seamlessly with `aggregator.py`:

1. Plug the OpenMV into the host (Raspberry Pi or other Linux machine) with the USB cable.
2. The camera enumerates as a virtual COM port (`/dev/ttyACM0` or similar).
3. Run `camera.py` on the OpenMV (via the IDE, or save it as `main.py` so it auto-starts). While idle it periodically emits:
   ```
   READY:camera
   ```
4. Launch `aggregator.py` on the host. It discovers the port by the `READY:` handshake, then sends `START`.
5. The camera resets its internal timer and begins streaming one JSON object per frame. On Ctrl-C the aggregator sends `STOP`; the camera returns to the READY heartbeat.

Baud rate is 115200 by convention; USB CDC ignores the baud setting.

### Protocol (camera ↔ aggregator)
| Direction | Token / format | Meaning |
|-----------|----------------|---------|
| Camera → host | `READY:camera` | Idle heartbeat / self-identification |
| Host → camera | `START` | Begin sampling; reset `t_ms` to 0 |
| Host → camera | `STOP` | Halt sampling; return to READY |
| Camera → host | JSON line | One telemetry record per frame |

Example telemetry line:
```json
{"t_ms":1520,"n_dots":3,"overall_cx":160.2,"overall_cy":128.5,"dot1_cx":158,"dot1_cy":95,"dot1_area":1200,"dot2_cx":161,"dot2_cy":130,"dot2_area":980,"dot3_cx":162,"dot3_cy":165,"dot3_area":1100}
```

The aggregator wraps each line with `host_ts` and `device` and writes JSON Lines. See `README-AGGREGATOR.md` for the host-side details.

### Legacy single-device path (`server.py`)
`server.py` can still be used if you only have the camera and want a simple CSV log, but it expects the older CSV format. The preferred multi-device path is `aggregator.py`.

### Optical and exposure notes
- Disable auto-gain, auto-white-balance, and auto-exposure once the scene is stable. The script does this so the brightness threshold remains valid.
- Tune `BRIGHT_THRESH` (the lower grayscale bound) using the OpenMV IDE histogram on a live frame until the three lobes separate cleanly.
- Start with `sensor.QVGA`. Drop to `sensor.QQVGA` if you need higher frame rate.
- Fixed exposure (`exposure_us`) may need adjustment for your laser intensity.

## 4. Running the code

### With the aggregator (preferred)
1. Open the OpenMV IDE, connect to the camera, and run `camera.py` (or save it as `main.py` for auto-start).
2. Confirm the serial terminal shows periodic `READY:camera` lines.
3. On the Raspberry Pi (or other host):
   ```bash
   python3 aggregator.py
   ```
4. The aggregator discovers the camera, sends `START`, and begins writing `aggregated_<timestamp>.jsonl`.
5. Press Ctrl-C on the host to send `STOP` and exit cleanly.

### Local file logging (`camera_local.py`)
Use this variant when you want the camera to record data by itself with no host computer attached. The center-of-mass calculations are identical to `camera.py`; only the output destination changes. **This file is unchanged.**

1. Insert a microSD card if you want the log on removable media (otherwise it writes to the internal filesystem).
2. Open `camera_local.py` in the OpenMV IDE and run it.
3. The script creates/overwrites `beam_local.csv` and appends one line per frame.
4. Stop the script when finished, then copy `beam_local.csv` off the camera (via the IDE file browser or by reading the SD card).

The CSV format is:
```
t_ms,n_dots,overall_cx,overall_cy,dot1_cx,dot1_cy,dot1_area,dot2_cx,dot2_cy,dot2_area,dot3_cx,dot3_cy,dot3_area
```

The file is flushed periodically so a power loss or reset does not lose the entire run. Change `LOG_FILE` at the top of the script if you want a different name.

## 5. Additional notes

### Metrics produced
Each JSON record contains:
- `t_ms` — milliseconds since the most recent `START`
- `n_dots` — number of bright lobes found (0–3)
- `overall_cx`, `overall_cy` — pixel-weighted center of mass of all selected lobes
- `dot1_cx/cy/area`, `dot2_…`, `dot3_…` — individual lobe centers and areas, sorted top-to-bottom (`null` / `0` if fewer than three are present)

Raise `BRIGHT_THRESH` if the three lobes merge into one blob; lower it if the weaker lobes disappear. The script uses `merge=False` so that necks between lobes can fall below threshold and separate the peaks.

### Troubleshooting
- **No READY lines** — confirm `camera.py` is running (not the local logger) and that the USB cable supports data.
- **Aggregator does not discover the camera** — check that the port appears under `/dev/ttyACM*` and that the user is in the `dialout` group.
- **No blobs detected** — lower `BRIGHT_THRESH` or increase exposure; check that the laser is in the field of view.
- **Lobes merge into one** — raise `BRIGHT_THRESH` so the connecting necks fall below threshold.
- **Low frame rate** — reduce resolution or raise the threshold so fewer pixels are examined.

### Relation to the rest of the project
This live path feeds the same style of time-series analysis that was performed on the earlier `.h264` clips. Once you have a JSONL from `aggregator.py` (or a CSV from `camera_local.py`) you can reuse plotting and slope logic from `analyze_beam.py` or `process.py`.

### TensorFlow Lite
The board can run quantized `.tflite` models via the `ml` (or older `tf`) module. For pure laser-spot tracking the classical pipeline is preferable. You can later add a small classifier (beam quality, presence/absence, anomaly) and append a confidence value to the JSON record without changing the serial protocol.

### Extending the stream
To add more fields, include them in the `record` dict in `camera.py` before calling `emit_json`. The aggregator will automatically preserve any extra keys when it wraps the line.
