"""
Metrics engine for ManageUp.
All functions are pure: they take a DataFrame (or csv path) and return
plain Python types or DataFrames. No side effects except the ARR warning.
"""
import math
import pandas as pd


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _month_bounds(as_of_month: str):
    """Return (month_start, month_end) Timestamps for a 'YYYY-MM' string."""
    start = pd.Timestamp(f"{as_of_month}-01")
    end = start + pd.offsets.MonthEnd(0)
    return start, end


def _active_at(df: pd.DataFrame, point: pd.Timestamp) -> pd.DataFrame:
    """Customers active at a specific point in time (inclusive on start, exclusive on end_date)."""
    return df[
        (df["signup_date"] <= point)
        & (df["end_date"].isna() | (df["end_date"] > point))
    ]


def _active_during(df: pd.DataFrame, month_start: pd.Timestamp, month_end: pd.Timestamp) -> pd.DataFrame:
    """Customers active at any point during a calendar month."""
    return df[
        (df["signup_date"] <= month_end)
        & (df["end_date"].isna() | (df["end_date"] >= month_start))
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_and_clean(csv_path: str) -> pd.DataFrame:
    """
    Load the CSV and parse dates.
    Blank end_date → NaT (customer still active in the raw data).
    No 'status' column is added here — active/churned is always evaluated
    point-in-time by the calling function using _active_at().
    """
    df = pd.read_csv(csv_path)
    df["signup_date"] = pd.to_datetime(df["signup_date"], errors="coerce")
    df["end_date"]    = pd.to_datetime(df["end_date"],    errors="coerce")
    return df


def summary_kpis(df: pd.DataFrame, as_of_month: str) -> dict:
    """
    Key metrics for a given month.

    Returns:
        current_arr         – ARR of all active customers at month-end
        prior_month_arr     – ARR at the end of the previous month
        arr_change_pct      – MoM ARR growth (%)
        net_new_customers   – customers who signed up this month
        churned_this_month  – customers whose end_date fell in this month
        churn_rate_pct      – churned / active-at-start-of-month (%)
        top_3_new_signups   – list of dicts: name, mrr, industry
    """
    month_start, month_end = _month_bounds(as_of_month)
    prior_month_end = month_start - pd.Timedelta(days=1)

    active_eom   = _active_at(df, month_end)
    active_prior = _active_at(df, prior_month_end)

    current_arr  = float(active_eom["mrr_usd"].sum() * 12)
    prior_arr    = float(active_prior["mrr_usd"].sum() * 12)
    arr_change_pct = (
        round((current_arr - prior_arr) / prior_arr * 100, 1) if prior_arr else 0.0
    )

    new_mask = (df["signup_date"] >= month_start) & (df["signup_date"] <= month_end)
    new_this_month = df[new_mask]
    net_new_customers = int(len(new_this_month))

    churn_mask = (
        df["end_date"].notna()
        & (df["end_date"] >= month_start)
        & (df["end_date"] <= month_end)
    )
    churned_this_month = int(churn_mask.sum())
    active_at_start = len(active_prior)
    churn_rate_pct = (
        round(churned_this_month / active_at_start * 100, 1) if active_at_start else 0.0
    )

    top3 = (
        new_this_month
        .sort_values(["mrr_usd", "customer_name"], ascending=[False, True])
        .head(3)
    )
    top_3_new_signups = [
        {"name": r["customer_name"], "mrr": r["mrr_usd"], "industry": r["industry"]}
        for _, r in top3.iterrows()
    ]

    return {
        "current_arr":        current_arr,
        "prior_month_arr":    prior_arr,
        "arr_change_pct":     arr_change_pct,
        "net_new_customers":  net_new_customers,
        "churned_this_month": churned_this_month,
        "churn_rate_pct":     churn_rate_pct,
        "top_3_new_signups":  top_3_new_signups,
    }


def cohort_retention(df: pd.DataFrame, as_of_month: str) -> pd.DataFrame:
    """
    Cohort retention table, evaluated as of as_of_month.

    Index  : signup month (YYYY-MM), only cohorts up to as_of_month
    Columns: cohort_size, month_1, month_3, month_6, month_12
    Values : % of cohort still active at that age
             NaN = milestone falls after as_of_month_end (future data)

    "Surviving to month N" means end_date is NaT OR end_date > milestone.
    Note: this uses actual end_date values, so for milestones that fall
    after as_of_month we would "see the future" of any churn that has
    already been recorded. In practice this only matters for cohorts whose
    milestone dates exceed as_of_month_end — those cells are left NaN.
    """
    _, as_of_end = _month_bounds(as_of_month)

    df = df.copy()
    df["cohort"] = df["signup_date"].dt.to_period("M")
    as_of_period = pd.Period(as_of_month, freq="M")
    milestones = [1, 3, 6, 12]

    records = []
    for cohort in sorted(df["cohort"].dropna().unique()):
        if cohort > as_of_period:
            continue                          # skip cohorts that haven't started yet
        cohort_start = cohort.to_timestamp()
        cohort_df    = df[df["cohort"] == cohort]
        cohort_size  = len(cohort_df)
        if cohort_size == 0:
            continue

        row = {"cohort": str(cohort), "cohort_size": cohort_size}
        for m in milestones:
            milestone = cohort_start + pd.DateOffset(months=m)
            if milestone > as_of_end:
                row[f"month_{m}"] = float("nan")   # too early as of this report
            else:
                survived = cohort_df[
                    cohort_df["end_date"].isna() | (cohort_df["end_date"] > milestone)
                ]
                row[f"month_{m}"] = round(len(survived) / cohort_size * 100, 1)
        records.append(row)

    if not records:
        cols = ["cohort_size", "month_1", "month_3", "month_6", "month_12"]
        return pd.DataFrame(columns=cols)

    return pd.DataFrame(records).set_index("cohort")


def arr_waterfall(df: pd.DataFrame, as_of_month: str) -> dict:
    """
    ARR waterfall for a given month.

    starting_arr + new_arr + expansion_arr - churn_arr == ending_arr
    Prints a warning to the console if this doesn't balance.
    expansion_arr is always 0 for the MVP (no upsell data).
    """
    month_start, month_end = _month_bounds(as_of_month)
    prior_month_end = month_start - pd.Timedelta(days=1)

    starting_arr  = float(_active_at(df, prior_month_end)["mrr_usd"].sum() * 12)
    expansion_arr = 0.0

    new_customers = df[
        (df["signup_date"] >= month_start) & (df["signup_date"] <= month_end)
    ]
    new_arr = float(new_customers["mrr_usd"].sum() * 12)

    churned = df[
        df["end_date"].notna()
        & (df["end_date"] >= month_start)
        & (df["end_date"] <= month_end)
    ]
    churn_arr = float(churned["mrr_usd"].sum() * 12)

    ending_arr = float(_active_at(df, month_end)["mrr_usd"].sum() * 12)

    computed = starting_arr + new_arr + expansion_arr - churn_arr
    if not math.isclose(computed, ending_arr, rel_tol=1e-6):
        print(
            f"WARNING [{as_of_month}] ARR waterfall doesn't balance: "
            f"start+new-churn={computed:,.0f}  actual ending={ending_arr:,.0f}  "
            f"gap={ending_arr - computed:,.0f}"
        )

    return {
        "starting_arr":  starting_arr,
        "new_arr":       new_arr,
        "expansion_arr": expansion_arr,
        "churn_arr":     churn_arr,
        "ending_arr":    ending_arr,
    }


def geography_mix_by_month(df: pd.DataFrame, as_of_month: str) -> pd.DataFrame:
    """
    Active customer count by country, from the first signup month up to
    and including as_of_month. Future months are excluded.
    Rows = month (YYYY-MM), Columns = country, Values = integer count.
    """
    min_m     = df["signup_date"].min().to_period("M")
    max_m     = pd.Period(as_of_month, freq="M")

    records = []
    for month in pd.period_range(min_m, max_m, freq="M"):
        ms = month.to_timestamp()
        me = ms + pd.offsets.MonthEnd(0)
        counts = _active_during(df, ms, me).groupby("country").size()
        row = {"month": str(month)}
        row.update(counts.to_dict())
        records.append(row)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records).set_index("month").fillna(0).astype(int)


