"""Excel export for extraction sessions (openpyxl)."""

from __future__ import annotations

from .models import ExtractionSession


def export_session(session: ExtractionSession, path: str) -> str:
    """Write a summary sheet + one data sheet per series to an .xlsx file."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    for col, head in enumerate(["Series", "Points", "Color HSV", "Source"], start=1):
        cell = summary.cell(row=1, column=col, value=head)
        cell.font = Font(bold=True)
    for i, s in enumerate(session.series, start=2):
        summary.cell(row=i, column=1, value=s.name)
        summary.cell(row=i, column=2, value=len(s.points))
        summary.cell(row=i, column=3, value=str(s.color_hsv))
        summary.cell(row=i, column=4, value=session.image_path or "")

    for idx, s in enumerate(session.series, start=1):
        name = (s.name or f"Series{idx}")[:31]
        ws = wb.create_sheet(title=name)
        for col, head in enumerate(["X", "Y", "px", "py", "confidence"], start=1):
            ws.cell(row=1, column=col, value=head).font = Font(bold=True)
        for r, p in enumerate(s.points, start=2):
            ws.cell(row=r, column=1, value=round(p.data_x, 6))
            ws.cell(row=r, column=2, value=round(p.data_y, 6))
            ws.cell(row=r, column=3, value=round(p.px, 2))
            ws.cell(row=r, column=4, value=round(p.py, 2))
            ws.cell(row=r, column=5, value=round(p.confidence, 3))
        ws.freeze_panes = "A2"

    wb.save(path)
    return path
