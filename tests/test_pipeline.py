"""
End-to-end smoke test for ManageUp.
Run from the project root: python tests/test_pipeline.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

AS_OF = "2025-04"
CSV   = os.path.join(os.path.dirname(__file__), "..", "sample_data", "demo_transactions.csv")

failures = []

def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}" + (f": {detail}" if detail else ""))
        failures.append(label)

print("=== ManageUp smoke test ===")
print(f"CSV:         {os.path.abspath(CSV)}")
print(f"as_of_month: {AS_OF}")
print()

# ------------------------------------------------------------------
# 1. Load and clean
# ------------------------------------------------------------------
print("[1/3] Loading data...")
try:
    from metrics import (
        load_and_clean, summary_kpis, cohort_retention, arr_waterfall,
        geography_mix_by_month, industry_mix_by_month,
        logo_highlights, icp_snapshot,
    )
    df = load_and_clean(CSV)
    check("load_and_clean returns rows", len(df) > 0, f"got {len(df)} rows")
except Exception as exc:
    check("load_and_clean", False, str(exc))
    df = None

# ------------------------------------------------------------------
# 2. All metric functions
# ------------------------------------------------------------------
print("[2/3] Computing metrics...")
if df is not None:
    try:
        kpis = summary_kpis(df, AS_OF)
        check("summary_kpis", isinstance(kpis, dict))
    except Exception as exc:
        check("summary_kpis", False, str(exc))

    try:
        ret = cohort_retention(df, AS_OF)
        check("cohort_retention", len(ret) > 0)
    except Exception as exc:
        check("cohort_retention", False, str(exc))

    try:
        wf = arr_waterfall(df, AS_OF)
        check("arr_waterfall", "ending_arr" in wf)
    except Exception as exc:
        check("arr_waterfall", False, str(exc))

    try:
        geo = geography_mix_by_month(df, AS_OF)
        check("geography_mix_by_month", len(geo) > 0)
    except Exception as exc:
        check("geography_mix_by_month", False, str(exc))

    try:
        ind = industry_mix_by_month(df, AS_OF)
        check("industry_mix_by_month", len(ind) > 0)
    except Exception as exc:
        check("industry_mix_by_month", False, str(exc))

    try:
        logos = logo_highlights(df, AS_OF, n=5)
        check("logo_highlights", isinstance(logos, list))
    except Exception as exc:
        check("logo_highlights", False, str(exc))

    try:
        icp = icp_snapshot(df, AS_OF)
        check("icp_snapshot", isinstance(icp, dict))
    except Exception as exc:
        check("icp_snapshot", False, str(exc))

# ------------------------------------------------------------------
# 3. Full PDF generation
# ------------------------------------------------------------------
print("[3/3] Generating PDF...")
with tempfile.TemporaryDirectory() as tmpdir:
    pdf_path = os.path.join(tmpdir, "smoke_report.pdf")
    try:
        from report import build_report
        build_report(
            CSV, AS_OF, pdf_path,
            commentary="Smoke test commentary.",
            logo_notes={},
        )

        exists = os.path.isfile(pdf_path)
        check("PDF file exists", exists)

        if exists:
            size = os.path.getsize(pdf_path)
            check("PDF > 50 KB", size > 50_000, f"actual {size:,} bytes")
            check("PDF > 200 KB (proxy for multi-page)", size > 200_000,
                  f"actual {size:,} bytes")

            with open(pdf_path, "rb") as f:
                content = f.read()
            page_count = content.count(b"/Type /Page\n") + content.count(b"/Type /Page\r")
            if page_count == 0:
                # fallback: count stream objects as loose proxy
                page_count = content.count(b"endstream")
            check("PDF appears multi-page", page_count > 1,
                  f"page marker count: {page_count}")

    except Exception as exc:
        check("build_report", False, str(exc))

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print()
if failures:
    print(f"FAIL  ({len(failures)} check(s) failed: {', '.join(failures)})")
    sys.exit(1)
else:
    print("PASS  All checks passed.")
