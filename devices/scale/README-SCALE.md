# OpenScale-IoT Local Weight Logging

This note covers the local CSV logging setup that runs on a SparkFun OpenScale-IoT and records high-precision weight data to a file on the ESP32 filesystem. It is the scale counterpart to the camera local logger (`camera_local.py`).

- **`scale_local.py`** — MicroPython script that runs on the OpenScale-IoT’s ESP32. On startup it tares (zeroes) the scale, then repeatedly reads the HX711 24-bit ADC, converts to a calibrated weight, and appends one CSV line per sample to a local file.

There is no host-side server at this stage. A future revision can add a serial or TCP stream (similar to `camera.py` + `server.py`) if remote logging is needed.

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

### Software
- MicroPython firmware for ESP32 (see flashing notes below). The stock SparkFun Arduino firmware must be replaced for this script.
- Thonny, mpremote, or the OpenMV IDE-style workflow you already use for the camera (any tool that can upload and run a `.py` file on the ESP32).
- A serial terminal at 115200 baud if you want to watch the startup tare messages.

### Firmware
Flash a recent MicroPython build for the ESP32 (generic ESP32 or the Pico-Mini variant). Official builds are available from [micropython.org](https://micropython.org/download/esp32/). After flashing, the board appears as a USB serial device and accepts MicroPython scripts.

## 2. Packages needed

### On the ESP32 (for `scale_local.py`)
Nothing extra. The script is self-contained and uses only built-in modules:
- `machine` — Pin, I2C
- `time` — timestamps and delays

No external HX711 library is required; a minimal driver is included in the file.

### On the host
Nothing required for local logging. After a run, copy `scale_local.csv` off the board with your MicroPython file tool.

## 3. Engineering details

### Pins (OpenScale-IoT)
- HX711 DOUT → GPIO 25
- HX711 PD_SCK → GPIO 26
- Onboard TMP102 → I²C address 0x49 (pins are board-specific; set `I2C_SDA` / `I2C_SCL` in the script if you want temperature logged)

### Sample rate and precision
The HX711 is a 24-bit ADC. Default rate is 10 SPS (RATE solder jumper closed). Opening the RATE jumper selects 80 SPS at the cost of a higher noise floor (~90 nV). The script logs:
- the raw (averaged) ADC count
- the zeroed, scale-factor-converted weight with 8 decimal places
- the tare offset and scale factor used
- optional temperature

This preserves the full resolution of the converter for later analysis.

### Startup zero (tare)
On every run the script averages `TARE_SAMPLES` readings (default 15) with the assumption that the scale is in its desired zero condition (empty, or with the permanent tare weight already present). This matches the “zero on startup” behavior described for the device. The resulting offset is stored and written to every CSV row so the zero point is documented.

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
The onboard TMP102 can be read for post-processing temperature compensation. Set the I²C pins in the configuration section; otherwise temperature is logged as `nan`. The stock firmware notes that scale readings themselves are not automatically temperature-compensated—that step is left to the user.

## 4. Running the code

1. Flash MicroPython to the OpenScale-IoT if you have not already done so.
2. Connect via USB-C.
3. Upload `scale_local.py` to the board.
4. Ensure the scale is in the desired zero condition (no sample, or with the permanent platform/tare weight).
5. Run the script (or save it as `main.py` so it auto-starts on power-up).
6. The script prints the tare offset, then begins appending lines to `scale_local.csv`.
7. When finished, stop the script and copy the CSV off the board.

Example CSV header and a few lines:
```
t_ms,weight_g,raw,tare_offset,scale_factor,temp_c,n_samples
0,0.00000000,123456.00,123456.00,1.00000000,nan,3
102,-0.01234567,123455.96,123456.00,1.00000000,nan,3
205,100.12345678,223456.12,123456.00,1000.00000000,24.0625,3
```

The file is flushed periodically so a reset or power loss does not discard the entire run. Change `LOG_FILE` at the top of the script if you want a different name.

## 5. Additional notes

### Metrics produced
Each line contains:
- `t_ms` — milliseconds since script start (after the tare)
- `weight_g` — calibrated weight in grams (8 decimal places)
- `raw` — averaged raw HX711 reading
- `tare_offset` — the zero offset captured at startup
- `scale_factor` — the conversion factor in use
- `temp_c` — onboard temperature in °C, or `nan` if I²C is not configured
- `n_samples` — number of raw readings averaged for this row

### Future server connection
This version only writes a local CSV. A later revision can add a serial or TCP stream of the same CSV lines (analogous to `camera.py` + `server.py`) so a host can collect data in real time. The column layout is intentionally stable so a host parser can be written against it now.

### Troubleshooting
- **HX711 timeout** — check load-cell wiring (especially E+/E- and A+/A-), confirm the board is powered, and verify DOUT/SCK pins.
- **Weight is zero or nonsense** — `SCALE_FACTOR` is still 1.0, or the tare was taken with weight already on the cell. Re-tare and re-calibrate.
- **No temperature** — I²C pins are left as `None`, or the wrong pins were chosen. Temperature is optional.
- **File not growing** — confirm the script is still running and that you are looking at the correct filesystem (the ESP32 internal flash, not an SD card).

### Relation to the rest of the project
This logger produces a time-series CSV that can be analyzed with the same tools used for the earlier weight and beam experiments. The timestamp and high-precision weight columns are the primary signals of interest.
