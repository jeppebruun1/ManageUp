"""
PDF report builder for ManageUp.
Call build_report(csv_path, as_of_month, output_path) to produce the PDF.
"""
import os
import sys
import tempfile

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Image, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

sys.path.insert(0, os.path.dirname(__file__))
from metrics import (
    arr_waterfall, cohort_retention, geography_mix_by_month,
    industry_mix_by_month, icp_snapshot, load_and_clean,
    logo_highlights, summary_kpis,
)
from charts import (
    plot_arr_trend, plot_arr_waterfall, plot_cohort_heatmap,
    plot_geography_mix, plot_industry_mix,
)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = letter        # 8.5 × 11 inches
MARGIN    = 0.75 * inch
CONTENT_W = PAGE_W - 2 * MARGIN

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
C_BLUE        = colors.HexColor("#2563EB")
C_BLUE_LIGHT  = colors.HexColor("#EFF6FF")
C_BLUE_BORDER = colors.HexColor("#BFDBFE")
C_GREEN       = colors.HexColor("#16A34A")
C_RED         = colors.HexColor("#DC2626")
C_GRAY        = colors.HexColor("#6B7280")
C_DARK        = colors.HexColor("#111827")
C_ROW_ALT     = colors.HexColor("#F9FAFB")

# ---------------------------------------------------------------------------
# Text styles
# ---------------------------------------------------------------------------
_ss = getSampleStyleSheet()

S_TITLE = ParagraphStyle(
    "Title", parent=_ss["Normal"],
    fontSize=24, fontName="Helvetica-Bold",
    textColor=C_DARK, leading=28, spaceAfter=2,
)
S_SUBTITLE = ParagraphStyle(
    "Subtitle", parent=_ss["Normal"],
    fontSize=11, fontName="Helvetica",
    textColor=C_GRAY, leading=14, spaceAfter=12,
)
S_H2 = ParagraphStyle(
    "H2", parent=_ss["Normal"],
    fontSize=14, fontName="Helvetica-Bold",
    textColor=C_BLUE, leading=17, spaceAfter=6, spaceBefore=4,
)
S_BODY = ParagraphStyle(
    "Body", parent=_ss["Normal"],
    fontSize=10, fontName="Helvetica",
    textColor=C_DARK, leading=14, spaceAfter=4,
)
S_SMALL = ParagraphStyle(
    "Small", parent=_ss["Normal"],
    fontSize=8, fontName="Helvetica",
    textColor=C_GRAY, leading=11,
)
S_KPI_LABEL = ParagraphStyle(
    "KpiLabel", parent=_ss["Normal"],
    fontSize=9, fontName="Helvetica",
    textColor=C_GRAY, alignment=TA_CENTER,
)
S_KPI_VALUE = ParagraphStyle(
    "KpiValue", parent=_ss["Normal"],
    fontSize=20, fontName="Helvetica-Bold",
    textColor=C_DARK, alignment=TA_CENTER, leading=24,
)
S_KPI_DELTA = ParagraphStyle(
    "KpiDelta", parent=_ss["Normal"],
    fontSize=9, fontName="Helvetica",
    alignment=TA_CENTER, leading=12,
)
S_BANNER = ParagraphStyle(
    "Banner", parent=_ss["Normal"],
    fontSize=12, fontName="Helvetica-Bold",
    textColor=colors.white, alignment=TA_CENTER,
)
S_TH = ParagraphStyle(
    "TH", parent=_ss["Normal"],
    fontSize=9, fontName="Helvetica-Bold",
    textColor=colors.white, alignment=TA_CENTER,
)
S_TD = ParagraphStyle(
    "TD", parent=_ss["Normal"],
    fontSize=9, fontName="Helvetica",
    textColor=C_DARK, alignment=TA_LEFT, leading=12,
)
S_TD_C = ParagraphStyle(
    "TDC", parent=_ss["Normal"],
    fontSize=9, fontName="Helvetica",
    textColor=C_DARK, alignment=TA_CENTER, leading=12,
)


# ---------------------------------------------------------------------------
# Reusable building blocks
# ---------------------------------------------------------------------------

def _gap(h: float = 0.15) -> Spacer:
    return Spacer(1, h * inch)


def _rule() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.5,
                      color=C_BLUE_BORDER, spaceAfter=6)


def _banner(text: str) -> Table:
    """Full-width blue section banner."""
    tbl = Table([[Paragraph(text, S_BANNER)]],
                colWidths=[CONTENT_W], rowHeights=[0.38 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BLUE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _kpi_row(items: list) -> Table:
    """
    Row of KPI boxes.
    items: list of (label, big_value, delta_html_or_empty)
    """
    n = len(items)
    w = CONTENT_W / n
    row_label = [Paragraph(lbl, S_KPI_LABEL) for lbl, _, _ in items]
    row_value = [Paragraph(val, S_KPI_VALUE) for _, val, _ in items]
    row_delta = [Paragraph(dlt, S_KPI_DELTA) for _, _, dlt in items]

    tbl = Table([row_label, row_value, row_delta], colWidths=[w] * n)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BLUE_LIGHT),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BLUE_BORDER),
        ("LINEBEFORE",    (1, 0), (-1, -1), 0.5, C_BLUE_BORDER),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tbl


