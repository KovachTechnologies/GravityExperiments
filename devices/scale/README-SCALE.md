# OpenScale-IoT Weight Logging

This note covers both the local CSV logger and the aggregator-streaming script that run on a SparkFun OpenScale-IoT.

- **`scale.py`** — MicroPython script that runs on the OpenScale-IoT’s ESP32. It tares (zeroes) the scale on startup, then waits for a `START` command from the host aggregator. After `START` it streams high-precision weight measurements as JSON lines over USB serial. Implements the `READY` / `START` / `STOP` handshake used by `aggregator.py`.
- **`scale_local.py`** — Identical HX711 reading and tare logic, but writes CSV lines to a local file (`scale_local.csv`) on the ESP32 filesystem instead of streaming. Use this when no host computer is connected during the run. This file is unchanged.

The board is the SparkFun OpenScale-IoT (red PCB with the SparkFun logo and “OpenScale-IoT” silkscreen). It contains an ESP32-PICO-MINI, an HX711 24-bit load-cell ADC, and an onboard TMP102 temperature sensor.

## 1. Prerequisites

### Hardware
- SparkFun OpenScale-IoT.
- Load cell (4-wire or 5-wire) wired to the LOAD CELL screw terminals:
  - E+ / VCC → red
  - E- / GND → black (or yellow)
  - A- / O- / S- → white
  - A+ / O+ / S+ → green (or blue)
  - Optional shield → yellow/shield terminal
- USB-C cable that supports data (not charge-only).
- Stable platform so the load cell sees a consistent zero condition at startup.
- For aggregator use: Raspberry Pi (or other host) running `aggregator.py`.

### Software
- MicroPython firmware for ESP32 (see flashing notes below). The stock SparkFun Arduino firmware must be replaced for these scripts.
- Thonny, mpremote, or any tool that can upload and run a `.py` file on the ESP32.
- On the host (for `aggregator.py`): Python 3.8+ and `pyserial`.

