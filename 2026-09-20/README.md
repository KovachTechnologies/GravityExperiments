# Calibrated-weight experiments (50 kV on quartz)

50 kV applied across a quartz-slide dielectric while a calibrated weight sensor is logged as a single `value` versus Unix timestamp. Five control takes (supply off) and four voltage takes.

Control collection is ~1 min per take (61–63 s, 122–128 samples). Voltage collection is ~1–1.5 min (65–99 s, 131–197 samples). Sampling is about two points per second. All nine traces sit on 2000-01-01 UTC; chronological order is **not** the array order in `data.json`:

| Clock (UTC) | File slot | Duration |
|---|---|---|
| 00:00:31–00:01:41 | Voltage 2 | 70 s |
| 00:03:52–00:04:57 | Voltage 3 | 65 s |
| 00:06:55–00:08:20 | Voltage 4 | 85 s |
| 00:45:00–00:46:03 | Control 1 | 63 s |
| 00:49:05–00:50:08 | Control 2 | 63 s |
| 00:51:32–00:52:34 | Control 3 | 62 s |
| 00:53:53–00:54:55 | Control 4 | 62 s |
| 00:56:02–00:57:03 | Control 5 | 61 s |
| 00:59:30–01:01:09 | Voltage 1 | 99 s |

Voltage 2–4 ran first, then a ~37 min gap, then the five controls, then Voltage 1. Rest between V2→V3 and V3→V4 is only ~2 min. That matters for the “not enough rest after V3” reading of V4.

Figures use a shared value scale of \([-180, 643]\) (global min/max) and a fixed color per run across every plot.

## Files

| Path | Role |
|---|---|
| `data.json` | `control` (5 runs) and `voltage` (4 runs); each point is `{value, timestamp}` |
| `process.py` | Histograms and stacked time series |
| `control.png` / `voltage.png` | One histogram panel per run |
| `histograms.png` | Overlapping control (top) and voltage (bottom) |
| `control_timeseries.png` / `voltage_timeseries.png` | Value vs clock time, stacked |
| `tcp_server.py` / `tcp_client_snippet.py` | Ingest `<value>,<timestamp>` lines on `0.0.0.0:5000` into `data.txt` |

`python3 process.py` regenerates the five PNG files.

## What was analyzed

Per-run mean, sample std, min/max, and a least-squares slope of `value` against elapsed seconds. Early window is the first 10 s of each take; late window is the last 20 s. Those windows are the closest thing in this dataset to a pre/post split — the voltage-on time was **not** logged in `data.json`.

Control group: \(n = 624\), mean \(-0.7\), std \(38.3\), range \([-112, 95]\).  
Voltage group: \(n = 640\), mean \(127.2\), std \(175.8\), range \([-180, 643]\).

## Results

**Controls are the same shape, not the same zero.** All five control histograms are ~60-unit-wide humps with \(\sigma \approx 22\)–\(27\). That part of the lab note is right. The *centers* are not:

| Run | Mean | \(\sigma\) | Slope (s\(^{-1}\)) | Early 10 s | Late 20 s | Late − early |
|---|---|---|---|---|---|---|
| Control 1 | 20.0 | 26.5 | \(+0.28\) | 6.5 | 21.3 | \(+15\) |
| Control 2 | 23.3 | 26.7 | \(-0.36\) | 34.6 | 15.5 | \(-19\) |
| Control 3 | −24.1 | 26.7 | \(+0.02\) | −27.1 | −19.4 | \(+8\) |
| Control 4 | 21.6 | 25.5 | \(+0.50\) | 6.3 | 29.1 | \(+23\) |
| Control 5 | −46.3 | 21.5 | \(+0.09\) | −54.4 | −47.0 | \(+7\) |

Controls 1, 2, and 4 sit near \(+20\). Control 3 is a full \(\sigma_\text{group}\) lower. Control 5 is lower still. Slopes are \(|\lesssim 0.5|\) /s and change sign. Late−early offsets also change sign. A baseline wander of tens of counts exists with the supply off; any voltage claim has to beat that, not just look different from zero.

**Voltage 1 and 2 are not control-like.** Both ramp at \(\approx 5.2\) /s.