def industry_mix_by_month(df: pd.DataFrame, as_of_month: str) -> pd.DataFrame:
    """
    Active customer count by industry, from the first signup month up to
    and including as_of_month. Future months are excluded.
    Rows = month (YYYY-MM), Columns = industry, Values = integer count.
    """
    min_m = df["signup_date"].min().to_period("M")
    max_m = pd.Period(as_of_month, freq="M")

    records = []
    for month in pd.period_range(min_m, max_m, freq="M"):
        ms = month.to_timestamp()
        me = ms + pd.offsets.MonthEnd(0)
        counts = _active_during(df, ms, me).groupby("industry").size()
        row = {"month": str(month)}
        row.update(counts.to_dict())
        records.append(row)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records).set_index("month").fillna(0).astype(int)


def logo_highlights(df: pd.DataFrame, as_of_month: str, n: int = 5) -> list:
    """
    Top N new customers in as_of_month, sorted by MRR desc (name asc for ties).
    Returns a list of dicts: name, domain, mrr, industry, country.
    """
    month_start, month_end = _month_bounds(as_of_month)
    new_this_month = df[
        (df["signup_date"] >= month_start) & (df["signup_date"] <= month_end)
    ]

    top_n = (
        new_this_month
        .sort_values(["mrr_usd", "customer_name"], ascending=[False, True])
        .head(n)
    )

    return [
        {
            "name":     r["customer_name"],
            "domain":   r["customer_domain"],
            "mrr":      r["mrr_usd"],
            "industry": r["industry"],
            "country":  r["country"],
        }
        for _, r in top_n.iterrows()
    ]


def icp_snapshot(df: pd.DataFrame, as_of_month: str) -> dict:
    """
    Profile of the top quartile of customers active as of as_of_month.

    Returns avg_mrr, median_mrr, top_industry, top_country,
    inbound_pct, outbound_pct, sample_size.
    """
    _, as_of_end = _month_bounds(as_of_month)
    active = _active_at(df, as_of_end).copy()

    if active.empty:
        return {
            "avg_mrr": 0.0, "median_mrr": 0.0,
            "top_industry": None, "top_country": None,
            "inbound_pct": 0.0, "outbound_pct": 0.0,
            "sample_size": 0,
        }

    threshold = active["mrr_usd"].quantile(0.75)
    top_q = active[active["mrr_usd"] >= threshold]

    if top_q.empty:
        top_q = active

    total = len(top_q)
    channel_counts = top_q["acquisition_channel"].value_counts()

    return {
        "avg_mrr":    round(float(top_q["mrr_usd"].mean()), 2),
        "median_mrr": round(float(top_q["mrr_usd"].median()), 2),
        "top_industry": str(top_q["industry"].value_counts().idxmax()),
        "top_country":  str(top_q["country"].value_counts().idxmax()),
        "inbound_pct":  round(channel_counts.get("inbound",  0) / total * 100, 1),
        "outbound_pct": round(channel_counts.get("outbound", 0) / total * 100, 1),
        "sample_size":  total,
    }
