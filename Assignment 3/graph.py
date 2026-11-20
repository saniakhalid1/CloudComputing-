# Assignment 3 graphs
#   httperf_summary.csv -> rate and processed requests (one row per 30 s step)
#   metrics.csv         -> replicas and CPU (monitor.sh, one row every 5 s)
import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

STEP = 30        # seconds per httperf step
OFFSET = 0       # seconds between starting monitor.sh and starting load.sh

# use Lexend if it is installed, otherwise the default font
fonts = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams.update({
    "font.family": "Lexend" if "Lexend" in fonts else "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#444444", "axes.linewidth": 0.8,
    "axes.labelcolor": "#222222", "axes.labelpad": 8,
    "xtick.color": "#444444", "ytick.color": "#444444",
    "xtick.direction": "out", "ytick.direction": "out",
    "axes.grid": True, "grid.color": "#ececec", "grid.linewidth": 0.7,
    "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
})

def finish(fig, ax, name, ylabel, xmax, ymax):
    ax.set_xlabel("Time (min)")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.spines["left"].set_position(("outward", 6))
    ax.spines["bottom"].set_position(("outward", 6))
    fig.tight_layout()
    fig.savefig(name + ".png", dpi=200)
    fig.savefig(name + ".pdf")
    plt.close(fig)

s = pd.read_csv("httperf_summary.csv")
start = [(OFFSET + i * STEP) / 60 for i in range(len(s))]
end = start[-1] + STEP / 60
mid = [t + STEP / 120 for t in start]

# 1. Request rate
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.step(start + [end], list(s["rate"]) + [s["rate"].iloc[-1]],
        where="post", color="#2f5bd3", lw=2.2)
finish(fig, ax, "1_rate", "Request rate (req/s)", end, s["rate"].max() * 1.15)

# 2. Processed requests
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.plot(mid, s["processed_requests"], color="#1d9a6c", lw=1.8,
        marker="o", ms=5, mfc="white", mew=1.6)
finish(fig, ax, "2_processed_requests", "Processed requests (per 30 s)",
       end, s["processed_requests"].max() * 1.15)

if os.path.exists("metrics.csv"):
    m = pd.read_csv("metrics.csv")
    mx = (m["time"] - m["time"].min()) / 60

    # 3. Replicas
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.step(mx, m["replicas"], where="post", color="#e0761f", lw=2.4)
    ax.set_yticks(range(0, int(m["replicas"].max()) + 2))
    finish(fig, ax, "3_replicas", "Replicas (pods)", mx.max(), m["replicas"].max() + 1)

    # 4. CPU usage
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(mx, m["hpa_cpu_pct"], color="#c2334d", lw=1.6)
    finish(fig, ax, "4_cpu", "Avg pod CPU (%)", mx.max(), m["hpa_cpu_pct"].max() * 1.12)
else:
    print("metrics.csv not found - made graphs 1 and 2 only")
