"""FigDataX project files (.fdx).

A project is a single JSON document containing the extraction session (calibration,
series, points), the eyedropper target color, and — for portability — an embedded
PNG copy of the source image. Opening a project therefore never depends on the
original image still being at its recorded path.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional, Tuple

import cv2
import numpy as np

from .models import ExtractionSession

FORMAT = "figdatax-project"
FORMAT_VERSION = 1
SUFFIX = ".fdx"


class ProjectError(Exception):
    """Raised when a project file cannot be read or is not a valid .fdx."""


def _encode_image(bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise ProjectError("Could not encode the source image for embedding.")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _decode_image(b64: str) -> np.ndarray:
    data = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
    bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ProjectError("Embedded image data is corrupt.")
    return bgr


def save_project(path: str, session: ExtractionSession,
                 image_bgr: Optional[np.ndarray] = None,
                 target_hsv: Optional[Tuple[int, int, int]] = None) -> str:
    """Write the session to ``path`` (forced to the .fdx suffix). Returns the path."""
    if not path.endswith(SUFFIX):
        path += SUFFIX
    doc = {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "session": session.to_dict(),
        "target_hsv": list(target_hsv) if target_hsv else None,
        "image_png_base64": _encode_image(image_bgr) if image_bgr is not None else None,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    os.replace(tmp, path)
    return path


def load_project(path: str):
    """Read a .fdx file.

    Returns ``(session, image_bgr, target_hsv)``. ``image_bgr`` comes from the
    embedded copy when present, else from ``session.image_path`` if it still exists,
    else None (the UI should tell the user to relocate the image).
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError(f"Cannot read project file: {exc}") from exc

    if doc.get("format") != FORMAT:
        raise ProjectError("Not a FigDataX project file (.fdx).")
    if int(doc.get("version", 0)) > FORMAT_VERSION:
        raise ProjectError(
            f"Project was saved by a newer FigDataX (format v{doc['version']}, "
            f"this app reads up to v{FORMAT_VERSION}). Please update the app.")

    session = ExtractionSession.from_dict(doc.get("session", {}))

    image_bgr = None
    if doc.get("image_png_base64"):
        image_bgr = _decode_image(doc["image_png_base64"])
    elif session.image_path and os.path.exists(session.image_path):
        image_bgr = cv2.imread(session.image_path)

    hsv = doc.get("target_hsv")
    target_hsv = tuple(int(v) for v in hsv) if hsv else None
    return session, image_bgr, target_hsv
