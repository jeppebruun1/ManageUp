"""
Metrics engine for ManageUp — transaction-based model.
Input: one row per monthly charge (transaction_date, customer_name, customer_domain,
       amount_usd, acquisition_channel, country, industry).
All functions are pure: they take a DataFrame and return plain Python types or DataFrames.
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


def _snapshot(df: pd.DataFrame, month: pd.Period) -> pd.DataFrame:
    """
    One row per customer with a charge in the given month.
    If a customer somehow has multiple rows in one month, keeps the last by transaction_date.
    """
    rows = df[df["month"] == month]
    if rows.empty:
        return rows.copy()
    return (
        rows.sort_values("transaction_date")
            .groupby("customer_name", as_index=False)
            .last()
            .reset_index(drop=True)
    )


def _first_months(df: pd.DataFrame) -> pd.Series:
    """First charge month per customer (customer_name → pd.Period)."""
    return df.groupby("customer_name")["month"].min()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_and_clean(csv_path: str) -> pd.DataFrame:
    """
    Load the CSV and parse transaction_date.
    Adds a 'month' Period column for fast grouping.
    """
    df = pd.read_csv(csv_path)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["month"] = df["transaction_date"].dt.to_period("M")
    return df


def summary_kpis(df: pd.DataFrame, as_of_month: str) -> dict:
    """
    Key metrics for a given month.

    Returns:
        current_arr         - ARR of all active customers at month-end
        prior_month_arr     - ARR at the end of the previous month
        arr_change_pct      - MoM ARR growth (%)
        net_new_customers   - customers with their first-ever charge this month
        churned_this_month  - customers active last month with no charge this month
        churn_rate_pct      - churned / active-last-month (%)
        top_3_new_signups   - list of dicts: name, mrr, industry
    """
    period      = pd.Period(as_of_month, freq="M")
    prev_period = period - 1

    snap_curr = _snapshot(df, period)
    snap_prev = _snapshot(df, prev_period)

    current_arr    = float(snap_curr["amount_usd"].sum() * 12)
    prior_arr      = float(snap_prev["amount_usd"].sum() * 12)
    arr_change_pct = (
        round((current_arr - prior_arr) / prior_arr * 100, 1) if prior_arr else 0.0
    )

    curr_names = set(snap_curr["customer_name"])
    prev_names = set(snap_prev["customer_name"])
    fm         = _first_months(df)

    new_names      = {n for n in curr_names if fm.get(n) == period}
    churned_names  = prev_names - curr_names

    net_new_customers  = len(new_names)
    churned_this_month = len(churned_names)
    active_at_start    = len(prev_names)
    churn_rate_pct = (
        round(churned_this_month / active_at_start * 100, 1) if active_at_start else 0.0
    )

    new_rows = snap_curr[snap_curr["customer_name"].isin(new_names)]
    top3 = (
        new_rows
        .sort_values(["amount_usd", "customer_name"], ascending=[False, True])
        .head(3)
    )
    top_3_new_signups = [
        {"name": r["customer_name"], "mrr": r["amount_usd"], "industry": r["industry"]}
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
    Cohort retention table evaluated as of as_of_month.

    Index  : first charge month (YYYY-MM), only cohorts up to as_of_month
    Columns: cohort_size, month_1, month_3, month_6, month_12
    Values : % of cohort still active (has a charge) at that milestone age
             NaN = milestone falls after as_of_month (future data)
    """
    as_of_period = pd.Period(as_of_month, freq="M")
    fm           = _first_months(df)

    valid_cohorts = [c for c in fm.unique() if c <= as_of_period]
    oldest        = min(valid_cohorts) if valid_cohorts else as_of_period
    max_age       = min(as_of_period.ordinal - oldest.ordinal, 24)
    milestones    = list(range(1, max_age + 1))

    records = []
    for cohort_period in sorted(fm.unique()):
        if cohort_period > as_of_period:
            continue

        cohort_customers = set(fm[fm == cohort_period].index)
        cohort_size      = len(cohort_customers)

        row = {"cohort": str(cohort_period), "cohort_size": cohort_size}
        for m in milestones:
            milestone_period = cohort_period + m
            if milestone_period > as_of_period:
                row[f"month_{m}"] = float("nan")
            else:
                active_at_milestone = set(
                    df[
                        (df["month"] == milestone_period)
                        & df["customer_name"].isin(cohort_customers)
                    ]["customer_name"]
                )
                row[f"month_{m}"] = round(
                    len(active_at_milestone) / cohort_size * 100, 1
                )
        records.append(row)

    if not records:
        cols = ["cohort_size", "month_1", "month_3", "month_6", "month_12"]
        return pd.DataFrame(columns=cols)

    return pd.DataFrame(records).set_index("cohort")


