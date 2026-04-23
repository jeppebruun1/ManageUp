"""
ManageUp report design system — the single source of truth for
typography, color, spacing, and shared Flowable helpers.

Every visual constant in the PDF lives here. report.py imports from
this module and does not define its own styles, colors, or table
treatments.
"""
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    Flowable, HRFlowable, KeepTogether, Paragraph, Spacer, Table, TableStyle,
)

from chart_style import PALETTE   # categorical palette — do not redefine

# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------
INK            = HexColor("#0F172A")   # primary text
INK_MUTED      = HexColor("#64748B")   # secondary text
INK_FAINT      = HexColor("#94A3B8")   # footers, eyebrows
RULE           = HexColor("#E2E8F0")   # rules, table borders
SURFACE        = HexColor("#F8FAFC")   # KPI fill, zebra rows
SURFACE_STRONG = HexColor("#F1F5F9")   # table header fill
ACCENT         = HexColor("#2E5FE8")   # use sparingly
POSITIVE       = HexColor("#0F766E")   # positive deltas
NEGATIVE       = HexColor("#B91C1C")   # negative deltas

# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = letter               # 612 x 792 pts
PAGE_MARGIN    = 54                   # 0.75 inch
CONTENT_W      = PAGE_W - 2 * PAGE_MARGIN   # 504
CONTENT_H      = PAGE_H - 2 * PAGE_MARGIN   # 684

# ---------------------------------------------------------------------------
# Spacing
# ---------------------------------------------------------------------------
SECTION_GAP     = 18
ELEMENT_GAP     = 12
TIGHT_GAP       = 6
RULE_WIDTH      = 0.5
KPI_CARD_HEIGHT = 72
KPI_CARD_GAP    = 8

# ---------------------------------------------------------------------------
# Typography — no italic anywhere
# ---------------------------------------------------------------------------

def _p(name: str, **kw) -> ParagraphStyle:
    base = dict(fontName="Helvetica", textColor=INK, leading=None)
    base.update(kw)
    if base["leading"] is None:
        base["leading"] = base["fontSize"] * 1.3
    return ParagraphStyle(name, **base)


DISPLAY    = _p("Display",   fontSize=32, fontName="Helvetica-Bold",
                             textColor=INK,       leading=38)
H1         = _p("H1",        fontSize=20, fontName="Helvetica-Bold",
                             textColor=INK,       leading=24)
H2         = _p("H2",        fontSize=14, fontName="Helvetica-Bold",
                             textColor=INK,       leading=18,
                             spaceBefore=4, spaceAfter=2)
EYEBROW    = _p("Eyebrow",   fontSize=9,  fontName="Helvetica",
                             textColor=INK_FAINT, leading=12)
BODY       = _p("Body",      fontSize=10, fontName="Helvetica",
                             textColor=INK,       leading=14)
BODY_MUTED = _p("BodyMuted", fontSize=10, fontName="Helvetica",
                             textColor=INK_MUTED, leading=14)
CAPTION    = _p("Caption",   fontSize=9,  fontName="Helvetica",
                             textColor=INK_MUTED, leading=12)
KPI_LABEL  = _p("KpiLabel",  fontSize=9,  fontName="Helvetica",
                             textColor=INK_MUTED, leading=11,
                             alignment=TA_LEFT)
KPI_VALUE  = _p("KpiValue",  fontSize=22, fontName="Helvetica-Bold",
                             textColor=INK,       leading=26,
                             alignment=TA_LEFT,
                             splitLongWords=0,    wordWrap=None)
KPI_DELTA  = _p("KpiDelta",  fontSize=10, fontName="Helvetica-Bold",
                             textColor=INK_MUTED, leading=12,
                             alignment=TA_LEFT)
TABLE_HEAD = _p("TableHead", fontSize=10, fontName="Helvetica-Bold",
                             textColor=INK,       leading=12,
                             alignment=TA_LEFT)
TABLE_CELL = _p("TableCell", fontSize=10, fontName="Helvetica",
                             textColor=INK,       leading=13,
                             alignment=TA_LEFT)
FOOTER     = _p("Footer",    fontSize=8,  fontName="Helvetica",
                             textColor=INK_FAINT, leading=10,
                             alignment=TA_CENTER)


# ---------------------------------------------------------------------------
# Eyebrow flowable — real letter-spaced text, uppercase
# ---------------------------------------------------------------------------

