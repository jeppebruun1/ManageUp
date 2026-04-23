"""
ManageUp — Streamlit UI
Run with:  streamlit run src/app.py
"""
import os
import sys
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
from metrics import load_and_clean, logo_highlights
from report import build_report

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ManageUp",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Hide Streamlit chrome + CSS polish
# ---------------------------------------------------------------------------
st.markdown("""
<style>
#MainMenu                        { visibility: hidden; }
footer                           { visibility: hidden; }
[data-testid="stDeployButton"]   { display: none; }

/* Breathing room at the top */
.main .block-container           { padding-top: 1rem; }

/* Slightly smaller default h1 */
h1                               { font-size: 2rem !important; }

/* Primary button — dark fill */
[data-testid="stBaseButton-primary"],
button[kind="primary"] {
    background-color: #0F172A !important;
    color: white !important;
    border: none !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Required CSV columns
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = {
    "customer_name", "customer_domain", "amount_usd",
    "transaction_date", "acquisition_channel",
    "country", "industry",
}
PIPELINE_REQUIRED_COLUMNS = {
    "opportunity_name", "company_name", "stage",
    "amount_usd", "expected_close_date",
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_defaults = {
    "last_filename":          None,
    "last_pipeline_filename": None,
    "pdf_bytes":              None,
    "pdf_month":              None,
    "pdf_timestamp":          None,
    "pdf_size_kb":            None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================================
# STAGE 1 — UPLOAD
# ============================================================================
st.title("ManageUp")
st.markdown("Turn transaction data into an investor-ready report.")

uploaded = st.file_uploader(
    "Transaction data CSV",
    type="csv",
    label_visibility="collapsed",
)

if uploaded is None:
    st.info("Drag and drop a CSV file here, or click Browse.")
    st.stop()

pipeline_uploaded = st.file_uploader(
    "Sales pipeline CSV (optional)",
    type="csv",
    help=(
        "Optional. If provided, the report will include a sales pipeline page. "
        "Required columns: opportunity_name, company_name, stage, amount_usd, "
        "expected_close_date."
    ),
)

# Reset PDF when a new file is uploaded
if st.session_state.last_filename != uploaded.name:
    for k in ("pdf_bytes", "pdf_month", "pdf_timestamp", "pdf_size_kb"):
        st.session_state[k] = None
    st.session_state.last_filename = uploaded.name

# Write to a temp file so pandas can read it by path
with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as _tmp:
    _tmp.write(uploaded.getvalue())
    csv_path = _tmp.name

# Validate columns, then load
try:
    _raw_cols = set(pd.read_csv(csv_path, nrows=0).columns)
    missing   = REQUIRED_COLUMNS - _raw_cols
    if missing:
        st.error(f"CSV is missing columns: {', '.join(sorted(missing))}")
        st.stop()
    df = load_and_clean(csv_path)
except Exception as exc:
    st.error(f"Could not read CSV: {exc}")
    st.stop()

# Optional pipeline CSV
pipeline_csv_path = None
if pipeline_uploaded is not None:
    if st.session_state.last_pipeline_filename != pipeline_uploaded.name:
        st.session_state.last_pipeline_filename = pipeline_uploaded.name

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as _ptmp:
        _ptmp.write(pipeline_uploaded.getvalue())
        _pipe_path = _ptmp.name

    try:
        _p_cols   = set(pd.read_csv(_pipe_path, nrows=0).columns)
        _p_miss   = PIPELINE_REQUIRED_COLUMNS - _p_cols
        if _p_miss:
            st.error(
                f"Pipeline CSV is missing columns: {', '.join(sorted(_p_miss))}. "
                "The report will be generated without the sales pipeline page."
            )
        else:
            pipeline_csv_path = _pipe_path
            _pipe_preview = pd.read_csv(_pipe_path)
            st.caption(
                f"Pipeline loaded: {len(_pipe_preview):,} opportunities"
            )
    except Exception as exc:
        st.error(f"Could not read pipeline CSV: {exc}")
else:
    st.session_state.last_pipeline_filename = None

# ============================================================================
# STAGE 2 — REVIEW
# ============================================================================
st.divider()

_min_m            = df["month"].min()
_max_m            = df["month"].max()
_unique_customers = df["customer_name"].nunique()
st.caption(
    f"Loaded {len(df):,} transactions  ·  "
    f"{_unique_customers:,} customers  ·  "
    f"{_min_m} to {_max_m}"
)

st.dataframe(df.head(5), use_container_width=True)

# Month selector — displays "October 2024", returns "2024-10"
_months = sorted(
    df["month"].dropna().unique().astype(str),
    reverse=True,
)
as_of_month = st.selectbox(
    "Reporting month",
    options=_months,
    format_func=lambda x: datetime.strptime(x, "%Y-%m").strftime("%B %Y"),
)

# ============================================================================
# STAGE 3 — ADD CONTEXT
# ============================================================================
st.divider()

commentary = st.text_area(
    "Founder commentary",
    height=150,
    max_chars=800,
    placeholder=(
        "Share context on this month's performance. "
        "What went well? What's changed? What are you focused on next?"
    ),
)

top5 = logo_highlights(df, as_of_month, n=5)
logo_notes: dict = {}
if top5:
    st.markdown("**Notes on new signups this month**")
    for lg in top5:
        note = st.text_input(
            f"Note on {lg['name']}",
            max_chars=140,
            placeholder="Optional: why this signup matters...",
            key=f"note_{lg['name']}_{as_of_month}",
        )
        if note.strip():
            logo_notes[lg["name"]] = note.strip()

# ============================================================================
# STAGE 4 — GENERATE
# ============================================================================
st.divider()

if st.button("Generate report PDF", type="primary", width="stretch"):
    st.session_state.pdf_bytes = None
    try:
        with st.status("Generating report...", expanded=True) as _status:
            st.write("Crunching numbers...")
            st.write("Rendering charts...")
            st.write("Building PDF...")
            with tempfile.TemporaryDirectory() as _tmpdir:
                _pdf_path = os.path.join(_tmpdir, "report.pdf")
                build_report(
                    csv_path,
                    as_of_month,
                    _pdf_path,
                    commentary=commentary,
                    logo_notes=logo_notes,
                    pipeline_csv_path=pipeline_csv_path,
                )
                with open(_pdf_path, "rb") as _f:
                    st.session_state.pdf_bytes = _f.read()
            st.session_state.pdf_month     = as_of_month
            st.session_state.pdf_timestamp = datetime.now().strftime("%H:%M:%S")
            st.session_state.pdf_size_kb   = round(
                len(st.session_state.pdf_bytes) / 1024
            )
            _status.update(
                label="Report ready!", state="complete", expanded=False
            )
    except Exception as exc:
        st.error(f"Report generation failed: {exc}")

if st.session_state.pdf_bytes:
    _month_label = datetime.strptime(
        st.session_state.pdf_month, "%Y-%m"
    ).strftime("%B %Y")
    st.download_button(
        label=f"Download PDF  —  {_month_label}",
        data=st.session_state.pdf_bytes,
        file_name=f"manageup_{st.session_state.pdf_month}.pdf",
        mime="application/pdf",
        width="stretch",
    )
    st.caption(
        f"Generated {st.session_state.pdf_timestamp}  ·  "
        f"{st.session_state.pdf_size_kb} KB"
    )
