# Changelog

Versioning is independent per product: the **skill** (`skill-vX.Y.Z`) and the
**desktop app** (`app-vX.Y.Z`).

## Skill

### skill-v1.0.0 — 2026-07-06

First hardened, tested release. The engine now runs on modern OpenCV and degrades
gracefully when optional dependencies are absent.

**Fixed**
- OpenCV ≥5 / 4.13 crash: `HoughLinesP` now handled for both `(N,4)` and `(N,1,4)`
  output shapes (`auto_detect_plot_area`, `remove_grid`, `detect_axes_hough`).
- Module now imports with only cv2+numpy; matplotlib and scipy are imported lazily
  (validation plot / curve tracing) so ~16 functions work without them.
- `calibrate_axes_multipoint` raises `CalibrationError` on log-of-≤0 and reciprocal-of-0
  instead of silently producing `nan`/`inf`.
- Pixel→data conversion no longer rounds to 4 decimals — small-magnitude and log-axis
  values keep full precision.
- Every image-taking function normalizes grayscale / RGBA / 16-bit input (previously
  crashed `cvtColor(BGR2HSV)`); bad paths raise `InputError` instead of returning `None`.
- `extract_by_color_adaptive` warns (naming the nearest dominant color) on 0 detections
  and supports `auto_widen`.
- `extract_error_bars` scan is gap-tolerant and returns data-unit `{y_low, y_high}` with
  `y_high ≥ y_low`.
- `detect_data_colors` no longer discards bright saturated colors (V=255) and is
  deterministic (seeded); dead `bg_threshold` parameter removed.
- `auto_extract_bars` accepts an `AxisCalibration`; stacked-segment math corrected.
- `trace_curve` handles duplicate columns and short sequences; scipy imports are lazy.
- Crossover assignment uses trajectory (velocity) prediction so crossing curves pass
  through instead of bouncing apart; Hungarian algorithm when scipy is present.

**Added**
- `AxisCalibration` class: forward + inverse transform, RMSE (absolute and % of span),
  and JSON serialization (`to_dict`/`from_dict`).
- `pick_color`, `hsv_of_bgr`, `bgr_of_hsv` color helpers.
- `extract_boxplot`, `extract_pie`, `extract_heatmap` — closing the box/pie/heatmap
  chart types the description advertised.
- Subcommand CLI (`extract`, `calibrate`, `overlay`, `panels`, `colors`, `self-test`)
  with a `--calibration-points` JSON file for multi-point calibration.
- `scripts/setup.sh` skill-local venv bootstrap (uv, pip fallback).
- pytest suite with synthetic ground-truth charts and one regression test per fixed bug;
  `examples/` fixtures.
- Package split (`scripts/figdatax/{core,calibrate,extract,morph,charts,validate,cli}.py`),
  import path `from scripts.figdatax import ...` preserved.

**Changed**
- `requirements.txt` version floors raised to tested versions; `scikit-image` removed
  (never imported).
- SKILL.md rewritten with progressive disclosure (core workflow + `references/`), a
  mandatory pre-flight section, and an OpenCV-traps section.

## App

_No releases yet. The `app/` desktop GUI (PySide6) is under development; see
[app/README.md](app/README.md)._
