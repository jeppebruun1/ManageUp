"""
Generates all five charts and prints the saved file paths.
Run from the project root:  python tests/test_charts.py
Open the files in output/ to visually inspect the charts.
"""
import sys, os
sys.path.insert(0, "src")

from metrics import (
    load_and_clean, cohort_retention, arr_waterfall,
    geography_mix_by_month, industry_mix_by_month,
)
from charts import (
    plot_arr_trend, plot_arr_waterfall, plot_cohort_heatmap,
    plot_geography_mix, plot_industry_mix,
)

AS_OF  = "2025-04"
CSV    = "sample_data/demo_transactions.csv"
OUTDIR = "output"

print("Loading data...")
df = load_and_clean(CSV)

print("Generating charts...")

path = plot_arr_trend(df, AS_OF, OUTDIR)
size = os.path.getsize(path)
print(f"  [1/5] ARR trend       -> {path}  ({size:,} bytes)")
assert size > 5_000, "File suspiciously small"

wf   = arr_waterfall(df, AS_OF)
path = plot_arr_waterfall(wf, AS_OF, OUTDIR)
size = os.path.getsize(path)
print(f"  [2/5] ARR waterfall   -> {path}  ({size:,} bytes)")
assert size > 5_000, "File suspiciously small"

ret  = cohort_retention(df, AS_OF)
path = plot_cohort_heatmap(ret, OUTDIR)
size = os.path.getsize(path)
print(f"  [3/5] Cohort heatmap  -> {path}  ({size:,} bytes)")
assert size > 5_000, "File suspiciously small"

geo  = geography_mix_by_month(df, AS_OF)
path = plot_geography_mix(geo, OUTDIR)
size = os.path.getsize(path)
print(f"  [4/5] Geography mix   -> {path}  ({size:,} bytes)")
assert size > 5_000, "File suspiciously small"

ind  = industry_mix_by_month(df, AS_OF)
path = plot_industry_mix(ind, OUTDIR)
size = os.path.getsize(path)
print(f"  [5/5] Industry mix    -> {path}  ({size:,} bytes)")
assert size > 5_000, "File suspiciously small"

print()
print("All 5 charts saved. Open the output/ folder to inspect them.")
