#!/usr/bin/env python3
"""
graphs_loadgen.py - PDF graphs for the synthetic-load experiment (loadgen.py + autoscaler).

Inputs (same folder by default):
    loadgen.csv   timestamp,users,requests,requests_per_s,avg_response_ms,errors   (every 10 s)
    metrics.csv   autoscaler output                                                 (every 10 s)
Both files have clock times, so they are matched by time directly (no start time needed).

Usage:
    python3 graphs_loadgen.py
    python3 graphs_loadgen.py --loadgen loadgen.csv --metrics metrics.csv --out graphs_loadgen_pdf

Output (graphs_loadgen_pdf/):
  Over time (x = minutes since start)
    01_workload_users.pdf       synthetic users (the offered load)
    02_throughput.pdf           requests per second answered
    03_response_time.pdf        average response time (ms)
    04_avg_cpu.pdf              average CPU per container + 70 % / 30 % lines
    05_cpu_per_container.pdf    app1..app4
    06_replicas.pdf             running containers, scale-out / scale-in marked
    07_errors.pdf               failed requests per 10 s
    08_memory.pdf               average memory
    09_overview.pdf             users + throughput + response time + CPU + replicas stacked
  By load level (x = number of users)
    10_by_users_throughput.pdf
    11_by_users_response_time.pdf
    12_by_users_cpu.pdf
    13_by_users_replicas.pdf
    14_by_users_overview.pdf
  plus matched.csv (each metrics row with the loadgen values of the same 10 s) and by_users.csv
"""
import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TS = "%d-%m-%Y %H:%M:%S"
BLUE, GREEN, RESP, ORANGE, PURPLE, RED, GREY = (
    "#1f77b4", "#2b8a3e", "#c2255c", "#e8590c", "#6741d9", "#c92a2a", "#868e96")
APP_COLORS = ["#1f77b4", "#2b8a3e", "#e8a200", "#d6336c"]