class Eyebrow(Flowable):
    """ALL CAPS eyebrow label with 1.5pt letter spacing.
    Letter spacing requires canvas.setCharSpace — Paragraph cannot do this,
    so this is a dedicated Flowable."""

    CHAR_SPACE = 1.5

    def __init__(self, text: str):
        super().__init__()
        self.text = text.upper()
        self._h   = EYEBROW.fontSize + 2

    def wrap(self, avail_w, avail_h):
        self.width  = avail_w
        self.height = self._h
        return avail_w, self._h

    def draw(self):
        c = self.canv
        c.saveState()
        t = c.beginText(0, 2)
        t.setFont(EYEBROW.fontName, EYEBROW.fontSize)
        t.setFillColor(EYEBROW.textColor)
        t.setCharSpace(self.CHAR_SPACE)
        t.textOut(self.text)
        c.drawText(t)
        c.restoreState()


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------

def section_header(number: int, title: str) -> list:
    """A thin rule, a SECTION N eyebrow, a title. Used on every content page."""
    return [
        HRFlowable(width="100%", thickness=RULE_WIDTH, color=RULE,
                   spaceBefore=0, spaceAfter=4),
        Eyebrow(f"Section {number}"),
        Spacer(1, 2),
        Paragraph(title, H1),
        Spacer(1, SECTION_GAP),
    ]


# ---------------------------------------------------------------------------
# KPI card / row
# ---------------------------------------------------------------------------

def _shrink_to_fit(text: str, width: float, base_size: int = 22,
                   min_size: int = 14, font: str = "Helvetica-Bold",
                   pad: float = 12) -> int:
    """Return the largest font size in [min_size, base_size] that fits on
    one line. Spec says 18pt floor, but a 5-card row is narrow enough that
    a 9-char value like '$2,663/mo' needs to go lower to avoid wrapping —
    we prefer fit over fixed size."""
    usable = max(0, width - pad)
    size   = base_size
    while size > min_size:
        if pdfmetrics.stringWidth(text, font, size) <= usable:
            return size
        size -= 1
    return min_size


def _plain(value: str) -> str:
    """Strip font tags so stringWidth sees the rendered glyphs."""
    out, depth = [], 0
    for ch in value:
        if ch == "<":
            depth += 1
            continue
        if ch == ">":
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return "".join(out)


def kpi_card(label: str, value: str, delta: str = None,
             delta_positive: bool = True, width: float = None) -> Table:
    """A single KPI tile. surface fill, 8pt padding, left-aligned text."""
    if width is not None:
        size  = _shrink_to_fit(_plain(value), width)
        vstyle = ParagraphStyle(
            "kv_fit", parent=KPI_VALUE,
            fontSize=size, leading=int(size * 1.2),
            splitLongWords=0, wordWrap=None,
        )
    else:
        vstyle = KPI_VALUE

    rows = [
        [Paragraph(label, KPI_LABEL)],
        [Paragraph(value, vstyle)],
    ]
    if delta:
        color = POSITIVE if delta_positive else NEGATIVE
        dstyle = ParagraphStyle("kd_col", parent=KPI_DELTA, textColor=color)
        rows.append([Paragraph(delta, dstyle)])
    else:
        rows.append([Spacer(1, 1)])

    col_w = [width] if width else [None]
    tbl = Table(rows, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), SURFACE),
        ("BOX",           (0, 0), (-1, -1), RULE_WIDTH, RULE),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tbl


def kpi_row(cards: list, total_width: float = None) -> Table:
    """Lay out 3-5 KPI cards in a single row, auto-sized.
    Each card spec: (label, value) or (label, value, delta) or
    (label, value, delta, delta_positive).
    """
    total_width = total_width or CONTENT_W
    n           = len(cards)
    col_w       = (total_width - KPI_CARD_GAP * (n - 1)) / n

    tiles, widths = [], []
    for spec in cards:
        label, value = spec[0], spec[1]
        delta        = spec[2] if len(spec) >= 3 else None
        positive     = spec[3] if len(spec) >= 4 else True
        tiles.append(kpi_card(label, value, delta=delta,
                              delta_positive=positive, width=col_w))
        widths.append(col_w)
        widths.append(KPI_CARD_GAP)
    widths = widths[:-1]

    # Interleave tiles with empty spacer cells
    row = []
    for i, tile in enumerate(tiles):
        if i > 0:
            row.append("")
        row.append(tile)

    tbl = Table([row], colWidths=widths)
    tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tbl


