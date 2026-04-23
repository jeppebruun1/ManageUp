# ManageUp

ManageUp is a local tool for B2B SaaS founders preparing monthly investor updates. It takes a CSV of subscription transactions, computes standard metrics for a chosen reporting month, and produces a polished multi-page PDF. The goal is to replace the copy-paste spreadsheet process that most early-stage founders use today with a repeatable, one-click workflow. It was built as an MVP to validate the product concept before committing to a production infrastructure.

## What it does

- **Upload** a CSV of B2B SaaS customer records (one row per customer, with MRR, signup date, churn date, country, and industry).
- **Compute** standardized metrics for a user-selected reporting month: ARR trend, ARR waterfall (new / expansion / churn), cohort retention, geography and industry mix, logo highlights, and ICP snapshot — all point-in-time, so past reports stay consistent.
- **Generate** a seven-section PDF investor report, optionally including a founder commentary block and per-customer notes written in the UI.

## The report

1. Executive summary — ARR, net new customers, churn rate, top new signups, founder commentary
2. Cohort retention — heatmap showing what share of each signup cohort was still active at 1, 3, 6, and 12 months
3. ARR waterfall — starting ARR to ending ARR, broken down by new, expansion, and churn
4. Geography mix — stacked bar of active customers by country over time
5. Industry mix — stacked bar of active customers by industry over time
6. Logo highlights — table of new signups this month with optional founder notes
7. ICP snapshot — average and median MRR, top industry and country, inbound vs. outbound split

## Architecture

The stack is Python with pandas for metric computation, matplotlib for charts, ReportLab for PDF assembly, and Streamlit for the UI. pandas was chosen for its period-safe date arithmetic; matplotlib gives full control over chart styling without a front-end build step; ReportLab's Platypus layout engine handles multi-page documents with a custom canvas subclass for page numbering; Streamlit lets the UI live in a single Python file with no JavaScript.

- `src/metrics.py` — all numeric calculations
- `src/charts.py` — chart rendering
- `src/chart_style.py` — shared plot styling
- `src/report.py` — PDF assembly
- `src/app.py` — Streamlit UI
- `sample_data/demo.csv` — fake data for the demo
- `tests/` — verification scripts

## Running the demo

```powershell
# 1. Clone the repo and enter the project directory
cd ManageUp

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the smoke test (optional sanity check)
python tests/test_pipeline.py

# 5. Launch the app
streamlit run src/app.py

# 6. Open http://localhost:8501 and upload sample_data/demo.csv
```

## Known limitations and future work

- Single-tenant, no login, no database — the app runs locally and holds state in memory for one session.
- Industry and country come from the CSV; there is no live enrichment from a domain lookup service.
- Expansion ARR is not computed and is reported as $0 — the input schema is flat-rate subscription only, with no seat-count or tier-change events.
- No month-over-month persistence — each report generation is stateless; historical comparisons depend entirely on what is in the CSV.
- PDF generation is synchronous and blocks the UI; a dataset with thousands of rows would introduce a noticeable delay.
- A Claude-powered design rendering path is planned as a future direction to make the PDF layout fully customizable from natural language.

## About this project

ManageUp was built as a school project MVP in partnership with Claude Code. The implementation — metrics engine, chart pipeline, PDF layout, and Streamlit UI — was developed iteratively over a single session. The core idea being explored is ManageUp as a B2B SaaS product: a service that gives early-stage founders investor-ready reporting without a finance team. The code is a proof of concept for that idea, not a production system.
