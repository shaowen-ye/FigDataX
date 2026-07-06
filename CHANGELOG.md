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

### app-v0.2.0 — 2026-07-06

Completes the roadmap: the AI-assist layer, box/pie/heatmap extraction, and CI/packaging.

**Added**
- **AI-assist layer** (`figdatax_app/ai/`): pluggable providers — Claude Max/Pro via the
  `claude` CLI, ChatGPT Plus via the `codex` CLI, and any OpenAI-compatible API
  (DeepSeek, Qwen, Ollama, …). API keys are stored in the macOS Keychain.
  - **Analyze figure**: a vision model proposes chart type, axis-tick values, and series
    colors; the user confirms each tick in a review dialog before it becomes a calibration
    point. AI never sets a value unconfirmed; the engine stays deterministic.
  - **Summarize data mentions**: turns the flagged PDF numbers into a page-cited summary.
  - AI Settings dialog (provider/model/key + connection test); CLI calls run off the UI
    thread.
- **Box / pie / heatmap extraction** (Charts menu): five-number box summaries, pie wedge
  fractions, and colorbar-calibrated heatmap matrices, each viewable and Excel-exportable.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): macOS runner runs the skill pytest
  suite and the app smoke test on every push/PR; tagged `app-v*` builds attach the
  unsigned `.dmg`/`.app.zip` to the release.

**Fixed**
- py2app bundling of the engine package (`scripts/figdatax`) — repo root added to the
  build path so `No module named scripts` no longer aborts the build. Build venv pinned
  to Python 3.12.

### app-v0.1.0 — 2026-07-06

First functional release of **FigDataX Desktop** (PySide6), covering the Phase 1 MVP and
the Phase 2 document-intelligence pipeline. Runs from source (`bash app/run_dev.sh`);
`.dmg` packaging and the AI-assist layer are the next phases.

**Phase 1 — interactive digitizer + project management**
- QGraphicsView canvas (scene units = image pixels): zoom/pan, click-to-calibrate with
  value entry, eyedropper via the engine's `pick_color`, color extraction overlay, and a
  live pixel→data readout.
- Manual point editing: Add-point and Edit modes — click to add, drag markers (model and
  data coordinates update live), rubber-band select, Delete key / table button to remove;
  the results table stays in sync both ways.
- `.fdx` project files: versioned JSON with an embedded PNG copy of the source image, so
  projects reopen even if the original moved. New/Open/Save/Save As, recent projects
  (QSettings), dirty tracking with an unsaved-changes prompt.
- Excel export: summary sheet + one sheet per series.

**Phase 2 — PDF document intelligence**
- PDF loading and rendering via pypdfium2 (Apache/BSD — deliberately not AGPL PyMuPDF).
- Embedded-figure detection with a PDF→page-pixel coordinate flip; send any figure's
  native-resolution crop straight to the digitizer.
- Table extraction (pdfplumber) with in-app preview.
- Data-mention scanner: flags mean±SD, `n=`, p-values, correlations, %, ranges, CI,
  units, and Table/Figure references, each with its page and sentence; click to jump to
  the page. Sentence splitting preserves decimals so numbers aren't severed.
- Multi-sheet workbook export (`Export Document`): digitized figures + all tables + the
  data-mentions list.
- Headless smoke test (`run_dev.sh --smoke`) covers extraction accuracy, point-edit sync,
  `.fdx` round-trip, and the full PDF pipeline against a committed synthetic-paper fixture.

**Design (not yet implemented)**
- AI-assist layer — Claude Max (`claude` CLI), ChatGPT Plus (`codex` CLI), and
  OpenAI-compatible APIs (DeepSeek, …) for AI-assisted calibration and figure
  classification; see [app/AI_INTEGRATION.md](app/AI_INTEGRATION.md).
