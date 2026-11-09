# PyPortal Titano Light / Spectrum Intensity Logging

This note covers both the local CSV logger and the USB-serial streaming script for the Adafruit PyPortal Titano. It is the spectrum/light counterpart to the camera (`camera.py` / `camera_local.py`) and scale (`scale_local.py`) setups.

- **`spectrum_local.py`** — CircuitPython script that runs on the PyPortal Titano and writes high-precision light (and optional analog) measurements to a local CSV file. Use this for offline runs when no host is attached.
- **`spectrum.py`** — Streaming counterpart that implements the READY / START / STOP handshake expected by `aggregator.py`. It waits for a host `START` command, then emits one JSON telemetry line per sample over USB serial. On `STOP` it returns to the READY state.

The aggregator (`aggregator.py`) discovers the board by the `READY:spectrum` line, issues a common `START` with the other devices, records every JSON line with a host receipt timestamp, and sends `STOP` on exit. The local logger remains unchanged for standalone use.

The board is the Adafruit PyPortal Titano (product ID 4444). It uses an ATSAMD51J20 Cortex-M4, an ESP32 Wi-Fi co-processor, a 3.5″ 320×480 resistive-touch TFT, a speaker, a NeoPixel, a microSD slot, and STEMMA connectors. The Titano does **not** include the ADT7410 temperature sensor found on the original 3.2″ PyPortal. The primary onboard sensor relevant for intensity logging is the ambient light sensor (CdS / photoresistor) connected to `board.LIGHT`.

## 1. Prerequisites

### Hardware
- Adafruit PyPortal Titano.
- USB-C cable that supports data (not charge-only).
- Optional: microSD card inserted in the left-side slot for longer local runs (the internal CIRCUITPY flash is limited).
- Optional: external analog sensors wired to the D3 and/or D4 3-pin JST STEMMA ports.
- Stable mounting if the light sensor is being used to monitor a laser spot or other optical source.
- For aggregator use: Raspberry Pi (or other Linux host) running `aggregator.py`, with the Titano plugged into a USB port.

### Software
- CircuitPython firmware for the PyPortal Titano (see flashing notes below). The board ships with CircuitPython; update to a recent release if desired.
- Any text editor or the Mu / Thonny / VS Code CircuitPython workflow you already use. The board appears as a USB drive named `CIRCUITPY`.
- A serial terminal (115200 baud) if you want to watch the startup / READY messages.
- On the host (for `aggregator.py`): Python 3.8+ and `pyserial`.

