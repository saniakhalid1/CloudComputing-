import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MultipleLocator
import warnings

warnings.filterwarnings("ignore")

# ============================================================
# Load data
# ============================================================
file_path = "httperf_summary.csv"

df = pd.read_csv(file_path)

# Convert columns to numeric
columns = [
    "rate",
    "total_requests",
    "processed_requests",
    "unprocessed_requests",
    "avg_reply_time_ms"
]

for col in columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Remove invalid rows
df = df.dropna(subset=["rate"])

# IMPORTANT: Sort according to request rate
df = df.sort_values("rate").reset_index(drop=True)

print(df.head())
print(df.tail())


# ============================================================
# General Plot Settings
# ============================================================
TITLE_SIZE = 18
LABEL_SIZE = 14
TICK_SIZE = 11
LEGEND_SIZE = 12

LINE_WIDTH = 2.0

# Change these if you want different spacing
X_STEP = 1000


# ============================================================
# GRAPH 1
# Rate vs Processed and Unprocessed Requests
# ============================================================

fig, ax = plt.subplots(figsize=(12, 6))

ax.plot(
    df["rate"],
    df["processed_requests"],
    linewidth=LINE_WIDTH,
    label="Processed Requests"
)

ax.plot(
    df["rate"],
    df["unprocessed_requests"],
    linewidth=LINE_WIDTH,
    label="Unprocessed Requests"
)

ax.set_title(
    "Processed and Unprocessed Requests vs Request Rate",
    fontsize=TITLE_SIZE
)

ax.set_xlabel("Request Rate", fontsize=LABEL_SIZE)
ax.set_ylabel("Number of Requests", fontsize=LABEL_SIZE)

ax.xaxis.set_major_locator(MultipleLocator(X_STEP))

ax.tick_params(axis="both", labelsize=TICK_SIZE)

ax.grid(True, alpha=0.3)

ax.legend(
    fontsize=LEGEND_SIZE,
    loc="upper left"
)

plt.tight_layout()

plt.savefig(
    "Graph1_Processed_Unprocessed.pdf",
    bbox_inches="tight"
)

plt.show()


# ============================================================
# GRAPH 2
# Rate vs Total, Processed and Unprocessed Requests
# ============================================================

fig, ax = plt.subplots(figsize=(12, 6))

ax.plot(
    df["rate"],
    df["total_requests"],
    linewidth=LINE_WIDTH,
    label="Total Requests"
)

ax.plot(
    df["rate"],
    df["processed_requests"],
    linewidth=LINE_WIDTH,
    label="Processed Requests"
)

ax.plot(
    df["rate"],
    df["unprocessed_requests"],
    linewidth=LINE_WIDTH,
    label="Unprocessed Requests"
)

ax.set_title(
    "Total, Processed and Unprocessed Requests vs Request Rate",
    fontsize=TITLE_SIZE
)

ax.set_xlabel("Request Rate", fontsize=LABEL_SIZE)
ax.set_ylabel("Number of Requests", fontsize=LABEL_SIZE)

ax.xaxis.set_major_locator(MultipleLocator(X_STEP))

ax.tick_params(axis="both", labelsize=TICK_SIZE)

ax.grid(True, alpha=0.3)

ax.legend(
    fontsize=LEGEND_SIZE,
    loc="upper left"
)

plt.tight_layout()

plt.savefig(
    "Graph2_Total_Processed_Unprocessed.pdf",
    bbox_inches="tight"
)

plt.show()


# ============================================================
# GRAPH 3
# Rate vs Average Response Time
# ============================================================

fig, ax = plt.subplots(figsize=(12, 6))

ax.plot(
    df["rate"],
    df["avg_reply_time_ms"],
    linewidth=2.2,
    label="Average Response Time"
)

ax.set_title(
    "Average Response Time vs Request Rate",
    fontsize=TITLE_SIZE
)

ax.set_xlabel("Request Rate", fontsize=LABEL_SIZE)
ax.set_ylabel("Average Response Time (ms)", fontsize=LABEL_SIZE)

ax.xaxis.set_major_locator(MultipleLocator(X_STEP))

ax.tick_params(axis="both", labelsize=TICK_SIZE)

ax.grid(True, alpha=0.3)

ax.legend(
    fontsize=LEGEND_SIZE,
    loc="upper left"
)

plt.tight_layout()

plt.savefig(
    "Graph3_Response_Time.pdf",
    bbox_inches="tight"
)

plt.show()


# ============================================================
# GRAPH 4
# Side-by-side:
#
# LEFT:
# Rate vs Processed + Unprocessed
#
# RIGHT:
# Rate vs Response Time
# ============================================================

fig, axes = plt.subplots(
    1,
    2,
    figsize=(16, 6)
)


# --------------------------
# LEFT GRAPH
# --------------------------

ax1 = axes[0]

ax1.plot(
    df["rate"],
    df["processed_requests"],
    linewidth=LINE_WIDTH,
    label="Processed Requests"
)

ax1.plot(
    df["rate"],
    df["unprocessed_requests"],
    linewidth=LINE_WIDTH,
    label="Unprocessed Requests"
)

ax1.set_title(
    "Request Processing",
    fontsize=TITLE_SIZE
)

ax1.set_xlabel(
    "Request Rate",
    fontsize=LABEL_SIZE
)

ax1.set_ylabel(
    "Number of Requests",
    fontsize=LABEL_SIZE
)

ax1.xaxis.set_major_locator(
    MultipleLocator(X_STEP)
)

ax1.tick_params(
    axis="both",
    labelsize=TICK_SIZE
)

ax1.grid(
    True,
    alpha=0.3
)

ax1.legend(
    fontsize=LEGEND_SIZE,
    loc="upper left"
)


# --------------------------
# RIGHT GRAPH
# --------------------------

ax2 = axes[1]

ax2.plot(
    df["rate"],
    df["avg_reply_time_ms"],
    linewidth=2.2,
    label="Average Response Time"
)

ax2.set_title(
    "Response Time",
    fontsize=TITLE_SIZE
)

ax2.set_xlabel(
    "Request Rate",
    fontsize=LABEL_SIZE
)

ax2.set_ylabel(
    "Average Response Time (ms)",
    fontsize=LABEL_SIZE
)

ax2.xaxis.set_major_locator(
    MultipleLocator(X_STEP)
)

ax2.tick_params(
    axis="both",
    labelsize=TICK_SIZE
)

ax2.grid(
    True,
    alpha=0.3
)

ax2.legend(
    fontsize=LEGEND_SIZE,
    loc="upper left"
)


# Main title
fig.suptitle(
    "HTTPERF Load Test Results",
    fontsize=20
)

plt.tight_layout(
    rect=[0, 0, 1, 0.95]
)

plt.savefig(
    "Graph4_Requests_ResponseTime_SideBySide.pdf",
    bbox_inches="tight"
)

plt.show()
