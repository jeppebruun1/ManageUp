"""
PDF report builder for ManageUp — editorial layout.
All visual constants live in design.py; this file only arranges content.
Entry point: build_report(csv_path, as_of_month, output_path)
"""
import os
import sys
from datetime import date, datetime

from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle,
)

sys.path.insert(0, os.path.dirname(__file__))
from metrics import (
    arr_waterfall, cohort_retention, geography_mix_by_month,
    industry_mix_by_month, icp_snapshot, load_and_clean,
    load_pipeline, logo_highlights, pipeline_summary, summary_kpis,
)
from charts import (
    plot_arr_trend, plot_arr_waterfall, plot_cohort_heatmap,
    plot_geography_mix, plot_industry_mix, plot_pipeline_funnel,
)
import design
from design import (
    BODY, BODY_MUTED, CAPTION, CONTENT_H, CONTENT_W, DISPLAY, H2,
    INK, INK_FAINT, INK_MUTED, PAGE_H, PAGE_MARGIN, PAGE_W, RULE,
    SURFACE, SURFACE_STRONG, RULE_WIDTH, TABLE_CELL,
    data_table, draw_page_footer, gap, kpi_row, make_numbered_canvas,
    section_header,
)
from reportlab.platypus import Image


# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------

def _draw_cover(c, month_label: str, prepared_str: str) -> None:
    cx = PAGE_W / 2

    # Title — baseline at 60% from bottom
    title_y = PAGE_H * 0.60
    c.setFont(DISPLAY.fontName, DISPLAY.fontSize)
    c.setFillColor(INK)
    c.drawCentredString(cx, title_y, "ManageUp")

    # Thin rule below the title
    rule_y = title_y - 30
    c.setStrokeColor(RULE)
    c.setLineWidth(RULE_WIDTH)
    c.line(cx - 80, rule_y, cx + 80, rule_y)

    # Subtitle
    c.setFont("Helvetica", 14)
    c.setFillColor(INK_MUTED)
    c.drawCentredString(cx, rule_y - 22, "Investor Update")

    # Reporting month
    c.setFont("Helvetica", 12)
    c.setFillColor(INK_MUTED)
    c.drawCentredString(cx, rule_y - 40, month_label)

    # Prepared line at bottom
    c.setFont("Helvetica", 8)
    c.setFillColor(INK_FAINT)
    c.drawCentredString(cx, PAGE_MARGIN - 12, prepared_str)


# ---------------------------------------------------------------------------
# Chart flowable helper
# ---------------------------------------------------------------------------

def _chart(path: str, max_w: float = None, max_h: float = None) -> Image:
    from PIL import Image as PILImage
    max_w = max_w or CONTENT_W
    max_h = max_h or (CONTENT_H - 160)
    with PILImage.open(path) as im:
        px_w, px_h = im.size
        dpi = im.info.get("dpi", (200, 200))[0] or 200
    nat_w = px_w / dpi * 72
    nat_h = px_h / dpi * 72
    scale = min(max_w / nat_w, max_h / nat_h, 1.0)
    img = Image(path, width=nat_w * scale, height=nat_h * scale)
    img.hAlign = "CENTER"
    return img


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_summary(story, kpis, arr_chart_path, commentary=""):
    arr     = kpis["current_arr"]
    arr_str = f"${arr/1e6:.2f}M" if arr >= 1_000_000 else f"${arr/1e3:.0f}K"
    dp      = kpis["arr_change_pct"]
    sign    = "+" if dp >= 0 else ""
    delta   = f"{sign}{dp:.1f}% MoM"
    churn   = f"{kpis['churn_rate_pct']:.1f}%"
    churn_ok = kpis["churn_rate_pct"] <= 5

    story += [
        kpi_row([
            ("Current ARR",        arr_str, delta, dp >= 0),
            ("Net new customers",  str(kpis["net_new_customers"])),
            ("Churned this month", str(kpis["churned_this_month"])),
            ("Monthly churn rate", churn, "", churn_ok),
        ]),
        gap(14),
        _chart(arr_chart_path, max_h=CONTENT_H * 0.30),
        gap(14),
        Paragraph("Top 3 new signups this month", H2),
        gap(4),
    ]

    top3 = kpis["top_3_new_signups"]
    if top3:
        story.append(data_table(
            ["Company", "Industry", "MRR"],
            [[s["name"], s["industry"], f"${s['mrr']:,}/mo"] for s in top3],
            align=["L", "L", "R"],
        ))
    else:
        story.append(Paragraph("No new signups this month.", BODY))

    story += [
        gap(14),
        Paragraph("Founder commentary", H2),
        gap(4),
        Paragraph(
            commentary.strip() if commentary.strip() else (
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
                "eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut "
                "enim ad minim veniam, quis nostrud exercitation ullamco laboris "
                "nisi ut aliquip ex ea commodo. Duis aute irure dolor in "
                "reprehenderit in voluptate velit esse cillum dolore eu fugiat "
                "nulla pariatur."
            ),
            BODY,
        ),
    ]


