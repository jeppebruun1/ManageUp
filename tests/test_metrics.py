"""
Eyeball-test for every metrics function.
Run from the project root:  python tests/test_metrics.py
"""
import sys
import math
import pandas as pd

sys.path.insert(0, "src")
from metrics import (
    load_and_clean,
    summary_kpis,
    cohort_retention,
    arr_waterfall,
    geography_mix_by_month,
    industry_mix_by_month,
    logo_highlights,
    icp_snapshot,
)

AS_OF = "2025-04"
CSV   = "sample_data/demo_transactions.csv"

def flag(condition: bool, label: str):
    print(f"  {'OK' if condition else '!! PROBLEM'}: {label}")


# -- Load -------------------------------------------------------------------
print("=" * 60)
print("LOAD & CLEAN")
print("=" * 60)
df = load_and_clean(CSV)
print(f"  Rows             : {len(df)}")
print(f"  Unique customers : {df['customer_name'].nunique()}")
print(f"  Date range       : {df['month'].min()} to {df['month'].max()}")
flag(len(df) > 0,                             "rows > 0")
flag(df["transaction_date"].isna().sum() == 0, "no null transaction dates")
flag("month" in df.columns,                   "month column present")


# -- Summary KPIs -----------------------------------------------------------
print()
print("=" * 60)
print(f"SUMMARY KPIs  (as_of={AS_OF})")
print("=" * 60)
kpis = summary_kpis(df, AS_OF)
for k, v in kpis.items():
    if k != "top_3_new_signups":
        print(f"  {k:<25}: {v}")
print(f"  {'top_3_new_signups':<25}:")
for s in kpis["top_3_new_signups"]:
    print(f"      {s}")
flag(kpis["current_arr"] > 0,             "current ARR > 0")
flag(kpis["arr_change_pct"] > -100,       "ARR change > -100%")
flag(kpis["churn_rate_pct"] <= 100,       "churn rate <= 100%")
flag(kpis["churn_rate_pct"] >= 0,         "churn rate >= 0%")
flag(kpis["net_new_customers"] >= 0,      "net new customers >= 0")
flag(len(kpis["top_3_new_signups"]) <= 3, "top 3 has <= 3 entries")


# -- Cohort Retention -------------------------------------------------------
print()
print("=" * 60)
print("COHORT RETENTION")
print("=" * 60)
retention = cohort_retention(df, AS_OF)
print(retention.to_string())
pct_cols = [c for c in retention.columns if c.startswith("month_")]
for col in pct_cols:
    vals = retention[col].dropna()
    if len(vals):
        flag((vals >= 0).all() and (vals <= 100).all(), f"{col} values 0-100")
recent     = retention.index[-1]
last_col   = pct_cols[-1]
flag(
    pd.isna(retention.loc[recent, last_col]),
    f"most recent cohort ({recent}) {last_col} is NaN (too early)",
)


# -- ARR Waterfall ----------------------------------------------------------
print()
print("=" * 60)
print(f"ARR WATERFALL  (as_of={AS_OF})")
print("=" * 60)
wf = arr_waterfall(df, AS_OF)
for k, v in wf.items():
    print(f"  {k:<22}: ${v:>12,.0f}")
computed_end = (
    wf["starting_arr"] + wf["new_arr"] + wf["net_expansion_arr"] - wf["churn_arr"]
)
flag(math.isclose(computed_end, wf["ending_arr"], rel_tol=1e-6), "waterfall balances")
flag(wf["ending_arr"] > 0,   "ending ARR > 0")
flag(wf["churn_arr"] >= 0,   "churn ARR >= 0")
flag(wf["new_arr"] >= 0,     "new ARR >= 0")
print(f"  net_expansion reflects upgrades: {wf['net_expansion_arr']:,.0f}")


# -- Geography Mix ----------------------------------------------------------
print()
print("=" * 60)
print("GEOGRAPHY MIX BY MONTH")
print("=" * 60)
geo = geography_mix_by_month(df, AS_OF)
print(geo.to_string())
flag(len(geo) > 0,            "geo rows > 0")
flag((geo.values >= 0).all(), "all counts >= 0")
flag(geo.shape[1] >= 3,       "at least 3 countries")


# -- Industry Mix -----------------------------------------------------------
print()
print("=" * 60)
print("INDUSTRY MIX BY MONTH")
print("=" * 60)
ind = industry_mix_by_month(df, AS_OF)
print(ind.to_string())
flag(len(ind) > 0,            "ind rows > 0")
flag((ind.values >= 0).all(), "all counts >= 0")
flag(ind.shape[1] >= 4,       "at least 4 industries")


# -- Logo Highlights --------------------------------------------------------
print()
print("=" * 60)
print(f"LOGO HIGHLIGHTS  (as_of={AS_OF}, n=5)")
print("=" * 60)
logos = logo_highlights(df, AS_OF, n=5)
for i, l in enumerate(logos, 1):
    print(f"  {i}. {l['name']:<30} ${l['mrr']:,}/mo  {l['industry']}  {l['country']}")
flag(len(logos) <= 5, "<= 5 logos returned")
if len(logos) >= 2:
    flag(logos[0]["mrr"] >= logos[1]["mrr"], "sorted by MRR descending")


# -- ICP Snapshot -----------------------------------------------------------
print()
print("=" * 60)
print("ICP SNAPSHOT  (top quartile active customers)")
print("=" * 60)
icp = icp_snapshot(df, AS_OF)
for k, v in icp.items():
    print(f"  {k:<20}: {v}")
flag(icp["avg_mrr"] > 0,                                "avg MRR > 0")
flag(icp["inbound_pct"] + icp["outbound_pct"] == 100.0, "channel pcts sum to 100")
flag(icp["sample_size"] > 0,                            "sample size > 0")
flag(icp["top_industry"] is not None,                   "top industry present")
flag(icp["top_country"] is not None,                    "top country present")


print()
print("=" * 60)
print("ALL CHECKS DONE - review any !! PROBLEM lines above")
print("=" * 60)
