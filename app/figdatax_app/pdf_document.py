"""PDF ingestion — render pages, locate embedded figures, and extract tables.

Uses pypdfium2 (Apache/BSD, MIT-compatible) for rendering and page-object access, and
pdfplumber for table extraction. No AGPL dependency (deliberately not PyMuPDF).

Coordinate convention: everything this module returns is in **top-left pixel space of
the rendered page at ``scale``** (origin top-left, y grows downward), matching what the
Qt views and the extraction engine expect. pypdfium bounds are PDF points with a
bottom-left origin, so we flip y here once and never again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

try:
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c
    _PDF_OK = True
except Exception:  # pragma: no cover - optional dep missing
    _PDF_OK = False

RENDER_SCALE = 2.0            # page render zoom (points → pixels)
MIN_FIGURE_PX = 80           # ignore tiny embedded images (icons, logos, rules)


def pdf_available() -> bool:
    return _PDF_OK


@dataclass
class FigureRef:
    """An embedded raster image on a page, in rendered-page pixel space."""
    page_index: int
    bbox: Tuple[int, int, int, int]      # (left, top, right, bottom) in page pixels
    px_size: Tuple[int, int]             # native (w, h) of the embedded image
    image_bgr: Optional[np.ndarray] = None   # native-resolution crop (BGR), filled lazily

    @property
    def area(self) -> int:
        l, t, r, b = self.bbox
        return max(0, r - l) * max(0, b - t)


@dataclass
class TableRef:
    page_index: int
    bbox: Tuple[float, float, float, float]  # pdfplumber page coords (top-left origin, points)
    rows: List[List[str]] = field(default_factory=list)

    @property
    def shape(self) -> Tuple[int, int]:
        return (len(self.rows), max((len(r) for r in self.rows), default=0))


@dataclass
class PageText:
    page_index: int
    text: str
    width_pt: float
    height_pt: float


class PdfDocument:
    """Lazy façade over a single PDF: page rendering, figure and table detection."""

    def __init__(self, path: str):
        if not _PDF_OK:
            raise RuntimeError(
                "PDF support needs pypdfium2 + pdfplumber. Install them in the app venv "
                "(they are in app/requirements.txt).")
        self.path = path
        self._pdf = pdfium.PdfDocument(path)
        self.n_pages = len(self._pdf)

    def close(self):
        try:
            self._pdf.close()
        except Exception:
            pass

    # ── rendering ──
    def render_page(self, index: int, scale: float = RENDER_SCALE) -> np.ndarray:
        """Render a page to a BGR numpy array at ``scale`` (points × scale = pixels)."""
        page = self._pdf[index]
        pil = page.render(scale=scale).to_pil().convert("RGB")
        rgb = np.asarray(pil)
        return rgb[:, :, ::-1].copy()   # RGB → BGR

    def page_pixel_size(self, index: int, scale: float = RENDER_SCALE) -> Tuple[int, int]:
        w, h = self._pdf[index].get_size()
        return int(round(w * scale)), int(round(h * scale))

    # ── figures ──
    def detect_figures(self, index: int, scale: float = RENDER_SCALE) -> List[FigureRef]:
        """Find embedded raster images on a page, returned in page-pixel space,
        largest first. Tiny images (< MIN_FIGURE_PX on a side) are skipped."""
        page = self._pdf[index]
        page_h_pt = page.get_height()
        figs: List[FigureRef] = []
        for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)):
            try:
                l, b, r, t = obj.get_bounds()     # PDF points, bottom-left origin
            except Exception:
                continue
            # PDF (bottom-left) → page-pixel (top-left) space
            left = int(round(min(l, r) * scale))
            right = int(round(max(l, r) * scale))
            top = int(round((page_h_pt - max(t, b)) * scale))
            bottom = int(round((page_h_pt - min(t, b)) * scale))
            if (right - left) < MIN_FIGURE_PX or (bottom - top) < MIN_FIGURE_PX:
                continue
            try:
                pw, ph = obj.get_px_size()
            except Exception:
                pw, ph = (right - left, bottom - top)
            figs.append(FigureRef(index, (left, top, right, bottom), (int(pw), int(ph))))
        figs.sort(key=lambda f: f.area, reverse=True)
        return figs

    def crop_figure(self, fig: FigureRef, scale: float = RENDER_SCALE) -> np.ndarray:
        """Return the figure region as BGR. Renders the page region at high scale so the
        digitizer works on the sharpest available pixels."""
        page_bgr = self.render_page(fig.page_index, scale=scale)
        l, t, r, b = fig.bbox
        h, w = page_bgr.shape[:2]
        l, t = max(0, l), max(0, t)
        r, b = min(w, r), min(h, b)
        crop = page_bgr[t:b, l:r].copy()
        fig.image_bgr = crop
        return crop

    # ── tables ──
    def detect_tables(self, index: int) -> List[TableRef]:
        import pdfplumber
        refs: List[TableRef] = []
        with pdfplumber.open(self.path) as pl:
            page = pl.pages[index]
            for tbl in page.find_tables():
                rows = tbl.extract() or []
                clean = [["" if c is None else str(c).strip() for c in row] for row in rows]
                if any(any(cell for cell in row) for row in clean):
                    refs.append(TableRef(index, tuple(tbl.bbox), clean))
        return refs

    # ── text ──
    def page_text(self, index: int) -> PageText:
        page = self._pdf[index]
        tp = page.get_textpage()
        text = tp.get_text_range()
        w, h = page.get_size()
        return PageText(index, text, w, h)

    def all_text(self) -> List[PageText]:
        return [self.page_text(i) for i in range(self.n_pages)]
