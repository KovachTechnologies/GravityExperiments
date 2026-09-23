# Laser-spot results (21 Sep 2026)

Five H.264 takes of a beam reflected past the sample onto a backdrop. Hypothesis: an induced gravitational field, voltage on at \(t = 10\,\mathrm{s}\) and held for the rest of each ~90–108 s clip, would walk the spot center of mass and distort the pink halo.

The videos were reduced locally to per-frame CSVs with `analyze_beam.py`. Those files are what this note analyzes:

- `beam_analysis/metrics_2026-09-21-02.csv` … `06.csv` (~25 fps)
- comparison plots under `beam_analysis/`

Voltage on at 10 s in every take. A few spikes look like the switch flip or a table bump. Run 02 starts at 15.52 s and has no pre-switch baseline.

Quiet-beam floor after ~20 s is ~0.1 px on the better takes (runs 03 and 05 late \(\sigma_{c_x} \approx 0.07\)–\(0.09\) px). Saturated core radius is ~120–130 px.

## What repeats vs what does not

**Does not repeat (so it is not the field).** Late-time COM slopes are \(|\lesssim 0.06|\) px/s and do not share a sign. Pre→late offsets are mixed.

| Run | Pre (2–10 s) → late (20–100 s) \(\Delta c_x\), \(\Delta c_y\) | Late slope \(c_x\), \(c_y\) (px/s) | Late \(\sigma_{c_x}\), \(\sigma_{c_y}\) (px) |
|---|---|---|---|
| 02 | no pre-switch data (file starts at 15.52 s) | −0.013, +0.011 | 0.33, 0.31 |
| 03 | −0.87, +0.59 px | +0.0004, +0.005 | 0.067, 0.15 |
| 04 | +0.13, −0.20 px | −0.004, +0.008 | 0.13, 0.23 |
| 05 | −3.96, +5.99 px | −0.003, +0.004 | 0.090, 0.12 |
| 06 | −0.16, −0.43 px | +0.020, −0.056 | 0.50, 1.49 |

An 80 s slope of 0.005 px/s is 0.4 px total — and it does not point the same way from run to run. After ~20 s the quiet stretches are flat at the 0.1 px level.

Halo area change, same windows: +200, +125, −46, −166 px². Both signs. Ellipticity actually *falls* slightly toward ~0.20 in every run that has a pre-switch segment and then sits there. That is the spot settling to a slightly rounder clip contour, not a shear that appears when the voltage comes on.

**Does repeat, but it is not gravity.** Core area rises the same way in runs 03–06 over the first ~10 s, *starting at \(t \approx 0\)*, then plateaus. That curve is underway before the switch. It is camera / laser / clip-threshold warmup, not the supply.

## The spikes are mechanical, and they cluster

Frame-to-frame \(|\Delta\mathrm{COM}| > 1.5\) px:

| Run | \(t\) (s) | Jump (px) | Note |
|---|---|---|---|
| 06 | ~2.08–2.12 | 26, then 25 back | Before voltage. Bump or one-frame tracking glitch (\(c_y\) to 610 and back). |
| 05 | ~11.52–11.88 | 2–8 | Switch window; settles to a new offset. |
| 03 | ~12.16–12.96 | 2–6 | Switch window ringing. |
| 04 | ~11.96–12.60 | 1.5–3 | Switch window ringing. |
| 02 | ~15.56–16.08 | 2–13 | Tracker acquiring the spot; no 0–15 s data. |
| 06 | ~68.36–68.40 | 2–3 | Voltage already long on; new baseline. |
| 05 | ~101.00–101.48 | 1.6–1.9 | Late knock. |

The ~12 s events are an *impulse*, not a ramp. Run 05 is the extreme: it steps to a new offset (\(\Delta x \approx -4\) px, \(\Delta y \approx +6\) px) and then sits on that offset, dead flat, until the knock at ~101 s.

If the field were doing this, run 06 would have moved at 12 s the way 03–05 did. It barely twitched at the switch (\(\Delta x \approx -0.17\) px, \(\Delta y \approx -0.04\) px from 8–10 s to 12–14 s).

The ~2 s delay past “10 s” on 03–05 is also more consistent with “hand reached the switch a bit late / table rang” than with a field specified as turning on at 10 s and staying on.

## Halo

After the first-frame startup, \(\Delta\)(halo area) is a few hundred px² of noise around zero with no shared post-10 s trend. Mean halo radius is likewise stable. There is no ovalization or bloom that appears in all five samples when the voltage is applied.

## Sensitivity

On a quiet 20–100 s stretch the COM is good to ~0.1 px. That is about 0.08% of the ~125 px core radius. Anything smaller than a few tenths of a pixel, and anything that does not have the same sign in every run, is below what this setup can claim.

## Figures

| File | Content |
|---|---|
| `beam_analysis/com_timeseries.png` | \(\Delta x\), \(\Delta y\) stacked per run; voltage-on line at 10 s |
| `beam_analysis/switch_window.png` | 0–25 s COM relative to each run’s 2–10 s median |
| `beam_analysis/com_dx_overlay.png` / `com_dy_overlay.png` | All runs on one \(x\) or \(y\) axis |
| `beam_analysis/halo_delta_overlay.png` | Halo area minus pre-switch (or 20–25 s) median |
| `beam_analysis/area_delta_overlay.png` | Core area minus the same reference |
| `beam_analysis/ellipticity_timeseries.png` | Core ellipticity vs time |
| `beam_analysis/run_summary.csv` | The numeric table above |

## Conclusion

Switch-induced (and later) table or hand impulses — yes. Shared slow COM drift and shared halo distortion after \(t = 10\,\mathrm{s}\) — no.

This is not a detection of an electro-gravitational displacement. Another identical voltage-on video will not change that. Controls that would actually tighten the bound (sham switch, backdrop fiducial, locked exposure, off-on-off windows, pixel-to-angle scale) are listed in `README.md`.
