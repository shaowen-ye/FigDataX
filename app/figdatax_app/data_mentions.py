"""Scan PDF text for likely data-bearing passages and locate them.

The goal is to *surface* numeric evidence a reader would want to digitize or copy —
means±SD, sample sizes, p-values, correlations, percentages, ranges, confidence
intervals, and explicit Table/Figure references — each with its page and the sentence
it sits in, so the UI can jump straight there.

This is deliberately recall-oriented and language-light: it flags candidates, it does
not parse values into a schema (that is the extraction engine's and the user's job).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List

# Each pattern is (category, compiled regex). Order matters only for the category label
# shown when several match the same span — the first wins.
_NUM = r"[-+]?\d[\d,]*\.?\d*"

_PATTERNS = [
    ("mean±sd",   re.compile(rf"{_NUM}\s*(?:±|\+/?-|\\pm)\s*{_NUM}")),
    ("ci",        re.compile(r"\b(?:95\s*%?\s*)?C\.?I\.?\b|\bconfidence interval\b", re.I)),
    ("p-value",   re.compile(r"\bp\s*[<>=≤≥]\s*0?\.\d+", re.I)),
    ("n=",        re.compile(r"\bn\s*=\s*\d+", re.I)),
    ("correlation", re.compile(r"\b[rR]\s*=\s*[-+]?0?\.\d+|\bR\^?2\s*=\s*0?\.\d+|\bR²\s*=\s*0?\.\d+")),
    ("percentage", re.compile(rf"{_NUM}\s*%")),
    ("range",     re.compile(rf"{_NUM}\s*(?:–|—|-|to)\s*{_NUM}\b")),
    ("table-ref", re.compile(r"\b(?:Table|Tab\.)\s*\d+", re.I)),
    ("figure-ref", re.compile(r"\b(?:Figure|Fig\.?)\s*\d+", re.I)),
    ("units",     re.compile(rf"{_NUM}\s*(?:mg|kg|µg|ug|ml|mL|µm|um|mm|cm|km|nm|"
                             r"°C|℃|ppm|ppb|mol|mmol|µmol|g/L|mg/L|mg/kg|"
                             r"ind\.?/m2|ind/m²|CPUE)\b")),
]

# Sentences that are almost certainly not data (references section, page furniture).
_NOISE = re.compile(r"^\s*(?:doi|https?://|©|received|accepted|correspondence)", re.I)


@dataclass
class Mention:
    page_index: int          # 0-based
    category: str
    match_text: str          # the exact span that matched
    sentence: str            # the surrounding sentence (context)
    char_start: int          # offset of the match within the page text
    char_end: int

    @property
    def page_label(self) -> int:
        return self.page_index + 1


def _split_sentences(text: str) -> List[tuple]:
    """Yield (sentence, start_offset) over the page text, keeping char offsets so the
    UI can map back to a location.

    Boundaries are sentence punctuation followed by whitespace and a capital/opening
    bracket, or a blank line. Crucially it does NOT break on the period inside a
    decimal ("4.2") or an abbreviation ("ind./m2"), which would otherwise sever the
    very numbers we want to surface.
    """
    boundary = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])|\n{2,}")
    out = []
    pos = 0
    for m in boundary.finditer(text):
        seg = text[pos:m.start()]
        if seg.strip():
            out.append((seg.strip(), pos + (len(seg) - len(seg.lstrip()))))
        pos = m.end()
    tail = text[pos:]
    if tail.strip():
        out.append((tail.strip(), pos + (len(tail) - len(tail.lstrip()))))
    return out


def scan_text(page_index: int, text: str) -> List[Mention]:
    mentions: List[Mention] = []
    seen = set()
    for sentence, s_off in _split_sentences(text):
        if _NOISE.match(sentence):
            continue
        for category, rx in _PATTERNS:
            for m in rx.finditer(sentence):
                span = (s_off + m.start(), s_off + m.end())
                key = (span, category)
                if key in seen:
                    continue
                seen.add(key)
                mentions.append(Mention(
                    page_index=page_index,
                    category=category,
                    match_text=m.group().strip(),
                    sentence=_clip(sentence),
                    char_start=span[0],
                    char_end=span[1],
                ))
    return mentions


def _clip(sentence: str, limit: int = 240) -> str:
    s = re.sub(r"\s+", " ", sentence).strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def scan_pages(pages: Iterable) -> List[Mention]:
    """``pages`` is an iterable of objects with ``.page_index`` and ``.text``
    (e.g. ``PdfDocument.all_text()``)."""
    result: List[Mention] = []
    for p in pages:
        result.extend(scan_text(p.page_index, p.text))
    return result


# Categories that most strongly indicate directly-usable numeric data, for ranking.
_PRIORITY = {"mean±sd": 0, "ci": 1, "correlation": 1, "p-value": 2, "n=": 2,
             "units": 2, "percentage": 3, "range": 3, "table-ref": 4, "figure-ref": 4}


def rank(mentions: List[Mention]) -> List[Mention]:
    """Most data-dense mentions first (stable within a category, by page then position)."""
    return sorted(mentions, key=lambda m: (_PRIORITY.get(m.category, 9),
                                           m.page_index, m.char_start))
