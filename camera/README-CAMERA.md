# OpenMV Camera Real-Time Beam Analytics

This note covers the real-time laser-spot tracking setup that runs on an OpenMV Cam and streams metrics to a host computer. It is the live counterpart to the offline analysis in `analyze_beam.py`.

- **`camera.py`** — MicroPython script that runs on the OpenMV Cam. It captures frames, finds the bright laser lobes (up to three overlapping dots caused by tape refraction), computes each lobe’s center of mass plus a weighted overall COM, and streams one CSV line per frame over serial.
- **`camera_local.py`** — Identical center-of-mass logic to `camera.py`, but writes the CSV lines to a local file (`beam_local.csv`) on the OpenMV filesystem instead of streaming. Use this when no host computer is connected during the run.
- **`server.py`** — Python script that runs on the host computer. It opens the serial port, reads the telemetry lines from `camera.py`, prints them, and logs them to a timestamped CSV file.

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
- `image` — find_blobs, get_statistics, drawing
- `time` — timestamps and FPS
- `pyb.UART` — hardware serial (only in `camera.py` if `USE_HARDWARE_UART = True`)

`camera_local.py` writes to the OpenMV’s internal filesystem (or the root of an inserted microSD card). No additional packages are required.

## 3. Engineering details — connecting the camera

### Recommended path: USB virtual COM port
1. Plug the OpenMV into the host with the USB cable.
2. The camera enumerates as a virtual COM port:
   - Windows: `COMx` (Device Manager → Ports)
   - Linux: `/dev/ttyACM0` (or `ttyACM1`, …)
   - macOS: `/dev/tty.usbmodem…` or `/dev/cu.usbmodem…`
3. In `camera.py` leave `USE_HARDWARE_UART = False`. All `print()` output goes out the USB serial port.
4. In `server.py` set `PORT` to the device path found above.

This path is simplest, highest bandwidth, and requires no extra wiring. Baud rate on the USB VCP is largely ignored by the hardware; 115200 is a safe default.

### Alternative path: hardware UART (RS-232 shield or USB-TTL adapter)
1. If using the CAN/RS232 Shield, attach it to the OpenMV. RS-232 TX/RX are on P4/P5.
2. Wire:
   - OpenMV P4 (TX) → host adapter RX
   - OpenMV P5 (RX) → host adapter TX
   - Common ground
3. In `camera.py` set `USE_HARDWARE_UART = True`. The script opens `UART(3, …)` which is the standard mapping for those pins on most OpenMV boards.
4. Match the baud rate (default 115200) on both sides.
5. On the host, the adapter appears as `/dev/ttyUSB0` (Linux) or a `COMx` port (Windows). Point `server.py` at that port.

### Optical and exposure notes
- Disable auto-gain, auto-white-balance, and auto-exposure once the scene is stable. The script does this so the brightness threshold remains valid.
- Tune `BRIGHT_THRESH` (the lower grayscale bound) using the OpenMV IDE histogram on a live frame until only the laser core is detected.
- Start with `sensor.QVGA`. Drop to `sensor.QQVGA` if you need higher frame rate.
- Fixed exposure (`exposure_us`) may need adjustment for your laser intensity so the core is bright but not completely saturated across a large area.

## 4. Running the code

### Streaming to a host (`camera.py` + `server.py`)
1. Open the OpenMV IDE and connect to the camera.
2. Open `camera.py`.
3. Adjust `BRIGHT_THRESH`, `FRAMESIZE`, and the `USE_HARDWARE_UART` flag if needed.
4. Click the Run button (green arrow). The script begins streaming CSV lines over the serial port.
5. Optional: save the script as `main.py` on the camera’s filesystem so it auto-runs on power-up.

You should see CSV lines in the IDE serial terminal, for example:
```
t_ms,n_dots,overall_cx,overall_cy,dot1_cx,dot1_cy,dot1_area,dot2_cx,dot2_cy,dot2_area,dot3_cx,dot3_cy,dot3_area
1520,3,160.2,128.5,158,95,1200,161,130,980,162,165,1100
```

The three dots are sorted top-to-bottom. Missing lobes are reported as `nan`. The overall COM is the pixel-count-weighted average of the detected lobes.

On the host:
1. Edit `server.py` and set `PORT` to the correct device.
2. Run:
   ```bash
   python server.py
   ```
3. The script prints each line and writes a file `beam_telemetry_YYYYMMDD_HHMMSS.csv`.
4. Stop with Ctrl-C. The CSV is flushed and closed.

The CSV can be loaded into the same analysis tools used for the earlier offline runs (`analyze_beam.py` style plots, slope calculations, etc.).

### Local file logging (`camera_local.py`)
Use this variant when you want the camera to record data by itself with no host computer attached. The center-of-mass calculations are identical to `camera.py`; only the output destination changes.

1. Insert a microSD card if you want the log on removable media (otherwise it writes to the internal filesystem).
2. Open `camera_local.py` in the OpenMV IDE and run it.
3. The script creates/overwrites `beam_local.csv` and appends one line per frame.
4. Stop the script when finished, then copy `beam_local.csv` off the camera (via the IDE file browser or by reading the SD card).

The CSV format is identical to the streaming version. The file is flushed periodically so a power loss or reset does not lose the entire run. Change `LOG_FILE` at the top of the script if you want a different name.

## 5. Additional notes

### Metrics produced
Each line contains:
- `t_ms` — milliseconds since script start
- `n_dots` — number of bright lobes found (0–3)
- `overall_cx`, `overall_cy` — pixel-weighted center of mass of all selected lobes
- `dot1_cx/cy/area`, `dot2_…`, `dot3_…` — individual lobe centers and areas, sorted top-to-bottom (padded with `nan`/`0` if fewer than three are present)

Raise `BRIGHT_THRESH` if the three lobes merge into one blob; lower it if the weaker lobes disappear. The script uses `merge=False` so that necks between lobes can fall below threshold and separate the peaks.

### TensorFlow Lite
The board can run quantized `.tflite` models via the `ml` (or older `tf`) module. For pure laser-spot tracking the classical pipeline is preferable. You can later add a small classifier (beam quality, presence/absence, anomaly) and append a confidence value to the CSV line without changing the serial protocol.

### Troubleshooting
- **No serial port appears** — try a different USB cable or port; confirm the camera LED is on; reinstall the OpenMV drivers via the IDE.
- **Garbage or missing lines** — baud-rate mismatch (hardware UART path only); ensure the host and camera agree.
- **No blobs detected** — lower `BRIGHT_THRESH` or increase exposure; check that the laser is in the field of view and not completely clipped.
- **Multiple blobs** — the script always selects the largest by pixel count. Raise `MIN_PIXELS` / `MIN_AREA` or tighten the threshold.
- **Low frame rate** — reduce resolution, raise the threshold so fewer pixels are examined, or disable drawing in the IDE.

### Extending the stream
To add more fields, append them in the `line = …` f-string in `camera.py` and update the expected column count in `server.py`. Binary packing with `ustruct` is also possible if you later need higher throughput than text CSV.

### Relation to the rest of the project
This live path is intended to feed the same style of time-series analysis that was performed on the earlier `.h264` clips. Once you have a CSV from `server.py` you can reuse plotting and slope logic from `analyze_beam.py` or `process.py`.
