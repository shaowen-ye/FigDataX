---
name: figdatax
description: "FigDataX: High-precision scientific figure data extraction. Give it a figure image (or several) cropped/screenshotted from a paper and it runs an autonomous loop: engine detects the geometry (plot area, tick positions, series colors), Claude reads the semantics (tick values, legend) by vision, least-squares calibration with RMSE gating, sub-pixel color/morphology extraction, then Claude visually verifies a validation overlay and iterates. Supports scatter, line, bar (grouped/stacked), box, pie, heatmap, polar, error bars, log axes, multi-panel figures. Outputs CSV per figure + optional multi-sheet Excel + provenance. Use when the user wants to digitize a chart, extract data from a figure, get numbers from a graph, convert plots to data tables, batch-extract several figures. Also trigger on: '读取图中数据', '从图中提取数值', '图表数字化', '提取图表数据', '提取论文图数据', '批量提取图表', 'plot digitizer', 'digitize figure', 'extract figure data', 'figure data extraction'."
---

# FigDataX — High-Precision Scientific Figure Data Extraction

**FigDataX** = **Fig**ure **Data** e**X**traction. Input: figure image(s) the user
provides (cropped, screenshotted, or pasted from a paper). Output: the numbers, at up
to ±0.5% accuracy, with a validation overlay proving it.

**Division of labor** — the engine measures *geometry* (plot area, tick pixel
positions, series colors, sub-pixel centroids); **you (Claude) read *semantics***
(tick values, axis labels, legend names) with your own vision; the **user** is asked
only at the two gates below. Run the loop autonomously; do not narrate each step.

---

## Environment & pre-flight (MANDATORY — do this first)

```bash
SKILL_DIR="$HOME/.claude/skills/FigDataX"
PY="$SKILL_DIR/.venv/bin/python"
[ -x "$PY" ] && "$PY" -c "import cv2, numpy, pandas" 2>/dev/null || bash "$SKILL_DIR/scripts/setup.sh"
"$PY" -m scripts.figdatax self-test      # asserts <1% extraction error + tick detection
```

If the venv cannot be created, a `python3` that imports `cv2, numpy, pandas` may be
used — but **tell the user** what degrades (no matplotlib → no validation plot; no
scipy → no curve tracing). Never silently produce lower-quality output.

### Import path

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/FigDataX"))
from scripts.figdatax import (detect_ticks, suggest_series, auto_detect_plot_area,
                              calibrate_axes_multipoint, pick_color,
                              extract_by_color_adaptive, create_validation_plot)
```

> The folder is **`FigDataX`** (capital F, D, X) — case-sensitive on Linux.

---

## OpenCV traps (the #1 source of extraction errors)

- **Images are BGR**, not RGB. **HSV hue is `[0, 179]`**, not 0–360; S/V are `[0, 255]`.
  Saturated markers have V≈255 — that is data, not background (background = low S).
- **Never guess a target HSV** — use `suggest_series` or `pick_color` on a marker.
- Pixels index as `img[y, x]`; **pixel y grows downward**, so the TOP tick has the
  SMALLEST py and the LARGEST data value. Calibration handles it — pairing must too.
- `cv2.imread` returns `None` on bad paths; FigDataX loaders raise `InputError` and
  normalize grayscale/RGBA/16-bit inputs.

---

## THE AUTONOMOUS LOOP (single figure)

Run these steps end-to-end without asking the user, except at the gates.

### 0 · CLASSIFY — Read the image

View the figure with the Read tool. Note: chart type; axis scale (linear/log/
categorical); tick values printed on each axis; series count + legend + colors;
marker shape (its **geometric center** is the data point); grid lines; panels
(if multi-panel → `split_panels`, loop each panel).

### 1 · GEOMETRY — one engine call

```bash
"$PY" -m scripts.figdatax geometry FIG.png --json geom.json --annotate geom.png
```

Returns plot bbox + `ticks.{x,y}.positions` (sub-pixel px, **sorted ascending**) +
`series` (ready-to-use HSV targets tagged markers/line/region). Add `--bbox L T R B`
if auto-detection failed.

### 2 · VERIFY GEOMETRY — Read `geom.png` yourself

Checklist: green bbox hugs the plot frame (not the labels)? magenta tick strokes sit
on real tick marks? series swatches match what you saw in step 0? If the bbox is off:
fix with `--bbox` and rerun once. If ticks are `null` (chart has no tick marks) or
`spacing_cv > 0.15` (unreliable): **fall back to the grid overlay** —
`"$PY" -m scripts.figdatax overlay FIG.png`, Read it, and locate tick pixel positions
visually instead.

### 3 · SEMANTICS — you read the values, the engine gave the pixels

Pair tick *values* (read in step 0) with tick *positions* (step 1), in order:

- **x-axis**: ascending px ↔ ascending printed values (left → right).
- **y-axis**: ascending py ↔ **DESCENDING** printed values (top tick = largest value).
  This is the #1 pairing bug — check it twice.
- Count mismatch (e.g. 7 positions, 6 readable labels)? Re-Read a zoomed crop of the
  axis; engine may have caught an unlabeled edge tick — drop the unlabeled ones.
  Still unreadable → **GATE 1**.
- Categorical x-axis: skip x calibration entirely; use category indices.

### 4 · CALIBRATE — hard RMSE gate

```python
cal = calibrate_axes_multipoint(pixel_points_x=[...], data_values_x=[...],
                                pixel_points_y=[...], data_values_y=[...],
                                x_log=False, y_log=False)   # log axes: set the flag!
