"""
PDF report builder for ManageUp — editorial layout.
Entry point: build_report(csv_path, as_of_month, output_path)
"""
import os
import sys
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
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
# Page geometry
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = letter       # 612 x 792 pts
MARGIN    = 0.75 * inch       # 54 pts
CONTENT_W = PAGE_W - 2 * MARGIN   # 504 pts
CONTENT_H = PAGE_H - 2 * MARGIN   # 684 pts

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
C_INK   = colors.HexColor("#0F172A")
C_SLATE = colors.HexColor("#334155")
C_MUTED = colors.HexColor("#64748B")
C_FAINT = colors.HexColor("#94A3B8")
C_RULE  = colors.HexColor("#CBD5E1")
C_BLUE  = colors.HexColor("#2E5FE8")
C_BG    = colors.HexColor("#EFF6FF")
C_BGB   = colors.HexColor("#BFDBFE")
C_ROW   = colors.HexColor("#F8FAFC")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
_ss = getSampleStyleSheet()

def _s(name, **kw):
    return ParagraphStyle(name, parent=_ss["Normal"], **kw)

S_SECT_NUM   = _s("SN",  fontSize=9,  fontName="Helvetica",
                   textColor=C_FAINT, spaceAfter=2)
S_SECT_TITLE = _s("STi", fontSize=18, fontName="Helvetica-Bold",
                   textColor=C_INK,   leading=22, spaceAfter=0)
S_SUBHEAD    = _s("SH",  fontSize=14, fontName="Helvetica-Bold",
                   textColor=C_INK,   leading=18, spaceBefore=10, spaceAfter=4)
S_KPI_LABEL  = _s("KL",  fontSize=9,  fontName="Helvetica",
                   textColor=C_FAINT, alignment=TA_CENTER)
S_KPI_VALUE  = _s("KV",  fontSize=20, fontName="Helvetica-Bold",
                   textColor=C_INK,   alignment=TA_CENTER, leading=24)
S_KPI_DELTA  = _s("KD",  fontSize=9,  fontName="Helvetica",
                   alignment=TA_CENTER, leading=12)
S_BODY       = _s("BD",  fontSize=10, fontName="Helvetica",
                   textColor=C_SLATE, leading=14, spaceAfter=4)
S_LOREM      = _s("LR",  fontSize=10, fontName="Helvetica",
                   textColor=C_SLATE, leading=14)
S_CAPTION    = _s("CP",  fontSize=10, fontName="Helvetica-Oblique",
                   textColor=C_SLATE, leading=14, spaceAfter=8)
S_TH         = _s("TH",  fontSize=9,  fontName="Helvetica-Bold",
                   textColor=colors.white, alignment=TA_CENTER)
S_TD         = _s("TD",  fontSize=9,  fontName="Helvetica",
                   textColor=C_INK,   leading=13)
S_TD_C       = _s("TDC", fontSize=9,  fontName="Helvetica",
                   textColor=C_INK,   alignment=TA_CENTER, leading=13)
S_NOTE       = _s("NT",  fontSize=9,  fontName="Helvetica-Oblique",
                   textColor=C_FAINT, leading=12)


# ---------------------------------------------------------------------------
# Numbered canvas — draws "Page N of M" footer on every page except the cover
# ---------------------------------------------------------------------------

