"""Same-color multi-series: morphological detection + crossover assignment."""

from scripts.figdatax import (cluster_markers_by_x, assign_series_with_crossover)


def test_cluster_by_x():
    markers = [(10, 50, 100, 8, 8), (12, 150, 100, 8, 8),
               (60, 60, 100, 8, 8), (62, 140, 100, 8, 8)]
    groups = cluster_markers_by_x(markers, tolerance=25)
    assert len(groups) == 2
    assert all(len(g) == 2 for g in groups)


def test_assignment_tracks_crossover():
    # Two series that cross: series A goes top->bottom, series B bottom->top.
    groups = []
    for i in range(5):
        ya = 20 + i * 20          # descending on screen (increasing cy)
        yb = 120 - i * 20         # ascending on screen (decreasing cy)
        markers = sorted([(i * 30, ya, 100, 8, 8), (i * 30, yb, 100, 8, 8)],
                         key=lambda m: m[1])
        groups.append(markers)
    result = assign_series_with_crossover(groups, 2, ["A", "B"])
    a_ys = [p[1] for p in result["A"]]
    b_ys = [p[1] for p in result["B"]]
    # A should be continuous (monotonic increasing cy), not jump at the crossover
    assert a_ys == sorted(a_ys)
    assert b_ys == sorted(b_ys, reverse=True)


def test_missing_marker_fills_none():
    groups = [
        [(0, 40, 100, 8, 8), (0, 80, 100, 8, 8)],
        [(30, 42, 100, 8, 8)],  # only one marker (overlap)
        [(60, 44, 100, 8, 8), (60, 84, 100, 8, 8)],
    ]
    result = assign_series_with_crossover(groups, 2, ["A", "B"])
    assert None in result["A"] or None in result["B"]