### Firmware
Install or update CircuitPython from [circuitpython.org/board/pyportal_titano](https://circuitpython.org/board/pyportal_titano/). Double-click the Reset button to enter bootloader mode (`PORTALBOOT` drive appears), then drag the `.uf2` file onto it. After reboot the `CIRCUITPY` drive reappears.

## 2. Packages needed

### On the PyPortal Titano (for either script)
Nothing extra. Both scripts are self-contained and use only built-in CircuitPython modules:
- `board` — pin definitions
- `analogio` — AnalogIn for the light sensor and D3/D4
- `time` — timestamps and delays
- `microcontroller` — CPU temperature
- `json`, `sys`, `supervisor` — only in `spectrum.py` (serial handshake and JSON output)

No Adafruit library bundle is required.

### On the host
- For local logging: nothing. After a run, copy `spectrum_local.csv` off the `CIRCUITPY` drive (or the SD card).
- For aggregator mode: `pip install pyserial` (see `README-AGGREGATOR.md`).

## 3. Engineering details

### Pins (PyPortal Titano)
- Ambient light sensor → `board.LIGHT` (analog input, 0 = dark … 65535 = bright)
- STEMMA D3 → `board.D3` (analog or digital; also DAC)
- STEMMA D4 → `board.D4` (analog or digital)
- MCU temperature → `microcontroller.cpu.temperature` (°C)
- microSD → `board.SD_CS` / `board.SD_CARD_DETECT` (not used by the default scripts; see notes below)

### Sample rate and precision
The SAMD51 ADC is 12-bit native but CircuitPython’s `AnalogIn.value` presents a 16-bit left-aligned value (0–65535). Both scripts average `N_SAMPLES` readings (default 4) and record:
- the averaged raw count
- the converted voltage
- MCU temperature

This preserves essentially the full resolution of the converter for later analysis. Adjust `LOG_INTERVAL_MS` and `N_SAMPLES` at the top of either script to trade noise against bandwidth. The light sensor itself is a relatively slow photoresistor; sub-100 ms intervals are usually more than adequate.

### Voltage conversion
```
volts = (raw * 3.3) / 65536
```
The 3.3 V reference is the nominal board VCC. Absolute accuracy is limited by the reference and the sensor’s non-linearity; the raw counts are the most useful column for relative intensity work.

### Light sensor characteristics
The onboard sensor is a CdS photoresistor in a voltage-divider configuration. Resistance (and therefore ADC reading) decreases as illumination increases. It is broadband (visible light) and not a true spectrometer. In a laser-beam context it can serve as a simple intensity monitor when the spot is directed onto or near the sensor. For multi-wavelength work an external spectrometer module would be connected via I²C or the analog ports and the scripts extended accordingly.

### Aggregator protocol (`spectrum.py`)
`spectrum.py` speaks the same simple line protocol used by the other devices:

- While idle it periodically prints `READY:spectrum` (about once per second, plus an immediate line on start).
- The aggregator discovers the port by this line, then sends `START`.
- On `START` the device resets its internal `t_ms` timer and begins emitting one compact JSON object per sample.
- On `STOP` it halts sampling and returns to the READY heartbeat so it can be re-started without a reset.
- Telemetry is pure JSON (no CSV) so the aggregator parses it directly and only adds `host_ts` and `device`.

Example JSON line emitted by the device:
```json
{"t_ms":102,"light_raw":32810.5,"light_v":1.652148,"d3_raw":null,"d3_v":null,"d4_raw":null,"d4_v":null,"cpu_temp_c":32.51,"n_samples":4}
```
(The aggregator wraps this with `"host_ts"` and `"device":"spectrum"`.)

USB CDC serial is used (the same virtual COM port that appears when the board is plugged in). Baud rate is ignored by the hardware; 115200 is the conventional value used by the aggregator.

## 4. Running the code

### Local file logging (`spectrum_local.py`)
1. Confirm CircuitPython is running on the Titano (`CIRCUITPY` drive visible).
2. Copy `spectrum_local.py` to the root of the `CIRCUITPY` drive (or rename it to `code.py` / `main.py` so it auto-starts).
3. Optional: insert a microSD card if you plan a long run and have remounted the filesystem.
4. Open a serial console if desired and reset or run the script.
5. The script prints the header, then begins appending lines to `spectrum_local.csv`.
6. When finished, stop the script (Ctrl-C in the serial console, or power-cycle) and copy the CSV off the board.

Example CSV header and a few lines:
```
t_ms,light_raw,light_v,d3_raw,d3_v,d4_raw,d4_v,cpu_temp_c,n_samples
0,32768.00,1.650000,nan,nan,nan,nan,32.5000,4
102,32810.50,1.652148,nan,nan,nan,nan,32.5100,4
205,12005.25,0.604500,45000.00,2.264648,nan,nan,32.5200,4
```

The file is flushed periodically so a reset or power loss does not discard the entire run. Change `LOG_FILE` at the top of the script if you want a different name or path.

### Streaming to the aggregator (`spectrum.py` + `aggregator.py`)
1. Copy `spectrum.py` to the root of the `CIRCUITPY` drive (rename to `code.py` if you want it to auto-start on power-up).
2. Reset the board. It should begin printing `READY:spectrum` on the USB serial console.
3. On the Raspberry Pi (or host), with all desired devices plugged in, run:
   ```bash
   python3 aggregator.py
   ```
4. The aggregator discovers the Titano (and any other READY devices), sends `START`, and begins writing a JSON Lines file `aggregated_<UTC-timestamp>.jsonl`.
5. Press Ctrl-C on the host to stop. The aggregator sends `STOP`; the Titano returns to the READY state.

The device-side `t_ms` is relative to the moment `START` was received. The aggregator’s `host_ts` (Unix time of receipt) is the authoritative timestamp for cross-device alignment.

## 5. Additional notes

### Metrics produced
Each sample (CSV row or JSON object) contains:
- `t_ms` — milliseconds since script start (local) or since the most recent `START` (streaming)
- `light_raw` — averaged raw light-sensor ADC count (0–65535 scale)
- `light_v` — corresponding voltage (V)
- `d3_raw` / `d3_v` — same for the D3 STEMMA port (or `nan` / `null` if not present)
- `d4_raw` / `d4_v` — same for the D4 STEMMA port (or `nan` / `null` if not present)
- `cpu_temp_c` — microcontroller die temperature (°C)
- `n_samples` — number of ADC readings averaged for this row

### Using the microSD card (local logger only)
The internal flash is modest. For multi-hour local runs:
1. Insert a FAT-formatted microSD card.
2. In a short `boot.py` (or interactively) remount the SD as the root, or change `LOG_FILE` to a path on the mounted SD (typically `/sd/spectrum_local.csv` after using `adafruit_sdcard` + `storage`).
3. The default script writes to the CIRCUITPY root so it works with zero extra libraries.

### Troubleshooting
- **No CIRCUITPY drive** — use a data-capable USB-C cable; double-click Reset to re-enter bootloader and re-flash CircuitPython if needed.
- **Light reading stuck at 0 or 65535** — sensor is completely dark or saturated; adjust the optical path or exposure of the source.
- **D3/D4 always nan/null** — the ports are not wired or the `AnalogIn` constructor failed; check the serial console for startup messages.
- **Aggregator does not discover the board** — confirm `spectrum.py` is running (you should see `READY:spectrum` in a serial monitor) and that the USB cable supports data. The aggregator filters on known VIDs (Adafruit 0x239A) and on names containing `ttyACM`/`ttyUSB`.
- **No telemetry after START** — check that the aggregator successfully opened the port and that the board did not drop into the REPL. Ctrl-C on the serial console can interrupt the script; re-run or reset.
- **Self-heating** — the TFT backlight and CPU raise the die temperature; this is normal and is logged in `cpu_temp_c`.

### Relation to the rest of the project
Both loggers produce time-series data that can be analyzed with the same tools used for the earlier weight and beam experiments. The timestamp and high-precision light (intensity) columns are the primary signals of interest. The streaming script follows the same READY / START / STOP / JSON convention as the other devices so the three streams can be collected together by `aggregator.py`. The local script remains available for offline work and is intentionally left unchanged.