def _make_canvas(month_label: str) -> type:
    def _draw_footer(c, page_num: int, total: int) -> None:
        c.saveState()
        c.setStrokeColor(C_RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN, MARGIN, PAGE_W - MARGIN, MARGIN)
        c.setFont("Helvetica", 8)
        c.setFillColor(C_FAINT)
        txt = f"ManageUp  \xb7  {month_label}  \xb7  Page {page_num} of {total}"
        c.drawCentredString(PAGE_W / 2, MARGIN - 12, txt)
        c.restoreState()

    class _NC(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            rl_canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            for n, state in enumerate(self._saved_page_states, 1):
                self.__dict__.update(state)
                if n > 1:
                    _draw_footer(self, n, total)
                rl_canvas.Canvas.showPage(self)
            rl_canvas.Canvas.save(self)

    return _NC


# ---------------------------------------------------------------------------
# Cover page — drawn directly onto the canvas via onFirstPage callback
# ---------------------------------------------------------------------------

def _draw_cover(c, month_label: str, prepared_str: str) -> None:
    cx = PAGE_W / 2

    # "ManageUp" — baseline at 40% from top of page
    title_y = PAGE_H * 0.60
    c.setFont("Helvetica-Bold", 48)
    c.setFillColor(C_INK)
    c.drawCentredString(cx, title_y, "ManageUp")

    # Thin 200pt rule below title
    rule_y = title_y - 66
    c.setStrokeColor(C_RULE)
    c.setLineWidth(0.5)
    c.line(cx - 100, rule_y, cx + 100, rule_y)

    # "Investor Update"
    c.setFont("Helvetica", 18)
    c.setFillColor(C_SLATE)
    c.drawCentredString(cx, rule_y - 20, "Investor Update")

    # Reporting month  e.g. "October 2024"
    c.setFont("Helvetica", 16)
    c.setFillColor(C_MUTED)
    c.drawCentredString(cx, rule_y - 48, month_label)

    # Prepared line at bottom of page
    c.setFont("Helvetica", 9)
    c.setFillColor(C_FAINT)
    c.drawCentredString(cx, MARGIN - 12, prepared_str)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _gap(pts: float = 12) -> Spacer:
    return Spacer(1, pts)


def _section_header(num: int, title: str) -> list:
    return [
        HRFlowable(width="100%", thickness=0.5, color=C_RULE,
                   spaceBefore=0, spaceAfter=4),
        Paragraph(f"SECTION {num}", S_SECT_NUM),
        Paragraph(title, S_SECT_TITLE),
        _gap(16),
    ]


def _chart(path: str, max_w: float = None, max_h: float = None) -> Image:
    from PIL import Image as PILImage
    max_w = max_w or CONTENT_W
    max_h = max_h or (PAGE_H - 2.5 * inch)
    with PILImage.open(path) as im:
        px_w, px_h = im.size
        dpi = im.info.get("dpi", (200, 200))[0] or 200
    nat_w = px_w / dpi * 72
    nat_h = px_h / dpi * 72
    scale = min(max_w / nat_w, max_h / nat_h, 1.0)
    img = Image(path, width=nat_w * scale, height=nat_h * scale)
    img.hAlign = "CENTER"
    return img


def _kpi_row(items: list, col_widths: list = None) -> Table:
    n   = len(items)
    cw  = col_widths if col_widths else [CONTENT_W / n] * n
    tbl = Table(
        [
            [Paragraph(lbl, S_KPI_LABEL) for lbl, _, _ in items],
            [Paragraph(val, S_KPI_VALUE) for _, val, _ in items],
            [Paragraph(dlt, S_KPI_DELTA) for _, _, dlt in items],
        ],
        colWidths=cw,
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BG),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BGB),
        ("LINEBEFORE",    (1, 0), (-1, -1), 0.5, C_BGB),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tbl


def _data_table(headers: list, rows: list, col_widths: list) -> Table:
    data = [[Paragraph(h, S_TH) for h in headers]]
    for row in rows:
        data.append([
            Paragraph(str(c), S_TD) if j == 0 else Paragraph(str(c), S_TD_C)
            for j, c in enumerate(row)
        ])
    tbl = Table(data, colWidths=col_widths)
    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_BLUE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BGB),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, C_BGB),
    ])
    for i in range(1, len(data)):
        ts.add("BACKGROUND", (0, i), (-1, i),
               colors.white if i % 2 == 1 else C_ROW)
    tbl.setStyle(ts)
    return tbl


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_summary(story: list, kpis: dict, arr_chart_path: str,
                     commentary: str = "") -> None:
    arr     = kpis["current_arr"]
    arr_str = f"${arr/1e6:.2f}M" if arr >= 1_000_000 else f"${arr/1e3:.0f}K"
    dp      = kpis["arr_change_pct"]
    sign    = "+" if dp >= 0 else ""
    col     = "#16A34A" if dp >= 0 else "#DC2626"
    delta   = f'<font color="{col}">{sign}{dp:.1f}% MoM</font>'
    cc      = "#DC2626" if kpis["churn_rate_pct"] > 5 else "#16A34A"
    churn   = f'<font color="{cc}">{kpis["churn_rate_pct"]:.1f}%</font>'

    story += [
        _kpi_row([
            ("Current ARR",        arr_str,                          delta),
            ("Net New Customers",  str(kpis["net_new_customers"]),  ""),
            ("Churned This Month", str(kpis["churned_this_month"]), ""),
            ("Monthly Churn Rate", churn,                           ""),
        ]),
        _gap(14),
        _chart(arr_chart_path, max_h=CONTENT_H * 0.30),
        _gap(14),
        Paragraph("Top 3 new signups this month", S_SUBHEAD),
    ]

    top3 = kpis["top_3_new_signups"]
    if top3:
        story.append(_data_table(
            ["Company", "Industry", "MRR"],
            [[s["name"], s["industry"], f"${s['mrr']:,}/mo"] for s in top3],
            [CONTENT_W * 0.50, CONTENT_W * 0.30, CONTENT_W * 0.20],
        ))
    else:
        story.append(Paragraph("No new signups this month.", S_BODY))

    story += [
        _gap(14),
        Paragraph("Founder commentary", S_SUBHEAD),
        Paragraph(
            commentary.strip() if commentary.strip() else (
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
                "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, "
                "quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo. "
                "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore "
                "eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, "
                "sunt in culpa qui officia deserunt mollit anim id est laborum."
            ),
            S_LOREM,
        ),
    ]


