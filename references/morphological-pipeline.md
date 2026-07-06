# Same-Color Multi-Series Detection (Morphological Method)

When every data series shares the same color (e.g. all black lines that differ only
by marker shape or line style), color-based extraction cannot separate them. Use
morphological erosion to strip the thin connecting lines and keep the thick markers,
then group markers by x-position and assign them to series while tracking crossovers.

## Pipeline

```python
from scripts.figdatax import (detect_markers_morphological, cluster_markers_by_x,
                              assign_series_with_crossover, calibrate_axes_multipoint)

# 1. Detect marker centers (erosion removes ~2-3px lines, keeps ~8px+ markers)
markers = detect_markers_morphological(
    img, plot_bbox=(x0, y0, x1, y1),
    legend_bbox=(lx0, ly0, lx1, ly1),   # exclude the legend to avoid false markers
    kernel_size=4, area_range=(60, 300), aspect_range=(0.6, 1.5), max_dim=20)
# → [(cx, cy, area, bbox_w, bbox_h), ...] sorted by x

# 2. Group markers by x-position (one group per categorical x / tick)
groups = cluster_markers_by_x(markers, tolerance=25)

# 3. Assign markers to series, handling curve crossovers
series = assign_series_with_crossover(groups, n_series=3,
                                      series_names=["Spring", "Summer", "Autumn"])
# → {"Spring": [(cx, cy)|None, ...], ...}

# 4. Convert each (cx, cy) to data with your calibration
data = {name: [cal.pixel_to_data(*p) if p else None for p in pts]
        for name, pts in series.items()}
```

## Tuning the erosion kernel

| Kernel size | Effect | Use when |
|-------------|--------|----------|
| 3×3, 1 iter | Removes ~1px lines, keeps ~5px+ markers | Thin lines, small markers |
| **4×4, 1 iter** | **Removes ~2-3px lines, keeps ~8px+ markers** | **Default — most charts** |
| 5×5, 1 iter | Removes ~3-4px lines, keeps ~10px+ markers | Thick lines, large markers |

If too many line fragments survive: increase `kernel_size`. If markers disappear:
decrease it or reduce `erode_iterations`.

## Crossover handling

`assign_series_with_crossover` predicts each series' next y from its recent
**trajectory** (velocity extrapolation), not just its last position. This lets two
crossing curves pass through each other instead of "bouncing" apart at the crossing —
a plain nearest-neighbor assignment gets this wrong. With scipy installed it uses the
Hungarian algorithm; otherwise brute-force permutations (requires `n_series ≤ 8`).

## Common pitfalls

- **Overlapping markers**: when two series have nearly-equal values at an x-position,
  their markers merge into one blob. The group then has fewer markers than series, and
  the missing series gets a `None` — supplement with manual reading or interpolation.
- **Legend contamination**: always pass `legend_bbox` if the legend sits inside the
  plot area, or its symbols become false markers.
- **Hollow markers**: outline-only markers have a white center, but `cv2.moments`
  computes the centroid of the ring, which *is* the geometric center — correct as-is.
