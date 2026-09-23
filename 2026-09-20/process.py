#!/usr/bin/python3

###########################################################################
#
# name          : process.py
#
# purpose       : process data
#
# usage         : python3 process.py
#
# description   : Load experiment traces from data.json and write
#                 histograms of the "value" field plus stacked time series:
#                   - histograms.png          : overlapping control (top) and
#                     voltage (bottom) on a shared x-scale
#                   - control.png             : one stacked histogram per control run
#                   - voltage.png             : one stacked histogram per voltage run
#                   - control_timeseries.png  : value vs time, stacked control runs
#                   - voltage_timeseries.png  : value vs time, stacked voltage runs
#                 Experiment colors are fixed across all figures.
#
###########################################################################

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np


DATA_PATH = Path(__file__).resolve().parent / "data.json"
OUTPUT_OVERLAP = Path(__file__).resolve().parent / "histograms.png"
OUTPUT_CONTROL = Path(__file__).resolve().parent / "control.png"
OUTPUT_VOLTAGE = Path(__file__).resolve().parent / "voltage.png"
OUTPUT_CONTROL_TS = Path(__file__).resolve().parent / "control_timeseries.png"
OUTPUT_VOLTAGE_TS = Path(__file__).resolve().parent / "voltage_timeseries.png"

CONTROL_COLORS = ["#1f77b4", "#2ca02c", "#17becf", "#9467bd", "#8c564b"]
VOLTAGE_COLORS = ["#d62728", "#ff7f0e", "#e377c2", "#bcbd22"]


def _parse_trace(row):
    times = [
        datetime.fromtimestamp(int(point["timestamp"]), tz=timezone.utc)
        for point in row
    ]
    values = [point["value"] for point in row]
    return times, values


def load_experiments(path=DATA_PATH):
    with open(path, "r") as f:
        data = json.load(f)

    control = [_parse_trace(row) for row in data["control"]]
    voltage = [_parse_trace(row) for row in data["voltage"]]
    return control, voltage


def values_only(traces):
    return [values for _times, values in traces]


def value_range(control, voltage):
    all_values = [v for _t, vals in control for v in vals] + [v for _t, vals in voltage for v in vals]
    return min(all_values), max(all_values)


def style_axis(ax):
    ax.grid(axis="y", linestyle=":", alpha=0.45)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_one_histogram(ax, values, bins, color, label):
    counts, _, _ = ax.hist(
        values,
        bins=bins,
        color=color,
        alpha=0.45,
        edgecolor=color,
        linewidth=1.4,
        histtype="stepfilled",
        label=label,
    )
    ax.hist(
        values,
        bins=bins,
        color=color,
        histtype="step",
        linewidth=1.6,
    )
    ymax = counts.max() if len(counts) else 0
    if ymax:
        ax.set_ylim(0, ymax * 1.12)
    return ymax


def plot_overlapping(ax, experiments, bins, colors, title, group_label):
    ymax = 0
    for i, values in enumerate(experiments):
        peak = plot_one_histogram(
            ax,
            values,
            bins,
            colors[i],
            label=f"{group_label} {i + 1}  (n={len(values)})",
        )
        ymax = max(ymax, peak)

    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=8)
    ax.set_ylabel("Count")
    ax.legend(frameon=False, fontsize=8, loc="upper right", ncol=1)
    style_axis(ax)
    if ymax:
        ax.set_ylim(0, ymax * 1.12)


