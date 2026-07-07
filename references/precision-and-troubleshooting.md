# Precision Best Practices & Troubleshooting

## Precision checklist

1. **Resolution matters.** Extract from the highest-resolution source available; render
   figures from PDF at ≥300 DPI.
2. **Multi-point calibration.** Use 3+ real tick marks per axis, not just min/max — this
   is the single biggest accuracy lever. Prefer `calibrate_axes_multipoint`.
3. **Verify calibration RMSE.** `cal.x_rmse_pct` / `cal.y_rmse_pct` are the fit error as
   a percentage of the axis span. If either exceeds ~1%, a tick pixel was likely
   mis-read — re-check the calibration points.
4. **Marker center = data point.** The geometric center of a marker is the true value.
   Large markers (10–20px) can add 5–10% error if an edge is read instead of the center.
   `subpixel=True` refines to the centroid.
5. **Get the target color with `pick_color`, don't guess.** Guessed HSV values are the
   #1 cause of zero detections (see below).
6. **Remove grid lines first** (`remove_grid`) before automated color detection.
7. **Exclude the legend** from marker detection if it overlaps the plot area.
8. **Report method + RMSE** in every output so the extraction is reproducible.
9. **Always generate a validation overlay** — comparing the reconstructed data against
   the original figure is the most reliable way to catch errors.

## "0 detections" diagnosis

`extract_by_color_adaptive` returning `[]` almost always means the target HSV is wrong
or the threshold is too tight. The function emits a warning naming the nearest dominant
color. To fix:

1. Run `pick_color(img, x, y)` on an actual marker to read its exact HSV.
2. Or list the dominant colors: `detect_data_colors(img, plot_bbox)`.
3. Or raise `color_distance` (default 25), or pass `auto_widen=True` to retry
   automatically up to a distance of 80.

Remember OpenCV HSV ranges: **H ∈ [0, 179]** (not 0–360), S and V ∈ [0, 255]. Pure red
is H≈0, saturated markers have V≈255 (which is NOT background — background is low
saturation).

## `color_distance` tuning

`color_distance` is the max Euclidean distance in HSV space (hue scaled ×2, so the
overall range is ~0–360).

| Value | Behavior |
|-------|----------|
| 15–20 | Very strict; only near-exact color matches. Good when series colors are close. |
| 25 (default) | Balanced for distinct, saturated series. |
| 40–60 | Lenient; tolerates anti-aliasing and gradients, but may merge similar series. |
| 80 | Maximum useful; `auto_widen` stops here. |

## Grid overlay density

Use the default 3-level overlay (fine 10px / mid 50px / major 200px). The 10px fine grid
gives ~±5px reading precision (≈±0.01 data units on a typical chart). Do not use 2–3px
ultra-fine grids — they obscure the image without meaningful precision gain.

## Dependency tiers

| You have | You can run |
|----------|-------------|
| cv2 + numpy | calibration, color/scatter/bar/error-bar/polar/morphological extraction, plot-area & color detection, grid overlay, panels, box/pie/heatmap |
| + scipy | `trace_curve`, `interpolate_curve`, Hungarian crossover assignment |
| + matplotlib | `create_validation_plot` / `render_validation` |
| + pandas / openpyxl | CSV / Excel output (CLI) |

If a heavy dependency is missing the function raises a `FigDataXError` telling you to run
`bash scripts/setup.sh`; the rest of the library keeps working.

## Tick auto-detection (`detect_ticks`) failure modes

| Result | Meaning | What to do |
|--------|---------|-----------|
| axis is `null` | The chart has no tick marks (spine + gridlines only), or ticks are shorter than 1px / longer than `search_px`. | Fall back to the grid overlay: `overlay` command → Read it → locate tick pixel positions visually. |
| `spacing_cv > 0.15` | Detected positions are unevenly spaced — probably glyph noise or mixed major/minor strokes. | Treat positions as suspect; verify each against the annotated PNG, or fall back to the grid overlay. |
| fewer positions than printed labels | Edge ticks may coincide with the plot corners, or a label exists without a tick mark. | Pair only the ticks you can match confidently; 3+ per axis is enough. |
| more positions than printed labels | Unlabeled minor ticks survived (same length as majors). | Keep only positions whose spacing matches the labeled ticks; drop the rest. |

`detect_ticks` is best-effort by contract: precise where real tick marks exist
(±1px on rendered charts), and silent (`null`) where they do not — it never guesses.
The grid overlay is always the fallback path.
