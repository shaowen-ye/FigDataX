"""High-level AI assists built on a provider.

These functions turn a provider's free text into structured suggestions the UI can act
on. They never mutate a session directly — the caller confirms first.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

from .providers import AIError

_CALIB_SYSTEM = (
    "You are a scientific chart-reading assistant. You never invent values; if you "
    "cannot read a tick, omit it. Answer with a single JSON object only, no prose."
)

_CALIB_PROMPT = """Analyze this chart image and report calibration candidates.

Return JSON exactly:
{
  "chart_type": "scatter|line|bar|box|pie|heatmap|other",
  "x_ticks": [{"value": <number>, "frac": <0..1 left→right>}, ...],
  "y_ticks": [{"value": <number>, "frac": <0..1 bottom→top>}, ...],
  "series_colors": ["#rrggbb", ...],
  "notes": "<short>"
}
"frac" is the fractional position of the tick inside the plot area. Include only ticks
whose numeric value you can actually read. If none, use empty lists."""


@dataclass
class TickSuggestion:
    axis: str          # "x" or "y"
    value: float
    frac: float        # 0..1 within plot area (x: left→right, y: bottom→top)


@dataclass
class CalibrationSuggestion:
    chart_type: str = "other"
    x_ticks: List[TickSuggestion] = None
    y_ticks: List[TickSuggestion] = None
    series_colors: List[str] = None
    notes: str = ""

    def is_empty(self) -> bool:
        return not (self.x_ticks or self.y_ticks)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise AIError(f"AI did not return JSON: {text[:200]}")
    try:
        return json.loads(m.group())
    except json.JSONDecodeError as exc:
        raise AIError(f"AI returned invalid JSON: {exc}") from exc


def suggest_calibration(provider, image_bgr: np.ndarray,
                        plot_bbox: Optional[tuple] = None) -> CalibrationSuggestion:
    """Ask the AI to read chart type, tick candidates, and series colors from a figure.

    Returns suggestions in fractional plot-area coordinates; the caller maps ``frac`` to
    pixels (using ``plot_bbox``) and lets the user confirm each value before it is used.
    """
    crop = image_bgr
    if plot_bbox:
        l, t, r, b = plot_bbox
        crop = image_bgr[max(0, t):b, max(0, l):r]
    tmp = os.path.join(tempfile.gettempdir(), "figdatax_ai_crop.png")
    cv2.imwrite(tmp, crop)
    raw = provider.complete(_CALIB_PROMPT, images=[tmp], system=_CALIB_SYSTEM)
    data = _extract_json(raw)

    def ticks(key, axis):
        out = []
        for t in data.get(key, []) or []:
            try:
                out.append(TickSuggestion(axis, float(t["value"]), float(t["frac"])))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    return CalibrationSuggestion(
        chart_type=str(data.get("chart_type", "other")),
        x_ticks=ticks("x_ticks", "x"),
        y_ticks=ticks("y_ticks", "y"),
        series_colors=[str(c) for c in (data.get("series_colors") or [])],
        notes=str(data.get("notes", "")),
    )


def frac_to_pixel(sug: TickSuggestion, plot_bbox: tuple) -> float:
    """Map a fractional tick position to an image-pixel coordinate for its axis."""
    left, top, right, bottom = plot_bbox
    if sug.axis == "x":
        return left + sug.frac * (right - left)
    # y frac is bottom→top, image pixels grow downward
    return bottom - sug.frac * (bottom - top)


_SUMMARY_SYSTEM = ("You summarize quantitative findings from a paper. Be faithful, cite "
                   "the page for each figure, and never invent numbers.")


def summarize_mentions(provider, mentions, max_items: int = 40) -> str:
    """Turn flagged data mentions into a concise, page-cited bullet summary."""
    lines = [f"p{m.page_label} [{m.category}] {m.match_text} — {m.sentence}"
             for m in mentions[:max_items]]
    if not lines:
        return "No data mentions to summarize."
    prompt = ("Summarize the key quantitative findings below as short bullets, keeping the "
              "page number for each. Group related numbers.\n\n" + "\n".join(lines))
    return provider.complete(prompt, system=_SUMMARY_SYSTEM)
