# Electro-gravitational beam and sensor experiments

Two related lab setups live in this folder: a scalar sensor logged over TCP, and a laser spot reflected past the sample onto a backdrop. The laser-spot work is the one analyzed most recently.

## Experiments

**Scalar traces (`data.json`).** Five control runs and four voltage runs of a single `value` vs Unix timestamp. These were plotted as overlapping histograms and stacked time series.

**Laser on backdrop (21 Sep 2026).** A beam is reflected off the sample and lands on a screen. The working hypothesis was that an induced gravitational field, turned on with the high-voltage supply at \(t = 10\,\mathrm{s}\) and held for the rest of each ~90–108 s take, would walk the spot center of mass and distort the pink halo. Five raw H.264 clips (`2026-09-21-02` … `06`) were reduced to per-frame metrics. Voltage on at 10 s in every take; a few spikes are consistent with flipping the switch or bumping the table.

## What is in this folder

| Path | Role |
|---|---|
| `data.json` | Control / voltage scalar traces |
| `process.py` | Histograms and stacked time series for `data.json` |
| `tcp_server.py` / `tcp_client_snippet.py` | Ingest `<value>,<timestamp>` lines on `0.0.0.0:5000` into `data.txt` |
| `analyze_beam.py` | Laser-spot tracker (white core, COM, ellipse, halo, boundary) |
| `beam_analysis/` | Spot metrics CSVs, comparison plots, numeric summary |
| `control.png`, `voltage.png`, `histograms.png`, `*_timeseries.png` | Scalar-trace figures |

`analyze_beam.py` finds videos under `videos/`, `artifacts/videos/`, or `attachments/`. It isolates the saturated white core (\(R \ge 240\), \(G \ge 220\), \(B \ge 220\)), then logs intensity-weighted COM, geometric centroid, area, second-moment ellipse, \(r(\theta)\) boundary scatter and roughness, and halo-ring area/radius.

## What was analyzed here

The five metric CSVs (`beam_analysis/metrics_2026-09-21-0{2-6}.csv`, ~25 fps) were compared pre-switch (2–10 s) vs late (20–100 s), and around the 10 s mark. Run 02 starts at 15.52 s, so it has no pre-switch baseline.

Quiet-beam floor after ~20 s is ~0.1 px on the better takes (runs 03 and 05 late \(\sigma_{c_x} \approx 0.07\)–\(0.09\) px). Core radius is ~120–130 px.

## Results (laser spot)

No common-mode electro-gravitational signature.

- Late-time COM slopes are \(|\lesssim 0.06|\) px/s and **do not share a sign** across runs. Pre→late offsets are likewise mixed (−4 to +0.1 px in \(x\), −0.4 to +6 px in \(y\)).
- Halo area change over the same windows is both positive and negative (+200, +125, −46, −166 px²). Ellipticity settles near 0.20 in every run that has a pre-switch segment; it does not shear when voltage comes on.
- Core *area* rises the same way in runs 03–06 during the first ~10 s, **starting at \(t \approx 0\)**, then plateaus. That is camera/laser/clip warmup, not the supply.
- The large motions are impulses: run 06 at ~2.1 s (26 px, before voltage); runs 03–05 ringing at ~11.5–12.6 s (switch); run 06 a 3 px step at ~68 s; run 05 another knock at ~101 s. Run 06 barely moved at the switch (\(\Delta x \approx -0.17\) px, \(\Delta y \approx -0.04\) px). A field that stays on should not look like that.

Figures: `beam_analysis/com_timeseries.png`, `switch_window.png`, `halo_delta_overlay.png`, `area_delta_overlay.png`, `run_summary.csv`.

## How to rerun

```bash
python3 process.py          # scalar histograms + time series
python3 analyze_beam.py     # spot tracker; put .h264 files in videos/
```

## If this optical route is worth another pass

The tracker is already more sensitive than the systematics. Another voltage-on take of the same kind will not settle the question. What would:

1. **Sham switch.** Same reach-and-flip, supply left off (or HV cable disconnected at the sample). If the ~12 s ringing disappears, it was the hand/table, not the field.
2. **Fiducial on the backdrop.** A printed cross outside the spot. Subtract camera/tripod motion from the beam COM before claiming a deflection.
3. **Kill auto-exposure / lock white balance.** The shared first-10 s area rise is almost certainly the camera. Manual exposure, raw or flat response.
4. **Don’t start the science window at \(t = 0\).** Record 30–60 s of dark baseline, then switch, and keep recording after switch-off for a symmetric off-on-off test.
5. **Pixel scale.** One number: distance to the screen and the camera’s plate scale, so 0.1 px becomes microradians. Without that the null is only in pixels.
6. **Blind the analysis to switch time** when looking for slow drift; keep the sham-switch set as the noise model.

If those controls still show nothing above ~0.1 px that repeats in sign, this optical geometry is not going to see the effect as drawn. A shorter lever arm with a position-sensitive detector (or a quad cell) and vibration isolation would be a different experiment, not a continuation of these videos.
