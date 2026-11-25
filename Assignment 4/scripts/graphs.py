# ALL graphs for Assignment 4, Milestone 4. One script, no arguments.
#
# Put this file in:   Assignment 4/scripts/graphs.py
# Run it:             cd "Assignment 4/scripts"
#                     python3 graphs.py
#
# It reads the test folders from  Assignment 4/results/  (and from scripts/results/ if db.sh left them there):
#   long_fixed1/  long_hpa/  m4_fixed/  m4_hpa/       (whichever exist)
# and saves the graphs in ONE folder per run:
#   results/graphs/long_fixed1/   results/graphs/long_hpa/   results/graphs/m4_fixed/   results/graphs/m4_hpa/
# Each run folder gets every graph as its own file. All are smooth line graphs; ONLY replicas is a step graph:
#   1_request_rate  2_2xx_per_second  3_response_time  4_replicas  5_pod_cpu  6_host_cpu
#   all_in_one.pdf  (the six graphs on one page)
# m4_fixed/ also gets: graph1_response_time, graph2_pod_cpu, m4_summary.csv
# m4_hpa/   also gets: graph3_autoscaling
import os
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FixedFormatter, NullLocator

SCRIPTS = os.path.dirname(os.path.abspath(__file__))              # Assignment 4/scripts
RESULTS = os.path.normpath(os.path.join(SCRIPTS, "..", "results"))  # Assignment 4/results
GRAPHS = os.path.join(RESULTS, "graphs")                           # Assignment 4/results/graphs

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#ececec", "grid.linewidth": 0.7})
BLUE, GREEN, TEAL, ORANGE, RED, PURPLE = "#2f5bd3", "#1d9a6c", "#0f7f8c", "#e0761f", "#c2334d", "#7a4fbf"
TICKS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]


def find(name):
    """Folder of one test, or None."""
    for d in (os.path.join(RESULTS, name), os.path.join(SCRIPTS, "results", name)):
        if os.path.exists(os.path.join(d, "output.txt")):
            return d
    return None


def steps(folder):
    """One row per load step ('=== ... start=<time>' block) in output.txt."""
    rows = []
    for part in re.split(r"(?m)^=== ", open(os.path.join(folder, "output.txt")).read())[1:]:
        row = {k: int(v) for k, v in (kv.split("=") for kv in part.splitlines()[0].split())}
        resp = re.search(r"Reply time \[ms\]: response ([\d.]+)", part)
        if not resp:                                   # the last 'rate=0' line only marks the end
            continue
        dur = re.search(r"test-duration ([\d.]+) s", part)
        ok = re.search(r"2xx=(\d+)", part)
        bad = re.search(r"4xx=(\d+) 5xx=(\d+)", part)
        err = re.search(r"Errors: total (\d+)", part)
        row["duration"] = float(dur.group(1)) if dur else 60.0
        row["avg_response_ms"] = float(resp.group(1))
        row["ok_replies"] = int(ok.group(1)) if ok else 0
        row["ok_per_s"] = row["ok_replies"] / row["duration"]
        row["errors"] = (int(err.group(1)) if err else 0) + \
                        (int(bad.group(1)) + int(bad.group(2)) if bad else 0)
        rows.append(row)
    return pd.DataFrame(rows)


