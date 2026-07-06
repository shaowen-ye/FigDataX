"""Data model for a digitizing session, with JSON-friendly (de)serialization.

The dataclasses are the app's single in-memory representation; ``project.py`` wraps
them in a versioned .fdx project file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional, Tuple


@dataclass
class CalibPoint:
    px: float          # pixel coordinate (x for x-axis points, y for y-axis points)
    value: float       # data value at that tick
    # where the click happened, so markers can be restored on project load
    scene_x: float = 0.0
    scene_y: float = 0.0


@dataclass
class Calibration:
    x_points: List[CalibPoint] = field(default_factory=list)
    y_points: List[CalibPoint] = field(default_factory=list)
    x_log: bool = False
    y_log: bool = False

    def is_ready(self) -> bool:
        return len(self.x_points) >= 2 and len(self.y_points) >= 2

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Calibration":
        return cls(
            x_points=[CalibPoint(**p) for p in d.get("x_points", [])],
            y_points=[CalibPoint(**p) for p in d.get("y_points", [])],
            x_log=bool(d.get("x_log", False)),
            y_log=bool(d.get("y_log", False)),
        )


@dataclass
class DataPoint:
    px: float
    py: float
    data_x: float
    data_y: float
    confidence: float = 1.0
    manual: bool = False


@dataclass
class Series:
    name: str = "Series 1"
    color_hsv: Optional[Tuple[int, int, int]] = None
    points: List[DataPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "color_hsv": list(self.color_hsv) if self.color_hsv else None,
            "points": [asdict(p) for p in self.points],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Series":
        color = d.get("color_hsv")
        return cls(
            name=d.get("name", "Series 1"),
            color_hsv=tuple(color) if color else None,
            points=[DataPoint(**p) for p in d.get("points", [])],
        )


@dataclass
class ExtractionSession:
    image_path: Optional[str] = None
    plot_bbox: Optional[Tuple[int, int, int, int]] = None
    calibration: Calibration = field(default_factory=Calibration)
    series: List[Series] = field(default_factory=list)
    source_label: str = ""   # e.g. "paper.pdf p.3 figure 2" for PDF-cropped figures

    def active_series(self) -> Series:
        if not self.series:
            self.series.append(Series())
        return self.series[-1]

    def total_points(self) -> int:
        return sum(len(s.points) for s in self.series)

    def to_dict(self) -> dict:
        return {
            "image_path": self.image_path,
            "plot_bbox": list(self.plot_bbox) if self.plot_bbox else None,
            "calibration": self.calibration.to_dict(),
            "series": [s.to_dict() for s in self.series],
            "source_label": self.source_label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExtractionSession":
        bbox = d.get("plot_bbox")
        return cls(
            image_path=d.get("image_path"),
            plot_bbox=tuple(bbox) if bbox else None,
            calibration=Calibration.from_dict(d.get("calibration", {})),
            series=[Series.from_dict(s) for s in d.get("series", [])],
            source_label=d.get("source_label", ""),
        )
