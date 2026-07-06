# FigDataX Desktop

A macOS GUI (PySide6) over the [FigDataX](../README.md) extraction engine — digitize
charts interactively, and (in upcoming phases) load PDFs to detect data-bearing figures
and tables, extract them, export to Excel, and surface important data mentions with their
location in the document.

> **Status: `0.2.0` — feature-complete.** Interactive digitizing (open image → calibrate →
> pick color → extract → export Excel) with **project save/load** (`.fdx`) and **manual
> point editing**; the **PDF pipeline** (figure/table detection, data-mention scanner with
> jump-to-page, multi-sheet workbook export); **box/pie/heatmap** extraction; and an
> optional **AI-assist layer** (subscription CLIs or OpenAI-compatible APIs). Unsigned
> `.dmg` packaging and GitHub Actions CI are in place. See
> [../CHANGELOG.md](../CHANGELOG.md).

## Run from source

```bash
bash app/run_dev.sh          # creates app/.venv, installs deps, launches the GUI
bash app/run_dev.sh --smoke  # headless end-to-end self-check (no window)
```

The app imports the extraction engine directly from this repo (`scripts/figdatax`), so
there is a single source of truth — no vendored copy.

## Using the digitizer

1. **打开图片 / Open Image** — load a chart (PNG/JPG/TIFF).
2. **校准X / 校准Y** — click two or more ticks on each axis; enter the data value for each.
3. **取色 / Eyedropper** — click a data marker to set the target color (don't guess HSV).
4. **提取 / Extract** — detected points appear on the canvas and in the results table.
5. **加点 / 编辑点** — add points by clicking, or drag/select/Delete to correct them; the
   table stays in sync and data coordinates recompute live.
6. **导出 Excel** — write a workbook (summary sheet + one sheet per series).

Save the whole session (image, calibration, points, color) as a **`.fdx` project**
(`Ctrl+S`) and reopen it later — the source image is embedded, so projects are portable.
The status bar shows a live **pixel → data** readout once calibration is set.

## Working with a PDF

1. **打开 PDF / Open PDF** — the Document tab renders pages and analyzes the file in the
   background.
2. **图形 / Figures** — double-click a detected figure to send its native-resolution crop
   to the digitizer, then calibrate and extract as above.
3. **表格 / Tables** — preview tables pdfplumber found on any page.
4. **数据线索 / Data mentions** — every flagged number (mean±SD, `n=`, `p<`, %, ranges,
   correlations, CI, Table/Figure refs) with its sentence; click to jump to its page.
5. **导出整篇文档 / Export Document** (`Ctrl+Shift+E`) — one workbook with the digitized
   figure(s), every extracted table, and the full data-mentions list.

## Box / pie / heatmap (Charts menu)

For non-XY charts, use **图表 / Charts**:

- **箱线图 / Box plot** — calibrate the Y axis, pick the box fill color, get a
  five-number summary (whiskers, Q1, median, Q3) per box.
- **饼图 / Pie chart** — wedge fractions and percentages by angular color segmentation
  (auto-detects the disc, or give center/radius).
- **热图 / Heatmap** — a numeric matrix via colorbar calibration (give grid shape,
  colorbar box, and its value range).

Each result opens in a table you can export to Excel.

## AI assist (optional)

**AI → AI 设置 / Settings** to choose a provider — everything is optional and the app is
fully usable without it:

- **Claude 订阅 CLI** — your Claude Max/Pro subscription via the local `claude` CLI.
- **ChatGPT 订阅 CLI** — ChatGPT Plus via the local `codex` CLI.
- **OpenAI 兼容 API** — any `/chat/completions` endpoint (DeepSeek, Qwen, Ollama, …);
  the key is stored in the macOS Keychain.

Then:

- **AI 分析图形 / Analyze figure** reads the chart type and axis ticks and proposes
  calibration points — **you confirm each value** in a review dialog before it is applied.
- **AI 汇总数据线索 / Summarize data mentions** turns the flagged PDF numbers into a
  concise, page-cited summary.

AI output is always suggestive; the extraction engine itself stays fully deterministic.
See [AI_INTEGRATION.md](AI_INTEGRATION.md).

## Build a distributable app (unsigned)

```bash
bash app/build.sh
# → app/dist/FigDataX.app, FigDataX-<ver>.dmg, FigDataX-<ver>.app.zip
```

The bundle is **unsigned** (no Apple Developer account). To open it the first time:

- **Right-click the app → Open → Open**, or
- Clear the quarantine flag:
  ```bash
  xattr -dr com.apple.quarantine /Applications/FigDataX.app
  ```

A later release can add ad-hoc signing (`codesign --deep --sign -`, hook already in
`build.sh`) and full notarization once a Developer ID is available.

## Roadmap

- **Phase 1 (MVP)**: image digitize + Excel export + project save/load. _(this skeleton
  covers the digitize + export half)_
- **Phase 2 (Document intelligence)**: PDF figure/table detection (pypdfium2 + pdfplumber),
  data-mention scanner with jump-to-location highlighting, box/pie/heatmap panels, and the
  **AI-assist layer** — Claude Max / ChatGPT-Plus subscriptions via local CLIs, or any
  OpenAI-compatible API (DeepSeek, …) for AI-assisted calibration and figure classification;
  design in [AI_INTEGRATION.md](AI_INTEGRATION.md).
- **Phase 3 (Distribution)**: `.dmg` via GitHub Actions, batch export, docx ingestion.