def _chart(path: str, max_w: float = None, max_h: float = None) -> Image:
    """
    Load a chart PNG and scale it to fit within max_w × max_h, preserving
    aspect ratio. Uses Pillow to read pixel dimensions reliably.
    """
    from PIL import Image as PILImage
    max_w = max_w or CONTENT_W
    max_h = max_h or (PAGE_H - 2.5 * inch)   # generous page budget

    with PILImage.open(path) as im:
        px_w, px_h = im.size
        dpi = im.info.get("dpi", (150, 150))[0] or 150

    nat_w = px_w / dpi * 72   # natural width in pts
    nat_h = px_h / dpi * 72   # natural height in pts

    scale = min(max_w / nat_w, max_h / nat_h, 1.0)
    img = Image(path, width=nat_w * scale, height=nat_h * scale)
    img.hAlign = "CENTER"
    return img


def _data_table(headers: list, rows: list, col_widths: list) -> Table:
    """Styled data table with blue header row and alternating row colours."""
    header_row = [Paragraph(h, S_TH) for h in headers]
    data = [header_row]
    for i, row in enumerate(rows):
        style = S_TD_C  # default centered
        bg = colors.white if i % 2 == 0 else C_ROW_ALT
        data.append([Paragraph(str(c), S_TD) if j == 0 else Paragraph(str(c), S_TD_C)
                     for j, c in enumerate(row)])

    tbl = Table(data, colWidths=col_widths)
    style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_BLUE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BLUE_BORDER),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, C_BLUE_BORDER),
    ])
    for i in range(1, len(data)):
        bg = colors.white if i % 2 == 1 else C_ROW_ALT
        style.add("BACKGROUND", (0, i), (-1, i), bg)
    tbl.setStyle(style)
    return tbl


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_summary(story: list, kpis: dict, chart_path: str) -> None:
    arr = kpis["current_arr"]
    arr_str = f"${arr/1e6:.2f}M" if arr >= 1e6 else f"${arr/1e3:.0f}K"

    delta_pct = kpis["arr_change_pct"]
    delta_color = "#16A34A" if delta_pct >= 0 else "#DC2626"
    delta_sign  = "+" if delta_pct >= 0 else ""
    delta_html  = f'<font color="{delta_color}">{delta_sign}{delta_pct:.1f}% MoM</font>'

    churn_color = "#DC2626" if kpis["churn_rate_pct"] > 5 else "#16A34A"

    story += [
        _kpi_row([
            ("Current ARR",      arr_str,                              delta_html),
            ("Net New Customers", str(kpis["net_new_customers"]),      ""),
            ("Churned This Month", str(kpis["churned_this_month"]),    ""),
            ("Monthly Churn Rate",
             f'<font color="{churn_color}">{kpis["churn_rate_pct"]:.1f}%</font>'.replace(
                 "<font", '<font'),
             ""),
        ]),
        _gap(0.2),
        _chart(chart_path),
        _gap(0.2),
        Paragraph("Top 3 New Signups This Month", S_H2),
    ]

    top3 = kpis["top_3_new_signups"]
    if top3:
        rows = [[s["name"], s["industry"], f"${s['mrr']:,}/mo"] for s in top3]
        story.append(_data_table(
            ["Company", "Industry", "MRR"],
            rows,
            [CONTENT_W * 0.5, CONTENT_W * 0.3, CONTENT_W * 0.2],
        ))
    else:
        story.append(Paragraph("No new signups this month.", S_BODY))


def _section_cohort(story: list, chart_path: str) -> None:
    story += [
        Paragraph(
            "Each row is a cohort of customers who signed up in the same month. "
            "Percentages show what share of that cohort was still active at "
            "1, 3, 6, and 12 months. Gray cells mean the cohort isn't old enough yet.",
            S_BODY,
        ),
        _gap(0.1),
        _chart(chart_path),
    ]


def _section_waterfall(story: list, wf: dict, chart_path: str) -> None:
    story += [
        _chart(chart_path),
        _gap(0.15),
        _data_table(
            ["", "ARR (USD)"],
            [
                ["Starting ARR",  f"${wf['starting_arr']:>12,.0f}"],
                ["+ New",         f"${wf['new_arr']:>12,.0f}"],
                ["+ Expansion",   f"${wf['expansion_arr']:>12,.0f}"],
                ["- Churn",       f"${wf['churn_arr']:>12,.0f}"],
                ["= Ending ARR",  f"${wf['ending_arr']:>12,.0f}"],
            ],
            [CONTENT_W * 0.55, CONTENT_W * 0.45],
        ),
    ]