def read(path):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        r["t"] = datetime.strptime(r["timestamp"], TS)
    return rows


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
    fig.savefig(os.path.join(out, name))
    plt.close(fig)
    print("saved", os.path.join(out, name))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--loadgen", default="loadgen.csv")
    p.add_argument("--metrics", default="metrics.csv")
    p.add_argument("--out", default="graphs_loadgen_pdf")
    a = p.parse_args()

    lg, mt = read(a.loadgen), read(a.metrics)
    t0 = min(lg[0]["t"], mt[0]["t"])
    mins = lambda t: (t - t0).total_seconds() / 60
    os.makedirs(a.out, exist_ok=True)
    XL = "Time (minutes since start)"

    # loadgen series
    lx = [mins(r["t"]) for r in lg]
    users = [int(r["users"]) for r in lg]
    rps = [float(r["requests_per_s"]) for r in lg]
    resp = [float(r["avg_response_ms"]) for r in lg]
    errs = [int(r["errors"]) for r in lg]
    # metrics series
    mx = [mins(r["t"]) for r in mt]
    cpu = [float(r["avg_cpu"]) for r in mt]
    mem = [float(r["avg_memory"]) for r in mt]
    cnt = [int(r["container_count"]) for r in mt]
    x_end = max(lx[-1], mx[-1])

    # match: each metrics row gets the loadgen row whose 10 s window contains it
    for r in mt:
        later = [g for g in lg if g["t"] >= r["t"]]
        g = later[0] if later and (later[0]["t"] - r["t"]).total_seconds() <= 12 else None
        r["users"] = int(g["users"]) if g else 0
        r["rps"] = float(g["requests_per_s"]) if g else 0.0
        r["resp"] = float(g["avg_response_ms"]) if g else float("nan")
        r["errors"] = int(g["errors"]) if g else 0
        r["phase"] = "load" if g else "no load"
    with open(os.path.join(a.out, "matched.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "minute", "users", "requests_per_s", "avg_response_ms", "errors",
                    "container_count", "avg_cpu", "avg_memory", "action", "phase"])
        for r in mt:
            w.writerow([r["timestamp"], f"{mins(r['t']):.2f}", r["users"], r["rps"], r["resp"], r["errors"],
                        r["container_count"], r["avg_cpu"], r["avg_memory"], r["action"], r["phase"]])

    # scaling events for markers
    events = [(mx[i], "out" if cnt[i] > cnt[i - 1] else "in") for i in range(1, len(cnt)) if cnt[i] != cnt[i - 1]]

    def mark(ax):
        for x, kind in events:
            ax.axvline(x, color=GREEN if kind == "out" else RED, lw=0.8, ls=":", alpha=0.8)

    # ---------- over time
    def single(name, title, ylabel, plot):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        plot(ax)
        mark(ax)
        style(ax, title, ylabel, XL)
        save(fig, a.out, name)

    single("01_workload_users.pdf", "Workload (synthetic users)", "Concurrent users",
           lambda ax: ax.step(lx, users, where="pre", color=BLUE, lw=1.8))
    single("02_throughput.pdf", "Throughput", "Requests per second",
           lambda ax: (ax.plot(lx, rps, color=GREEN, lw=1.8), ax.set_ylim(bottom=0)))
    single("03_response_time.pdf", "Average response time", "Milliseconds",
           lambda ax: (ax.plot(lx, resp, color=RESP, lw=1.8, marker="o", ms=3), ax.set_ylim(bottom=0)))

    def cpu_plot(ax):
        ax.plot(mx, cpu, color=ORANGE, lw=1.8)
        thresholds(ax, x_end)
        ax.set_ylim(0, 115)
    single("04_avg_cpu.pdf", "Average CPU utilization of containers", "CPU (% of 1 core)", cpu_plot)

    def apps_plot(ax):
        for k, c in zip(range(1, 5), APP_COLORS):
            pts = [(mins(r["t"]), float(r[f"app{k}_cpu"])) for r in mt if r.get(f"app{k}_cpu")]
            if pts:
                ax.plot([p_[0] for p_ in pts], [p_[1] for p_ in pts], color=c, lw=1.4, label=f"app{k}")
        thresholds(ax, x_end)
        ax.set_ylim(0, 115)
        ax.legend(frameon=False, ncol=4, loc="lower center")
    single("05_cpu_per_container.pdf", "CPU utilization per container", "CPU (% of 1 core)", apps_plot)

    def rep_plot(ax):
        ax.step(mx, cnt, where="post", color=PURPLE, lw=2)
        ax.set_ylim(0, 4.6)
        ax.set_yticks([0, 1, 2, 3, 4])
    single("06_replicas.pdf", "Running containers (replicas)", "Containers", rep_plot)
    single("07_errors.pdf", "Failed requests", "Errors per 10 s",
           lambda ax: (ax.bar(lx, errs, width=0.12, color=RED), ax.set_ylim(0, max(max(errs), 1) + 1)))
    single("08_memory.pdf", "Average memory utilization of containers", "Memory (% of 1 GB)",
           lambda ax: (ax.plot(mx, mem, color=GREEN, lw=1.8), ax.set_ylim(bottom=0)))

    # ---------- overview
    fig, axs = plt.subplots(5, 1, figsize=(9, 15), sharex=True)
    axs[0].step(lx, users, where="pre", color=BLUE, lw=1.8)
    style(axs[0], "Workload (synthetic users)", "Users", None)
    axs[1].plot(lx, rps, color=GREEN, lw=1.8); axs[1].set_ylim(bottom=0)
    style(axs[1], "Throughput", "Requests / s", None)
    axs[2].plot(lx, resp, color=RESP, lw=1.8); axs[2].set_ylim(bottom=0)
    style(axs[2], "Average response time", "ms", None)
    axs[3].plot(mx, cpu, color=ORANGE, lw=1.8); thresholds(axs[3], x_end); axs[3].set_ylim(0, 115)
    style(axs[3], "Average CPU", "CPU %", None)
    axs[4].step(mx, cnt, where="post", color=PURPLE, lw=2)
    axs[4].set_ylim(0, 4.6); axs[4].set_yticks([0, 1, 2, 3, 4])
    style(axs[4], "Replicas", "Containers", XL)
    for ax in axs:
        mark(ax)
    save(fig, a.out, "09_overview.pdf")

    # ---------- by users (only rows with load)
    grp = defaultdict(lambda: {"rps": [], "resp": [], "cpu": [], "cnt": []})
    for g in lg:
        if int(g["users"]) > 0:
            grp[int(g["users"])]["rps"].append(float(g["requests_per_s"]))
            grp[int(g["users"])]["resp"].append(float(g["avg_response_ms"]))
    for r in mt:
        if r["phase"] == "load" and r["users"] > 0:
            grp[r["users"]]["cpu"].append(float(r["avg_cpu"]))
            grp[r["users"]]["cnt"].append(int(r["container_count"]))
    levels = sorted(grp)
    xs = list(range(len(levels)))
    st = lambda v: (sum(v) / len(v), min(v), max(v)) if v else (0, 0, 0)
    S = {u: {k: st(v) for k, v in grp[u].items()} for u in levels}

    with open(os.path.join(a.out, "by_users.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["users", "avg_requests_per_s", "avg_response_ms", "avg_cpu", "avg_containers", "max_containers"])
        for u in levels:
            w.writerow([u, f"{S[u]['rps'][0]:.0f}", f"{S[u]['resp'][0]:.2f}", f"{S[u]['cpu'][0]:.1f}",
                        f"{S[u]['cnt'][0]:.2f}", S[u]["cnt"][2]])

    XU = "Concurrent synthetic users"

    def errline(ax, key, color, fmt):
        m = [S[u][key][0] for u in levels]
        ax.errorbar(xs, m, yerr=[[S[u][key][0] - S[u][key][1] for u in levels],
                                 [S[u][key][2] - S[u][key][0] for u in levels]],
                    color=color, lw=1.8, marker="o", ms=6, capsize=4, elinewidth=1)
        for xi, v in zip(xs, m):
            ax.annotate(fmt.format(v), (xi, v), xytext=(7, 4), textcoords="offset points", fontsize=8)

    def uaxes(ax, title, ylabel):
        ax.set_xticks(xs)
        ax.set_xticklabels([str(u) for u in levels])
        style(ax, title, ylabel, XU)

    def rep_bars(ax):
        ax.bar(xs, [S[u]["cnt"][2] for u in levels], 0.55, color=PURPLE, alpha=0.25, label="maximum")
        ax.bar(xs, [S[u]["cnt"][0] for u in levels], 0.55, color=PURPLE, label="average")
        ax.set_ylim(0, 4.6); ax.set_yticks([0, 1, 2, 3, 4])
        ax.legend(frameon=False, loc="upper left")

    for name, key, color, title, ylabel, fmt in [
            ("10_by_users_throughput.pdf", "rps", GREEN, "Throughput vs users", "Requests per second", "{:.0f}"),
            ("11_by_users_response_time.pdf", "resp", RESP, "Response time vs users", "Milliseconds", "{:.1f}"),
            ("12_by_users_cpu.pdf", "cpu", ORANGE, "Average CPU vs users", "CPU (% of 1 core)", "{:.0f} %")]:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        errline(ax, key, color, fmt)
        if key == "cpu":
            thresholds(ax, len(levels) - 1); ax.set_ylim(0, 115)
        else:
            ax.set_ylim(bottom=0)
        uaxes(ax, title, ylabel)
        save(fig, a.out, name)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    rep_bars(ax)
    uaxes(ax, "Running containers vs users", "Containers")
    save(fig, a.out, "13_by_users_replicas.pdf")

    fig, axs = plt.subplots(2, 2, figsize=(13, 9))
    errline(axs[0][0], "rps", GREEN, "{:.0f}"); axs[0][0].set_ylim(bottom=0)
    uaxes(axs[0][0], "Throughput", "req/s")
    errline(axs[0][1], "resp", RESP, "{:.1f}"); axs[0][1].set_ylim(bottom=0)
    uaxes(axs[0][1], "Response time", "ms")
    errline(axs[1][0], "cpu", ORANGE, "{:.0f}"); thresholds(axs[1][0], len(levels) - 1); axs[1][0].set_ylim(0, 115)
    uaxes(axs[1][0], "Average CPU", "CPU %")
    rep_bars(axs[1][1])
    uaxes(axs[1][1], "Containers", "Containers")
    save(fig, a.out, "14_by_users_overview.pdf")


if __name__ == "__main__":
    main()