def arr_waterfall(df: pd.DataFrame, as_of_month: str) -> dict:
    """
    ARR waterfall for a given month.

    starting_arr + new_arr + net_expansion_arr - churn_arr == ending_arr

    net_expansion_arr = sum of (current_amount - prior_amount) for customers
    active in both this month and last month. Positive = net expansion,
    negative = net contraction.
    """
    period      = pd.Period(as_of_month, freq="M")
    prev_period = period - 1

    snap_curr = _snapshot(df, period)
    snap_prev = _snapshot(df, prev_period)

    curr_names = set(snap_curr["customer_name"])
    prev_names = set(snap_prev["customer_name"])
    fm         = _first_months(df)

    starting_arr = float(snap_prev["amount_usd"].sum() * 12)
    ending_arr   = float(snap_curr["amount_usd"].sum() * 12)

    new_names = {n for n in curr_names if fm.get(n) == period}
    new_arr   = float(
        snap_curr[snap_curr["customer_name"].isin(new_names)]["amount_usd"].sum() * 12
    )

    churned_names = prev_names - curr_names
    churn_arr     = float(
        snap_prev[snap_prev["customer_name"].isin(churned_names)]["amount_usd"].sum() * 12
    )

    retained_names = curr_names & prev_names
    if retained_names:
        curr_amts = (
            snap_curr[snap_curr["customer_name"].isin(retained_names)]
            .set_index("customer_name")["amount_usd"]
        )
        prev_amts = (
            snap_prev[snap_prev["customer_name"].isin(retained_names)]
            .set_index("customer_name")["amount_usd"]
        )
        net_expansion_arr = float(curr_amts.subtract(prev_amts, fill_value=0).sum() * 12)
    else:
        net_expansion_arr = 0.0

    computed = starting_arr + new_arr + net_expansion_arr - churn_arr
    if not math.isclose(computed, ending_arr, rel_tol=1e-6):
        print(
            f"WARNING [{as_of_month}] ARR waterfall doesn't balance: "
            f"computed={computed:,.0f}  actual={ending_arr:,.0f}  "
            f"gap={ending_arr - computed:,.0f}"
        )

    return {
        "starting_arr":      starting_arr,
        "new_arr":           new_arr,
        "net_expansion_arr": net_expansion_arr,
        "churn_arr":         churn_arr,
        "ending_arr":        ending_arr,
    }


def geography_mix_by_month(df: pd.DataFrame, as_of_month: str) -> pd.DataFrame:
    """
    Active customer count by country per month, up to as_of_month.
    Rows = month (YYYY-MM), Columns = country, Values = integer count.
    """
    min_m = df["month"].min()
    max_m = pd.Period(as_of_month, freq="M")

    records = []
    for month in pd.period_range(min_m, max_m, freq="M"):
        snap   = _snapshot(df, month)
        counts = snap.groupby("country").size()
        row    = {"month": str(month)}
        row.update(counts.to_dict())
        records.append(row)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records).set_index("month").fillna(0).astype(int)


def industry_mix_by_month(df: pd.DataFrame, as_of_month: str) -> pd.DataFrame:
    """
    Active customer count by industry per month, up to as_of_month.
    Rows = month (YYYY-MM), Columns = industry, Values = integer count.
    """
    min_m = df["month"].min()
    max_m = pd.Period(as_of_month, freq="M")

    records = []
    for month in pd.period_range(min_m, max_m, freq="M"):
        snap   = _snapshot(df, month)
        counts = snap.groupby("industry").size()
        row    = {"month": str(month)}
        row.update(counts.to_dict())
        records.append(row)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records).set_index("month").fillna(0).astype(int)


def logo_highlights(df: pd.DataFrame, as_of_month: str, n: int = 5) -> list:
    """
    Top N new customers in as_of_month (first-ever charge this month),
    sorted by MRR desc (name asc for ties).
    """
    period = pd.Period(as_of_month, freq="M")
    snap   = _snapshot(df, period)
    fm     = _first_months(df)

    new_names = {name for name in snap["customer_name"] if fm.get(name) == period}
    top_n = (
        snap[snap["customer_name"].isin(new_names)]
        .sort_values(["amount_usd", "customer_name"], ascending=[False, True])
        .head(n)
    )

    return [
        {
            "name":     r["customer_name"],
            "domain":   r["customer_domain"],
            "mrr":      r["amount_usd"],
            "industry": r["industry"],
            "country":  r["country"],
        }
        for _, r in top_n.iterrows()
    ]


