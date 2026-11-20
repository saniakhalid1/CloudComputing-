#!/usr/bin/env python3
"""
Graphs from httperf output (output.txt) + autoscaler metrics (metrics.csv).

  1_response_time_and_cpu.png      response time  |  average CPU          (over time)
  2_response_2xx_cpu.png           response time  |  2xx replies/s  |  average CPU
  3_cpu_and_replicas.png           average CPU (+ per container)  |  replicas

httperf prints no clock time, so each 30 s run is placed one after another,
starting at the first timestamp of metrics.csv (change with --start "HH:MM:SS").

Usage:
    python3 make_graphs.py                                   # output.txt + metrics.csv here
    python3 make_graphs.py --httperf output.txt --metrics metrics.csv --out graphs
    python3 make_graphs.py --start 20:37:19
"""
import argparse
import csv
import os
import re
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# one colour per metric, the same in every figure
C_RESP, C_CPU, C_2XX, C_REPL = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
C_APPS = ["#2a78d6", "#1baf7a", "#eda100", "#e87ba4"]   # app1..app4
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e6e6e6"


# ------------------------------------------------------------------ read httperf
def read_httperf(path):
    """One entry per httperf run: rate, duration, req/s, response ms, 2xx, errors."""
    text = open(path, errors="ignore").read()
    runs = []
    for block in re.split(r"(?m)^(?=httperf --)", text):
        rate = re.search(r"--rate[= ](\d+(?:\.\d+)?)", block)
        dur = re.search(r"test-duration ([\d.]+) s", block)
        if not (rate and dur):
            continue                                  # incomplete run (stopped early)
        req = re.search(r"Request rate: ([\d.]+) req/s", block)
        resp = re.search(r"Reply time \[ms\]: response ([\d.]+)", block)
        ok = re.search(r"2xx=(\d+)", block)
        err = re.search(r"Errors: total (\d+)", block)
        runs.append({
            "rate": float(rate.group(1)),
            "duration": float(dur.group(1)),
            "req_s": float(req.group(1)) if req else 0.0,
            "resp_ms": float(resp.group(1)) if resp else float("nan"),
            "ok": int(ok.group(1)) if ok else 0,
            "errors": int(err.group(1)) if err else 0,
        })
    return runs


# ------------------------------------------------------------------ read metrics.csv
def read_metrics(path):
    rows = []
    for r in csv.DictReader(open(path)):
        if not r.get("timestamp"):
            continue
        row = {"t": datetime.strptime(r["timestamp"], "%d-%m-%Y %H:%M:%S"),
               "count": int(r["container_count"]),
               "cpu": float(r["avg_cpu"]),
               "mem": float(r["avg_memory"]),
               "apps": {}}
        for i in range(1, 5):
            v = r.get(f"app{i}_cpu", "")
            if v not in ("", None):
                row["apps"][f"app{i}"] = float(v)
        rows.append(row)
    return rows


# ------------------------------------------------------------------ helpers
def place_runs(runs, start):
    """Give every httperf run a start/end time, one run after the other."""
    t = start
    for r in runs:
        r["start"] = t
        r["end"] = t + timedelta(seconds=r["duration"])
        r["mid"] = t + timedelta(seconds=r["duration"] / 2)
        r["ok_s"] = r["ok"] / r["duration"]
        t = r["end"]
    return runs


def style(ax, title, ylabel):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK)
    ax.set_ylabel(ylabel, color=INK)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED)


def time_axis(ax):
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.set_xlabel("Time (HH:MM)", color=INK)


def stepped(runs, key):
    """x, y for a step line: each run's value holds for its whole 30 s."""
    xs, ys = [], []
    for r in runs:
        xs += [r["start"], r["end"]]
        ys += [r[key], r[key]]
    return xs, ys