def _section_cohort(story, chart_path):
    story += [
        Paragraph(
            "Each row is a cohort of customers who signed up in the same month. "
            "Cells show what share of that cohort was still active at the given "
            "month milestone. Gray cells mean the cohort is not yet old enough "
            "to measure.",
            BODY,
        ),
        gap(12),
        _chart(chart_path, max_h=CONTENT_H * 0.72),
    ]


def _section_waterfall(story, wf, chart_path):
    net_exp = wf["net_expansion_arr"]
    net_lbl = "+ Net expansion" if net_exp >= 0 else "- Net expansion"
    story += [
        _chart(chart_path, max_h=CONTENT_H * 0.50),
        gap(14),
        data_table(
            ["Movement", "ARR (USD)"],
            [
                ["Starting ARR",    f"${wf['starting_arr']:,.0f}"],
                ["+ New",           f"${wf['new_arr']:,.0f}"],
                [net_lbl,           f"${abs(net_exp):,.0f}"],
                ["- Churn",         f"${wf['churn_arr']:,.0f}"],
                ["= Ending ARR",    f"${wf['ending_arr']:,.0f}"],
            ],
            align=["L", "R"],
        ),
    ]


def _section_logos(story, logos, notes=None):
    """Logos table — uses design.data_table with HTML-in-cell for the
    multi-line Company and Industry/Country cells."""
    if not logos:
        story.append(Paragraph("No new customers signed up this month.", BODY))
        return

    notes = notes or {}
    rows  = []
    for i, lg in enumerate(logos, 1):
        name_cell = (
            f'<b>{lg["name"]}</b><br/>'
            f'<font color="#64748B" size="8">{lg["domain"]}</font>'
        )
        note = notes.get(lg["name"], "")
        if note:
            name_cell += f'<br/><font color="#64748B" size="8">{note}</font>'
        industry_cell = (
            f'{lg["industry"]}<br/>'
            f'<font color="#64748B" size="8">{lg["country"]}</font>'
        )
        rows.append([
            str(i), name_cell, f'${lg["mrr"]:,}/mo', industry_cell,
        ])

    story.append(data_table(
        ["#", "Company", "MRR", "Industry / Country"],
        rows,
        align=["C", "L", "R", "L"],
        widths=[28, 220, 80, CONTENT_W - 28 - 220 - 80],
    ))


def _section_icp(story, icp):
    dominant = "inbound" if icp["inbound_pct"] >= icp["outbound_pct"] else "outbound"
    pct      = max(icp["inbound_pct"], icp["outbound_pct"])
    caption  = (
        f"Your highest-MRR customers skew toward {icp['top_industry']} companies "
        f"in {icp['top_country']}, acquired mostly via {dominant} ({pct:.0f}%)."
    )
    story += [
        Paragraph(caption, BODY_MUTED),
        gap(14),
        kpi_row([
            ("Avg MRR",      f"${icp['avg_mrr']:,.0f}"),
            ("Median MRR",   f"${icp['median_mrr']:,.0f}"),
            ("Top industry", icp["top_industry"] or "-"),
            ("Top country",  icp["top_country"]  or "-"),
        ]),
        gap(12),
        kpi_row([
            ("Inbound",      f"{icp['inbound_pct']:.0f}%"),
            ("Outbound",     f"{icp['outbound_pct']:.0f}%"),
            ("Sample size",  str(icp["sample_size"])),
        ]),
    ]


