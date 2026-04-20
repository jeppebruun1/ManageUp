"""
Run this to confirm pandas is installed and the CSV loaded correctly.
Usage: python tests/check_env.py
"""
import sys
import pandas as pd

CSV_PATH = "sample_data/demo.csv"

print(f"Python version : {sys.version.split()[0]}")
print(f"Pandas version : {pd.__version__}")
print()

df = pd.read_csv(CSV_PATH, parse_dates=["signup_date", "end_date"])
print(f"Rows loaded    : {len(df)}")
print(f"Columns        : {list(df.columns)}")
print()

total_mrr   = df["mrr_usd"].sum()
active_mask = df["end_date"].isna()
active_mrr  = df.loc[active_mask, "mrr_usd"].sum()
churned     = (~active_mask).sum()

print(f"Total customers  : {len(df)}")
print(f"Active customers : {active_mask.sum()}")
print(f"Churned          : {churned}")
print(f"Churn rate       : {churned / len(df) * 100:.1f}%")
print()
print(f"Total MRR (all)  : ${total_mrr:,.0f}")
print(f"Active MRR       : ${active_mrr:,.0f}")
print(f"Implied ARR      : ${active_mrr * 12:,.0f}")
print()
print("MRR breakdown:")
print(df["mrr_usd"].describe().apply(lambda x: f"  ${x:,.0f}").to_string())
print()
print("Customers by country:")
print(df["country"].value_counts().to_string())
print()
print("Customers by industry:")
print(df["industry"].value_counts().to_string())
print()
print("Acquisition channel split:")
print(df["acquisition_channel"].value_counts().to_string())
print()
print("Date range:")
print(f"  Earliest signup : {df['signup_date'].min().date()}")
print(f"  Latest signup   : {df['signup_date'].max().date()}")
print()
print("Everything looks good! Your environment is ready.")