### Firmware
Flash a recent MicroPython build for the ESP32 (generic ESP32 or the Pico-Mini variant). Official builds are available from [micropython.org](https://micropython.org/download/esp32/). After flashing, the board appears as a USB serial device and accepts MicroPython scripts.

## 2. Packages needed

### On the ESP32 (for `scale.py` or `scale_local.py`)
Nothing extra. Both scripts are self-contained and use only built-in modules:
- `machine` — Pin, I2C
- `time` — timestamps and delays
- `json`, `sys`, `select` — serial handshake and JSON output (`scale.py` only)

No external HX711 library is required; a minimal driver is included in each file.

### On the host (for aggregator mode)
```bash
pip install pyserial
```
That is the only external dependency for `aggregator.py`.

## 3. Engineering details

### Pins (OpenScale-IoT)
- HX711 DOUT → GPIO 25
- HX711 PD_SCK → GPIO 26
- Onboard TMP102 → I²C address 0x49 (pins are board-specific; set `I2C_SDA` / `I2C_SCL` in the script if you want temperature logged)

### Sample rate and precision
The HX711 is a 24-bit ADC. Default rate is 10 SPS (RATE solder jumper closed). Opening the RATE jumper selects 80 SPS at the cost of a higher noise floor (~90 nV). Both scripts report:
- the raw (averaged) ADC count
- the zeroed, scale-factor-converted weight with high precision (8 decimal places)
- the tare offset and scale factor used
- optional temperature

This preserves the full resolution of the converter for later analysis.

### Startup zero (tare)
On every run the script averages `TARE_SAMPLES` readings (default 15) with the assumption that the scale is in its desired zero condition (empty, or with the permanent tare weight already present). This matches the “zero on startup” behavior described for the device. The resulting offset is stored and included in every record so the zero point is documented.

### Calibration
`SCALE_FACTOR` converts raw counts to grams:

```
weight_g = (raw - tare_offset) / SCALE_FACTOR
```

To determine the factor:
1. Set `SCALE_FACTOR = 1.0` and run the script (or use the REPL).
2. Note the zeroed raw value with nothing on the scale (should be near 0 after tare).
3. Place a known mass (e.g. 100 g) and note the new zeroed raw value.
4. Compute `SCALE_FACTOR = known_grams / zeroed_raw`.
5. Put that number into the script and re-run.

The factor is load-cell specific. Re-check periodically if ambient temperature or mechanical setup changes.

### Temperature
The onboard TMP102 can be read for post-processing temperature compensation. Set the I²C pins in the configuration section; otherwise temperature is reported as `null` / `nan`. The stock firmware notes that scale readings themselves are not automatically temperature-compensated—that step is left to the user.

### Aggregator protocol (`scale.py`)
`scale.py` implements the same handshake used by `aggregator.py` and `spectrum.py`:

- While idle, the script periodically emits:
  ```
  READY:scale
  ```
- The aggregator discovers the device by this line, then sends `START`.
- On `START` the device timer resets and the script begins streaming one JSON object per sample.
- On `STOP` (sent by the aggregator on clean exit) the script stops sampling and returns to emitting `READY:scale`.

Example telemetry line (JSON):
```json
{"t_ms":1234,"weight_g":12.345678,"raw":223456.12,"tare_offset":123456.0,"scale_factor":1000.0,"temp_c":24.0625,"n_samples":3}
```

The aggregator wraps each line with a host receipt timestamp (`host_ts`) and device id (`device`), writing a single JSON Lines file that can later be aligned with the camera and spectrum streams.

## 4. Running the code

### Streaming to the aggregator (`scale.py`)
1. Flash MicroPython to the OpenScale-IoT if you have not already done so.
2. Connect via USB-C.
3. Upload `scale.py` to the board (or save it as `main.py` so it auto-starts).
4. Ensure the scale is in the desired zero condition, then run the script. It tares, then begins emitting `READY:scale`.
5. On the host, run:
   ```bash
   python3 aggregator.py
   ```
6. The aggregator discovers the scale (and any other devices), sends `START`, and records all streams to `aggregated_<timestamp>.jsonl`.
7. Press Ctrl-C on the aggregator to send `STOP` and close the ports.

### Local file logging (`scale_local.py`)
Use this variant when you want the scale to record data by itself with no host computer attached. The HX711 and tare logic are identical to `scale.py`; only the output destination changes.

1. Upload and run `scale_local.py`.
2. The script creates/overwrites `scale_local.csv` and appends one line per sample.
3. Stop the script when finished, then copy `scale_local.csv` off the board.

Example CSV header and a few lines:
```
t_ms,weight_g,raw,tare_offset,scale_factor,temp_c,n_samples
0,0.00000000,123456.00,123456.00,1.00000000,nan,3
102,-0.01234567,123455.96,123456.00,1.00000000,nan,3
```

The file is flushed periodically so a reset or power loss does not discard the entire run. Change `LOG_FILE` at the top of the script if you want a different name.

## 5. Additional notes

### Metrics produced
Each record (JSON or CSV) contains:
- `t_ms` — milliseconds since script start (after the tare) / since `START`
- `weight_g` — calibrated weight in grams
- `raw` — averaged raw HX711 reading
- `tare_offset` — the zero offset captured at startup
- `scale_factor` — the conversion factor in use
- `temp_c` — onboard temperature in °C, or null/`nan` if I²C is not configured
- `n_samples` — number of raw readings averaged for this row

### Relationship to the aggregator
`scale.py` is the streaming counterpart to `scale_local.py`. It is designed to run alongside `camera.py` and `spectrum.py` under a single `aggregator.py` process on a Raspberry Pi. All three devices share a common `START`/`STOP` and are timestamped on the host so the weight, beam, and spectrum streams can be aligned later.

### Troubleshooting
- **HX711 timeout** — check load-cell wiring (especially E+/E- and A+/A-), confirm the board is powered, and verify DOUT/SCK pins.
- **Weight is zero or nonsense** — `SCALE_FACTOR` is still 1.0, or the tare was taken with weight already on the cell. Re-tare and re-calibrate.
- **No temperature** — I²C pins are left as `None`, or the wrong pins were chosen. Temperature is optional.
- **Aggregator does not see the scale** — confirm `scale.py` is running and printing `READY:scale`, the USB cable supports data, and the host user can open the serial port (e.g. membership in the `dialout` group).
- **File not growing (`scale_local.py`)** — confirm the script is still running and that you are looking at the correct filesystem (the ESP32 internal flash, not an SD card).

### Relation to the rest of the project
This logger produces a time-series of high-precision weight that can be analyzed with the same tools used for the earlier weight and beam experiments. When used with the aggregator, the host timestamps allow the scale stream to be synchronized with the camera and spectrum streams.