def _section_cohort(story: list, chart_path: str) -> None:
    story += [
        Paragraph(
            "Each row is a cohort of customers who signed up in the same month. "
            "Cells show what share of that cohort was still active at 1, 3, 6, and "
            "12 months. Gray cells mean the cohort is not yet old enough to measure.",
            S_BODY,
        ),
        _gap(12),
        _chart(chart_path, max_h=CONTENT_H * 0.74),
    ]


def _section_waterfall(story: list, wf: dict, chart_path: str) -> None:
    story += [
        _chart(chart_path, max_h=CONTENT_H * 0.52),
        _gap(14),
        _data_table(
            ["Movement", "ARR (USD)"],
            [
                ["Starting ARR",  f"${wf['starting_arr']:,.0f}"],
                ["+ New",         f"${wf['new_arr']:,.0f}"],
                ["+ Expansion",   f"${wf['expansion_arr']:,.0f}"],
                ["- Churn",       f"${wf['churn_arr']:,.0f}"],
                ["= Ending ARR",  f"${wf['ending_arr']:,.0f}"],
            ],
            [CONTENT_W * 0.55, CONTENT_W * 0.45],
        ),
    ]


def _section_logos(story: list, logos: list, notes: dict = None) -> None:
    if not logos:
        story.append(Paragraph("No new customers signed up this month.", S_BODY))
        return

    notes   = notes or {}
    col_w   = [28, 190, 80, CONTENT_W - 28 - 190 - 80]   # last col = 206

    data    = [[Paragraph(h, S_TH) for h in
                ["#", "Company", "MRR", "Industry / Country"]]]

    for i, lg in enumerate(logos, 1):
        data.append([
            Paragraph(str(i), S_TD_C),
            Paragraph(
                f'<b>{lg["name"]}</b><br/>'
                f'<font color="#64748B" size="8">{lg["domain"]}</font>',
                S_TD,
            ),
            Paragraph(f'${lg["mrr"]:,}/mo', S_TD_C),
            Paragraph(
                f'{lg["industry"]}<br/>'
                f'<font color="#64748B" size="8">{lg["country"]}</font>',
                S_TD,
            ),
        ])
        note = notes.get(lg["name"], "")
        if note:
            data.append([
                Paragraph("", S_TD),
                Paragraph(note, S_NOTE),
                Paragraph("", S_TD),
                Paragraph("", S_TD),
            ])

    tbl = Table(data, colWidths=col_w)
    ts  = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_BLUE),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BGB),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, C_BGB),
    ])
    for i in range(1, len(data)):
        ts.add("BACKGROUND", (0, i), (-1, i),
               colors.white if i % 2 == 1 else C_ROW)
    tbl.setStyle(ts)
    story.append(tbl)