def log_ms(ax, top):
    """Log scale, but labelled with normal numbers (2, 5, 10 ... 1000 ms)."""
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator(TICKS))
    ax.yaxis.set_major_formatter(FixedFormatter([str(t) for t in TICKS]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_ylim(2, max(10, top * 1.6))


def save(fig, run, name, pdf_only=False):
    folder = os.path.join(GRAPHS, run)
    os.makedirs(folder, exist_ok=True)
    fig.tight_layout()
    if not pdf_only:
        fig.savefig(os.path.join(folder, name + ".png"), dpi=200)
    fig.savefig(os.path.join(folder, name + ".pdf"))
    plt.close(fig)


def changes(series):
    """kubectl top repeats the same number until metrics-server refreshes (~every 60 s).
    Keep only the new readings, so the CPU line is a real line and not a staircase."""
    series = series.round(1)
    return series[series != series.shift()]


def smooth(ax, x, y, color, log=False):
    """Smooth line through the points (monotone cubic, Fritsch-Carlson).
    It passes exactly through every point and never overshoots, so peaks keep their real value."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if log:
        y = np.log10(y)
    if len(x) > 2:
        h = np.diff(x)
        d = np.diff(y) / h
        k = np.zeros_like(y)
        k[0], k[-1] = d[0], d[-1]
        for i in range(1, len(y) - 1):
            if d[i - 1] * d[i] > 0:
                w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                k[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
        xs, ys = [], []
        for i in range(len(x) - 1):
            t = np.linspace(0, 1, 30)
            h00, h10 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t
            h01, h11 = -2 * t**3 + 3 * t**2, t**3 - t**2
            xs.append(x[i] + t * h[i])
            ys.append(h00 * y[i] + h10 * h[i] * k[i] + h01 * y[i + 1] + h11 * h[i] * k[i + 1])
        xs, ys = np.concatenate(xs), np.concatenate(ys)
    else:
        xs, ys = x, y
    if log:
        ys, y = 10 ** ys, 10 ** y
    ax.plot(xs, ys, color=color, lw=2.2)
    ax.plot(x, y, "o", color=color, ms=3.5)


# ===================== timeline of one run =====================
def timeline(name):
    D = find(name)
    if not D:
        return
    s = steps(D)
    t0 = s["start"].min()
    t_end = (s["start"] + s["duration"]).max() + 60
    m = lambda t: (t - t0) / 60                    # seconds -> minutes from the start
    mid = m(s["start"] + s["duration"] / 2)        # one point in the middle of each load step

    pods = pd.read_csv(os.path.join(D, "pods.csv"))
    web = pods[pods["pod"].str.startswith("emi-web") & pods["time"].between(t0 - 5, t_end)]
    web_cpu = changes(web.groupby("time")["cpu_m"].mean())       # request is 100m, so millicores = %
    host = pd.read_csv(os.path.join(D, "host_cpu.csv"))
    host = host[host["time"].between(t0 - 5, t_end)]
    host_smooth = host["host_cpu_pct"].rolling(30, center=True, min_periods=1).mean()   # 30 s average

    def rate(ax):
        smooth(ax, mid, s["rate"], BLUE)
        ax.set_ylabel("Request rate set\n(req/s)")

    def ok(ax):
        smooth(ax, mid, s["ok_per_s"], GREEN)
        ax.set_ylabel("2xx replies\nper second")

    def resp(ax):
        smooth(ax, mid, s["avg_response_ms"], TEAL, log=True)
        log_ms(ax, s["avg_response_ms"].max())
        ax.set_ylabel("Avg response time\n(ms)")

    def replicas(ax):                              # the only step graph
        if "replicas" in s.columns:                # fixed run: replicas that were set
            ax.step(list(m(s["start"])) + [m(t_end)], list(s["replicas"]) + [s["replicas"].iloc[-1]],
                    where="post", color=ORANGE, lw=2)
        else:                                      # HPA run: replicas the HPA reported
            h = pd.read_csv(os.path.join(D, "hpa.csv"))
            h = h[h["time"].between(t0 - 5, t_end)]
            ax.step(m(h["time"]), h["replicas"], where="post", color=ORANGE, lw=2)
        ax.set_yticks(range(0, 7))
        ax.set_ylabel("Web replicas")

    def pod_cpu(ax):
        smooth(ax, m(web_cpu.index), web_cpu.values, RED)
        ax.set_ylabel("Avg web pod CPU\n(% of request)")

    def host_cpu(ax):
        ax.plot(m(host["time"]), host_smooth, color=PURPLE, lw=1.6)
        ax.set_ylabel("Host (machine)\nCPU (%)")

    panels = [("1_request_rate", rate), ("2_2xx_per_second", ok), ("3_response_time", resp),
              ("4_replicas", replicas), ("5_pod_cpu", pod_cpu), ("6_host_cpu", host_cpu)]

    def finish(ax, log=False):
        if not log:
            ax.set_ylim(bottom=0)
        ax.set_xlim(-0.3, m(t_end))
        ax.set_xlabel("Time (min)")

    for fname, draw in panels:                     # each graph as its own file
        fig, ax = plt.subplots(figsize=(10, 3.6))
        draw(ax)
        finish(ax, fname == "3_response_time")
        save(fig, name, fname)

    fig, axes = plt.subplots(6, 1, figsize=(11, 16))   # all six on one page
    for ax, (fname, draw) in zip(axes, panels):
        draw(ax)
        finish(ax, fname == "3_response_time")
    save(fig, name, "all_in_one", pdf_only=True)
    print(f"{name}: {len(s)} load steps, {int(s['errors'].sum())} failed requests "
          f"-> results/graphs/{name}/")


for run in ("long_fixed1", "long_hpa", "m4_fixed", "m4_hpa"):
    timeline(run)

# ===================== Graphs 1 and 2: the 15 fixed runs =====================
FIX = find("m4_fixed")
if FIX:
    f = steps(FIX)
    table = f[["replicas", "rate", "avg_response_ms", "ok_replies", "errors"]]
    table.to_csv(os.path.join(GRAPHS, "m4_fixed", "m4_summary.csv"), index=False)
    print(table.to_string(index=False))

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for color, (rep, g) in zip([BLUE, GREEN, ORANGE], f.groupby("replicas")):
        ax.plot(g["rate"], g["avg_response_ms"], marker="o", lw=2, color=color,
                label=f"{rep} replica" + ("s" if rep > 1 else ""))
    log_ms(ax, f["avg_response_ms"].max())
    ax.set_xticks(sorted(f["rate"].unique()))
    ax.set_xlabel("Request rate (req/s)")
    ax.set_ylabel("Average response time (ms)")
    ax.legend(frameon=False)
    save(fig, "m4_fixed", "graph1_response_time")

    run = f[(f["replicas"] == 3) & (f["rate"] == 100)].iloc[0]
    p = pd.read_csv(os.path.join(FIX, "pods.csv"))
    p = p[p["pod"].str.startswith("emi-web")]
    w = p[p["time"].between(run["start"] + 30, run["start"] + 90)]   # metrics-server is ~60 s behind
    cpu = w.groupby("pod")["cpu_m"].mean()
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar([n.split("-")[-1] for n in cpu.index], cpu.values, color=BLUE, width=0.5)
    ax.bar_label(bars, fmt="%.0f%%", padding=3)
    ax.set_xlabel("Web pod (3 replicas, 100 req/s)")
    ax.set_ylabel("Average CPU (% of request)")
    ax.set_ylim(0, max(60, cpu.max() * 1.3))
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
    save(fig, "m4_fixed", "graph2_pod_cpu")
else:
    print("m4_fixed not found yet (run ./db.sh fixed): skipped graph 1 and 2")

# ===================== Graph 3: the 10-minute HPA test =====================
HPA = find("m4_hpa")
if HPA:
    a = steps(HPA)
    t0 = a["start"].min()
    m = lambda t: (t - t0) / 60
    h = pd.read_csv(os.path.join(HPA, "hpa.csv"))
    h = h[h["time"].between(t0 - 5, t0 + 11 * 60)]
    fig, ax = plt.subplots(3, 1, figsize=(9, 8))
    smooth(ax[0], m(a["start"] + a["duration"] / 2), a["rate"], BLUE)
    ax[0].set_ylabel("Request rate\n(req/s)")
    cpu = changes(h.set_index("time")["cpu_pct"])
    smooth(ax[1], m(cpu.index), cpu.values, RED)
    ax[1].axhline(50, color="#999999", lw=1)
    ax[1].text(10.9, 52, "target 50%", ha="right", fontsize=8, color="#666666")
    ax[1].set_ylabel("Average CPU\n(% of request)")
    ax[2].step(m(h["time"]), h["replicas"], where="post", color=ORANGE, lw=2)
    ax[2].set_yticks(range(0, 7))
    ax[2].set_ylabel("Web replicas")
    for x in ax:
        x.set_xlim(-0.2, 11)
        x.set_ylim(bottom=0)
        x.set_xlabel("Time (min)")
    save(fig, "m4_hpa", "graph3_autoscaling")
else:
    print("m4_hpa not found yet (run ./db.sh hpa): skipped graph 3")
