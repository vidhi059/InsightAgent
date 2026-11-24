"""
report_agent.py
---------------
Fills predefined templates with live data to produce:
  - PPTX reports (weekly_sales, quarterly_trends)
  - HTML email reports (rep_summary)

NEVER generates raw XML or freeform formatting.
Only fills named placeholders in fixed templates.
"""

import uuid
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

BASE_DIR      = Path(__file__).resolve().parent.parent
TEMPLATE_DIR  = BASE_DIR / "templates"
OUTPUT_DIR    = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


# ── PPTX report ────────────────────────────────────────────────────────────────

def _make_pptx(
    report_type: str,
    df:          pd.DataFrame | None,
    analysis:    str,
    chart_path:  str | None,
) -> str:
    """Build a PPTX using python-pptx. Returns the output file path."""
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
    except ImportError:
        raise ImportError("python-pptx not installed. Run: pip install python-pptx")

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]  # completely blank

    # ── Slide 1: Title ────────────────────────────────────────────────────────
    slide = prs.slides.add_slide(blank_layout)

    title_map = {
        "weekly_sales":       "Weekly Sales Performance Report",
        "quarterly_trends":   "Quarterly Regional Trends Report",
        "rep_summary":        "Rep / Segment Performance Summary",
    }
    title_text = title_map.get(report_type, "Sales Report")

    # Title box
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(1.5))
    tf    = txBox.text_frame
    p     = tf.paragraphs[0]
    p.text = title_text
    p.runs[0].font.size  = Pt(36)
    p.runs[0].font.bold  = True
    p.runs[0].font.color.rgb = RGBColor(0x2C, 0x3E, 0x50)

    # Subtitle box
    subBox = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(11), Inches(0.8))
    stf    = subBox.text_frame
    sp     = stf.paragraphs[0]
    sp.text = f"Generated: {date.today().strftime('%B %d, %Y')}"
    sp.runs[0].font.size = Pt(16)
    sp.runs[0].font.color.rgb = RGBColor(0x4A, 0x90, 0xD9)

    # ── Slide 2: Data Table ───────────────────────────────────────────────────
    slide2 = prs.slides.add_slide(blank_layout)

    hdr = slide2.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(0.6))
    hdr.text_frame.paragraphs[0].text = "Data Summary"
    hdr.text_frame.paragraphs[0].runs[0].font.size = Pt(20)
    hdr.text_frame.paragraphs[0].runs[0].font.bold = True

    if df is not None and not df.empty:
        # Build a simple text table (max 20 rows for readability)
        preview = df.head(20).to_string(index=False)
        tBox = slide2.shapes.add_textbox(Inches(0.5), Inches(1.0), Inches(12), Inches(5.5))
        tf2  = tBox.text_frame
        tf2.word_wrap = True
        p2   = tf2.paragraphs[0]
        p2.text = preview
        p2.runs[0].font.size = Pt(9)
        p2.runs[0].font.name = "Courier New"

    # ── Slide 3: Chart ────────────────────────────────────────────────────────
    if chart_path and Path(chart_path).exists():
        slide3 = prs.slides.add_slide(blank_layout)
        hdr3   = slide3.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(0.6))
        hdr3.text_frame.paragraphs[0].text = "Chart"
        hdr3.text_frame.paragraphs[0].runs[0].font.size = Pt(20)
        hdr3.text_frame.paragraphs[0].runs[0].font.bold = True
        slide3.shapes.add_picture(chart_path, Inches(1.5), Inches(1.0), Inches(10), Inches(5.5))

    # ── Slide 4: Insights ─────────────────────────────────────────────────────
    slide4 = prs.slides.add_slide(blank_layout)
    hdr4   = slide4.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(0.6))
    hdr4.text_frame.paragraphs[0].text = "Key Insights"
    hdr4.text_frame.paragraphs[0].runs[0].font.size = Pt(20)
    hdr4.text_frame.paragraphs[0].runs[0].font.bold = True

    iBox = slide4.shapes.add_textbox(Inches(0.5), Inches(1.0), Inches(12), Inches(5.5))
    itf  = iBox.text_frame
    itf.word_wrap = True
    ip   = itf.paragraphs[0]
    ip.text = analysis or "No analysis available."
    ip.runs[0].font.size = Pt(12)

    # Save
    fname = f"{report_type}_{uuid.uuid4().hex[:8]}.pptx"
    out   = OUTPUT_DIR / fname
    prs.save(str(out))
    logger.info(f"PPTX saved: {out}")
    return str(out)


# ── HTML email report ──────────────────────────────────────────────────────────

def _make_html(
    df:       pd.DataFrame | None,
    analysis: str,
) -> str:
    """Renders the Jinja2 HTML email template. Returns the output file path."""
    env      = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("rep_summary.html")

    table_html = df.to_html(index=False, border=0, classes="data-table") if df is not None and not df.empty else "<p>No data.</p>"

    html = template.render(
        title          = "Rep / Segment Performance Summary",
        period         = "Latest available data",
        generated_date = date.today().strftime("%B %d, %Y"),
        table_html     = table_html,
        analysis       = analysis or "No analysis available.",
    )

    fname = f"rep_summary_{uuid.uuid4().hex[:8]}.html"
    out   = OUTPUT_DIR / fname
    out.write_text(html, encoding="utf-8")
    logger.info(f"HTML report saved: {out}")
    return str(out)


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_report(
    report_type: str,
    data:        pd.DataFrame | None = None,
    analysis:    str                 = "",
    chart_path:  str | None          = None,
) -> str:
    """
    Generates a report and returns the output file path.

    Args:
        report_type: "weekly_sales" | "quarterly_trends" | "rep_summary"
        data:        DataFrame of query results
        analysis:    Plain-text analysis summary
        chart_path:  Path to a chart PNG (optional)

    Returns:
        Path to the generated file (.pptx or .html)
    """
    if report_type in ("weekly_sales", "quarterly_trends"):
        return _make_pptx(report_type, data, analysis, chart_path)
    elif report_type == "rep_summary":
        return _make_html(data, analysis)
    else:
        raise ValueError(f"Unknown report type: {report_type}. "
                         f"Choose from: weekly_sales, quarterly_trends, rep_summary")