def _section_icp(story: list, icp: dict) -> None:
    dominant = "inbound" if icp["inbound_pct"] >= icp["outbound_pct"] else "outbound"
    pct      = max(icp["inbound_pct"], icp["outbound_pct"])
    caption  = (
        f"Your highest-MRR customers skew toward {icp['top_industry']} companies "
        f"in {icp['top_country']}, acquired mostly via {dominant} ({pct:.0f}%)."
    )
    # Column widths: MRR values are short; industry/country can be long.
    # 87 + 87 + 155 + 175 = 504 = CONTENT_W
    icp_cw = [87, 87, 155, 175]
    story += [
        Paragraph(caption, S_CAPTION),
        _gap(12),
        _kpi_row([
            ("Avg MRR",      f"${icp['avg_mrr']:,.0f}",   ""),
            ("Median MRR",   f"${icp['median_mrr']:,.0f}", ""),
            ("Top industry", icp["top_industry"] or "-",   ""),
            ("Top country",  icp["top_country"]  or "-",   ""),
        ], col_widths=icp_cw),
        _gap(12),
        _kpi_row([
            ("Inbound",      f"{icp['inbound_pct']:.0f}%",  ""),
            ("Outbound",     f"{icp['outbound_pct']:.0f}%", ""),
            ("Sample size",  str(icp["sample_size"]),        ""),
            ("",             "",                             ""),
        ], col_widths=icp_cw),
    ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_report(csv_path: str, as_of_month: str,
                 output_path: str = "output/report.pdf",
                 commentary: str = "", logo_notes: dict = None) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    chart_dir = os.path.join(
        os.path.dirname(os.path.abspath(output_path)), "charts"
    )

    # Metrics
    df     = load_and_clean(csv_path)
    kpis   = summary_kpis(df, as_of_month)
    ret_df = cohort_retention(df, as_of_month)
    wf     = arr_waterfall(df, as_of_month)
    geo_df = geography_mix_by_month(df, as_of_month)
    ind_df = industry_mix_by_month(df, as_of_month)
    logos  = logo_highlights(df, as_of_month, n=5)
    icp    = icp_snapshot(df, as_of_month)

    # Charts
    arr_png   = plot_arr_trend(df, as_of_month, chart_dir)
    wfall_png = plot_arr_waterfall(wf, as_of_month, chart_dir)
    coh_png   = plot_cohort_heatmap(ret_df, chart_dir)
    geo_png   = plot_geography_mix(geo_df, chart_dir)
    ind_png   = plot_industry_mix(ind_df, chart_dir)

    # Labels
    dt           = datetime.strptime(as_of_month, "%Y-%m")
    month_label  = dt.strftime("%B %Y")          # "October 2024"
    today        = date.today()
    prepared_str = f"Prepared {today.day} {today.strftime('%B %Y')}"

    # Document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )
    NC = _make_canvas(month_label)

    # Story
    story = []

    # Page 1 — cover (onFirstPage draws it; PageBreak moves past it)
    story.append(PageBreak())

    # Page 2 — Executive Summary
    story += _section_header(1, "Executive summary")
    _section_summary(story, kpis, arr_png, commentary=commentary)

    # Page 3 — Cohort Retention
    story.append(PageBreak())
    story += _section_header(2, "Cohort retention")
    _section_cohort(story, coh_png)

    # Page 4 — ARR Waterfall
    story.append(PageBreak())
    story += _section_header(3, "ARR waterfall")
    _section_waterfall(story, wf, wfall_png)

    # Page 5 — Geography Mix
    story.append(PageBreak())
    story += _section_header(4, "Geography mix")
    story.append(_chart(geo_png, max_h=CONTENT_H * 0.78))

    # Page 6 — Industry Mix
    story.append(PageBreak())
    story += _section_header(5, "Industry mix")
    story.append(_chart(ind_png, max_h=CONTENT_H * 0.78))

    # Page 7 — Logo Highlights
    story.append(PageBreak())
    story += _section_header(6, "Logo highlights")
    _section_logos(story, logos, notes=logo_notes)

    # Page 8 — ICP Snapshot
    story.append(PageBreak())
    story += _section_header(7, "ICP snapshot")
    _section_icp(story, icp)

    cover_fn = lambda c, d: _draw_cover(c, month_label, prepared_str)
    doc.build(
        story,
        onFirstPage=cover_fn,
        onLaterPages=lambda c, d: None,
        canvasmaker=NC,
    )

    return os.path.abspath(output_path)
