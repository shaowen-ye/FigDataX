"""PDF figure ingestion — render pages, locate figures, crop them for digitizing.

This is the bridge from a professional-literature PDF to the figures inside it: it
finds the charts (embedded bitmaps, and — as a fallback — pages that carry a figure
caption but were drawn as vectors), crops them at high resolution, and writes a small
manifest an agent can walk. It deliberately does **not** extract tables or mine text;
the skill is about getting numbers out of *figures*.

Uses pypdfium2 (Apache/BSD, MIT-compatible) — an optional dependency loaded lazily via
``core._require``, so importing this module (or the package) works without it.

Coordinate convention: everything returned is in **top-left pixel space of the rendered
page at ``scale``** (origin top-left, y grows downward), matching the extraction engine.
pypdfium bounds are PDF points with a bottom-left origin, so we flip y here once.

Page numbering: the Python API uses 0-based ``page_index``; the manifest uses 1-based
``page``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from . import __version__
from .core import FigDataXError, InputError, _require

RENDER_SCALE = 2.0            # page render zoom (points → pixels)
CROP_SCALE = 4.0             # figure-crop zoom: digitizer wants the sharpest pixels
MIN_FIGURE_PX = 80           # ignore tiny embedded images (icons, logos, rules)

_CAPTION_RX = re.compile(r"\b(Fig(?:ure)?\.?)\s*(\d+[a-z]?)", re.I)


def pdf_available() -> bool:
    """Cheap check (no import) that the optional pypdfium2 dependency is installed."""
    return importlib.util.find_spec("pypdfium2") is not None


def _pdfium():
    return _require("pypdfium2", "PDF page rendering / figure detection")


def _pdfium_raw():
    return _require("pypdfium2.raw", "PDF figure detection")


@dataclass
class FigureRef:
    """An embedded raster figure on a page, in rendered-page pixel space."""
    page_index: int
    bbox: Tuple[int, int, int, int]      # (left, top, right, bottom) in page pixels
    px_size: Tuple[int, int]             # native (w, h) of the embedded image
    label: Optional[str] = None          # e.g. "Figure 2" (from caption harvesting)
    caption: Optional[str] = None        # first ~200 chars of the caption line
    image_bgr: Optional[np.ndarray] = None   # crop (BGR), filled by crop_figure

    @property
    def area(self) -> int:
        l, t, r, b = self.bbox
        return max(0, r - l) * max(0, b - t)


@dataclass
class PageText:
    page_index: int
    text: str
    width_pt: float
    height_pt: float


class PdfDocument:
    """Lazy façade over a single PDF: page rendering and figure detection."""

    def __init__(self, path: str):
        if not os.path.exists(path):
            raise InputError(f"PDF not found: {path}")
        if not pdf_available():
            raise FigDataXError(
                "PDF support requires 'pypdfium2'. Bootstrap the skill environment "
                "with `bash scripts/setup.sh` and run FigDataX with "
                "`<skill_dir>/.venv/bin/python`.")
        self.path = path
        self._pdf = _pdfium().PdfDocument(path)
        self.n_pages = len(self._pdf)

    def close(self):
        try:
            self._pdf.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

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
        """Find embedded raster figures on a page, in page-pixel space, largest first.

        Note: only BITMAP objects are found — vector-drawn charts (matplotlib/R PDF
        output) yield no candidates here; ``scan_figures`` surfaces those pages under
        ``vector_pages`` with a full-page render instead.
        """
        pdfium_c = _pdfium_raw()
        page = self._pdf[index]
        page_h_pt = page.get_height()
        figs: List[FigureRef] = []
        for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)):
            try:
                l, b, r, t = obj.get_bounds()     # PDF points, bottom-left origin
            except Exception:
                continue
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

    def crop_figure(self, fig: FigureRef, scale: float = CROP_SCALE) -> np.ndarray:
        """Return the figure region as BGR, rendered at high ``scale`` so the digitizer
        works on the sharpest available pixels. ``fig.bbox`` is in RENDER_SCALE space;
        the crop rectangle is rescaled internally."""
        page_bgr = self.render_page(fig.page_index, scale=scale)
        f = scale / RENDER_SCALE
        l, t, r, b = (int(round(v * f)) for v in fig.bbox)
        h, w = page_bgr.shape[:2]
        l, t = max(0, l), max(0, t)
        r, b = min(w, r), min(h, b)
        if r <= l or b <= t:
            raise InputError(f"Empty figure crop for bbox {fig.bbox}")
        crop = page_bgr[t:b, l:r].copy()
        fig.image_bgr = crop
        return crop

    # ── captions (just to name/label a figure) ──
    def find_caption(self, fig: FigureRef, band_pt: float = 60.0,
                     scale: float = RENDER_SCALE) -> Optional[str]:
        """Harvest the caption line under (or, as fallback, above) a figure bbox to fill
        ``fig.label`` ("Figure 2") and ``fig.caption``. Returns the caption or None."""
        page = self._pdf[fig.page_index]
        page_h_pt = page.get_height()
        tp = page.get_textpage()
        l_px, t_px, r_px, b_px = fig.bbox
        l_pt, r_pt = l_px / scale, r_px / scale
        top_pt = page_h_pt - t_px / scale
        bot_pt = page_h_pt - b_px / scale
        for (bottom, top) in ((bot_pt - band_pt, bot_pt), (top_pt, top_pt + band_pt)):
            try:
                text = tp.get_text_bounded(left=l_pt, bottom=max(0, bottom),
                                           right=r_pt, top=min(page_h_pt, top))
            except Exception:
                continue
            text = (text or "").strip()
            m = _CAPTION_RX.search(text)
            if m:
                fig.label = f"Figure {m.group(2)}"
                start = m.start()
                fig.caption = re.sub(r"\s+", " ", text[start:start + 200]).strip()
                return fig.caption
        return None

    # ── text (only to spot captions on vector pages) ──
    def page_text(self, index: int) -> PageText:
        page = self._pdf[index]
        text = page.get_textpage().get_text_range()
        w, h = page.get_size()
        return PageText(index, text, w, h)


# ───────────────────────────────────────────────────────────────────
#  scan_figures — pull every figure out of a PDF for digitizing
# ───────────────────────────────────────────────────────────────────

def scan_figures(pdf_path: str, out_dir: str, scale: float = RENDER_SCALE,
                 crop_scale: float = CROP_SCALE) -> dict:
    """Crop every figure in a PDF to a PNG and write a manifest to walk.

    Layout under ``out_dir``: figures/*.png, pages/*.png (only pages that carry a
    figure caption but no detectable bitmap — vector-drawn charts to crop visually),
    manifest.json. Manifest paths are relative to ``out_dir``; pages are 1-based.
    Returns the manifest dict.
    """
    os.makedirs(out_dir, exist_ok=True)
    for sub in ("figures", "pages"):
        os.makedirs(os.path.join(out_dir, sub), exist_ok=True)

    fig_entries, vector_pages = [], []
    with PdfDocument(pdf_path) as doc:
        for i in range(doc.n_pages):
            figs = doc.detect_figures(i, scale=scale)
            for k, fig in enumerate(figs, start=1):
                doc.find_caption(fig, scale=scale)
                fig_id = f"fig_p{i + 1}_{k}"
                png_rel = os.path.join("figures", f"{fig_id}.png")
                crop = doc.crop_figure(fig, scale=crop_scale)
                cv2.imwrite(os.path.join(out_dir, png_rel), crop)
                fig_entries.append({
                    "id": fig_id, "page": i + 1, "bbox_px": list(fig.bbox),
                    "native_px": list(fig.px_size), "png": png_rel,
                    "label": fig.label, "caption": fig.caption,
                })
            if figs:
                continue
            # Vector fallback: a figure caption but no bitmap → full-page render.
            pt = doc.page_text(i)
            m = re.search(r"^\s*(Fig(?:ure)?\.?\s*\d+[a-z]?)[.:]?\s*(.{0,160})",
                          pt.text, re.I | re.M)
            if m:
                page_rel = os.path.join("pages", f"page_{i + 1:02d}.png")
                cv2.imwrite(os.path.join(out_dir, page_rel),
                            doc.render_page(i, scale=scale))
                vector_pages.append({
                    "page": i + 1,
                    "label": re.sub(r"\s+", " ", m.group(1)).strip(),
                    "caption": re.sub(r"\s+", " ", (m.group(1) + " " + m.group(2))).strip(),
                    "page_png": page_rel,
                    "note": "vector-drawn or undetected; view page_png and crop visually",
                })

    manifest = {
        "schema": "figdatax-figures/1",
        "source_pdf": os.path.abspath(pdf_path),
        "engine_version": __version__,
        "render_scale": scale, "crop_scale": crop_scale,
        "n_figures": len(fig_entries),
        "figures": fig_entries,
        "vector_pages": vector_pages,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    return manifest
