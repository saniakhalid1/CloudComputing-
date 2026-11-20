#!/usr/bin/env python3
"""
graphs.py - all experiment graphs as PDF files.

Inputs (same folder by default):
    httperf_summary.csv  rate,total_requests,processed_requests,unprocessed_requests,avg_reply_time_ms
                         (one row per httperf run of 30 s)
    metrics.csv          autoscaler output (one row every 10 s)

Usage:
    python3 graphs.py --start "13-10-2026 11:52:02"
    python3 graphs.py --summary httperf_summary.csv --metrics metrics.csv --start "13-10-2026 11:52:02" --out graphs_pdf

--start = clock time when the FIRST httperf run started. It is used to put every
10-second metrics row into the right 30-second httperf run. (Default: first metrics row.)

Output (graphs_pdf/):
  Over time (x = run number, 30 s each, like the World Cup workload figure)
    01_workload_rate.pdf          httperf rate (sessions/s) per run (the workload trace)
    02_2xx_replies.pdf            successful 2xx replies per second
    03_response_time.pdf          average reply time (ms)
    04_requests_processed.pdf     total vs processed (2xx) requests x1000, unprocessed
    05_avg_cpu.pdf                average CPU per container, 70 % / 30 % thresholds
    06_cpu_per_container.pdf      app1..app4 CPU
    07_replicas.pdf               number of running containers
    08_memory.pdf                 average memory
    09_overview.pdf               workload + 2xx + response time + CPU + replicas stacked
  By load level (x = rate)
    10_by_rate_response_time.pdf
    11_by_rate_cpu.pdf
    12_by_rate_processed.pdf
    13_by_rate_replicas.pdf
    14_by_rate_overview.pdf
  plus per_run.csv and by_rate.csv with the numbers behind the graphs.
"""
import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STEP = 30                     # seconds per httperf run
TS = "%d-%m-%Y %H:%M:%S"
BLUE, ORANGE, GREEN, RED, PURPLE, GREY = "#1f77b4", "#e8590c", "#2b8a3e", "#c92a2a", "#6741d9", "#868e96"
RESP = "#c2255c"             # response time (magenta-red, different from workload and CPU)
APP_COLORS = ["#1f77b4", "#2b8a3e", "#e8a200", "#d6336c"]


# ------------------------------------------------------------------ data
def load(summary_path, metrics_path, start):
    runs = []
    for r in csv.DictReader(open(summary_path)):
        runs.append({
            "rate": int(float(r["rate"])),
            "total": int(float(r["total_requests"])),
            "processed": int(float(r["processed_requests"])),
            "unprocessed": int(float(r.get("unprocessed_requests") or 0)),
            "resp": float(r["avg_reply_time_ms"]),
            "cpu": [], "count": [], "mem": [], "apps": defaultdict(list),
        })
    rows = list(csv.DictReader(open(metrics_path)))
    if start is None:
        start = datetime.strptime(rows[0]["timestamp"], TS)
    for row in rows:
        i = int((datetime.strptime(row["timestamp"], TS) - start).total_seconds() // STEP)
        if 0 <= i < len(runs):
            r = runs[i]
            r["cpu"].append(float(row["avg_cpu"]))
            r["count"].append(int(row["container_count"]))
            r["mem"].append(float(row["avg_memory"]))
            for k in range(1, 5):
                v = row.get(f"app{k}_cpu", "")
                if v not in ("", None):
                    r["apps"][f"app{k}"].append(float(v))
    nan = float("nan")
    mean = lambda v: sum(v) / len(v) if v else nan
    for r in runs:
        r["cpu_m"], r["mem_m"] = mean(r["cpu"]), mean(r["mem"])
        r["count_m"] = mean(r["count"])
        r["count_max"] = max(r["count"]) if r["count"] else nan
        r["app_m"] = {a: mean(v) for a, v in r["apps"].items()}
        r["failed"] = r["total"] - r["processed"]
    return runs, start


# ------------------------------------------------------------------ style
def style(ax, title, ylabel, xlabel):
    ax.set_title(title, fontweight="bold", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=11)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11)
    ax.grid(True, ls="--", lw=0.6, color="#bbbbbb")
    ax.set_axisbelow(True)