def plot_overlap_figure(control, voltage, bins, vmin, vmax, output_path=OUTPUT_OVERLAP):
    fig, (ax_ctrl, ax_volt) = plt.subplots(
        nrows=2,
        ncols=1,
        sharex=True,
        figsize=(12, 8),
        gridspec_kw={"hspace": 0.28},
        layout="constrained",
    )

    plot_overlapping(
        ax_ctrl,
        control,
        bins,
        CONTROL_COLORS,
        title="Control experiments",
        group_label="Control",
    )
    plot_overlapping(
        ax_volt,
        voltage,
        bins,
        VOLTAGE_COLORS,
        title="Voltage experiments",
        group_label="Voltage",
    )

    ax_volt.set_xlabel("Value")
    ax_ctrl.set_xlim(vmin, vmax)
    fig.suptitle("Overlapping value histograms by experiment group", fontsize=14, fontweight="bold")
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_stacked_figure(experiments, colors, group_label, title, bins, vmin, vmax, output_path):
    n = len(experiments)
    fig, axes = plt.subplots(
        nrows=n,
        ncols=1,
        sharex=True,
        figsize=(12, 2.15 * n + 0.8),
        layout="constrained",
    )
    if n == 1:
        axes = [axes]

    for i, (ax, values) in enumerate(zip(axes, experiments)):
        plot_one_histogram(
            ax,
            values,
            bins,
            colors[i],
            label=f"{group_label} {i + 1}  (n={len(values)})",
        )
        ax.set_ylabel("Count")
        ax.legend(frameon=False, fontsize=8, loc="upper right")
        style_axis(ax)
        ax.set_title(f"{group_label} experiment {i + 1}", loc="left", fontsize=11, fontweight="bold", pad=4)

    axes[0].set_xlim(vmin, vmax)
    axes[-1].set_xlabel("Value")
    fig.suptitle(title, fontsize=14, fontweight="bold")
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_one_timeseries(ax, times, values, color, label):
    ax.plot(times, values, color=color, linewidth=1.35, marker="o", markersize=2.2, label=label)
    ax.axhline(0, color="#888888", linewidth=0.6, alpha=0.5)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())


def plot_stacked_timeseries(traces, colors, group_label, title, vmin, vmax, output_path):
    n = len(traces)
    fig, axes = plt.subplots(
        nrows=n,
        ncols=1,
        sharex=False,
        figsize=(12, 2.15 * n + 0.8),
        layout="constrained",
    )
    if n == 1:
        axes = [axes]

    for i, (ax, (times, values)) in enumerate(zip(axes, traces)):
        plot_one_timeseries(
            ax,
            times,
            values,
            colors[i],
            label=f"{group_label} {i + 1}  (n={len(values)})",
        )
        ax.set_ylabel("Value")
        ax.set_ylim(vmin, vmax)
        ax.legend(frameon=False, fontsize=8, loc="upper right")
        style_axis(ax)
        ax.set_title(f"{group_label} experiment {i + 1}", loc="left", fontsize=11, fontweight="bold", pad=4)
        ax.grid(axis="x", linestyle=":", alpha=0.35)

    axes[-1].set_xlabel("Time (UTC)")
    fig.suptitle(title, fontsize=14, fontweight="bold")
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def main():
    control, voltage = load_experiments()
    control_values = values_only(control)
    voltage_values = values_only(voltage)
    vmin, vmax = value_range(control, voltage)
    bins = np.linspace(vmin, vmax, 45)

    overlap_path = plot_overlap_figure(control_values, voltage_values, bins, vmin, vmax)
    control_path = plot_stacked_figure(
        control_values,
        CONTROL_COLORS,
        "Control",
        "Control experiments",
        bins,
        vmin,
        vmax,
        OUTPUT_CONTROL,
    )
    voltage_path = plot_stacked_figure(
        voltage_values,
        VOLTAGE_COLORS,
        "Voltage",
        "Voltage experiments",
        bins,
        vmin,
        vmax,
        OUTPUT_VOLTAGE,
    )
    control_ts_path = plot_stacked_timeseries(
        control,
        CONTROL_COLORS,
        "Control",
        "Control experiments — value vs time",
        vmin,
        vmax,
        OUTPUT_CONTROL_TS,
    )
    voltage_ts_path = plot_stacked_timeseries(
        voltage,
        VOLTAGE_COLORS,
        "Voltage",
        "Voltage experiments — value vs time",
        vmin,
        vmax,
        OUTPUT_VOLTAGE_TS,
    )

    print(f"Min value: {vmin}")
    print(f"Max value: {vmax}")
    print(f"Wrote {overlap_path}")
    print(f"Wrote {control_path}")
    print(f"Wrote {voltage_path}")
    print(f"Wrote {control_ts_path}")
    print(f"Wrote {voltage_ts_path}")


if __name__ == "__main__":
    main()
