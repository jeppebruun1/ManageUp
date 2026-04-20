"""
Chart builder for ManageUp.
Each function accepts pre-computed data from metrics.py, saves a PNG,
and returns the file path. Nothing is displayed on screen.
"""
import os

import matplotlib
matplotlib.use("Agg")  # must be before pyplot — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

from chart_style import apply_style, PALETTE

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _save(fig: plt.Figure, output_dir: str, filename: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    fig.savefig(path)   # dpi and bbox set globally via savefig.dpi / savefig.bbox
    plt.close(fig)
    return path


def _arr_formatter(max_val: float):
    """$2.5M style for large values, $800K for smaller."""
    if max_val >= 1_000_000:
        return mticker.FuncFormatter(lambda x, _: f"${x/1e6:.1f}M")
    return mticker.FuncFormatter(lambda x, _: f"${x/1e3:.0f}K")


# ---------------------------------------------------------------------------
# 1. ARR trend
# ---------------------------------------------------------------------------

def plot_arr_trend(df: pd.DataFrame, as_of_month: str,
                   output_dir: str = "output") -> str:
    """
    Line chart of ending ARR from first signup month up to as_of_month.
    Capped at as_of_month so the end label matches the KPI card ARR.
    """
    apply_style()

    min_m = df["signup_date"].min().to_period("M")
    max_m = pd.Period(as_of_month, freq="M")
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
    x = range(len(labels))

    fig, ax = plt.subplots(figsize=(10, 4))

    ax.plot(labels, arr_values, color="#2E5FE8", linewidth=2,
            marker="o", markersize=5, zorder=3)

    # End label — positioned just right of the last point
    ax.annotate(
        f"${arr_values[-1]/1e6:.2f}M",
        xy=(len(labels) - 1, arr_values[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        va="center",
        ha="left",
        fontsize=9,
        color="#2E5FE8",
        fontweight="medium",
    )

    ax.set_title("")   # section header in the PDF covers this
    ax.set_ylabel("ARR")
    ax.yaxis.set_major_formatter(_arr_formatter(max(arr_values)))
    ax.tick_params(axis="x", rotation=45)
    # Give the end label a little room on the right
    ax.set_xlim(-0.5, len(labels) - 0.2)

    fig.tight_layout()
    return _save(fig, output_dir, "arr_trend.png")


# ---------------------------------------------------------------------------
# 2. ARR waterfall
# ---------------------------------------------------------------------------

def plot_arr_waterfall(wf: dict, as_of_month: str,
                       output_dir: str = "output") -> str:
    """
    Waterfall: Starting ARR → New → Expansion → Churn → Ending ARR.
    Each movement floats at the right baseline; totals sit on the x-axis.
    """
    apply_style()

    C_GRAY  = "#5F5E5A"
    C_TEAL  = "#17A583"
    C_AMBER = "#D97706"
    C_RED   = "#E24B4A"
    C_BLUE  = "#2E5FE8"

    peak = wf["starting_arr"] + wf["new_arr"] + wf["expansion_arr"]

    # (label, bar_height, bottom, color, sign_for_label)
    segments = [
        ("Starting\nARR",  wf["starting_arr"],  0,       C_GRAY,  ""),
        ("New",            wf["new_arr"],        wf["starting_arr"],  C_TEAL,  "+"),
        ("Expansion",      wf["expansion_arr"],  wf["starting_arr"] + wf["new_arr"],  C_AMBER, "+"),
        ("Churn",          wf["churn_arr"],
            wf["starting_arr"] + wf["new_arr"] + wf["expansion_arr"] - wf["churn_arr"],
            C_RED,  "-"),
        ("Ending\nARR",    wf["ending_arr"],     0,       C_BLUE, ""),
    ]

    fig, ax = plt.subplots(figsize=(9, 5))

    for i, (label, height, bottom, color, sign) in enumerate(segments):
        if height == 0 and sign:   # skip zero-value movement bars
            continue
        ax.bar(i, height, bottom=bottom, color=color, width=0.5, zorder=3)
        top = bottom + height
        label_str = f"{sign}${height/1e3:.0f}K"
        ax.text(
            i, top + peak * 0.012,
            label_str,
            ha="center", va="bottom",
            fontsize=9, fontweight=500,
        )

    # Dashed connectors between bars
    connector_tops = [
        wf["starting_arr"],
        wf["starting_arr"] + wf["new_arr"],
        wf["starting_arr"] + wf["new_arr"] + wf["expansion_arr"],
        wf["ending_arr"],
    ]
    for i, top in enumerate(connector_tops):
        ax.plot(
            [i + 0.25, i + 0.75], [top, top],
            color="#B4B2A9", linewidth=0.5,
            linestyle=(0, (2, 2)),   # dashes (2 on, 2 off)
            zorder=2,
        )

    ax.set_title("")
    ax.set_ylabel("ARR")
    ax.set_xticks(range(len(segments)))
    ax.set_xticklabels([s[0] for s in segments], fontsize=10)
    ax.yaxis.set_major_formatter(_arr_formatter(peak))
    ax.set_ylim(0, peak * 1.22)
    ax.grid(axis="y")

    fig.tight_layout()
    return _save(fig, output_dir, "arr_waterfall.png")


# ---------------------------------------------------------------------------
# 3. Cohort retention heatmap
# ---------------------------------------------------------------------------

def plot_cohort_heatmap(retention_df: pd.DataFrame,
                        output_dir: str = "output") -> str:
    """
    Single-hue green heatmap. NaN cells are plain gray, no label.
    No colorbar — the percentages in each cell are self-explanatory.
    """
    apply_style()

    GREEN_CMAP = LinearSegmentedColormap.from_list(
        "manageup_green", ["#E1F5EE", "#0F6E56"]
    )
    GREEN_CMAP.set_bad(color="#F1EFE8")

    pct_cols = [c for c in retention_df.columns if c.startswith("month_")]
    data = retention_df[pct_cols].copy()
    col_labels = [f"Month {c.split('_')[1]}" for c in pct_cols]

    mat = data.values.astype(float)
    masked = np.ma.masked_invalid(mat)

    n_rows = mat.shape[0]
    fig_h = max(3.5, n_rows * 0.52)
    fig, ax = plt.subplots(figsize=(7, fig_h))

    ax.imshow(masked, cmap=GREEN_CMAP, vmin=0, vmax=100, aspect="auto")

    # Annotate non-NaN cells only
    for row in range(mat.shape[0]):
        for col in range(mat.shape[1]):
            v = mat[row, col]
            if not np.isnan(v):
                text_color = "white" if v > 50 else "#1A3A2E"
                ax.text(col, row, f"{v:.0f}%",
                        ha="center", va="center",
                        fontsize=9, fontweight="medium",
                        color=text_color)
            # NaN cells: no label, background handled by cmap.set_bad

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=10)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(data.index.tolist(), fontsize=9)
    ax.set_title("Cohort retention by signup month")
    ax.grid(False)

    fig.tight_layout()
    return _save(fig, output_dir, "cohort_heatmap.png")


# ---------------------------------------------------------------------------
# 4 & 5. Geography and industry stacked bars
# ---------------------------------------------------------------------------

def _stacked_bar(df: pd.DataFrame, title: str, ylabel: str,
                 filename: str, output_dir: str) -> str:
    """Shared stacked bar logic. Legend sits outside the plot area."""
    apply_style()

    fig, ax = plt.subplots(figsize=(7, 6))
    x = np.arange(len(df))
    bottoms = np.zeros(len(df))

    for i, col in enumerate(df.columns):
        heights = df[col].values.astype(float)
        ax.bar(x, heights, bottom=bottoms,
               label=col, color=PALETTE[i % len(PALETTE)])
        bottoms += heights

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(df.index.tolist(), rotation=45, ha="right", fontsize=9)

    ax.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        frameon=False,
        fontsize=9,
    )

    fig.tight_layout()
    fig.subplots_adjust(right=0.82)   # room for the outside legend
    return _save(fig, output_dir, filename)


def plot_geography_mix(geo_df: pd.DataFrame,
                       output_dir: str = "output") -> str:
    return _stacked_bar(
        geo_df,
        title="Active customers by country",
        ylabel="Active customers",
        filename="geography_mix.png",
        output_dir=output_dir,
    )


def plot_industry_mix(ind_df: pd.DataFrame,
                      output_dir: str = "output") -> str:
    return _stacked_bar(
        ind_df,
        title="Active customers by industry",
        ylabel="Active customers",
        filename="industry_mix.png",
        output_dir=output_dir,
    )
