"""
ManageUp — Streamlit UI (Lovable.dev-inspired)
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
# Required columns
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = [
    "customer_name", "customer_domain", "amount_usd",
    "transaction_date", "acquisition_channel",
    "country", "industry",
]
PIPELINE_REQUIRED_COLUMNS = [
    "opportunity_name", "company_name", "stage",
    "amount_usd", "expected_close_date",
]

# ---------------------------------------------------------------------------
# Lovable.dev-inspired styling
# ---------------------------------------------------------------------------
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<style>
/* Hide Streamlit chrome */
#MainMenu                        { visibility: hidden; }
footer                           { visibility: hidden; }
header                           { visibility: hidden; }
[data-testid="stDeployButton"]   { display: none; }

/* Base */
html, body, [class*="css"], .stApp, [data-testid="stMarkdownContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.stApp {
    background:
        radial-gradient(ellipse 60% 40% at 100% 0%, rgba(139, 92, 246, 0.06), transparent 60%),
        radial-gradient(ellipse 50% 40% at 0% 100%, rgba(6, 182, 212, 0.05), transparent 60%),
        #F6F7FB;
}
.main .block-container {
    padding-top: 0 !important;
    padding-bottom: 4rem;
    max-width: 780px;
}

/* Logo (lives inside hero, top-left) */
.mu-logo {
    position: absolute;
    top: 1.25rem;
    left: 1.5rem;
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 700;
    font-size: 18px;
    letter-spacing: -0.01em;
    color: #FFFFFF;
    z-index: 2;
}
.mu-logo-mark {
    width: 26px; height: 26px;
    border-radius: 7px;
    background: linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 10px rgba(139, 92, 246, 0.4);
}
.mu-logo-mark svg { width: 15px; height: 15px; stroke: #FFFFFF; }
.mu-logo span.mu-logo-up {
    background: linear-gradient(135deg, #C4B5FD 0%, #67E8F9 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* Hero */
.mu-hero {
    margin: -1rem -1rem 2rem -1rem;
    padding: 4rem 2rem 3rem 2rem;
    border-radius: 0 0 24px 24px;
    background:
        radial-gradient(ellipse 80% 60% at 30% 20%, rgba(139, 92, 246, 0.35), transparent 60%),
        radial-gradient(ellipse 60% 50% at 80% 60%, rgba(6, 182, 212, 0.28), transparent 60%),
        linear-gradient(180deg, #0B0F1A 0%, #0F172A 100%);
    color: #FFFFFF;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.mu-hero h1 {
    font-size: 48px !important;
    font-weight: 800 !important;
    line-height: 1.05 !important;
    letter-spacing: -0.02em;
    margin: 0 0 1rem 0 !important;
    color: #FFFFFF !important;
    background: linear-gradient(135deg, #FFFFFF 0%, #C7D2FE 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.mu-hero p {
    font-size: 17px;
    color: #94A3B8;
    margin: 0 auto 1.5rem auto;
    max-width: 480px;
    line-height: 1.5;
}
.mu-feature-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
    margin-top: 1.5rem;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
}
.mu-feature {
    font-size: 12px;
    font-weight: 500;
    color: #CBD5E1;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 999px;
    padding: 5px 12px;
    backdrop-filter: blur(4px);
}

/* Vertical side stepper */
html { scroll-behavior: smooth; }
.mu-stepper {
    position: fixed;
    top: 50%;
    left: 24px;
    transform: translateY(-50%);
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 16px 14px;
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    backdrop-filter: blur(8px);
    box-shadow: 0 4px 20px rgba(15, 23, 42, 0.04);
    z-index: 100;
}
.mu-step {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #64748B;
    font-size: 13px;
    font-weight: 500;
    text-decoration: none !important;
    cursor: pointer;
    padding: 8px 10px;
    border-radius: 8px;
    transition: background 0.15s ease, color 0.15s ease;
    white-space: nowrap;
}
.mu-step:hover {
    background: #F1F5F9;
    color: #0F172A;
}
.mu-step:hover .mu-step-num {
    background: #0F172A;
    color: #FFFFFF;
}
.mu-step-line {
    width: 1px;
    height: 12px;
    background: #E2E8F0;
    margin: 0 0 0 21px;
}
@media (max-width: 1100px) {
    .mu-stepper { display: none; }
}

/* Client-side active highlight when user clicks a step (URL fragment changes).
   Overrides server-rendered active class. */
:root:has(#stage-1:target) .mu-step,
:root:has(#stage-2:target) .mu-step,
:root:has(#stage-3:target) .mu-step,
:root:has(#stage-4:target) .mu-step {
    color: #94A3B8; font-weight: 500;
}
:root:has(#stage-1:target) .mu-step .mu-step-num,
:root:has(#stage-2:target) .mu-step .mu-step-num,
:root:has(#stage-3:target) .mu-step .mu-step-num,
:root:has(#stage-4:target) .mu-step .mu-step-num {
    background: #F1F5F9; color: #94A3B8;
}
:root:has(#stage-1:target) a.mu-step[href="#stage-1"],
:root:has(#stage-2:target) a.mu-step[href="#stage-2"],
:root:has(#stage-3:target) a.mu-step[href="#stage-3"],
:root:has(#stage-4:target) a.mu-step[href="#stage-4"] {
    color: #0F172A; font-weight: 600;
}
:root:has(#stage-1:target) a.mu-step[href="#stage-1"] .mu-step-num,
:root:has(#stage-2:target) a.mu-step[href="#stage-2"] .mu-step-num,
:root:has(#stage-3:target) a.mu-step[href="#stage-3"] .mu-step-num,
:root:has(#stage-4:target) a.mu-step[href="#stage-4"] .mu-step-num {
    background: linear-gradient(135deg, #8B5CF6, #06B6D4);
    color: #FFFFFF;
}
.mu-step-num {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #F1F5F9;
    color: #94A3B8;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    flex-shrink: 0;
}
.mu-step.active .mu-step-num {
    background: linear-gradient(135deg, #8B5CF6, #06B6D4);
    color: #FFFFFF;
}
.mu-step.active { color: #0F172A; font-weight: 600; }
.mu-step.done .mu-step-num { background: #0F172A; color: #FFFFFF; }
.mu-step.done { color: #0F172A; }
.mu-step-line {
    flex: 1;
    height: 1px;
    background: #E2E8F0;
    margin: 0 4px;
}

/* Stage card */
.mu-card {
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1.75rem;
    margin: 0 0 1.5rem 0;
    background: #FFFFFF;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}
.mu-card-header { display: flex; align-items: center; gap: 12px; margin-bottom: 0.5rem; }
.mu-card-badge {
    width: 28px; height: 28px;
    border-radius: 8px;
    background: #F1F5F9;
    color: #0F172A;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
}
.mu-card-title { font-size: 18px; font-weight: 700; color: #0F172A; margin: 0; }
.mu-card-desc { font-size: 14px; color: #64748B; margin: 0 0 1.25rem 0; line-height: 1.5; }

/* Required columns checklist */
.mu-checklist {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
}
.mu-checklist-title {
    font-size: 12px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
    color: #64748B; margin-bottom: 0.5rem;
}
.mu-checklist-items { display: flex; flex-wrap: wrap; gap: 6px; }
.mu-chip {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12px;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 3px 8px;
    color: #334155;
}
.mu-chip.ok { background: #ECFDF5; border-color: #A7F3D0; color: #065F46; }
.mu-chip.miss { background: #FEF2F2; border-color: #FECACA; color: #991B1B; }

/* Stats card */
.mu-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.mu-stat-label {
    font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
    color: #94A3B8; margin: 0 0 4px 0;
}
.mu-stat-value { font-size: 22px; font-weight: 700; color: #0F172A; line-height: 1.1; }
.mu-stat-sub { font-size: 12px; color: #64748B; margin-top: 2px; }

/* Buttons */
[data-testid="stBaseButton-primary"],
button[kind="primary"] {
    background: linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.7rem 1.25rem !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
[data-testid="stBaseButton-primary"]:hover,
button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(139, 92, 246, 0.35) !important;
}
[data-testid="stBaseButton-secondary"], button[kind="secondary"] {
    border-radius: 10px !important;
    border: 1px solid #E2E8F0 !important;
    background: #FFFFFF !important;
    color: #0F172A !important;
    font-weight: 500 !important;
}

/* File uploader */
[data-testid="stFileUploader"] section {
    border: 1.5px dashed #CBD5E1 !important;
    border-radius: 12px !important;
    background: #F8FAFC !important;
    padding: 1.5rem !important;
}
[data-testid="stFileUploader"] section:hover {
    border-color: #8B5CF6 !important;
    background: #FAF5FF !important;
}

/* Inputs */
.stTextArea textarea, .stTextInput input, .stSelectbox > div > div {
    border-radius: 10px !important;
    border: 1px solid #E2E8F0 !important;
    font-family: 'Inter', sans-serif !important;
}

/* Generation panel */
.mu-progress {
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    color: #FFFFFF;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.mu-progress h4 { color: #FFFFFF; margin: 0 0 0.5rem 0; font-size: 15px; font-weight: 600; }
.mu-progress p  { color: #94A3B8; margin: 0; font-size: 13px; }

/* Hide labels we replace with cards */
.mu-hide-label label { display: none !important; }

/* Caption polish */
[data-testid="stCaptionContainer"], .stCaption { color: #64748B !important; }

/* Divider hide (we use cards) */
hr { display: none; }
</style>
""", unsafe_allow_html=True)

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
    "pdf_thumbnail":          None,
    "use_sample":             False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _render_stepper(current: int):
    """current: 1..4"""
    steps = ["Upload", "Review", "Context", "Generate"]
    parts = ['<div class="mu-stepper">']
    for i, name in enumerate(steps, 1):
        cls = "active" if i == current else ("done" if i < current else "")
        parts.append(
            f'<a href="#stage-{i}" class="mu-step {cls}">'
            f'<span class="mu-step-num">{i}</span>{name}</a>'
        )
        if i < len(steps):
            parts.append('<div class="mu-step-line"></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _stage_card_open(num: int, title: str, desc: str):
    st.markdown(
        f'<div class="mu-card" id="stage-{num}">'
        f'<div class="mu-card-header">'
        f'<span class="mu-card-badge">{num}</span>'
        f'<h3 class="mu-card-title">{title}</h3>'
        f'</div>'
        f'<p class="mu-card-desc">{desc}</p>',
        unsafe_allow_html=True,
    )


def _stage_card_close():
    st.markdown("</div>", unsafe_allow_html=True)


def _checklist(present: set, required: list):
    chips = []
    for col in required:
        ok = col in present
        cls = "ok" if ok else "miss"
        mark = "✓" if ok else "✗"
        chips.append(f'<span class="mu-chip {cls}">{mark} {col}</span>')
    st.markdown(
        '<div class="mu-checklist">'
        '<div class="mu-checklist-title">Required columns</div>'
        f'<div class="mu-checklist-items">{"".join(chips)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="mu-hero">'
    '<div class="mu-logo">'
    '<span class="mu-logo-mark">'
    '<svg viewBox="0 0 24 24" fill="none" stroke-width="3" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="4 17 10 11 14 15 20 7"/>'
    '<polyline points="14 7 20 7 20 13"/>'
    '</svg>'
    '</span>'
    'Manage<span class="mu-logo-up">Up</span>'
    '</div>'
    '<h1>Investor updates,<br>on autopilot.</h1>'
    '<p>Consistent monthly reporting your investors actually read — '
    'same numbers, same format, every month. Upload a CSV, get a polished '
    'PDF in under a minute.</p>'
    '<div class="mu-feature-row">'
    '<span class="mu-feature">📊 ARR &amp; retention</span>'
    '<span class="mu-feature">🧊 Cohort triangles</span>'
    '<span class="mu-feature">🎯 ICP breakdowns</span>'
    '<span class="mu-feature">🚀 Pipeline forecast</span>'
    '<span class="mu-feature">✍️ Founder commentary</span>'
    '<span class="mu-feature">📥 Investor-ready PDF</span>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)

# Determine current step
if st.session_state.pdf_bytes:
    current_step = 4
elif st.session_state.last_filename:
    current_step = 3
else:
    current_step = 1

_render_stepper(current_step)

# ============================================================================
# STAGE 1 — UPLOAD
# ============================================================================
_stage_card_open(
    1, "Upload your data",
    "A transactions CSV (required) and an optional sales pipeline CSV.",
)

# Sample data shortcut
SAMPLE_TX   = "sample_data/demo_transactions.csv"
SAMPLE_PIPE = "sample_data/demo_pipeline.csv"
_have_sample = os.path.exists(SAMPLE_TX)

col_a, col_b = st.columns([3, 1])
with col_b:
    if _have_sample and st.button("Try sample data", use_container_width=True):
        st.session_state.use_sample = True
        st.rerun()
with col_a:
    if st.session_state.use_sample:
        st.caption(f"Using sample: {os.path.basename(SAMPLE_TX)}")

uploaded = None
if not st.session_state.use_sample:
    uploaded = st.file_uploader(
        "Transaction data CSV",
        type="csv",
        label_visibility="collapsed",
    )

# Resolve csv_path
csv_path = None
csv_source_name = None
if st.session_state.use_sample:
    csv_path = SAMPLE_TX
    csv_source_name = os.path.basename(SAMPLE_TX)
elif uploaded is not None:
    if st.session_state.last_filename != uploaded.name:
        for k in ("pdf_bytes", "pdf_month", "pdf_timestamp", "pdf_size_kb", "pdf_thumbnail"):
            st.session_state[k] = None
        st.session_state.last_filename = uploaded.name
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as _tmp:
        _tmp.write(uploaded.getvalue())
        csv_path = _tmp.name
    csv_source_name = uploaded.name

if csv_path is None:
    _checklist(set(), REQUIRED_COLUMNS)
    _stage_card_close()
    st.stop()

# Validate + load
try:
    _raw_cols = set(pd.read_csv(csv_path, nrows=0).columns)
    _checklist(_raw_cols, REQUIRED_COLUMNS)
    missing = set(REQUIRED_COLUMNS) - _raw_cols
    if missing:
        st.error(f"CSV is missing columns: {', '.join(sorted(missing))}")
        _stage_card_close()
        st.stop()
    df = load_and_clean(csv_path)
except Exception as exc:
    st.error(f"Could not read CSV: {exc}")
    _stage_card_close()
    st.stop()

# Optional pipeline
st.markdown("&nbsp;", unsafe_allow_html=True)
pipeline_csv_path = None

if st.session_state.use_sample and os.path.exists(SAMPLE_PIPE):
    pipeline_csv_path = SAMPLE_PIPE
    _pipe_preview = pd.read_csv(SAMPLE_PIPE)
    st.caption(f"Sample pipeline loaded: {len(_pipe_preview):,} opportunities")
else:
    pipeline_uploaded = st.file_uploader(
        "Sales pipeline CSV (optional)",
        type="csv",
        help="Required columns: " + ", ".join(PIPELINE_REQUIRED_COLUMNS),
    )
    if pipeline_uploaded is not None:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as _ptmp:
            _ptmp.write(pipeline_uploaded.getvalue())
            _pipe_path = _ptmp.name
        try:
            _p_cols = set(pd.read_csv(_pipe_path, nrows=0).columns)
            _p_miss = set(PIPELINE_REQUIRED_COLUMNS) - _p_cols
            if _p_miss:
                st.error(
                    f"Pipeline CSV is missing: {', '.join(sorted(_p_miss))}. "
                    "Report will skip the pipeline page."
                )
            else:
                pipeline_csv_path = _pipe_path
                _pipe_preview = pd.read_csv(_pipe_path)
                st.caption(f"Pipeline loaded: {len(_pipe_preview):,} opportunities")
        except Exception as exc:
            st.error(f"Could not read pipeline CSV: {exc}")

_stage_card_close()

# ============================================================================
# STAGE 2 — REVIEW
# ============================================================================
_stage_card_open(
    2, "Review your numbers",
    f"Loaded from {csv_source_name}. Pick the reporting month.",
)

_min_m            = df["month"].min()
_max_m            = df["month"].max()
_unique_customers = df["customer_name"].nunique()
_total_amount     = df["amount_usd"].sum()
_min_label = datetime.strptime(str(_min_m), "%Y-%m").strftime("%b %Y")
_max_label = datetime.strptime(str(_max_m), "%Y-%m").strftime("%b %Y")

st.markdown(
    f'<div class="mu-stats">'
    f'<div><p class="mu-stat-label">Transactions</p>'
    f'<div class="mu-stat-value">{len(df):,}</div></div>'
    f'<div><p class="mu-stat-label">Customers</p>'
    f'<div class="mu-stat-value">{_unique_customers:,}</div></div>'
    f'<div><p class="mu-stat-label">Total revenue</p>'
    f'<div class="mu-stat-value">${_total_amount/1000:,.0f}K</div></div>'
    f'<div><p class="mu-stat-label">Date range</p>'
    f'<div class="mu-stat-value" style="font-size:14px;">{_min_label}<br>→ {_max_label}</div></div>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown("&nbsp;", unsafe_allow_html=True)

_months = sorted(
    df["month"].dropna().unique().astype(str),
    reverse=True,
)
as_of_month = st.selectbox(
    "Reporting month",
    options=_months,
    format_func=lambda x: datetime.strptime(x, "%Y-%m").strftime("%B %Y"),
)

_stage_card_close()

# ============================================================================
# STAGE 3 — ADD CONTEXT
# ============================================================================
_stage_card_open(
    3, "Add your commentary",
    "Investors read the numbers — but the narrative is yours.",
)

with st.expander("Show example commentary"):
    st.markdown(
        "> **Strong month on net new logos** — closed Vertex Labs and Nimbus Data, "
        "both inbound from our content push. ARR up 14% MoM.\n\n"
        "> **Churn ticked up to 3.2%** — concentrated in our SMB segment. "
        "We're rolling out usage-based pricing in May to address this."
    )

commentary = st.text_area(
    "Founder commentary",
    height=140,
    max_chars=800,
    placeholder=(
        "Share context on this month's performance. "
        "What went well? What's changed? What are you focused on next?"
    ),
    label_visibility="collapsed",
)

top5 = logo_highlights(df, as_of_month, n=5)
logo_notes: dict = {}
if top5:
    st.markdown(
        '<p style="font-size:13px; font-weight:600; color:#0F172A; '
        'margin: 1rem 0 0.5rem 0;">Notes on new signups this month</p>',
        unsafe_allow_html=True,
    )
    for lg in top5:
        note = st.text_input(
            f"Note on {lg['name']}",
            max_chars=140,
            placeholder=f"Why {lg['name']} matters...",
            key=f"note_{lg['name']}_{as_of_month}",
        )
        if note.strip():
            logo_notes[lg["name"]] = note.strip()

_stage_card_close()

# ============================================================================
# STAGE 4 — GENERATE
# ============================================================================
_stage_card_open(
    4, "Generate your report",
    "A 9–10 page PDF with cover, KPIs, retention, cohorts, logos, and pipeline.",
)

if st.button("Generate report PDF", type="primary", use_container_width=True):
    st.session_state.pdf_bytes = None
    st.session_state.pdf_thumbnail = None
    _progress = st.empty()
    try:
        _progress.markdown(
            '<div class="mu-progress">'
            '<h4>⚡ Generating your report</h4>'
            '<p>Crunching numbers · Rendering charts · Building PDF...</p>'
            '</div>',
            unsafe_allow_html=True,
        )
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
            try:
                import pymupdf
                _doc = pymupdf.open(_pdf_path)
                _pix = _doc[0].get_pixmap(dpi=120)
                st.session_state.pdf_thumbnail = _pix.tobytes("png")
                _doc.close()
            except Exception:
                st.session_state.pdf_thumbnail = None
        st.session_state.pdf_month     = as_of_month
        st.session_state.pdf_timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.pdf_size_kb   = round(
            len(st.session_state.pdf_bytes) / 1024
        )
        _progress.empty()
    except Exception as exc:
        _progress.empty()
        st.error(f"Report generation failed: {exc}")

if st.session_state.pdf_bytes:
    _month_label = datetime.strptime(
        st.session_state.pdf_month, "%Y-%m"
    ).strftime("%B %Y")

    if st.session_state.pdf_thumbnail:
        col_t1, col_t2, col_t3 = st.columns([1, 2, 1])
        with col_t2:
            st.image(
                st.session_state.pdf_thumbnail,
                caption=f"Cover — {_month_label}",
                use_container_width=True,
            )

    st.download_button(
        label=f"⬇  Download PDF  —  {_month_label}",
        data=st.session_state.pdf_bytes,
        file_name=f"manageup_{st.session_state.pdf_month}.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary",
    )
    st.caption(
        f"Generated {st.session_state.pdf_timestamp}  ·  "
        f"{st.session_state.pdf_size_kb} KB"
    )

_stage_card_close()
