# Graphs for one long run (load.sh), all on one time axis, saved as PDF + PNG in that folder.
#   request rate, 2xx replies/s, response time (ms), web replicas, web pod CPU, host CPU
#   Every graph has its own time axis.
# Usage:  python3 long_timeline.py results/long_hpa
#         python3 long_timeline.py results/long_fixed1
import re
import sys
import pandas as pd
import matplotlib.pyplot as plt

D = sys.argv[1].rstrip("/")
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#ececec", "grid.linewidth": 0.7})
BLUE, GREEN, TEAL, ORANGE, RED, PURPLE = "#2f5bd3", "#1d9a6c", "#0f7f8c", "#e0761f", "#c2334d", "#7a4fbf"

# ---- the 60 s steps from output.txt ----
steps = []
for part in re.split(r"(?m)^=== ", open(f"{D}/output.txt").read())[1:]:
    row = {k: int(v) for k, v in (kv.split("=") for kv in part.splitlines()[0].split())}
    dur = re.search(r"test-duration ([\d.]+) s", part)
    ok = re.search(r"2xx=(\d+)", part)
    resp = re.search(r"Reply time \[ms\]: response ([\d.]+)", part)
    if not dur:                       # the final 'rate=0' line only marks the end
        continue
    row["duration"] = float(dur.group(1))
    row["ok_per_s"] = int(ok.group(1)) / row["duration"]
    row["response_ms"] = float(resp.group(1))
    bad = re.search(r"4xx=(\d+) 5xx=(\d+)", part)
    err = re.search(r"Errors: total (\d+)", part)
    row["failed"] = (int(bad.group(1)) + int(bad.group(2)) if bad else 0) + (int(err.group(1)) if err else 0)
    steps.append(row)
s = pd.DataFrame(steps)
t0 = s["start"].min()
t_end = s["start"].max() + 120
m = lambda t: (t - t0) / 60


def line(ax, column, color):
    """Flat while a step lasts, joined to the next step."""
    x, y = [], []
    for _, r in s.iterrows():
        x += [m(r["start"]), m(r["start"] + r["duration"])]
        y += [r[column], r[column]]
    ax.plot(x, y, color=color, lw=2)


pods = pd.read_csv(f"{D}/pods.csv")
web = pods[pods["pod"].str.startswith("emi-web") & pods["time"].between(t0 - 5, t_end)]
web_cpu = web.groupby("time")["cpu_m"].mean()                 # % of the 100m request
host = pd.read_csv(f"{D}/host_cpu.csv")
host = host[host["time"].between(t0 - 5, t_end)]

fig, ax = plt.subplots(6, 1, figsize=(11, 16))          # each graph has its own time axis

line(ax[0], "rate", BLUE)
ax[0].set_ylabel("Request rate set\n(req/s)")

line(ax[1], "ok_per_s", GREEN)
ax[1].set_ylabel("2xx replies\nper second")

line(ax[2], "response_ms", TEAL)
# log scale, but labelled with normal numbers (2, 5, 10 ... 1000 ms), so 4 ms and 3000 ms are both visible
from matplotlib.ticker import FixedLocator, FixedFormatter, NullLocator
ax[2].set_yscale("log")
ticks = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
ax[2].yaxis.set_major_locator(FixedLocator(ticks))
ax[2].yaxis.set_major_formatter(FixedFormatter([str(t) for t in ticks]))
ax[2].yaxis.set_minor_locator(NullLocator())
ax[2].set_ylim(2, max(10, s["response_ms"].max() * 1.6))
ax[2].set_ylabel("Avg response time\n(ms)")

if "replicas" in s.columns:                                   # fixed run: the replicas that were set
    ax[3].step([m(t0), m(t_end)], [s["replicas"].iloc[0]] * 2, where="post", color=ORANGE, lw=2)
else:                                                         # HPA run: what the HPA reported
    h = pd.read_csv(f"{D}/hpa.csv")
    h = h[h["time"].between(t0 - 5, t_end)]
    ax[3].step(m(h["time"]), h["replicas"], where="post", color=ORANGE, lw=2)
ax[3].set_ylabel("Web replicas")
ax[3].set_yticks(range(0, 7))

ax[4].plot(m(web_cpu.index), web_cpu.values, color=RED, lw=1.8, marker="o", ms=3)
ax[4].set_ylabel("Avg web pod CPU\n(% of request)")

ax[5].plot(m(host["time"]), host["host_cpu_pct"], color=PURPLE, lw=0.8)
ax[5].set_ylabel("Host (machine)\nCPU (%)")

for i, a in enumerate(ax):
    if i != 2:
        a.set_ylim(bottom=0)
    a.set_xlim(-0.3, m(t_end))
    a.set_xlabel("Time (min)")
fig.tight_layout()
name = D.split("/")[-1]
fig.savefig(f"{D}/{name}_timeline.pdf")
fig.savefig(f"{D}/{name}_timeline.png", dpi=200)
print(f"saved {D}/{name}_timeline.pdf and .png")
print(f"steps: {len(s)}   failed requests in total: {int(s['failed'].sum())}")
