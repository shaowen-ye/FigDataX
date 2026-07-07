"""PDF figure ingestion against the synthetic sample_paper.pdf.

Skipped entirely when the optional pypdfium2 dependency is absent."""

import json
import os

import pytest

pytest.importorskip("pypdfium2")

from scripts.figdatax import pdf_available, scan_figures
from scripts.figdatax.pdf import PdfDocument

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
SAMPLE_PDF = os.path.join(ASSETS, "sample_paper.pdf")


def test_pdf_available():
    assert pdf_available() is True


def test_open_and_render():
    with PdfDocument(SAMPLE_PDF) as doc:
        assert doc.n_pages == 1
        page = doc.render_page(0)
        assert page.ndim == 3 and page.shape[2] == 3
        assert page.shape[0] > 200 and page.shape[1] > 200


def test_detect_figures_and_crop():
    with PdfDocument(SAMPLE_PDF) as doc:
        figs = doc.detect_figures(0)
        assert figs, "expected at least one embedded bitmap figure"
        l, t, r, b = figs[0].bbox
        assert r > l and b > t
        crop = doc.crop_figure(figs[0])
        assert crop.ndim == 3 and crop.shape[0] > 80 and crop.shape[1] > 80


def test_scan_figures_manifest(tmp_path):
    out = tmp_path / "figs"
    man = scan_figures(SAMPLE_PDF, str(out))

    assert man["schema"] == "figdatax-figures/1"
    for key in ("figures", "vector_pages", "n_figures", "source_pdf"):
        assert key in man
    assert man["n_figures"] == len(man["figures"]) >= 1

    assert (out / "manifest.json").exists()
    for f in man["figures"]:
        assert (out / f["png"]).exists()
        assert f["page"] == 1                          # 1-based
        assert "bbox_px" in f

    # manifest is valid JSON on disk
    with open(out / "manifest.json", encoding="utf-8") as fh:
        assert json.load(fh)["schema"] == "figdatax-figures/1"


def test_missing_pdf_raises(tmp_path):
    from scripts.figdatax import InputError
    with pytest.raises(InputError):
        PdfDocument(str(tmp_path / "nope.pdf"))