assert cal.x_rmse_pct < 1.0 and cal.y_rmse_pct < 1.0, "mispaired ticks — re-pair, do NOT proceed"
```

RMSE ≥ 1% almost always means a mispaired or misread tick (or a missed log flag).
Fix the pairing; never extract on a bad calibration.

### 5 · EXTRACT — per series

For each series from `geom.json` (or after **GATE 2** if the legend↔color mapping is
ambiguous):

```python
det = extract_by_color_adaptive(FIG, tuple(s["hsv"]), color_distance=25,
                                subpixel=True, auto_widen=True)
rows = [(*cal.pixel_to_data(cx, cy), conf) for cx, cy, _a, conf in det]
```

- `geometry == "line"` → `trace_curve(FIG, bbox, target_hsv=..., converter=cal)`.
- Same-color multi-series → morphological pipeline
  ([references/morphological-pipeline.md](references/morphological-pipeline.md)).
- Box/pie/heatmap/polar/error bars → [references/special-cases.md](references/special-cases.md).

### 6 · VALIDATE — Read the overlay yourself (always)

```python
create_validation_plot(FIG, points, f"{stem}_validation.png")
```

Read the PNG and check: reconstructed shape matches the original? y-range matches the
tick values you read? point count plausible (vs. what you counted in step 0)? any
systematic offset (all points shifted one direction)?

### 7 · ITERATE — max 3 rounds, then gate

| Symptom on the overlay | Correction |
|---|---|
| Many points missing | raise `color_distance` (40→60→80) or check `auto_widen` warning for the suggested color |
| Extra junk points | lower `color_distance`; exclude legend region; `remove_grid` first |
| Two series merged | lower `color_distance`; or morphological pipeline |
| Systematic offset | bbox included axis labels — re-run geometry with tighter `--bbox` |
| y-values mirrored | you paired y ascending — flip to descending (step 3) |
| Off by 10×/2× on one axis | misread tick value or missed log flag — redo steps 3–4 |

After 3 failed rounds: show the user the overlay, state what is wrong, ask how to
proceed (this is the only other time you may ask).

### 8 · DELIVER

- `{stem}_extracted.csv` per figure (columns: series, x, y, confidence),
  `{stem}_validation.png` — saved **next to the input image**, never in the skill dir.
- Report (always include method + RMSE):

```
=== FigDataX Extraction Report ===
Source: Figure 3, Smith et al. 2024 (user-provided crop)
Chart: scatter, 2 series | Method: M1 auto-calibrated | Rounds: 1
Calibration RMSE: x=0.23%, y=0.15% | Points: 24 | Est. accuracy: ±0.8%
Saved: fig3_extracted.csv | Validation: fig3_validation.png
```

---

## HUMAN GATES — the only questions you may ask mid-loop

- **GATE 1 (unreadable semantics)**: tick values/units still illegible after a zoomed
  re-read → show the crop, ask for the values (AskUserQuestion).
- **GATE 2 (series identity)**: legend↔color mapping ambiguous (no legend, N legend
  entries ≠ N detected colors, colorblind-unsafe palette) → show the swatches, ask
  which series is which.

Everything else: decide yourself and proceed silently.

---

## BATCH — multiple figures

The user may provide several images at once ("这几张图都提取一下").

1. **1–2 figures**: run the loop sequentially.
2. **3+ figures**: fan out **one general-purpose subagent per figure**, each with a
   self-contained prompt: the image path, this loop (steps 0–8), and the report format.
   Collect their CSVs; batch GATE questions together at the end rather than one-by-one.
3. **Gather into Excel** (default deliverable for batches, on request for singles):

```bash
"$PY" -m scripts.figdatax xlsx spec.json
# spec.json: {"out": "figures.xlsx", "source": "Smith et al. 2024",
#   "figures": [{"name": "Fig3", "csv": ".../fig3_extracted.csv",
#                "provenance": "Fig.3 | M1 | RMSE x=0.23% y=0.15% | 1 round"}, ...]}
```

One sheet per figure + a provenance sheet (method/RMSE/rounds per figure).

---

## Efficiency rules

- **One consolidated script per figure** — classify once, then geometry + calibrate +
  extract + validate in a single run. No iterative pixel scanning.
- Do not re-Read the image between every step; Read it at step 0, the annotated
  geometry at step 2, and the validation overlay at step 6. That is 3 image reads
  per clean extraction.
- Categorical x-axis → calibrate only y. No grid lines → skip `remove_grid`.

---

## References (load on demand)

- [references/precision-and-troubleshooting.md](references/precision-and-troubleshooting.md)
  — precision checklist, "0 detections" diagnosis, `color_distance` tuning, tick-detection
  failure modes, dependency tiers.
- [references/morphological-pipeline.md](references/morphological-pipeline.md)
  — same-color multi-series detection and crossover handling.
- [references/special-cases.md](references/special-cases.md)
  — log/reciprocal axes, error bars, grouped/stacked bars, box/pie/heatmap, polar,
  multi-panel, dual-Y.
- [references/cli.md](references/cli.md) — full command-line reference
  (`geometry`, `extract`, `calibrate`, `overlay`, `panels`, `colors`, `xlsx`, `self-test`).
