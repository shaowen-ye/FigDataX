# FigDataX CLI reference

Run with the skill venv interpreter:

```bash
PY="$HOME/.claude/skills/FigDataX/.venv/bin/python"
$PY -m scripts.figdatax <subcommand> ...
```

## `geometry` — the engine geometry pass (start here)

```bash
$PY -m scripts.figdatax geometry IMAGE [--bbox L T R B] [--json OUT.json] [--annotate OUT.png]
```

One call: auto-detects the plot bbox, tick pixel positions per axis (`detect_ticks` —
sub-pixel, with a `spacing_cv` confidence; `null` when the chart has no tick marks),
and ready-to-use series HSV targets tagged markers/line/region (`suggest_series`).
Prints the JSON and writes an annotated PNG to eyeball before calibrating.
`spacing_cv > 0.15` prints a warning — treat those positions as suspect.

## `extract` — extract data points

```bash
$PY -m scripts.figdatax extract IMAGE [options]
```

| Option | Meaning |
|--------|---------|
| `--mode {semi,trace}` | `semi` = color-based points (default); `trace` = continuous curve |
| `--calibration-points FILE` | JSON calibration (see below) — preferred, multi-point |
| `--x-range MIN MAX` / `--y-range MIN MAX` | 2-point bbox calibration (fallback) |
| `--x-log` / `--y-log` | log-scale axes |
| `--bbox L T R B` | plot area (auto-detected if omitted) |
| `--color-target H S V` | target color (OpenCV HSV) — required for `semi`/`trace` |
| `--color-distance D` | color match threshold (default 30) |
| `--subpixel` | sub-pixel centroid refinement |
| `--auto-widen` | retry with a wider threshold if nothing is found |
| `--validate` | also write a side-by-side validation PNG |
| `--output PATH` | output CSV (default `<image>_extracted.csv`, next to the image) |

## `calibrate` — fit & report a calibration

```bash
$PY -m scripts.figdatax calibrate CALIB.json
```

Prints slope/intercept and RMSE (absolute and as % of axis span) for each axis.

## `overlay` — coordinate grid for manual reading

```bash
$PY -m scripts.figdatax overlay IMAGE [--bbox L T R B] [--output PATH]
```

## `panels` — split a multi-panel figure

```bash
$PY -m scripts.figdatax panels IMAGE [--layout 2x2|1x3|auto]
```

## `colors` — dominant colors or pick one pixel

```bash
$PY -m scripts.figdatax colors IMAGE --at X Y        # HSV/BGR/hex at a pixel
$PY -m scripts.figdatax colors IMAGE --bbox L T R B  # dominant series colors
```

## `xlsx` — gather figure CSVs into one Excel workbook

```bash
$PY -m scripts.figdatax xlsx SPEC.json
```

```json
{
  "out": "figures.xlsx",
  "source": "Smith et al. 2024",
  "figures": [
    {"name": "Fig3", "csv": "/abs/fig3_extracted.csv",
     "provenance": "Fig.3 | M1 | RMSE x=0.23% y=0.15% | 1 round"}
  ]
}
```

One sheet per figure (headers bold, frozen) + an Index and a Provenance sheet.

## `self-test` — fast synthetic self-check

```bash
$PY -m scripts.figdatax self-test
```

Synthesizes a scatter chart, extracts it, and asserts < 1% error. Use it as a
pre-flight check that the environment is healthy.

## `--calibration-points` JSON format

```json
{
  "x": [[85, 0], [200, 10], [430, 30]],
  "y": [[380, 0], [190, 50], [95, 75]],
  "x_log": false,
  "y_log": false,
  "x_transform": null,
  "y_transform": null
}
```

Each entry is `[pixel_coordinate, data_value]`: `x` uses pixel x-coordinates, `y` uses
pixel y-coordinates. Provide 3+ points per axis for best accuracy.
