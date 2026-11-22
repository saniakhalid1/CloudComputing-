import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import os

# ============================================================
# CONFIGURATION
# ============================================================

HTTPERF_FILE = "httperf_summary.csv"

CPU_FILES = {
    "VM-1": "CPU_VM-1.csv",
    "VM-2": "CPU_VM-2.csv",
    "VM-3": "CPU_VM-3.csv"
}

# CPU is measured every 1 second.
# One httperf experiment runs for 60 seconds.
SECONDS_PER_RUN = 60


# ============================================================
# STEP 1: AVERAGE EACH CPU FILE EVERY 60 SECONDS
# ============================================================

cpu_averaged_data = {}

for vm_name, file_name in CPU_FILES.items():

    print("\n========================================")
    print(f"Processing {vm_name}")
    print("========================================")

    # Read CPU CSV
    df = pd.read_csv(file_name)

    # Convert required columns to numeric
    df["elapsed_s"] = pd.to_numeric(
        df["elapsed_s"],
        errors="coerce"
    )

    df["cpu_percent"] = pd.to_numeric(
        df["cpu_percent"],
        errors="coerce"
    )

    # Remove invalid rows
    df = df.dropna(
        subset=["elapsed_s", "cpu_percent"]
    )

    # Sort according to elapsed seconds
    df = df.sort_values(
        "elapsed_s"
    ).reset_index(drop=True)

    print("Original CPU rows:", len(df))

    # --------------------------------------------------------
    # Check that number of rows is divisible by 60
    # --------------------------------------------------------

    remainder = len(df) % SECONDS_PER_RUN

    if remainder != 0:
        print(
            f"WARNING: {len(df)} rows are not exactly divisible "
            f"by {SECONDS_PER_RUN}."
        )

    # --------------------------------------------------------
    # Create 60-second/minute groups
    #
    # Rows:
    # 0-59    -> minute 1
    # 60-119  -> minute 2
    # etc.
    # --------------------------------------------------------

    df["minute"] = (
        df.index // SECONDS_PER_RUN
    ) + 1

    # --------------------------------------------------------
    # Average CPU for every 60 rows
    # --------------------------------------------------------

    avg_df = (
        df.groupby("minute", as_index=False)
        .agg(
            avg_cpu_percent=("cpu_percent", "mean"),
            samples=("cpu_percent", "count")
        )
    )

    # Round CPU values
    avg_df["avg_cpu_percent"] = (
        avg_df["avg_cpu_percent"].round(2)
    )

    print("Averaged rows:", len(avg_df))

    # --------------------------------------------------------
    # Save averaged CPU file
    # --------------------------------------------------------

    output_file = f"{vm_name}_CPU_1Minute_Average.csv"

    avg_df.to_csv(
        output_file,
        index=False
    )

    print("Saved:", output_file)

    # Store for later mapping
    cpu_averaged_data[vm_name] = avg_df


# ============================================================
# STEP 2: READ HTTPERF SUMMARY
# ============================================================

httperf = pd.read_csv(HTTPERF_FILE)

httperf["rate"] = pd.to_numeric(
    httperf["rate"],
    errors="coerce"
)

httperf = httperf.dropna(
    subset=["rate"]
)

# Sort rate numerically
httperf = httperf.sort_values(
    "rate"
).reset_index(drop=True)

print("\n========================================")
print("HTTPERF")
print("========================================")

print("Number of httperf rates:", len(httperf))

print(
    "First rate:",
    httperf["rate"].iloc[0]
)

print(
    "Last rate:",
    httperf["rate"].iloc[-1]
)


# ============================================================
# STEP 3: MAP HTTPERF RATE TO CPU AVERAGES
# ============================================================

for vm_name, avg_df in cpu_averaged_data.items():

    print("\n========================================")
    print(f"Mapping {vm_name}")
    print("========================================")

    # --------------------------------------------------------
    # Number of observations that can actually be mapped
    # --------------------------------------------------------

    n = min(
        len(httperf),
        len(avg_df)
    )

    if len(httperf) != len(avg_df):
        print(
            f"WARNING: httperf has {len(httperf)} rates "
            f"but {vm_name} has {len(avg_df)} CPU minute averages."
        )

        print(
            f"Only first {n} observations will be mapped."
        )

    # --------------------------------------------------------
    # Create mapped dataframe
    # --------------------------------------------------------

    mapped = pd.DataFrame({

        "rate":
            httperf["rate"].iloc[:n].values,

        "avg_cpu_percent":
            avg_df["avg_cpu_percent"].iloc[:n].values

    })

    # --------------------------------------------------------
    # Save mapped file
    # --------------------------------------------------------

    mapped_file = f"{vm_name}_Rate_CPU_Mapped.csv"

    mapped.to_csv(
        mapped_file,
        index=False
    )

    print("Saved:", mapped_file)

    print("\nFirst few mappings:")

    print(
        mapped.head(10).to_string(index=False)
    )


    # ========================================================
    # STEP 4: PLOT RATE VS CPU
    # ========================================================

    fig, ax = plt.subplots(
        figsize=(14, 6)
    )

    ax.plot(
        mapped["rate"],
        mapped["avg_cpu_percent"],
        linewidth=2,
        marker="o",
        markersize=3,
        label=f"{vm_name} CPU"
    )

    # --------------------------------------------------------
    # Titles / labels
    # --------------------------------------------------------

    ax.set_title(
        f"{vm_name}: CPU Utilization vs Request Rate",
        fontsize=18
    )

    ax.set_xlabel(
        "Request Rate",
        fontsize=14
    )

    ax.set_ylabel(
        "Average CPU Utilization (%)",
        fontsize=14
    )

    # CPU percentage range
    ax.set_ylim(
        0,
        100
    )

    # Rate ticks
    ax.xaxis.set_major_locator(
        MultipleLocator(1000)
    )

    # Grid
    ax.grid(
        True,
        alpha=0.3
    )

    # Tick size
    ax.tick_params(
        axis="both",
        labelsize=11
    )

    # Legend
    ax.legend(
        fontsize=12,
        loc="upper left"
    )

    plt.tight_layout()

    # --------------------------------------------------------
    # Save PDF
    # --------------------------------------------------------

    pdf_file = f"{vm_name}_CPU_vs_Rate.pdf"

    plt.savefig(
        pdf_file,
        bbox_inches="tight"
    )

    plt.show()

    print("Saved:", pdf_file)


print("\n========================================")
print("DONE")
print("========================================")
