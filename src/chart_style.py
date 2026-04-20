"""
Shared visual style for all ManageUp charts.
Import and call apply_style() at the top of every chart function.
"""
import matplotlib.pyplot as plt
from cycler import cycler

PALETTE = [
    "#2E5FE8",  # blue
    "#17A583",  # teal
    "#D97706",  # amber
    "#B14AED",  # purple
    "#E24B4A",  # red
    "#5F5E5A",  # gray
]


def apply_style() -> None:
    """Apply ManageUp rcParams globally. Call once at the top of each chart function."""
    plt.rcParams.update({
        # Font
        "font.family":          "DejaVu Sans",

        # Color cycle
        "axes.prop_cycle":      cycler(color=PALETTE),

        # Spines — remove top/right; thin remaining two
        "axes.spines.top":      False,
        "axes.spines.right":    False,
        "axes.linewidth":       0.5,

        # Grid — horizontal only
        "axes.grid":            True,
        "axes.grid.axis":       "y",
        "grid.color":           "#E5E5E5",
        "grid.linewidth":       0.5,
        "grid.linestyle":       "-",

        # Figure background
        "figure.facecolor":     "white",
        "axes.facecolor":       "white",

        # Title
        "axes.titlesize":       14,
        "axes.titleweight":     "medium",
        "axes.titlepad":        10,

        # Axis labels
        "axes.labelsize":       10,
        "axes.labelcolor":      "#5F5E5A",

        # Tick labels
        "xtick.labelsize":      9,
        "ytick.labelsize":      9,
        "xtick.color":          "#5F5E5A",
        "ytick.color":          "#5F5E5A",

        # DPI — set once here, applies to every savefig call
        "savefig.dpi":          200,
        "savefig.bbox":         "tight",
    })