# ---------------------------------------------------------------------------
# Sales pipeline
# ---------------------------------------------------------------------------

PIPELINE_STAGES = [
    "Discovery", "Demo", "Proposal", "Negotiation", "Verbal Agreement",
]
STAGE_PROBABILITIES = {
    "Discovery":         0.10,
    "Demo":              0.25,
    "Proposal":          0.50,
    "Negotiation":       0.75,
    "Verbal Agreement":  0.90,
}


def load_pipeline(csv_path: str) -> pd.DataFrame:
    """Load a pipeline CSV and parse expected_close_date."""
    df = pd.read_csv(csv_path)
    df["expected_close_date"] = pd.to_datetime(
        df["expected_close_date"], errors="coerce"
    )
    return df


def pipeline_summary(pipeline_df: pd.DataFrame, current_arr: float = 0.0) -> dict:
    """
    Compute sales pipeline metrics.

    Returns:
        total_pipeline_arr      - sum(amount_usd) * 12 across all open opps
        weighted_pipeline_arr   - probability-weighted pipeline ARR
        open_opportunities      - count of open deals (in recognized stages)
        avg_deal_size           - mean amount_usd (monthly)
        coverage_ratio          - total_pipeline_arr / current_arr
        by_stage                - dict: stage -> {count, amount_arr, weighted_arr}
        top_5_deals             - list of dicts with opportunity, company, stage, mrr, close_date
    """
    df = pipeline_df[pipeline_df["stage"].isin(PIPELINE_STAGES)].copy()

    total_mrr          = float(df["amount_usd"].sum())
    total_pipeline_arr = total_mrr * 12

    df["probability"]  = df["stage"].map(STAGE_PROBABILITIES)
    weighted_mrr       = float((df["amount_usd"] * df["probability"]).sum())
    weighted_pipeline_arr = weighted_mrr * 12

    open_opportunities = len(df)
    avg_deal_size      = float(df["amount_usd"].mean()) if open_opportunities else 0.0
    coverage_ratio     = round(total_pipeline_arr / current_arr, 2) if current_arr > 0 else 0.0

    by_stage = {}
    for stage in PIPELINE_STAGES:
        s_df = df[df["stage"] == stage]
        by_stage[stage] = {
            "count":        int(len(s_df)),
            "amount_arr":   float(s_df["amount_usd"].sum() * 12),
            "weighted_arr": float((s_df["amount_usd"] * STAGE_PROBABILITIES[stage]).sum() * 12),
        }

    top = (
        df.sort_values(["amount_usd", "company_name"], ascending=[False, True]).head(5)
    )
    top_5_deals = []
    for _, r in top.iterrows():
        close = r["expected_close_date"]
        close_str = close.strftime("%d %b %Y") if pd.notna(close) else ""
        top_5_deals.append({
            "opportunity": str(r.get("opportunity_name", "")),
            "company":     str(r["company_name"]),
            "stage":       str(r["stage"]),
            "mrr":         float(r["amount_usd"]),
            "close_date":  close_str,
        })

    return {
        "total_pipeline_arr":    total_pipeline_arr,
        "weighted_pipeline_arr": weighted_pipeline_arr,
        "open_opportunities":    open_opportunities,
        "avg_deal_size":         avg_deal_size,
        "coverage_ratio":        coverage_ratio,
        "by_stage":              by_stage,
        "top_5_deals":           top_5_deals,
    }


def icp_snapshot(df: pd.DataFrame, as_of_month: str) -> dict:
    """
    Profile of the top quartile of customers active as of as_of_month.
    """
    period = pd.Period(as_of_month, freq="M")
    snap   = _snapshot(df, period)

    if snap.empty:
        return {
            "avg_mrr": 0.0, "median_mrr": 0.0,
            "top_industry": None, "top_country": None,
            "inbound_pct": 0.0, "outbound_pct": 0.0,
            "sample_size": 0,
        }

    threshold = snap["amount_usd"].quantile(0.75)
    top_q = snap[snap["amount_usd"] >= threshold]
    if top_q.empty:
        top_q = snap

    total          = len(top_q)
    channel_counts = top_q["acquisition_channel"].value_counts()

    return {
        "avg_mrr":      round(float(top_q["amount_usd"].mean()), 2),
        "median_mrr":   round(float(top_q["amount_usd"].median()), 2),
        "top_industry": str(top_q["industry"].value_counts().idxmax()),
        "top_country":  str(top_q["country"].value_counts().idxmax()),
        "inbound_pct":  round(channel_counts.get("inbound",  0) / total * 100, 1),
        "outbound_pct": round(channel_counts.get("outbound", 0) / total * 100, 1),
        "sample_size":  total,
    }
