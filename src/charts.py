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

    min_m = df["month"].min()
    max_m = pd.Period(as_of_month, freq="M")
    months = pd.period_range(min_m, max_m, freq="M")

    arr_values = []
    for month in months:
        active = df[df["month"] == month]
        # one row per customer (last charge if duplicates)
        active = (
            active.sort_values("transaction_date")
                  .groupby("customer_name", as_index=False)
                  .last()
        )
        arr_values.append(float(active["amount_usd"].sum() * 12))

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

    net_exp = wf["net_expansion_arr"]
    peak    = wf["starting_arr"] + wf["new_arr"] + max(0.0, net_exp)

    # Net expansion is always amber (its own color in the palette) so
    # positive and negative expansion read as the same movement.
    if net_exp >= 0:
        exp_height, exp_bottom, exp_sign = (
            net_exp, wf["starting_arr"] + wf["new_arr"], "+"
        )
    else:
        exp_height, exp_bottom, exp_sign = (
            -net_exp, wf["starting_arr"] + wf["new_arr"] + net_exp, "-"
        )
    exp_color = C_AMBER

    # (label, bar_height, bottom, color, sign_for_label)
    segments = [
        ("Starting\nARR",   wf["starting_arr"], 0,                   C_GRAY, ""),
        ("New",             wf["new_arr"],       wf["starting_arr"],  C_TEAL, "+"),
        ("Net\nExpansion",  exp_height,          exp_bottom,          exp_color, exp_sign),
        ("Churn",           wf["churn_arr"],     wf["ending_arr"],    C_RED,  "-"),
        ("Ending\nARR",     wf["ending_arr"],    0,                   C_BLUE, ""),
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
        wf["starting_arr"] + wf["new_arr"] + wf["net_expansion_arr"],
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
    n_cols = mat.shape[1]

    # Size scales with data so cells never squeeze microscopically
    fig_h = 2.0 + 0.30 * n_rows
    fig_w = 3.0 + 0.40 * n_cols
    fig_w = min(fig_w, 11.0)   # cap so it never exceeds page width
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    ax.imshow(masked, cmap=GREEN_CMAP, vmin=0, vmax=100, aspect="auto")

    # Cell text size bands
    if n_cols <= 8:
        cell_fs = 10
    elif n_cols <= 12:
        cell_fs = 8
    else:
        cell_fs = 7

    for row in range(mat.shape[0]):
        for col in range(mat.shape[1]):
            v = mat[row, col]
            if not np.isnan(v):
                text_color = "white" if v > 50 else "#1A3A2E"
                ax.text(col, row, f"{v:.0f}%",
                        ha="center", va="center",
                        fontsize=cell_fs, fontweight="medium",
                        color=text_color)

    # Column headers: rotate 45° when there are many, so they don't overlap
    ax.set_xticks(range(len(col_labels)))
    if n_cols > 12:
        ax.set_xticklabels(col_labels, fontsize=8, rotation=45, ha="left")
        ax.xaxis.tick_top()
    else:
        ax.set_xticklabels(col_labels, fontsize=9)
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
    """Shared stacked bar logic. 16:9 aspect, legend outside plot area."""
    apply_style()

    # 16:9 aspect — horizontal axis is the time dimension
    fig, ax = plt.subplots(figsize=(10, 5.625))
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

    n_months = len(df)
    if n_months > 12:
        ax.set_xticklabels(df.index.tolist(),
                           rotation=45, ha="right", fontsize=8)
        fig.subplots_adjust(bottom=0.22)
    else:
        ax.set_xticklabels(df.index.tolist(),
                           rotation=45, ha="right", fontsize=9)

    ax.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        frameon=False,
        fontsize=9,
    )

    fig.tight_layout()
    fig.subplots_adjust(right=0.82)
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


# ---------------------------------------------------------------------------
# 6. Pipeline funnel (optional — only when pipeline CSV is provided)
# ---------------------------------------------------------------------------

def plot_pipeline_funnel(by_stage: dict,
                         output_dir: str = "output") -> str:
    """
    Horizontal funnel chart. One bar per stage, width = ARR in that stage.
    Stages are plotted top-to-bottom: Discovery -> Verbal Agreement.
    """
    apply_style()

    STAGES = ["Discovery", "Demo", "Proposal", "Negotiation", "Verbal Agreement"]
    # Single-hue teal ramp (the categorical palette's teal, lightened and darkened)
    FUNNEL_COLORS = ["#CFEDE4", "#9BD8C4", "#5EBFA2", "#2E9E7E", "#0F6E56"]

    amounts = [by_stage[s]["amount_arr"] for s in STAGES]
    counts  = [by_stage[s]["count"]      for s in STAGES]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    y_pos = np.arange(len(STAGES))

    ax.barh(y_pos, amounts, color=FUNNEL_COLORS, height=0.62, zorder=3)

    max_amt = max(amounts) if amounts and max(amounts) > 0 else 1.0
    for i, (amt, cnt) in enumerate(zip(amounts, counts)):
        if amt >= 1_000_000:
            amt_str = f"${amt/1e6:.2f}M"
        elif amt > 0:
            amt_str = f"${amt/1e3:.0f}K"
        else:
            amt_str = "$0"
        label = f"{cnt} deals  ·  {amt_str}"
        ax.text(
            amt + max_amt * 0.01, i, label,
            va="center", ha="left",
            fontsize=9, fontweight="medium",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(STAGES, fontsize=10)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(_arr_formatter(max_amt))
    ax.set_xlabel("Pipeline ARR")
    ax.set_xlim(0, max_amt * 1.38)

    # Horizontal-bar chart: want grid on x-axis, not y
    ax.grid(axis="x", zorder=0)
    ax.yaxis.grid(False)

    fig.tight_layout()
    return _save(fig, output_dir, "pipeline_funnel.png")