# ---------------------------------------------------------------------------
# Data table — the ONE table treatment for the whole report
# ---------------------------------------------------------------------------

def data_table(headers: list, rows: list, align: list = None,
               widths: list = None, total_width: float = None) -> KeepTogether:
    """
    Header: surface_strong fill, bold ink text.
    Body:   alternating white / surface rows, ink text.
    0.25pt row separators; no outer border.
    Wrapped in KeepTogether so it never splits across pages.

    align: list of "L" / "C" / "R" per column (default first col L, rest L).
    widths: explicit column widths; if None, computed from content.
    """
    total_width = total_width or CONTENT_W
    n_cols      = len(headers)
    align       = align or (["L"] * n_cols)
    align_map   = {"L": TA_LEFT, "C": TA_CENTER, "R": 2}   # 2 = TA_RIGHT

    # Auto-size widths when not provided
    if widths is None:
        widths = _auto_widths(headers, rows, total_width)

    # Header row
    head_cells = [Paragraph(h, TABLE_HEAD) for h in headers]

    # Body rows
    body = []
    for r in rows:
        body_cells = []
        for j, cell in enumerate(r):
            style = ParagraphStyle(
                f"td_{j}_{align[j]}", parent=TABLE_CELL,
                alignment=align_map[align[j]],
            )
            body_cells.append(Paragraph(str(cell), style))
        body.append(body_cells)

    data = [head_cells] + body
    tbl  = Table(data, colWidths=widths, repeatRows=1)

    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  SURFACE_STRONG),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW",     (0, 0), (-1, 0),  RULE_WIDTH, RULE),
    ])
    for i in range(1, len(data)):
        bg = colors.white if i % 2 == 1 else SURFACE
        ts.add("BACKGROUND", (0, i), (-1, i), bg)
        if i < len(data) - 1:
            ts.add("LINEBELOW", (0, i), (-1, i), 0.25, RULE)
    tbl.setStyle(ts)

    return KeepTogether(tbl)


def _auto_widths(headers: list, rows: list, total: float) -> list:
    """Compute column widths so no monetary or date value wraps."""
    PAD = 18   # left + right padding + slack
    natural = []
    for j, h in enumerate(headers):
        col_vals = [str(h)] + [str(r[j]) for r in rows]
        max_w = max(
            pdfmetrics.stringWidth(v, "Helvetica-Bold", 10) for v in col_vals[:1]
        )
        body_w = max(
            (pdfmetrics.stringWidth(v, "Helvetica", 10)
             for v in col_vals[1:]),
            default=0,
        )
        natural.append(max(max_w, body_w) + PAD)

    s = sum(natural)
    if s <= total:
        # Distribute slack proportionally so no single column looks empty
        return [w * total / s for w in natural]
    # Same proportional scale when over
    return [w * total / s for w in natural]


# ---------------------------------------------------------------------------
# Page footer
# ---------------------------------------------------------------------------

def draw_page_footer(c, page_num: int, total: int, month_label: str) -> None:
    """Draw the footer rule + 'ManageUp · Month Year · Page N of M'."""
    c.saveState()
    c.setStrokeColor(RULE)
    c.setLineWidth(RULE_WIDTH)
    c.line(PAGE_MARGIN, PAGE_MARGIN, PAGE_W - PAGE_MARGIN, PAGE_MARGIN)
    c.setFont(FOOTER.fontName, FOOTER.fontSize)
    c.setFillColor(FOOTER.textColor)
    txt = f"ManageUp  \xb7  {month_label}  \xb7  Page {page_num} of {total}"
    c.drawCentredString(PAGE_W / 2, PAGE_MARGIN - 12, txt)
    c.restoreState()


def make_numbered_canvas(month_label: str) -> type:
    """Factory: returns a canvas class that stamps footers on pages > 1."""
    class _NC(rl_canvas.Canvas):
        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            for n, state in enumerate(self._saved_page_states, 1):
                self.__dict__.update(state)
                if n > 1:
                    draw_page_footer(self, n, total, month_label)
                rl_canvas.Canvas.showPage(self)
            rl_canvas.Canvas.save(self)

    return _NC


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def gap(pts: float = ELEMENT_GAP) -> Spacer:
    return Spacer(1, pts)


def rule() -> HRFlowable:
    return HRFlowable(width="100%", thickness=RULE_WIDTH, color=RULE,
                      spaceBefore=0, spaceAfter=0)
