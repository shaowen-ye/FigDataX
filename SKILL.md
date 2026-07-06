---
name: figdatax
description: "FigDataX: High-precision scientific figure data extraction via axis-calibrated semi-automatic methods. Extracts numerical data from paper figures (bar, line, scatter, box, heatmap, pie, polar, stacked charts) with sub-pixel precision. Core approach: multi-point axis calibration + color-based detection. Also supports fully-automated color segmentation and Hough-line-guided curve tracing. Features: automatic plot area detection, adaptive grid removal, multi-point least-squares axis calibration, sub-pixel Gaussian centroid refinement, contour-based curve tracing, box/pie/heatmap extraction, and validation overlay. Use when the user wants to digitize a chart, extract data from a figure, get numbers from a graph, convert a plot to a data table. Also trigger on: '读取图中数据', '从图中提取数值', '图表数字化', '提取图表数据', 'plot digitizer', 'digitize figure', 'extract figure data', 'figure data extraction'."
---

# FigDataX — High-Precision Scientific Figure Data Extraction

**FigDataX** = **Fig**ure **Data** e**X**traction. Extract numerical data from scientific
figures with up to ±0.5% accuracy, centered on multi-point axis-calibrated extraction.

---

## Environment & pre-flight (MANDATORY — do this first)

FigDataX needs OpenCV, NumPy, pandas, matplotlib, and scipy. Resolve the interpreter in
this exact order before running anything:

```bash
SKILL_DIR="$HOME/.claude/skills/FigDataX"
PY="$SKILL_DIR/.venv/bin/python"

# 1. Prefer the skill-local venv.
if [ -x "$PY" ] && "$PY" -c "import cv2, numpy, pandas" 2>/dev/null; then :; else
    # 2. Bootstrap it (uses uv, falls back to python3 -m venv).
    bash "$SKILL_DIR/scripts/setup.sh"
fi
```

Then confirm the environment is healthy with the built-in self-test:

```bash
"$PY" -m scripts.figdatax self-test    # synthesizes a chart, extracts it, asserts < 1% error
```

If the venv cannot be created, you may fall back to a `python3` that already imports
`cv2, numpy, pandas` — but **explicitly tell the user** which features degrade
(no matplotlib → no validation plot; no scipy → no `trace_curve`/`interpolate_curve`).
Never silently produce lower-quality output.

### Import path

Add the skill root to `sys.path`, then import from the package:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/FigDataX"))
from scripts.figdatax import (calibrate_axes_multipoint, auto_detect_plot_area,
                              pick_color, extract_by_color_adaptive, create_validation_plot)
```

> The folder is **`FigDataX`** (capital F, D, X). On case-sensitive filesystems (Linux)
> the path is case-sensitive — use `FigDataX` exactly.

---

## OpenCV traps (the #1 source of extraction errors)

FigDataX is built on OpenCV. Internalize these or extraction will silently go wrong:

- **Images are BGR**, not RGB. `cv2.imread` returns blue-green-red order.
- **HSV hue is `[0, 179]`** (degrees ÷ 2), *not* 0–360. S and V are `[0, 255]`.
  Pure red ≈ H 0 (or 179); saturated markers have **V ≈ 255** (that is NOT background —
  background is *low saturation*, not high value).
- **Never guess a target HSV.** Call `pick_color(img, x, y)` on an actual marker to read
  its exact HSV. Guessed values are the top cause of "0 detections".
- Pixels are indexed **`img[y, x]`** (row first). Pixel **y increases downward**, so
  data-space y is inverted relative to pixel y (calibration handles this).
- `cv2.imread` returns **`None`** (does not raise) on a bad path. FigDataX's loaders
  raise `InputError` instead, and normalize grayscale / RGBA / 16-bit inputs for you.

---

## File paths & outputs

- **Input**: the user's image path (absolute or relative to their working directory).
- **Output**: saved **in the same directory as the input image**, named after it:
  - `{stem}_extracted.csv` — data table
  - `{stem}_validation.png` — side-by-side original vs. reconstructed
  - `{stem}_grid.png` — coordinate grid overlay (for manual reading)

Use `os.path.dirname(image_path)` for the output directory — never the skill directory.

---

## Extraction methods

| Method | Name | Best for | Typical accuracy |
|--------|------|----------|-----------------|
| **M1** | **Calibrated Semi-Auto** | **All charts — default & preferred** | **±0.5–2%** |
| M2 | Fully Automated | High-contrast charts with distinct colors | ±0.5–1% |
| M3 | Hough + Curve Trace | Line charts, continuous curves | ±0.5–1% |

**Always prefer M1.** It is the most accurate because it relies on human-verified axis
reference points, not AI-guessed values. M2/M3 supplement it for clean, automated cases.

---

## Method 1: Calibrated Semi-Auto (core workflow)

### Step 1 — Load, view, classify

Use the Read tool to view the figure. Identify: chart type; axes labels/units/scale
(linear/log/reciprocal); whether X is **categorical** (skip X calibration, use indices)
or **continuous**; tick values on each axis; data series count, legend, colors; marker
shape/size (its **geometric center** is the data point); grid lines.

### Step 2 — Detect the plot area

```python
from scripts.figdatax import auto_detect_plot_area
bbox = auto_detect_plot_area(image_path)   # (left, top, right, bottom) or None
```

If it returns `None` or looks wrong, determine the bbox from a grid overlay (Step 5) or
ask the user.

### Step 3 — Multi-point axis calibration (the key accuracy step)

Read each axis tick's pixel position and data value, then fit:

```python
from scripts.figdatax import calibrate_axes_multipoint
cal = calibrate_axes_multipoint(
    pixel_points_x=[85, 200, 315, 430], data_values_x=[0, 10, 20, 30],
    pixel_points_y=[380, 285, 190, 95], data_values_y=[0, 25, 50, 75],
    x_log=False, y_log=False)             # x_transform="reciprocal" for 1/x axes
