"""
Chart builder for ManageUp.
Each function accepts pre-computed data from metrics.py, saves a PNG,
and returns the file path. Nothing is displayed on screen.
"""
import os

import matplotlib
matplotlib.use("Agg")  # must be before pyplot import — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Shared style
# ---------------------------------------------------------------------------

PALETTE = [
    "#2563EB",  # blue
    "#16A34A",  # green
    "#9333EA",  # purple
    "#EA580C",  # orange
    "#0891B2",  # teal
    "#CA8A04",  # amber
    "#DC2626",  # red
    "#059669",  # emerald
]

C_POSITIVE = "#16A34A"
C_NEGATIVE = "#DC2626"
C_NEUTRAL  = "#6B7280"
C_PRIMARY  = "#2563EB"

plt.rcParams.update({
    "font.family": "sans-serif",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "axes.grid.axis":    "y",
    "grid.linestyle":    "--",
    "grid.alpha":        0.4,
})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _save(fig: plt.Figure, output_dir: str, filename: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _dollar_formatter(max_val: float):
    """Pick K vs M label scale based on the data range."""
    if max_val >= 1_000_000:
        return mticker.FuncFormatter(lambda x, _: f"${x/1e6:.1f}M")
    return mticker.FuncFormatter(lambda x, _: f"${x/1e3:.0f}K")


# ---------------------------------------------------------------------------
# 1. ARR trend
# ---------------------------------------------------------------------------

def plot_arr_trend(df: pd.DataFrame, output_dir: str = "output") -> str:
    """
    Line chart of ending ARR for every month in the data window.
    Computes the series internally from the full DataFrame.
    """
    min_m = df["signup_date"].min().to_period("M")
    max_m = df["signup_date"].max().to_period("M")
    months = pd.period_range(min_m, max_m, freq="M")

    arr_values = []
    for month in months:
        month_end = month.to_timestamp() + pd.offsets.MonthEnd(0)
        active = df[
            (df["signup_date"] <= month_end)
            & (df["end_date"].isna() | (df["end_date"] > month_end))
        ]
        arr_values.append(float(active["mrr_usd"].sum() * 12))

    labels = [str(m) for m in months]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(labels, arr_values, color=C_PRIMARY, linewidth=2.5,
            marker="o", markersize=5, zorder=3)
    ax.fill_between(labels, arr_values, alpha=0.08, color=C_PRIMARY)

    ax.set_title("ARR Over Time", fontsize=14, fontweight="bold", pad=12)
    ax.set_ylabel("ARR (USD)", fontsize=11)
    ax.yaxis.set_major_formatter(_dollar_formatter(max(arr_values)))
    ax.tick_params(axis="x", rotation=45, labelsize=9)

    fig.tight_layout()
    return _save(fig, output_dir, "arr_trend.png")


# ---------------------------------------------------------------------------
# 2. ARR waterfall
# ---------------------------------------------------------------------------

def plot_arr_waterfall(wf: dict, as_of_month: str,
                       output_dir: str = "output") -> str:
    """
    Waterfall chart: Starting ARR → New → Expansion → Churn → Ending ARR.
    Floating bars show each movement; totals sit on the baseline.
    """
    # Each entry: (label, bar_height, bottom, bar_color, label_sign)
    running = wf["starting_arr"]
    segments = [
        ("Starting\nARR",  wf["starting_arr"],  0,       C_NEUTRAL,  ""),
        ("New",            wf["new_arr"],        running, C_POSITIVE, "+"),
        ("Expansion",      wf["expansion_arr"],  running + wf["new_arr"], C_POSITIVE, "+"),
        ("Churn",          wf["churn_arr"],
            running + wf["new_arr"] + wf["expansion_arr"] - wf["churn_arr"],
            C_NEGATIVE, "-"),
        ("Ending\nARR",    wf["ending_arr"],     0,       C_PRIMARY,  ""),
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    peak = wf["starting_arr"] + wf["new_arr"] + wf["expansion_arr"]

    for i, (label, height, bottom, color, sign) in enumerate(segments):
        if height == 0:
            continue
        ax.bar(i, height, bottom=bottom, color=color, alpha=0.85,
               width=0.5, zorder=3)
        top = bottom + height
        ax.text(i, top + peak * 0.015,
                f"{sign}${height/1e3:.0f}K",
                ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Dashed connectors between bars
    connector_tops = [
        wf["starting_arr"],
        wf["starting_arr"] + wf["new_arr"],
        wf["starting_arr"] + wf["new_arr"] + wf["expansion_arr"],
        wf["ending_arr"],
    ]
    for i, top in enumerate(connector_tops):
        ax.plot([i + 0.25, i + 0.75], [top, top],
                color="#9CA3AF", linewidth=0.8, linestyle="--", zorder=2)

    ax.set_title(f"ARR Waterfall  —  {as_of_month}",
                 fontsize=14, fontweight="bold", pad=12)
    ax.set_ylabel("ARR (USD)", fontsize=11)
    ax.set_xticks(range(len(segments)))
    ax.set_xticklabels([s[0] for s in segments], fontsize=10)
    ax.yaxis.set_major_formatter(_dollar_formatter(peak))
    ax.set_ylim(0, peak * 1.2)

    fig.tight_layout()
    return _save(fig, output_dir, "arr_waterfall.png")


# ---------------------------------------------------------------------------
# 3. Cohort retention heatmap
# ---------------------------------------------------------------------------

def plot_cohort_heatmap(retention_df: pd.DataFrame,
                        output_dir: str = "output") -> str:
    """
    Color-coded heatmap of cohort retention percentages.
    Red = low retention, green = high. NaN cells are light gray.
    """
    pct_cols = [c for c in retention_df.columns if c.startswith("month_")]
    data = retention_df[pct_cols].copy()

    mat = data.values.astype(float)
    masked = np.ma.masked_invalid(mat)

    cmap = plt.cm.RdYlGn.copy()
    cmap.set_bad(color="#E5E7EB")  # light gray for NaN / not-yet-measurable

    n_rows, n_cols = mat.shape
    fig_height = max(3.5, n_rows * 0.55)
    fig, ax = plt.subplots(figsize=(7, fig_height))

    im = ax.imshow(masked, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    # Annotate each cell
    for row in range(n_rows):
        for col in range(n_cols):
            v = mat[row, col]
            if np.isnan(v):
                ax.text(col, row, "n/a", ha="center", va="center",
                        fontsize=8, color="#9CA3AF")
            else:
                text_color = "white" if (v < 35 or v > 80) else "#1F2937"
                ax.text(col, row, f"{v:.0f}%", ha="center", va="center",
                        fontsize=9, color=text_color, fontweight="bold")

    col_labels = [c.replace("month_", "Mo ") for c in pct_cols]
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(col_labels, fontsize=10)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(data.index.tolist(), fontsize=9)
    ax.set_title("Cohort Retention (%)", fontsize=14,
                 fontweight="bold", pad=12)
    ax.grid(False)  # heatmap looks cleaner without grid lines

    plt.colorbar(im, ax=ax, label="% Retained", fraction=0.03, pad=0.04)
    fig.tight_layout()
    return _save(fig, output_dir, "cohort_heatmap.png")


# ---------------------------------------------------------------------------
# 4 & 5. Stacked bar charts (geography + industry share the same logic)
# ---------------------------------------------------------------------------

def _stacked_bar(df: pd.DataFrame, title: str, ylabel: str,
                 filename: str, output_dir: str) -> str:
    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(df))
    bottoms = np.zeros(len(df))

    for i, col in enumerate(df.columns):
        heights = df[col].values.astype(float)
        ax.bar(x, heights, bottom=bottoms, label=col,
               color=PALETTE[i % len(PALETTE)], alpha=0.88)
        bottoms += heights

    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(df.index.tolist(), rotation=45,
                       ha="right", fontsize=9)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.7)

    fig.tight_layout()
    return _save(fig, output_dir, filename)


def plot_geography_mix(geo_df: pd.DataFrame,
                       output_dir: str = "output") -> str:
    """Stacked bar: active customers by country per month."""
    return _stacked_bar(
        geo_df,
        title="Active Customers by Country",
        ylabel="Active Customers",
        filename="geography_mix.png",
        output_dir=output_dir,
    )


def plot_industry_mix(ind_df: pd.DataFrame,
                      output_dir: str = "output") -> str:
    """Stacked bar: active customers by industry per month."""
    return _stacked_bar(
        ind_df,
        title="Active Customers by Industry",
        ylabel="Active Customers",
        filename="industry_mix.png",
        output_dir=output_dir,
    )
