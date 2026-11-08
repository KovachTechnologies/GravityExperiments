# PyPortal Titano Local Light / Spectrum Intensity Logging

This note covers the local CSV logging setup that runs on an Adafruit PyPortal Titano and records high-precision light (and optional analog) measurements to a file on the CircuitPython filesystem. It is the spectrum/light counterpart to the camera local logger (`camera_local.py`) and the scale local logger (`scale_local.py`).

- **`spectrum_local.py`** — CircuitPython script that runs on the PyPortal Titano. It repeatedly reads the onboard ambient light sensor, converts the raw ADC counts to voltage, optionally reads the D3/D4 STEMMA analog ports, samples the MCU die temperature, and appends one CSV line per sample to a local file.

There is no host-side server at this stage. A future revision can add a serial or TCP stream (similar to `camera.py` + `server.py`) if remote logging is needed.

The board is the Adafruit PyPortal Titano (product ID 4444). It uses an ATSAMD51J20 Cortex-M4, an ESP32 Wi-Fi co-processor, a 3.5″ 320×480 resistive-touch TFT, a speaker, a NeoPixel, a microSD slot, and STEMMA connectors. The Titano does **not** include the ADT7410 temperature sensor found on the original 3.2″ PyPortal. The primary onboard sensor relevant for intensity logging is the ambient light sensor (CdS / photoresistor) connected to `board.LIGHT`.

## 1. Prerequisites

### Hardware
- Adafruit PyPortal Titano.
- USB-C cable that supports data (not charge-only).
- Optional: microSD card inserted in the left-side slot for longer runs (the internal CIRCUITPY flash is limited).
- Optional: external analog sensors wired to the D3 and/or D4 3-pin JST STEMMA ports.
- Stable mounting if the light sensor is being used to monitor a laser spot or other optical source.

### Software
- CircuitPython firmware for the PyPortal Titano (see flashing notes below). The board ships with CircuitPython; update to a recent release if desired.
- Any text editor or the Mu / Thonny / VS Code CircuitPython workflow you already use. The board appears as a USB drive named `CIRCUITPY`.
- A serial terminal (115200 baud) if you want to watch the startup messages.

### Firmware
Install or update CircuitPython from [circuitpython.org/board/pyportal_titano](https://circuitpython.org/board/pyportal_titano/). Double-click the Reset button to enter bootloader mode (`PORTALBOOT` drive appears), then drag the `.uf2` file onto it. After reboot the `CIRCUITPY` drive reappears.

## 2. Packages needed

### On the PyPortal Titano (for `spectrum_local.py`)
Nothing extra. The script is self-contained and uses only built-in CircuitPython modules:
- `board` — pin definitions
- `analogio` — AnalogIn for the light sensor and D3/D4
- `time` — timestamps and delays
- `microcontroller` — CPU temperature

No Adafruit library bundle is required for this logger.

### On the host
Nothing required for local logging. After a run, copy `spectrum_local.csv` off the `CIRCUITPY` drive (or the SD card).

## 3. Engineering details

### Pins (PyPortal Titano)
- Ambient light sensor → `board.LIGHT` (analog input, 0 = dark … 65535 = bright)
- STEMMA D3 → `board.D3` (analog or digital; also DAC)
- STEMMA D4 → `board.D4` (analog or digital)
- MCU temperature → `microcontroller.cpu.temperature` (°C)
- microSD → `board.SD_CS` / `board.SD_CARD_DETECT` (not used by the default script; see notes below)

### Sample rate and precision
The SAMD51 ADC is 12-bit native but CircuitPython’s `AnalogIn.value` presents a 16-bit left-aligned value (0–65535). The script averages `N_SAMPLES` readings (default 4) and logs:
- the averaged raw count (2 decimal places)
- the converted voltage at 6 decimal places
- MCU temperature at 4 decimal places

This preserves essentially the full resolution of the converter for later analysis. Adjust `LOG_INTERVAL_MS` and `N_SAMPLES` to trade noise against bandwidth. The light sensor itself is a relatively slow photoresistor; sub-100 ms intervals are usually more than adequate.

### Voltage conversion
```
volts = (raw * 3.3) / 65536
```
The 3.3 V reference is the nominal board VCC. Absolute accuracy is limited by the reference and the sensor’s non-linearity; the raw counts are the most useful column for relative intensity work.

### Light sensor characteristics
The onboard sensor is a CdS photoresistor in a voltage-divider configuration. Resistance (and therefore ADC reading) decreases as illumination increases. It is broadband (visible light) and not a true spectrometer. In a laser-beam context it can serve as a simple intensity monitor when the spot is directed onto or near the sensor. For multi-wavelength work an external spectrometer module would be connected via I²C or the analog ports and the script extended accordingly.

## 4. Running the code

1. Confirm CircuitPython is running on the Titano (`CIRCUITPY` drive visible).
2. Copy `spectrum_local.py` to the root of the `CIRCUITPY` drive (or into a `code.py` / `main.py` name if you want it to auto-start).
3. Optional: insert a microSD card if you plan a long run and have remounted the filesystem (see Additional notes).
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

## 5. Additional notes

### Metrics produced
Each line contains:
- `t_ms` — milliseconds since script start
- `light_raw` — averaged raw light-sensor ADC count (0–65535 scale)
- `light_v` — corresponding voltage (V)
- `d3_raw` / `d3_v` — same for the D3 STEMMA port (or `nan` if not present)
- `d4_raw` / `d4_v` — same for the D4 STEMMA port (or `nan` if not present)
- `cpu_temp_c` — microcontroller die temperature (°C)
- `n_samples` — number of ADC readings averaged for this row

### Using the microSD card
The internal flash is modest. For multi-hour runs:
1. Insert a FAT-formatted microSD card.
2. In a short `boot.py` (or interactively) remount the SD as the root, or change `LOG_FILE` to a path on the mounted SD (typically `/sd/spectrum_local.csv` after using `adafruit_sdcard` + `storage`).
3. The default script writes to the CIRCUITPY root so it works with zero extra libraries.

### Future server connection
This version only writes a local CSV. A later revision can add a serial or TCP stream of the same CSV lines (analogous to `camera.py` + `server.py`) so a host can collect data in real time. The column layout is intentionally stable so a host parser can be written against it now. The ESP32 co-processor can also be used for Wi-Fi upload if desired.

### Troubleshooting
- **No CIRCUITPY drive** — use a data-capable USB-C cable; double-click Reset to re-enter bootloader and re-flash CircuitPython if needed.
- **Light reading stuck at 0 or 65535** — sensor is completely dark or saturated; adjust the optical path or exposure of the source.
- **D3/D4 always nan** — the ports are not wired or the `AnalogIn` constructor failed; check the try/except messages on the serial console.
- **File not growing** — confirm the script is still running (serial console) and that you are looking at the correct drive (`CIRCUITPY` or the SD card).
- **Self-heating** — the TFT backlight and CPU raise the die temperature; this is normal and is logged in `cpu_temp_c`.

### Relation to the rest of the project
This logger produces a time-series CSV that can be analyzed with the same tools used for the earlier weight and beam experiments. The timestamp and high-precision light (intensity) columns are the primary signals of interest. It follows the same local-file, high-precision, configuration-at-top style as `camera_local.py` and `scale_local.py` so the three devices remain consistent.