print(f"RMSE x={cal.x_rmse_pct:.2f}%  y={cal.y_rmse_pct:.2f}%")   # want < ~1%
dx, dy = cal.pixel_to_data(px, py)        # forward
px, py = cal.data_to_pixel(dx, dy)        # inverse (for overlays / re-projection)
```

Use **3+ ticks per axis**. Log axes require positive tick values (else `CalibrationError`).

### Step 4 — Grid removal (only if grids interfere)

```python
from scripts.figdatax import remove_grid
clean = remove_grid(image_path, method="adaptive")   # or "hough" / "color"
```

### Step 5 — Extract data points

**Get the target color reliably**, then detect:

```python
from scripts.figdatax import pick_color, extract_by_color_adaptive
target = pick_color(image_path, marker_x, marker_y)["hsv"]     # don't guess HSV
det = extract_by_color_adaptive(clean, target, color_distance=25,
                                subpixel=True, auto_widen=True)
# → [(cx, cy, area, confidence), ...]  (cx, cy = marker CENTER)
```

If markers are large, many series share a color, or you want a manual read, generate a
grid overlay and read marker centers by eye:

```python
from scripts.figdatax import generate_grid_overlay
generate_grid_overlay(image_path, f"{stem}_grid.png", plot_bbox=bbox)
```

For **same-color multi-series** charts, use the morphological pipeline instead — see
[references/morphological-pipeline.md](references/morphological-pipeline.md).

### Step 6 — Convert & save

```python
import pandas as pd
rows = [(*cal.pixel_to_data(cx, cy), conf) for cx, cy, _, conf in det]
df = pd.DataFrame(rows, columns=["x", "y", "confidence"])
df.to_csv(f"{stem}_extracted.csv", index=False, encoding="utf-8-sig")
```

### Step 7 — Validate (always)

```python
from scripts.figdatax import create_validation_plot
create_validation_plot(image_path, [(r.x, r.y) for r in df.itertuples()],
                       f"{stem}_validation.png")
```

---

## Method 2: Fully Automated

For clean, high-contrast charts. See [references/special-cases.md](references/special-cases.md)
for bar / scatter details.

```python
from scripts.figdatax import detect_data_colors, auto_extract_bars, auto_extract_scatter
colors = dict(detect_data_colors(img, bbox, n_clusters=4))    # {name: (H,S,V)}
bars = auto_extract_bars(img, bbox, converter=cal, colors_hsv=colors)
pts = auto_extract_scatter(img, bbox, target_hsv=target, converter=cal)
```

## Method 3: Hough + Curve Trace (line charts, needs scipy)

```python
from scripts.figdatax import trace_curve
curve = trace_curve(img, bbox, target_hsv=target, converter=cal, n_samples=200, subpixel=True)
```

---

## Other chart types

`extract_boxplot`, `extract_pie`, `extract_heatmap`, `extract_polar`, `extract_error_bars`,
`split_panels`, `interpolate_curve` — usage in
[references/special-cases.md](references/special-cases.md).

## Command-line interface

Everything above is also available via subcommands (`extract`, `calibrate`, `overlay`,
`panels`, `colors`, `self-test`) — see [references/cli.md](references/cli.md).

---

## Efficiency guidelines

**Do the extraction in ONE consolidated script**: read the image once, classify, then
calibrate + detect + extract + validate in a single run. Avoid iterative pixel scanning.

| Situation | Shortcut |
|-----------|----------|
| Categorical X (time labels, group names) | Use category indices; calibrate only Y |
| Clean tick labels visible | Read tick values directly; multi-point calibrate |
| No grid lines | Skip grid removal |
| Well-separated colored series | Automated color detection |
| All same-color markers | Morphological pipeline (reference) |

---

## Output report format

```
=== FigDataX Extraction Report ===
Source: Figure 2a from Smith et al. (2024)
Chart type: Grouped bar chart    |    Method: M1 Calibrated Semi-Auto
Calibration RMSE: x=0.23%, y=0.15%    |    Points: 12    |    Est. accuracy: ±0.8%
Saved: /path/to/figure2a_extracted.csv    |    Validation: /path/to/figure2a_validation.png
```

Always state the method and calibration RMSE.

---

## References (load on demand)

- [references/precision-and-troubleshooting.md](references/precision-and-troubleshooting.md)
  — precision checklist, "0 detections" diagnosis, `color_distance` tuning, dependency tiers.
- [references/morphological-pipeline.md](references/morphological-pipeline.md)
  — same-color multi-series detection and crossover handling.
- [references/special-cases.md](references/special-cases.md)
  — log/reciprocal, error bars, grouped/stacked bars, box/pie/heatmap, polar, panels, dual-Y.
- [references/cli.md](references/cli.md) — full command-line reference.
