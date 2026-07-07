# FigDataX

**Fig**ure **Data** e**X**traction — high-precision scientific figure data extraction,
as an agentic **Claude Code skill**.

Give Claude a figure image (or several) cropped from a paper; it extracts the numbers
at up to **±0.5% accuracy** and proves it with a validation overlay. The engine measures
the geometry (plot area, tick pixel positions, series colors, sub-pixel centroids);
Claude reads the semantics (tick values, legend) with vision; you are asked only when
something is genuinely ambiguous.

Supported: scatter, line, bar (grouped/stacked), box, pie, heatmap, polar, error bars,
log axes, multi-panel figures. Output: CSV per figure + optional multi-sheet Excel with
provenance (method, calibration RMSE, validation rounds).

中文说明见 [中文说明.md](中文说明.md)。

## Install

```bash
git clone https://github.com/Shaowen-Ye/FigDataX ~/.claude/skills/FigDataX
bash ~/.claude/skills/FigDataX/scripts/setup.sh      # creates .venv, installs deps (uv)
~/.claude/skills/FigDataX/.venv/bin/python -m scripts.figdatax self-test
```

> The folder name is **`FigDataX`** (case-sensitive on Linux).

## Use

In Claude Code, just ask:

```
> 提取 /path/to/figure.png 图片数据
> Extract data from ./results/fig3.png
> 这几张图都提取一下，汇总成一个 Excel
```

Claude runs the autonomous loop in [SKILL.md](SKILL.md): classify the chart → engine
geometry pass (`figdatax geometry`: bbox + tick positions + series colors) → visually
verify the annotated overlay → pair tick values by vision → calibrate (hard RMSE < 1%
gate) → extract sub-pixel centroids → visually check the validation overlay → iterate
up to 3 rounds → deliver CSV/Excel + a provenance report.

### Zero-typing entry points (macOS)

```bash
bash ~/.claude/skills/FigDataX/integrations/macos/install.sh
```

installs two shortcuts so you barely type at all:

- **`/figx` slash command** — in Claude Code, type `/figx` and drag the image(s) into
  the terminal. Full interactivity (Claude can still ask at the two gates).
- **Finder Quick Action** — select images in Finder → right-click → 快捷操作 →
  **FigDataX 提取数据**. Runs headless (`claude -p`, billed to your subscription),
  drops CSV/validation/Excel next to the images, then notifies you. In headless mode
  Claude cannot ask questions: at the gates it proceeds with best judgment and flags
  the uncertainty in the report. Model override: `FIGX_MODEL=claude-opus-4-8`.

Or use the CLI directly (see [references/cli.md](references/cli.md)):

```bash
PY="$HOME/.claude/skills/FigDataX/.venv/bin/python"
$PY -m scripts.figdatax geometry figure.png --json geom.json --annotate geom.png
$PY -m scripts.figdatax extract figure.png \
    --calibration-points calib.json --color-target 0 255 255 --subpixel --validate
```

## Documentation

- [SKILL.md](SKILL.md) — the autonomous extraction loop (the single source of truth).
- [references/](references/) — precision & troubleshooting, morphological pipeline,
  special cases, full CLI reference.
- [CHANGELOG.md](CHANGELOG.md) — release notes.

## History

A desktop app (PySide6) was developed and later discontinued in favor of the pure
skill — Claude Code natively provides what the GUI required manual clicks for. Its
source remains at tag [`app-v0.2.0`](https://github.com/Shaowen-Ye/FigDataX/tree/app-v0.2.0).

## License

MIT — see [LICENSE](LICENSE).
