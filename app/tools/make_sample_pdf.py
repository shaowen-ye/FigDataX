"""Regenerate the synthetic test PDF fixture used by the PDF-pipeline smoke test.

Run once when the fixture needs updating (needs fpdf2, a dev-only dependency):

    app/.venv/bin/python -m tools.make_sample_pdf

Output: figdatax_app/assets/sample/sample_paper.pdf — a one-figure, one-table page
with data-bearing sentences, so figure detection, table extraction, and the
data-mention scanner all have something real to find.
"""

from __future__ import annotations

import os

import cv2
import numpy as np
from fpdf import FPDF

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(HERE, "..", "figdatax_app", "assets", "sample")
CHART_PNG = os.path.join(SAMPLE_DIR, "sample_scatter.png")
OUT_PDF = os.path.join(SAMPLE_DIR, "sample_paper.pdf")


def _ensure_chart() -> str:
    """Reuse the existing scatter fixture; synthesize one if it is missing."""
    if os.path.exists(CHART_PNG):
        return CHART_PNG
    img = np.full((440, 640, 3), 255, np.uint8)
    cv2.rectangle(img, (90, 40), (590, 380), (0, 0, 0), 2)
    for x in range(0, 11):
        px = int(90 + x / 10 * 500)
        cv2.circle(img, (px, int(380 - (2 * x) / 25 * 340)), 6, (0, 255, 255), -1)
    cv2.imwrite(CHART_PNG, img)
    return CHART_PNG


def build() -> str:
    chart = _ensure_chart()
    pdf = FPDF(unit="pt", format="A4")
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 24, "Synthetic study of CPUE across sites", ln=1)

    pdf.set_font("Helvetica", "", 11)
    body = (
        "We sampled n = 42 stations across the watershed. Mean catch per unit effort "
        "was 4.2 +/- 0.8 ind./m2 at reference sites and differed significantly from "
        "impacted sites (p < 0.01). Species richness correlated with dissolved oxygen "
        "(r = 0.76). Recovery reached 63.5 % within the study window (95% CI 51-72). "
        "See Figure 1 for the dose-response relationship and Table 1 for site means."
    )
    pdf.multi_cell(0, 16, body)
    pdf.ln(8)

    # Figure 1 (embedded raster — this is what figure detection must find)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 14, "Figure 1. Response versus dose (y = 2x).", ln=1)
    pdf.image(chart, w=300)
    pdf.ln(10)

    # Table 1 (bordered cells → ruling lines pdfplumber can detect)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 14, "Table 1. Site means.", ln=1)
    rows = [
        ["Site", "Mean CPUE", "SD", "n"],
        ["Reference", "4.2", "0.8", "14"],
        ["Impacted", "1.9", "0.5", "14"],
        ["Recovering", "3.1", "0.6", "14"],
    ]
    pdf.set_font("Helvetica", "", 10)
    widths = [120, 90, 60, 50]
    for r, row in enumerate(rows):
        if r == 0:
            pdf.set_font("Helvetica", "B", 10)
        else:
            pdf.set_font("Helvetica", "", 10)
        for w, cell in zip(widths, row):
            pdf.cell(w, 18, cell, border=1)
        pdf.ln(18)

    os.makedirs(SAMPLE_DIR, exist_ok=True)
    pdf.output(OUT_PDF)
    print(f"wrote {os.path.normpath(OUT_PDF)}")
    return OUT_PDF


if __name__ == "__main__":
    build()