| Run | Mean | \(\sigma\) | Slope (s\(^{-1}\)) | Early 10 s | Late 20 s | Late − early |
|---|---|---|---|---|---|---|
| Voltage 1 | 326.1 | 170.0 | \(+5.20\) | 12.2 | 447.9 | \(+436\) |
| Voltage 2 | 78.4 | 117.3 | \(+5.32\) | −69.7 | 214.6 | \(+284\) |
| Voltage 3 | 7.4 | 34.6 | \(+1.23\) | −10.6 | 42.6 | \(+53\) |
| Voltage 4 | 30.1 | 46.4 | \(+1.35\) | 0.2 | 88.5 | \(+88\) |

Voltage 1 starts inside the control envelope (early mean \(12\), \(\sigma\) \(26\)) and ends near \(450\) with late \(\sigma\) only \(29\) — a shifted, still-narrow peak, not a spread-out mess. Voltage 2 does the same climb from a negative start. Those two takes are the only ones whose late−early jump (\(+284\), \(+436\)) is an order of magnitude above control wander.

**Voltage 3 is quieter, not a replica of the controls.** Mean \(7.4\) and \(\sigma\) \(35\) do look like Control 1/2/4 in a histogram glance (`voltage.png` panel 3, `histograms.png`). The time series still slopes \(+1.23\) /s and the late mean is \(+43\), about \(+53\) above its own first 10 s. That is larger than most control late−early deltas, but it is not the V1/V2 ramp, and it is not “topped out flat.” The “voltage still on, force has peaked” reading is possible; it is not required by the trace.

**Voltage 4 is a weak V1/V2, not a repeat.** Slope \(+1.35\) /s, late mean \(89\). Same sign as V1/V2, maybe a third of the V2 excursion, far below V1. The ~2 min gap after V3 is the obvious protocol suspect. It is also the same size as the V2→V3 gap, after which V3 did *not* climb like V2, so “not enough rest” is a hypothesis, not a result.

## What this does and does not show

- Two of four voltage takes (V1, V2) show a large, same-sign ramp that no control take produces. That is the causal-looking part of the note.
- The other two voltage takes do not reproduce that ramp. V3 in particular is easy to misread from the histogram alone; the time series is the better plot.
- Control zeros jump by ~70 counts across takes. Until that offset is understood (tare, drift, cable, warm-up), a late mean of \(+43\) or \(+89\) is not a detection by itself.
- Voltage-on time is not in the file. V1’s first 10 s looking like a control is suggestive that the supply came on *during* that take, but that is inferred, not logged.
- Polarity was not reversed. Sign of the ramp vs polarity is unknown.

## How to rerun

```bash
python3 process.py          # histograms + time series from data.json
python3 tcp_server.py       # listen 0.0.0.0:5000, append lines to data.txt
```

## If this is worth another pass

The present protocol is “collect for about a minute, sometimes with 50 kV on.” That is not enough to separate a field effect from tare drift and from whatever is left over from the previous take. A next series should look like this:

1. **Write the protocol into the file.** Start time, voltage-on time, voltage-off time, polarity, gap since last take. Inferring the switch from the trace is how V3 got labeled “still on / peaked.”
2. **Fixed window.** Example: 30 s baseline, voltage on at \(t = 10\) or \(t = 30\), hold until \(t = 180\), then off, keep recording 30–60 s. Same clock for every take.
3. **Rest.** 5 min with the supply off between takes, not 2. Log that wait.
4. **Sham switch.** Same reach-and-flip with the HV cable off the sample. If a +5 /s ramp appears anyway, it is not the field.
5. **Reverse polarity** on otherwise identical takes. A real coupling to the dielectric should flip or at least change; a thermal/EMI/tare artifact need not.
6. **Tare the controls.** Controls 3 and 5 are not on the same zero as 1, 2, and 4. Find that offset before calling V3 “control-like.”
7. **Don’t judge from histograms alone.** V1’s late histogram is a narrow peak far to the right; V3’s is a narrow peak near zero. Both can look “localized.” The stacked time series is what shows the ramp.

If a second series with logged switch times, sham takes, and both polarities still only lights up on some voltage runs and not others, the weight channel is seeing something besides a steady 50 kV field on the slide.
