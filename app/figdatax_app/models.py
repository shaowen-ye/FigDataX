"""Lightweight data model for a digitizing session.

Full project persistence (.fdxproj) lands in a later phase; these dataclasses give
the digitize result somewhere structured to live and to export from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class CalibPoint:
    px: float          # pixel coordinate (x for x-axis points, y for y-axis points)
    value: float       # data value at that tick


@dataclass
class Calibration:
    x_points: List[CalibPoint] = field(default_factory=list)
    y_points: List[CalibPoint] = field(default_factory=list)
    x_log: bool = False
    y_log: bool = False

    def is_ready(self) -> bool:
        return len(self.x_points) >= 2 and len(self.y_points) >= 2


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


@dataclass
class ExtractionSession:
    image_path: Optional[str] = None
    plot_bbox: Optional[Tuple[int, int, int, int]] = None
    calibration: Calibration = field(default_factory=Calibration)
    series: List[Series] = field(default_factory=list)

    def active_series(self) -> Series:
        if not self.series:
            self.series.append(Series())
        return self.series[-1]
