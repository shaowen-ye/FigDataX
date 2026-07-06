# FigDataX Desktop

A macOS GUI (PySide6) over the [FigDataX](../README.md) extraction engine — digitize
charts interactively, and (in upcoming phases) load PDFs to detect data-bearing figures
and tables, extract them, export to Excel, and surface important data mentions with their
location in the document.

> **Status: `0.1.0-alpha` skeleton.** The interactive digitize path (open image →
> calibrate axes → pick color → extract → export Excel) works end-to-end. The PDF
> pipeline, table extraction, and data-mentions panel are stubbed and land in the next
> phases (see [../CHANGELOG.md](../CHANGELOG.md) and [../PROJECT.md](../PROJECT.md)).

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
5. **导出 Excel** — write a workbook (summary sheet + one sheet per series).

The status bar shows a live **pixel → data** readout once calibration is set.

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