def thresholds(ax, x_right):
    ax.axhline(70, color=GREY, lw=1, ls="--")
    ax.axhline(30, color=GREY, lw=1, ls=":")
    ax.text(x_right, 71, "scale out 70 %", ha="right", va="bottom", fontsize=8, color=GREY)
    ax.text(x_right, 31, "scale in 30 %", ha="right", va="bottom", fontsize=8, color=GREY)


def save(fig, out, name):
    fig.tight_layout()
    fig.savefig(os.path.join(out, name))          # .pdf -> vector PDF
    plt.close(fig)
    print("saved", os.path.join(out, name))


# ------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--summary", default="httperf_summary.csv")
    p.add_argument("--metrics", default="metrics.csv")
    p.add_argument("--start", help='start of the first httperf run, "dd-mm-yyyy HH:MM:SS"')
    p.add_argument("--out", default="graphs_pdf")
    a = p.parse_args()
    start = datetime.strptime(a.start, TS) if a.start else None

    runs, start = load(a.summary, a.metrics, start)
    os.makedirs(a.out, exist_ok=True)
    x = list(range(len(runs)))
    XL = f"Time interval "
    end = start + timedelta(seconds=STEP * len(runs))
    print(f"{len(runs)} httperf runs: {start:%H:%M:%S} -> {end:%H:%M:%S}")

    # ---------- per-run CSV
    with open(os.path.join(a.out, "per_run.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run", "start", "rate", "total_requests", "processed_requests", "failed_requests",
                    "avg_reply_time_ms", "avg_cpu", "avg_containers", "max_containers", "avg_memory"])
        for i, r in enumerate(runs):
            w.writerow([i, (start + timedelta(seconds=STEP * i)).strftime("%H:%M:%S"), r["rate"],
                        r["total"], r["processed"], r["failed"], r["resp"], f"{r['cpu_m']:.2f}",
                        f"{r['count_m']:.2f}", r["count_max"], f"{r['mem_m']:.2f}"])

    col = lambda k: [r[k] for r in runs]

    # ---------- 01 workload (requests x1000) - World Cup style
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, col("rate"), color=BLUE, lw=1.8)
    style(ax, "Workload", "httperf rate (sessions/s)", XL)
    save(fig, a.out, "01_workload_rate.pdf")

    # ---------- 02 workload (rate)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, [v / STEP for v in col("processed")], color=GREEN, lw=1.8)
    ax.set_ylim(bottom=0)
    style(ax, "Successful (2xx) replies", "2xx replies per second", XL)
    save(fig, a.out, "02_2xx_replies.pdf")

    # ---------- 03 response time
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, col("resp"), color=RESP, lw=1.8, marker="o", ms=3)
    style(ax, "Average response time", "Reply time (ms)", XL)
    save(fig, a.out, "03_response_time.pdf")

    # ---------- 04 total vs processed
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, [v / 1000 for v in col("total")], color=GREY, lw=1.8, label="total requests")
    ax.plot(x, [v / 1000 for v in col("processed")], color=GREEN, lw=1.8, ls="--", label="processed (2xx replies)")
    ax.bar(x, [v / 1000 for v in col("failed")], color=RED, alpha=0.7, label="not processed")
    ax.legend(frameon=False)
    style(ax, "Requests sent vs processed", "# of Requests ×1000", XL)
    save(fig, a.out, "04_requests_processed.pdf")

    # ---------- 05 avg CPU
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, col("cpu_m"), color=ORANGE, lw=1.8)
    thresholds(ax, len(runs) - 1)
    ax.set_ylim(0, 110)
    style(ax, "Average CPU utilization of containers", "CPU (% of 1 core)", XL)
    save(fig, a.out, "05_avg_cpu.pdf")

    # ---------- 06 CPU per container
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for k, c in zip(range(1, 5), APP_COLORS):
        ys = [r["app_m"].get(f"app{k}", float("nan")) for r in runs]
        if any(v == v for v in ys):
            ax.plot(x, ys, color=c, lw=1.5, label=f"app{k}")
    thresholds(ax, len(runs) - 1)
    ax.set_ylim(0, 110)
    ax.legend(frameon=False, ncol=4)
    style(ax, "CPU utilization per container", "CPU (% of 1 core)", XL)
    save(fig, a.out, "06_cpu_per_container.pdf")

    # ---------- 07 replicas
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.step(x, col("count_max"), where="post", color=PURPLE, lw=2)
    ax.set_ylim(0, 4.5)
    ax.set_yticks([0, 1, 2, 3, 4])
    style(ax, "Running containers (replicas)", "Containers", XL)
    save(fig, a.out, "07_replicas.pdf")

    # ---------- 08 memory
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, col("mem_m"), color=GREEN, lw=1.8)
    ax.set_ylim(bottom=0)
    style(ax, "Average memory utilization of containers", "Memory (% of 1 GB)", XL)
    save(fig, a.out, "08_memory.pdf")

    # ---------- 09 overview stacked
    fig, axs = plt.subplots(5, 1, figsize=(9, 15), sharex=True)
    axs[0].plot(x, col("rate"), color=BLUE, lw=1.8)
    style(axs[0], "Workload", "Rate (sessions/s)", None)
    axs[1].plot(x, [v / STEP for v in col("processed")], color=GREEN, lw=1.8)
    axs[1].set_ylim(bottom=0)
    style(axs[1], "Successful (2xx) replies", "2xx replies / s", None)
    axs[2].plot(x, col("resp"), color=RESP, lw=1.8)
    style(axs[2], "Average response time", "ms", None)
    axs[3].plot(x, col("cpu_m"), color=ORANGE, lw=1.8)
    thresholds(axs[3], len(runs) - 1)
    axs[3].set_ylim(0, 110)
    style(axs[3], "Average CPU", "CPU %", None)
    axs[4].step(x, col("count_max"), where="post", color=PURPLE, lw=2)
    axs[4].set_ylim(0, 4.5)
    axs[4].set_yticks([0, 1, 2, 3, 4])
    style(axs[4], "Replicas", "Containers", XL)
    save(fig, a.out, "09_overview.pdf")

    # ---------- by rate
    by = defaultdict(list)
    for r in runs:
        by[r["rate"]].append(r)
    rates = sorted(by)
    xr = list(range(len(rates)))
    labels = [str(r) for r in rates]
    XR = "httperf rate (sessions/s)"

    def agg(key, fn=None):
        out = []
        for rate in rates:
            vals = [fn(r) if fn else r[key] for r in by[rate]]
            vals = [v for v in vals if v == v]
            out.append((sum(vals) / len(vals), min(vals), max(vals)) if vals else (0, 0, 0))
        return out

    resp, cpu = agg("resp"), agg("cpu_m")
    ok_pct = agg(None, lambda r: 100 * r["processed"] / r["total"] if r["total"] else float("nan"))
    proc, tot = agg("processed"), agg("total")
    rep_avg, rep_max = agg("count_m"), agg("count_max")

    with open(os.path.join(a.out, "by_rate.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rate", "runs", "avg_reply_time_ms", "avg_cpu", "avg_total_requests",
                    "avg_processed_requests", "processed_pct", "avg_containers", "max_containers"])
        for i, rate in enumerate(rates):
            w.writerow([rate, len(by[rate]), f"{resp[i][0]:.1f}", f"{cpu[i][0]:.1f}", f"{tot[i][0]:.0f}",
                        f"{proc[i][0]:.0f}", f"{ok_pct[i][0]:.2f}", f"{rep_avg[i][0]:.2f}", rep_max[i][2]])

    def errline(ax, data, color, label=None, fmt="{:.1f}"):
        m = [d[0] for d in data]
        ax.errorbar(xr, m, yerr=[[d[0] - d[1] for d in data], [d[2] - d[0] for d in data]],
                    color=color, lw=1.8, marker="o", ms=6, capsize=4, elinewidth=1, label=label)
        for xi, v in zip(xr, m):
            ax.annotate(fmt.format(v), (xi, v), xytext=(7, 4), textcoords="offset points", fontsize=8)

    def rate_axes(ax, title, ylabel):
        ax.set_xticks(xr)
        ax.set_xticklabels(labels)
        style(ax, title, ylabel, XR)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    errline(ax, resp, RESP)
    ax.set_yscale("log")
    rate_axes(ax, "Average response time vs rate", "Reply time (ms, log scale)")
    save(fig, a.out, "10_by_rate_response_time.pdf")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    errline(ax, cpu, ORANGE, fmt="{:.0f} %")
    thresholds(ax, len(rates) - 1)
    ax.set_ylim(0, 115)
    rate_axes(ax, "Average CPU vs rate", "CPU (% of 1 core)")
    save(fig, a.out, "11_by_rate_cpu.pdf")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    w_ = 0.38
    ax.bar([i - w_ / 2 for i in xr], [t[0] / 1000 for t in tot], w_, color=GREY, label="total requests")
    ax.bar([i + w_ / 2 for i in xr], [t[0] / 1000 for t in proc], w_, color=GREEN, label="processed (2xx)")
    for i in xr:
        ax.annotate(f"{ok_pct[i][0]:.2f} %", (i + w_ / 2, proc[i][0] / 1000), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8)
    ax.legend(frameon=False)
    rate_axes(ax, "Requests per run: total vs processed", "# of Requests ×1000")
    save(fig, a.out, "12_by_rate_processed.pdf")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(xr, [m[2] for m in rep_max], 0.55, color=PURPLE, alpha=0.25, label="maximum")
    ax.bar(xr, [m[0] for m in rep_avg], 0.55, color=PURPLE, label="average")
    ax.set_ylim(0, 4.6)
    ax.set_yticks([0, 1, 2, 3, 4])
    ax.legend(frameon=False, loc="upper left")
    rate_axes(ax, "Running containers vs rate", "Containers")
    save(fig, a.out, "13_by_rate_replicas.pdf")

    fig, axs = plt.subplots(2, 2, figsize=(13, 9))
    errline(axs[0][0], resp, RESP); axs[0][0].set_yscale("log")
    rate_axes(axs[0][0], "Response time", "ms (log scale)")
    errline(axs[0][1], cpu, ORANGE, fmt="{:.0f}"); thresholds(axs[0][1], len(rates) - 1)
    axs[0][1].set_ylim(0, 115)
    rate_axes(axs[0][1], "Average CPU", "CPU %")
    axs[1][0].bar([i - w_ / 2 for i in xr], [t[0] / 1000 for t in tot], w_, color=GREY, label="total")
    axs[1][0].bar([i + w_ / 2 for i in xr], [t[0] / 1000 for t in proc], w_, color=GREEN, label="processed (2xx)")
    axs[1][0].legend(frameon=False)
    rate_axes(axs[1][0], "Requests per run", "# Requests ×1000")
    axs[1][1].bar(xr, [m[2] for m in rep_max], 0.55, color=PURPLE, alpha=0.25, label="maximum")
    axs[1][1].bar(xr, [m[0] for m in rep_avg], 0.55, color=PURPLE, label="average")
    axs[1][1].set_ylim(0, 4.6); axs[1][1].set_yticks([0, 1, 2, 3, 4])
    axs[1][1].legend(frameon=False, loc="upper left")
    rate_axes(axs[1][1], "Containers", "Containers")
    save(fig, a.out, "14_by_rate_overview.pdf")


if __name__ == "__main__":
    main()