def cpu_panel(ax, metrics, per_container=False):
    t = [m["t"] for m in metrics]
    if per_container:
        for i, name in enumerate(["app1", "app2", "app3", "app4"]):
            ys = [m["apps"].get(name, float("nan")) for m in metrics]
            if any(y == y for y in ys):
                ax.plot(t, ys, lw=1.2, color=C_APPS[i], alpha=0.55, label=name)
    ax.plot(t, [m["cpu"] for m in metrics], lw=2, color=C_CPU, label="average CPU")
    ax.axhline(70, color=MUTED, lw=1, ls="--")
    ax.axhline(30, color=MUTED, lw=1, ls=":")
    ax.text(t[0], 71, " scale-out threshold 70 %", color=MUTED, fontsize=8, va="bottom")
    ax.text(t[0], 31, " scale-in threshold 30 %", color=MUTED, fontsize=8, va="bottom")
    ax.set_ylim(0, 105)
    style(ax, "Average CPU of application containers", "CPU (% of 1 core)")
    if per_container:
        ax.legend(frameon=False, fontsize=8, ncol=5, loc="upper right")


def response_panel(ax, runs):
    xs, ys = stepped(runs, "resp_ms")
    ax.plot(xs, ys, lw=2, color=C_RESP)
    ax.set_ylim(bottom=0)
    style(ax, "Average response time (httperf)", "Milliseconds")


def ok_panel(ax, runs):
    xs, ys = stepped(runs, "ok_s")
    ax.fill_between(xs, ys, color=C_2XX, alpha=0.15, lw=0)
    ax.plot(xs, ys, lw=2, color=C_2XX)
    errors = sum(r["errors"] for r in runs)
    ax.text(0.01, 0.95, f"errors (non-2xx / failed): {errors}", transform=ax.transAxes,
            ha="left", va="top", fontsize=9, color=INK)
    ax.set_ylim(bottom=0)
    style(ax, "Successful replies (2xx) per second", "2xx replies / s")


def replicas_panel(ax, metrics):
    t = [m["t"] for m in metrics]
    c = [m["count"] for m in metrics]
    ax.step(t, c, where="post", lw=2, color=C_REPL)
    for i in range(1, len(c)):
        if c[i] != c[i - 1]:
            label = "scale out" if c[i] > c[i - 1] else "scale in"
            ax.annotate(f"{label} {c[i-1]}→{c[i]}", (t[i], c[i]), xytext=(4, 6),
                        textcoords="offset points", fontsize=8, color=INK)
    ax.set_ylim(0, 4.6)
    ax.set_yticks([0, 1, 2, 3, 4])
    style(ax, "Running application containers (replicas)", "Containers")


def save(fig, out, name):
    fig.tight_layout()
    path = os.path.join(out, name)
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print("saved", path)


# ------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--httperf", default="output.txt")
    p.add_argument("--metrics", default="metrics.csv")
    p.add_argument("--out", default="graphs")
    p.add_argument("--start", help='start time of the first httperf run, "HH:MM:SS" '
                                    "(default: first timestamp in metrics.csv)")
    a = p.parse_args()

    metrics = read_metrics(a.metrics)
    runs = read_httperf(a.httperf)
    if not metrics or not runs:
        raise SystemExit("No data found - check the file names")

    start = metrics[0]["t"]
    if a.start:
        h, m, s = (int(x) for x in a.start.split(":"))
        start = start.replace(hour=h, minute=m, second=s)
    place_runs(runs, start)
    os.makedirs(a.out, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "figure.facecolor": "white"})

    print(f"{len(runs)} httperf runs ({runs[0]['start']:%H:%M:%S} - {runs[-1]['end']:%H:%M:%S}), "
          f"{len(metrics)} metric rows ({metrics[0]['t']:%H:%M:%S} - {metrics[-1]['t']:%H:%M:%S})")

    # 1. response time and CPU over time
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    response_panel(a1, runs)
    cpu_panel(a2, metrics)
    time_axis(a2)
    save(fig, a.out, "1_response_time_and_cpu.png")

    # 2. response time, 2xx replies and CPU over time
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    response_panel(a1, runs)
    ok_panel(a2, runs)
    cpu_panel(a3, metrics)
    time_axis(a3)
    save(fig, a.out, "2_response_2xx_cpu.png")

    # 3. CPU (average + per container) and replicas over time
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    cpu_panel(a1, metrics, per_container=True)
    replicas_panel(a2, metrics)
    time_axis(a2)
    save(fig, a.out, "3_cpu_and_replicas.png")


if __name__ == "__main__":
    main()
