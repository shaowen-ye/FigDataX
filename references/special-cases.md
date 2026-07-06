# Special Cases

All snippets assume `from scripts.figdatax import ...` with the skill root on
`sys.path`, and a fitted `cal = calibrate_axes_multipoint(...)`.

## Log-scale axes (semi-log, log-log)

```python
cal = calibrate_axes_multipoint(px_x, val_x, px_y, val_y, x_log=True, y_log=True)
```

Tick **values** must be strictly positive on a log axis; FigDataX raises
`CalibrationError` otherwise (rather than silently producing `nan`).

## Reciprocal axes (e.g. wavenumber)

```python
cal = calibrate_axes_multipoint(px_x, val_x, px_y, val_y, x_transform="reciprocal")
```

## Error bars / confidence intervals

```python
from scripts.figdatax import extract_error_bars
bars = extract_error_bars(img, centroids=[(cx, cy), ...], converter=cal,
                          error_color_hsv=(0, 0, 0), search_radius=20)
# → [{"x", "y", "y_low", "y_high"}, ...] in data units, y_high >= y_low
```

The scan skips the marker body (`marker_clearance`) and is gap-tolerant, so a marker
wider than the clearance does not truncate the whisker.

## Grouped / stacked bar charts

```python
from scripts.figdatax import auto_extract_bars
res = auto_extract_bars(img, plot_bbox, converter=cal,
                        colors_hsv={"Treatment": (120, 200, 200), "Control": (0, 200, 200)})
# stacked: pass stacked=True → each series is a list of segment dicts with "value"
```

## Box plots

```python
from scripts.figdatax import extract_boxplot, pick_color
fill = pick_color(img, box_center_x, box_center_y)["hsv"]
boxes = extract_boxplot(img, plot_bbox, cal, box_color_hsv=fill)
# → [{"x_center", "q1", "q3", "median", "whisker_low", "whisker_high"}, ...]
```

Works best on filled (patch_artist) boxes. For unfilled boxes, pass the outline color
and consider `median_color_hsv` if the median line is a distinct color.

## Pie charts

```python
from scripts.figdatax import extract_pie
wedges = extract_pie(img)            # auto-locates the disc, or pass center=(cx, cy), radius=r
# → [{"color_hsv", "hex", "start_deg", "end_deg", "fraction"}, ...] (fractions sum to ~1)
```

Angle convention: 0° = +x (east), counter-clockwise.

## Heatmaps

```python
from scripts.figdatax import extract_heatmap
matrix = extract_heatmap(img, plot_bbox, grid_shape=(n_rows, n_cols),
                         colorbar_bbox=(cl, ct, cr, cb),   # supply the colorbar strip
                         colorbar_range=(vmin, vmax),
                         colorbar_orientation="vertical")
# → float ndarray of shape grid_shape (values via nearest color in CIELab space)
```

The colorbar bounding box is **user-supplied** (not auto-detected). Accuracy depends on
the colormap being reasonably monotone (viridis, magma, etc.).

## Polar plots

```python
from scripts.figdatax import extract_polar
data = extract_polar(img, center=(cx, cy), r_range=(r_min, r_max, r_max_px),
                     target_hsv=(120, 200, 200))
# → [(r_data, theta_deg), ...]
```

## Multiple panels (a, b, c, d)

```python
from scripts.figdatax import split_panels
panels = split_panels(img, layout="2x2")   # or "1x3", "2x1", "auto"
# process each panel independently
```

## Dual Y-axis charts

Calibrate each axis separately and extract each series against its own calibration:
fit the left-axis calibration from the left ticks, extract the left-axis-colored
series; repeat with the right axis and its series.

## Violin plots

No dedicated extractor. Read the key quantiles (median, quartiles, extents) manually
from a grid overlay (`generate_grid_overlay`) and convert with the calibration — treat
it like a hand-read box plot.