def _section_logos(story: list, logos: list) -> None:
    story.append(Paragraph(
        "Top new customers this month by MRR. "
        "Use the Notes column to add context before sharing with investors.",
        S_BODY,
    ))
    story.append(_gap(0.1))

    if not logos:
        story.append(Paragraph("No new customers signed up this month.", S_BODY))
        return

    rows = []
    for i, lg in enumerate(logos, 1):
        rows.append([
            f"{i}. {lg['name']}",
            lg["domain"],
            f"${lg['mrr']:,}/mo",
            lg["industry"],
            lg["country"],
            "________________________________",   # founder notes placeholder
        ])

    story.append(_data_table(
        ["Company", "Domain", "MRR", "Industry", "Country", "Founder Notes"],
        rows,
        [
            CONTENT_W * 0.20,
            CONTENT_W * 0.14,
            CONTENT_W * 0.10,
            CONTENT_W * 0.12,
            CONTENT_W * 0.14,
            CONTENT_W * 0.30,
        ],
    ))


def _section_icp(story: list, icp: dict) -> None:
    avg  = f"${icp['avg_mrr']:,.0f}"
    med  = f"${icp['median_mrr']:,.0f}"
    inb  = f"{icp['inbound_pct']:.0f}% inbound"
    out  = f"{icp['outbound_pct']:.0f}% outbound"

    story += [
        Paragraph(
            f"Profile based on the top 25% of active customers by MRR "
            f"({icp['sample_size']} companies).",
            S_BODY,
        ),
        _gap(0.15),
        _kpi_row([
            ("Avg MRR",        avg, ""),
            ("Median MRR",     med, ""),
            ("Top Industry",   icp["top_industry"] or "—", ""),
            ("Top Country",    icp["top_country"]  or "—", ""),
        ]),
        _gap(0.15),
        _kpi_row([
            ("Inbound %",  f"{icp['inbound_pct']:.0f}%",  ""),
            ("Outbound %", f"{icp['outbound_pct']:.0f}%", ""),
            ("Sample Size", str(icp["sample_size"]),       ""),
            ("",           "",                             ""),
        ]),
    ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_report(csv_path: str, as_of_month: str,
                 output_path: str = "output/report.pdf") -> str:
    """
    Generate the full investor report PDF.

    Args:
        csv_path    : path to the transaction CSV
        as_of_month : reporting month, e.g. "2024-12"
        output_path : where to save the PDF

    Returns:
        Absolute path to the saved PDF.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # ── compute metrics ──────────────────────────────────────────────────────
    df      = load_and_clean(csv_path)
    kpis    = summary_kpis(df, as_of_month)
    ret_df  = cohort_retention(df, as_of_month)
    wf      = arr_waterfall(df, as_of_month)
    geo_df  = geography_mix_by_month(df, as_of_month)
    ind_df  = industry_mix_by_month(df, as_of_month)
    logos   = logo_highlights(df, as_of_month, n=5)
    icp     = icp_snapshot(df, as_of_month)

    # ── generate charts into a temp folder ──────────────────────────────────
    chart_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), "charts")
    arr_trend_png  = plot_arr_trend(df, chart_dir)
    waterfall_png  = plot_arr_waterfall(wf, as_of_month, chart_dir)
    cohort_png     = plot_cohort_heatmap(ret_df, chart_dir)
    geo_png        = plot_geography_mix(geo_df, chart_dir)
    ind_png        = plot_industry_mix(ind_df, chart_dir)

    # ── assemble PDF ─────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )

    story = []

    # ── Cover / header ───────────────────────────────────────────────────────
    story += [
        Paragraph("ManageUp", S_TITLE),
        Paragraph(f"Investor Report  ·  {as_of_month}", S_SUBTITLE),
        _rule(),
        _gap(0.1),
    ]

    # ── 1. Summary ───────────────────────────────────────────────────────────
    story += [_banner("1  |  Executive Summary"), _gap(0.15)]
    _section_summary(story, kpis, arr_trend_png)

    # ── 2. Cohort retention ──────────────────────────────────────────────────
    story += [PageBreak(), _banner("2  |  Cohort Retention"), _gap(0.15)]
    _section_cohort(story, cohort_png)

    # ── 3. ARR waterfall ─────────────────────────────────────────────────────
    story += [PageBreak(), _banner("3  |  ARR Waterfall"), _gap(0.15)]
    _section_waterfall(story, wf, waterfall_png)

    # ── 4. Geography mix ─────────────────────────────────────────────────────
    story += [PageBreak(), _banner("4  |  Geography Mix"), _gap(0.15)]
    story.append(_chart(geo_png))

    # ── 5. Industry mix ──────────────────────────────────────────────────────
    story += [_gap(0.2), _banner("5  |  Industry Mix"), _gap(0.15)]
    story.append(_chart(ind_png))

    # ── 6. Logo highlights ───────────────────────────────────────────────────
    story += [PageBreak(), _banner("6  |  Logo Highlights"), _gap(0.15)]
    _section_logos(story, logos)

    # ── 7. ICP snapshot ──────────────────────────────────────────────────────
    story += [PageBreak(), _banner("7  |  ICP Snapshot"), _gap(0.15)]
    _section_icp(story, icp)

    doc.build(story)
    return os.path.abspath(output_path)
