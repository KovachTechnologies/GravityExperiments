#!/usr/bin/python3
"""Track a laser spot on a backdrop and write time series of shape/position metrics.

Looks for raw .h264 (or common video containers) in:
  artifacts/videos, videos, attachments, artifacts
Falls back to the attached still if no videos are present.

Outputs (under artifacts/beam_analysis/):
  metrics_<stem>.csv
  timeseries_<stem>.png
  overlay_<stem>.png          first-frame annotation
  summary_overlay.png         still / first available frame
  comparison.png              overlaid traces across runs (if >=1 video)
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path("/Users/danielkovach/Desktop/GravityExperiments/2026-09-21")
OUT = ROOT / "beam_analysis"
STILL = Path("/Users/danielkovach/Desktop/GravityExperiments/2026-09-21/stills/laser_on_screen_still.png")

VIDEO_GLOBS = ("*.h264", "*.H264", "*.mp4", "*.mov", "*.mkv", "*.avi")
SEARCH_DIRS = (
    ROOT / "videos",
    Path("/Users/danielkovach/Desktop/GravityExperiments/2026-09-21/videos"),
    ROOT,
)

# White core: saturated laser on the screen. Halo is red/pink and is excluded
# by requiring G and B to be high as well.
CORE_R = 240
CORE_G = 220
CORE_B = 220
ROI_MARGIN = 280
ANGLE_BINS = 180


def find_videos() -> list[Path]:
    found: list[Path] = []
    for d in SEARCH_DIRS:
        if not d.is_dir():
            continue
        for pat in VIDEO_GLOBS:
            found.extend(sorted(d.glob(pat)))
    # unique, preserve order
    seen = set()
    out = []
    for p in found:
        if p.resolve() in seen:
            continue
        seen.add(p.resolve())
        out.append(p)
    return out


def rgb_to_arrays(rgb: np.ndarray):
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)
    intensity = np.maximum(np.maximum(r, g), b)
    return r, g, b, intensity


def core_mask(r, g, b) -> np.ndarray:
    raw = (r >= CORE_R) & (g >= CORE_G) & (b >= CORE_B)
    raw = ndimage.binary_opening(raw, structure=np.ones((3, 3)))
    raw = ndimage.binary_closing(raw, structure=np.ones((5, 5)))
    labeled, n = ndimage.label(raw)
    if n == 0:
        return np.zeros(raw.shape, dtype=bool)
    sizes = ndimage.sum(raw, labeled, index=np.arange(1, n + 1))
    keep = int(np.argmax(sizes)) + 1
    # reject tiny blobs (noise)
    if sizes[keep - 1] < 200:
        return np.zeros(raw.shape, dtype=bool)
    return labeled == keep


def largest_halo_mask(r, g, b, core: np.ndarray) -> np.ndarray:
    """Pink ring immediately around the white core, not the whole backdrop."""
    if not core.any():
        return np.zeros_like(core)
    # annulus: outside the core, inside a modest dilation of the core
    ring = ndimage.binary_dilation(core, iterations=28) & ~core
    # halo is saturated red but not white
    pink = (r >= 230) & (g < 160) & (b < 210)
    return ring & pink


def contour_radii(mask: np.ndarray, cy: float, cx: float, n_bins: int = ANGLE_BINS):
    """Boundary pixels in polar form, binned by angle -> r(theta)."""
    if mask.sum() < 20:
        return None
    eroded = ndimage.binary_erosion(mask)
    boundary = mask & ~eroded
    ys, xs = np.where(boundary)
    if len(xs) < 12:
        return None
    dx = xs.astype(np.float64) - cx
    dy = ys.astype(np.float64) - cy
    theta = np.arctan2(dy, dx)
    rad = np.hypot(dx, dy)
    bins = np.linspace(-np.pi, np.pi, n_bins + 1)
    idx = np.clip(np.digitize(theta, bins) - 1, 0, n_bins - 1)
    r_mean = np.full(n_bins, np.nan)
    for i in range(n_bins):
        sel = rad[idx == i]
        if sel.size:
            r_mean[i] = sel.mean()
    # interpolate small gaps
    good = np.isfinite(r_mean)
    if good.sum() < n_bins * 0.5:
        return None
    if good.sum() < n_bins:
        x = np.arange(n_bins)
        r_mean[~good] = np.interp(x[~good], x[good], r_mean[good], period=n_bins)
    return r_mean


def second_moments(mask: np.ndarray, weights: np.ndarray | None = None):
    ys, xs = np.where(mask)
    if len(xs) < 10:
        return None
    if weights is None:
        w = np.ones(len(xs), dtype=np.float64)
    else:
        w = weights[ys, xs].astype(np.float64)
        w = np.clip(w, 0, None)
        if w.sum() <= 0:
            w = np.ones_like(w)
    wsum = w.sum()
    cx = np.sum(xs * w) / wsum
    cy = np.sum(ys * w) / wsum
    dx = xs - cx
    dy = ys - cy
    mu20 = np.sum(w * dx * dx) / wsum
    mu02 = np.sum(w * dy * dy) / wsum
    mu11 = np.sum(w * dx * dy) / wsum
    cov = np.array([[mu20, mu11], [mu11, mu02]], dtype=np.float64)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    evals = np.clip(evals[order], 0, None)
    evecs = evecs[:, order]
    sigma_maj = math.sqrt(evals[0])
    sigma_min = math.sqrt(evals[1])
    # angle of major axis (image x to the right, y down)
    ang = math.atan2(evecs[1, 0], evecs[0, 0])
    ellipticity = 0.0 if sigma_maj <= 1e-9 else 1.0 - (sigma_min / sigma_maj)
    return {
        "cx": cx,
        "cy": cy,
        "sigma_x": math.sqrt(mu20),
        "sigma_y": math.sqrt(mu02),
        "sigma_maj": sigma_maj,
        "sigma_min": sigma_min,
        "orientation_deg": math.degrees(ang),
        "ellipticity": ellipticity,
        "area": float(mask.sum()),
    }


def analyze_frame(rgb: np.ndarray, roi: tuple[int, int, int, int] | None = None):
    """Return metrics dict and the core mask in full-image coordinates."""
    h, w = rgb.shape[:2]
    r, g, b, intensity = rgb_to_arrays(rgb)

    if roi is None:
        mask = core_mask(r, g, b)
        if not mask.any():
            return None, None, None
        ys, xs = np.where(mask)
        y0 = max(0, int(ys.min()) - ROI_MARGIN)
        y1 = min(h, int(ys.max()) + ROI_MARGIN + 1)
        x0 = max(0, int(xs.min()) - ROI_MARGIN)
        x1 = min(w, int(xs.max()) + ROI_MARGIN + 1)
        roi = (y0, y1, x0, x1)
    else:
        y0, y1, x0, x1 = roi
        mask = np.zeros((h, w), dtype=bool)
        sub = core_mask(r[y0:y1, x0:x1], g[y0:y1, x0:x1], b[y0:y1, x0:x1])
        mask[y0:y1, x0:x1] = sub
        if not mask.any():
            return None, roi, None

    y0, y1, x0, x1 = roi
    sub_int = intensity[y0:y1, x0:x1]
    sub_mask = mask[y0:y1, x0:x1]
    sub_r = r[y0:y1, x0:x1]
    sub_g = g[y0:y1, x0:x1]
    sub_b = b[y0:y1, x0:x1]

    # intensity-weighted COM of the white core (primary deflection metric)
    mom = second_moments(sub_mask, weights=sub_int)
    if mom is None:
        return None, roi, mask
    cx = mom["cx"] + x0
    cy = mom["cy"] + y0

    # unweighted geometric centroid of the saturated region
    geo = ndimage.center_of_mass(sub_mask)
    geo_cy, geo_cx = geo[0] + y0, geo[1] + x0

    # brightest pixel (coarse; saturated so not very informative)
    local = np.where(sub_mask, sub_int, -1)
    py, px = np.unravel_index(int(np.argmax(local)), local.shape)

    radii = contour_radii(sub_mask, mom["cy"], mom["cx"])
    if radii is not None:
        r_mean = float(np.mean(radii))
        r_std = float(np.std(radii))
        r_min = float(np.min(radii))
        r_max = float(np.max(radii))
        # high-frequency boundary roughness: residual after 4-harmonic ellipse-like fit
        th = np.linspace(-np.pi, np.pi, len(radii), endpoint=False)
        # fit r = a0 + a1 cos + b1 sin + a2 cos2 + b2 sin2
        A = np.column_stack(
            [
                np.ones_like(th),
                np.cos(th),
                np.sin(th),
                np.cos(2 * th),
                np.sin(2 * th),
            ]
        )
        coef, *_ = np.linalg.lstsq(A, radii, rcond=None)
        fit = A @ coef
        roughness = float(np.sqrt(np.mean((radii - fit) ** 2)))
    else:
        r_mean = r_std = r_min = r_max = roughness = float("nan")
        radii = None

    eq_radius = math.sqrt(mom["area"] / math.pi)
    boundary = sub_mask & ~ndimage.binary_erosion(sub_mask)
    perimeter = float(boundary.sum())
    circ = float("nan")
    if perimeter > 0:
        circ = float(4 * math.pi * mom["area"] / (perimeter * perimeter))

    halo = largest_halo_mask(sub_r, sub_g, sub_b, sub_mask)
    halo_area = float(halo.sum())
    if halo.any():
        # mean radius of halo pixels (outer glow scale)
        hy, hx = np.where(halo)
        halo_r = float(np.mean(np.hypot(hx - mom["cx"], hy - mom["cy"])))
    else:
        halo_r = float("nan")

    flux = float(sub_int[sub_mask].sum())
    peak = float(sub_int[sub_mask].max()) if sub_mask.any() else float("nan")

    metrics = {
        "cx": cx,
        "cy": cy,
        "geo_cx": geo_cx,
        "geo_cy": geo_cy,
        "peak_x": px + x0,
        "peak_y": py + y0,
        "area": mom["area"],
        "eq_radius": eq_radius,
        "sigma_x": mom["sigma_x"],
        "sigma_y": mom["sigma_y"],
        "sigma_maj": mom["sigma_maj"],
        "sigma_min": mom["sigma_min"],
        "orientation_deg": mom["orientation_deg"],
        "ellipticity": mom["ellipticity"],
        "radius_mean": r_mean,
        "radius_std": r_std,
        "radius_min": r_min,
        "radius_max": r_max,
        "boundary_roughness": roughness,
        "circularity": circ,
        "perimeter": perimeter,
        "halo_area": halo_area,
        "halo_radius": halo_r,
        "core_flux": flux,
        "peak_intensity": peak,
    }
    extras = {
        "roi": roi,
        "mask": mask,
        "radii": radii,
        "cx_local": mom["cx"],
        "cy_local": mom["cy"],
        "sigma_maj": mom["sigma_maj"],
        "sigma_min": mom["sigma_min"],
        "orientation_deg": mom["orientation_deg"],
        "halo": halo,
    }
    return metrics, roi, extras


def annotate(rgb: np.ndarray, metrics: dict, extras: dict, title: str, out_path: Path):
    y0, y1, x0, x1 = extras["roi"]
    crop = rgb[y0:y1, x0:x1].copy()
    mask = extras["mask"][y0:y1, x0:x1]
    halo = extras.get("halo")

    fig, axes = plt.subplots(1, 3, figsize=(15.2, 5.4), layout="constrained")

    ax = axes[0]
    ax.imshow(crop)
    ys, xs = np.where(mask & ~ndimage.binary_erosion(mask))
    if len(xs):
        ax.plot(xs, ys, ".", color="#00e5ff", markersize=0.4, alpha=0.55)
    cx = metrics["cx"] - x0
    cy = metrics["cy"] - y0
    ax.plot([cx], [cy], marker="+", color="yellow", markersize=14, markeredgewidth=2.0)
    # principal axes
    ang = math.radians(extras["orientation_deg"])
    for sig, col in ((extras["sigma_maj"], "yellow"), (extras["sigma_min"], "white")):
        dx = sig * 2 * math.cos(ang)
        dy = sig * 2 * math.sin(ang)
        ax.plot([cx - dx, cx + dx], [cy - dy, cy + dy], color=col, lw=1.2, alpha=0.9)
        ang += math.pi / 2
    if extras["radii"] is not None:
        th = np.linspace(-np.pi, np.pi, len(extras["radii"]), endpoint=False)
        ax.plot(
            cx + extras["radii"] * np.cos(th),
            cy + extras["radii"] * np.sin(th),
            color="#7CFF6B",
            lw=1.0,
            alpha=0.85,
        )
    ax.set_title("Core contour + COM + axes", loc="left", fontsize=10, fontweight="bold")
    ax.set_axis_off()

    ax = axes[1]
    vis = crop.copy()
    # tint halo
    if halo is not None and halo.any():
        overlay = vis.astype(np.float32)
        overlay[halo] = overlay[halo] * 0.55 + np.array([0, 80, 255], dtype=np.float32)
        vis = np.clip(overlay, 0, 255).astype(np.uint8)
    ax.imshow(vis)
    ax.plot([cx], [cy], marker="+", color="yellow", markersize=12, markeredgewidth=1.8)
    ax.set_title("Halo (blue tint) vs core", loc="left", fontsize=10, fontweight="bold")
    ax.set_axis_off()

    ax = axes[2]
    if extras["radii"] is not None:
        th = np.linspace(-180, 180, len(extras["radii"]), endpoint=False)
        ax.plot(th, extras["radii"], color="#d62728", lw=1.6)
        ax.axhline(metrics["radius_mean"], color="#444", ls="--", lw=1, label="mean r")
        ax.fill_between(
            th,
            metrics["radius_mean"] - metrics["radius_std"],
            metrics["radius_mean"] + metrics["radius_std"],
            color="#d62728",
            alpha=0.15,
            label="±1σ",
        )
        ax.set_xlabel("Angle (deg, 0 = +x)")
        ax.set_ylabel("Radius (px)")
        ax.legend(frameon=False, fontsize=8)
        ax.set_title(
            f"Boundary r(θ)   σ={metrics['radius_std']:.2f}px  rough={metrics['boundary_roughness']:.2f}px",
            loc="left",
            fontsize=10,
            fontweight="bold",
        )
        ax.grid(True, ls=":", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    else:
        ax.set_axis_off()
        ax.set_title("No contour", loc="left")

    fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_timeseries(rows: list[dict], stem: str, out_path: Path):
    if not rows:
        return
    t = np.array([r["t"] for r in rows])
    cx0, cy0 = rows[0]["cx"], rows[0]["cy"]
    dx = np.array([r["cx"] - cx0 for r in rows])
    dy = np.array([r["cy"] - cy0 for r in rows])
    dr = np.hypot(dx, dy)

    series = [
        ("Δx from frame 0 (px)", dx, "#1f77b4"),
        ("Δy from frame 0 (px)", dy, "#d62728"),
        ("Radial displacement (px)", dr, "#9467bd"),
        ("Core area (px²)", np.array([r["area"] for r in rows]), "#2ca02c"),
        ("Boundary radius σ (px)", np.array([r["radius_std"] for r in rows]), "#ff7f0e"),
        ("Boundary roughness (px)", np.array([r["boundary_roughness"] for r in rows]), "#8c564b"),
        ("Ellipticity", np.array([r["ellipticity"] for r in rows]), "#17becf"),
        ("Orientation (deg)", np.array([r["orientation_deg"] for r in rows]), "#e377c2"),
        ("Eq. radius (px)", np.array([r["eq_radius"] for r in rows]), "#bcbd22"),
        ("Core flux (a.u.)", np.array([r["core_flux"] for r in rows]), "#7f7f7f"),
    ]

    n = len(series)
    fig, axes = plt.subplots(n, 1, sharex=True, figsize=(12, 1.55 * n + 0.8), layout="constrained")
    for ax, (label, y, color) in zip(axes, series):
        ax.plot(t, y, color=color, lw=1.25)
        ax.set_ylabel(label, fontsize=8)
        ax.grid(True, ls=":", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"Laser-spot metrics — {stem}", fontsize=13, fontweight="bold")
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def write_csv(rows: list[dict], path: Path):
    if not rows:
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def decode_frames(path: Path):
    """Yield (t_seconds, rgb_ndarray) from a video file."""
    import av

    # raw annex-B often needs format='h264'
    opts = {}
    if path.suffix.lower() in {".h264", ".264"}:
        container = av.open(str(path), format="h264")
    else:
        container = av.open(str(path))

    stream = container.streams.video[0]
    fps = float(stream.average_rate) if stream.average_rate else None
    if fps is None or fps <= 1e-3:
        fps = 30.0

    for i, frame in enumerate(container.decode(video=0)):
        rgb = frame.to_ndarray(format="rgb24")
        if frame.time is not None:
            t = float(frame.time)
        elif frame.pts is not None and stream.time_base is not None:
            t = float(frame.pts * stream.time_base)
        else:
            t = i / fps
        yield t, rgb
    container.close()


def process_video(path: Path) -> list[dict]:
    print(f"Processing {path} ...", flush=True)
    rows = []
    roi = None
    extras0 = None
    rgb0 = None
    metrics0 = None
    n_fail = 0
    for i, (t, rgb) in enumerate(decode_frames(path)):
        metrics, roi, extras = analyze_frame(rgb, roi=roi)
        if metrics is None:
            n_fail += 1
            continue
        rec = {"frame": i, "t": t, **metrics}
        rows.append(rec)
        if extras0 is None:
            extras0, rgb0, metrics0 = extras, rgb, metrics
        if i % 50 == 0:
            print(f"  frame {i}  t={t:.2f}s  cx={metrics['cx']:.2f} cy={metrics['cy']:.2f}", flush=True)
    print(f"  kept {len(rows)} frames, failed {n_fail}", flush=True)

    stem = path.stem
    write_csv(rows, OUT / f"metrics_{stem}.csv")
    plot_timeseries(rows, stem, OUT / f"timeseries_{stem}.png")
    if extras0 is not None:
        annotate(rgb0, metrics0, extras0, f"{stem} — first tracked frame", OUT / f"overlay_{stem}.png")
    return rows


def process_still(path: Path):
    rgb = np.array(Image.open(path).convert("RGB"))
    metrics, roi, extras = analyze_frame(rgb)
    if metrics is None:
        raise RuntimeError("Could not find a laser core in the still image")
    annotate(
        rgb,
        metrics,
        extras,
        "Still frame — core, halo, boundary radius",
        OUT / "summary_overlay.png",
    )
    # single-row csv so the schema is documented
    write_csv([{"frame": 0, "t": 0.0, **metrics}], OUT / "metrics_still.csv")
    return metrics


def plot_comparison(all_runs: dict[str, list[dict]], out_path: Path):
    if not all_runs:
        return
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(12, 8.2), layout="constrained")
    colors = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#17becf"]
    for i, (name, rows) in enumerate(all_runs.items()):
        if not rows:
            continue
        color = colors[i % len(colors)]
        t = np.array([r["t"] for r in rows])
        cx0, cy0 = rows[0]["cx"], rows[0]["cy"]
        dx = np.array([r["cx"] - cx0 for r in rows])
        dy = np.array([r["cy"] - cy0 for r in rows])
        dr = np.hypot(dx, dy)
        rstd = np.array([r["radius_std"] for r in rows])
        axes[0].plot(t, dx, color=color, lw=1.2, label=name)
        axes[1].plot(t, dy, color=color, lw=1.2, label=name)
        axes[2].plot(t, rstd, color=color, lw=1.2, label=name)
    axes[0].set_ylabel("Δx (px)")
    axes[1].set_ylabel("Δy (px)")
    axes[2].set_ylabel("Boundary σ (px)")
    axes[2].set_xlabel("Time (s)")
    for ax in axes:
        ax.grid(True, ls=":", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(frameon=False, fontsize=8, ncol=3)
    fig.suptitle("Beam metrics across runs (each run referenced to its own first frame)", fontsize=13, fontweight="bold")
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("=== still-image detector check ===", flush=True)
    if STILL.exists():
        m = process_still(STILL)
        print(
            "still COM=({cx:.2f},{cy:.2f}) area={area:.0f} "
            "r_mean={radius_mean:.2f} r_std={radius_std:.2f} "
            "ellip={ellipticity:.4f} rough={boundary_roughness:.2f}".format(**m)
        )
    videos = find_videos()
    print(f"videos found: {len(videos)}")
    for v in videos:
        print(" ", v)
    runs = {}
    for v in videos:
        runs[v.stem] = process_video(v)
    if runs:
        plot_comparison(runs, OUT / "comparison.png")
    else:
        print(
            "No videos on disk. Put the .h264 files in artifacts/videos/ "
            "and re-run: python3 /home/workdir/artifacts/analyze_beam.py"
        )
    return 0 if True else 1


if __name__ == "__main__":
    sys.exit(main())
