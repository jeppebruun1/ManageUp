"""
ManageUp — Streamlit UI
Run with:  streamlit run src/app.py
"""
import os
import sys
import tempfile

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
from metrics import load_and_clean
from report import build_report

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ManageUp",
    page_icon="📊",
    layout="centered",
)

REQUIRED_COLUMNS = {
    "customer_name", "customer_domain", "mrr_usd",
    "signup_date", "end_date", "acquisition_channel",
    "country", "industry",
}

# ---------------------------------------------------------------------------
# Session state — keeps the PDF alive across Streamlit reruns so the
# download button doesn't vanish as soon as the user clicks it.
# ---------------------------------------------------------------------------
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "pdf_month" not in st.session_state:
    st.session_state.pdf_month = None

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("ManageUp")
st.markdown(
    "Upload a B2B SaaS transaction CSV, pick a reporting month, "
    "and download a PDF investor report."
)
st.divider()

# ---------------------------------------------------------------------------
# Step 1 — Upload
# ---------------------------------------------------------------------------
st.subheader("Step 1 — Upload your CSV")
uploaded = st.file_uploader("", type="csv", label_visibility="collapsed")

if uploaded is None:
    st.info("Drag and drop a CSV here, or click Browse.")
    st.stop()

# Reset any previously generated PDF when a new file is uploaded
if st.session_state.get("last_filename") != uploaded.name:
    st.session_state.pdf_bytes = None
    st.session_state.pdf_month = None
    st.session_state["last_filename"] = uploaded.name

# Write to a temp file so load_and_clean can read it by path
with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_csv:
    tmp_csv.write(uploaded.getvalue())
    csv_path = tmp_csv.name

# Validate columns
try:
    raw = pd.read_csv(csv_path, nrows=0)
    missing = REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        st.error(f"CSV is missing required columns: {', '.join(sorted(missing))}")
        st.stop()
    df = load_and_clean(csv_path)
except Exception as e:
    st.error(f"Could not read the CSV: {e}")
    st.stop()

# Quick data preview
with st.expander("Preview data", expanded=False):
    st.dataframe(df.head(10), use_container_width=True)

# Quick stats row — use today as the reference point for the preview display
_today = pd.Timestamp.today().normalize()
_active_today = df[df["end_date"].isna() | (df["end_date"] > _today)]
_churned_today = df[df["end_date"].notna() & (df["end_date"] <= _today)]
active_mrr = _active_today["mrr_usd"].sum()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Rows loaded",       len(df))
col2.metric("Active customers",  len(_active_today))
col3.metric("Churned",           len(_churned_today))
col4.metric("Active MRR",        f"${active_mrr:,.0f}")

st.divider()

# ---------------------------------------------------------------------------
# Step 2 — Pick reporting month
# ---------------------------------------------------------------------------
st.subheader("Step 2 — Choose the reporting month")
available_months = sorted(
    df["signup_date"].dt.to_period("M").dropna().unique().astype(str),
    reverse=True,
)

if not available_months:
    st.error("No valid signup dates found in the CSV.")
    st.stop()

as_of_month = st.selectbox(
    "Reporting month",
    available_months,
    help="The report will show metrics for the month you select.",
    label_visibility="collapsed",
)

st.divider()

# ---------------------------------------------------------------------------
# Step 3 — Generate
# ---------------------------------------------------------------------------
st.subheader("Step 3 — Generate & download")

if st.button("Generate Report", type="primary", use_container_width=True):
    st.session_state.pdf_bytes = None   # clear stale result while generating
    try:
        with st.spinner("Crunching numbers and building charts…"):
            with tempfile.TemporaryDirectory() as tmp_dir:
                pdf_path = os.path.join(tmp_dir, "report.pdf")
                build_report(csv_path, as_of_month, pdf_path)
                with open(pdf_path, "rb") as f:
                    st.session_state.pdf_bytes = f.read()
                st.session_state.pdf_month = as_of_month
        st.success("Report ready — click Download below.")
    except Exception as e:
        st.error(f"Report generation failed: {e}")

if st.session_state.pdf_bytes:
    st.download_button(
        label=f"Download PDF  —  {st.session_state.pdf_month}",
        data=st.session_state.pdf_bytes,
        file_name=f"manageup_{st.session_state.pdf_month}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