def _section_pipeline(story, pipe, chart_path):
    def _fmt(v):
        return f"${v/1e6:.2f}M" if v >= 1_000_000 else f"${v/1e3:.0f}K"

    intro = (
        "<b>Total pipeline</b> is the annualised value of every open deal. "
        "<b>Weighted pipeline</b> applies a close probability to each stage "
        "(Discovery 10%, Demo 25%, Proposal 50%, Negotiation 75%, "
        "Verbal Agreement 90%). <b>Open opps</b> is the count of deals not yet "
        "closed. <b>Avg deal size</b> is the mean monthly contract value across "
        "open opps. <b>Coverage</b> is total pipeline divided by current ARR — "
        "a rough guide to how much pipeline is in play relative to the book."
    )

    story += [
        Paragraph(intro, BODY_MUTED),
        gap(12),
        kpi_row([
            ("Total pipeline",    _fmt(pipe["total_pipeline_arr"])),
            ("Weighted pipeline", _fmt(pipe["weighted_pipeline_arr"])),
            ("Open opps",         str(pipe["open_opportunities"])),
            ("Avg deal size",     f"${pipe['avg_deal_size']:,.0f}/mo"),
            ("Coverage",          f"{pipe['coverage_ratio']:.2f}x"),
        ]),
        gap(14),
        Paragraph(
            "Each bar shows the annualised value of open deals at that stage. "
            "Deals move top-to-bottom as they progress toward close.",
            CAPTION,
        ),
        gap(4),
        _chart(chart_path, max_h=CONTENT_H * 0.34),
        gap(14),
    ]

    if pipe["top_5_deals"]:
        rows = [
            [d["company"], d["stage"], f"${d['mrr']:,.0f}/mo",
             d["close_date"] or "-"]
            for d in pipe["top_5_deals"]
        ]
        top5_block = KeepTogether([
            Paragraph("Top 5 open deals", H2),
            gap(2),
            Paragraph(
                "The five largest open deals by monthly contract value, "
                "regardless of stage.",
                BODY_MUTED,
            ),
            gap(6),
            data_table(
                ["Company", "Stage", "MRR", "Expected close"],
                rows,
                align=["L", "L", "R", "C"],
            ),
        ])
        story.append(top5_block)
    else:
        story += [
            Paragraph("Top 5 open deals", H2),
            gap(6),
            Paragraph("No open opportunities.", BODY),
        ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_report(csv_path: str, as_of_month: str,
                 output_path: str = "output/report.pdf",
                 commentary: str = "", logo_notes: dict = None,
                 pipeline_csv_path: str = None) -> str:
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

    pipe         = None
    pipeline_png = None
    if pipeline_csv_path:
        pipe_df      = load_pipeline(pipeline_csv_path)
        pipe         = pipeline_summary(pipe_df, current_arr=kpis["current_arr"])
        pipeline_png = plot_pipeline_funnel(pipe["by_stage"], chart_dir)

    arr_png   = plot_arr_trend(df, as_of_month, chart_dir)
    wfall_png = plot_arr_waterfall(wf, as_of_month, chart_dir)
    coh_png   = plot_cohort_heatmap(ret_df, chart_dir)
    geo_png   = plot_geography_mix(geo_df, chart_dir)
    ind_png   = plot_industry_mix(ind_df, chart_dir)

    dt           = datetime.strptime(as_of_month, "%Y-%m")
    month_label  = dt.strftime("%B %Y")
    today        = date.today()
    prepared_str = f"Prepared {today.day} {today.strftime('%B %Y')}"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,  bottomMargin=PAGE_MARGIN,
    )
    NC = make_numbered_canvas(month_label)

    story = []
    story.append(PageBreak())                          # past cover

    story += section_header(1, "Executive summary")
    _section_summary(story, kpis, arr_png, commentary=commentary)

    story.append(PageBreak())
    story += section_header(2, "Cohort retention")
    _section_cohort(story, coh_png)

    story.append(PageBreak())
    story += section_header(3, "ARR waterfall")
    _section_waterfall(story, wf, wfall_png)

    story.append(PageBreak())
    story += section_header(4, "Geography mix")
    story.append(_chart(geo_png, max_h=CONTENT_H * 0.76))

    story.append(PageBreak())
    story += section_header(5, "Industry mix")
    story.append(_chart(ind_png, max_h=CONTENT_H * 0.76))

    story.append(PageBreak())
    story += section_header(6, "Logo highlights")
    _section_logos(story, logos, notes=logo_notes)

    story.append(PageBreak())
    story += section_header(7, "ICP snapshot")
    _section_icp(story, icp)

    if pipe is not None:
        story.append(PageBreak())
        story += section_header(8, "Sales pipeline")
        _section_pipeline(story, pipe, pipeline_png)

    cover_fn = lambda c, d: _draw_cover(c, month_label, prepared_str)
    doc.build(
        story,
        onFirstPage=cover_fn,
        onLaterPages=lambda c, d: None,
        canvasmaker=NC,
    )

    return os.path.abspath(output_path)
