# FigDataX

**Fig**ure **Data** e**X**traction — high-precision scientific figure data extraction.

Extract numerical data from paper figures (bar, line, scatter, box, heatmap, pie, polar,
stacked charts) with up to **±0.5% accuracy**, via multi-point axis calibration + color
detection. Ships as both a **Claude Code skill** and a **desktop app** — see
[PROJECT.md](PROJECT.md) for how the two fit together.

中文说明见 [中文说明.md](中文说明.md)。

## Install (skill)

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
```

Claude follows the workflow in [SKILL.md](SKILL.md): view the figure, detect the plot
area, multi-point-calibrate the axes, extract marker centers (sub-pixel), and save the
data + a validation overlay next to the input image.

Or use the CLI directly (see [references/cli.md](references/cli.md)):

```bash
PY="$HOME/.claude/skills/FigDataX/.venv/bin/python"
$PY -m scripts.figdatax extract figure.png \
    --calibration-points calib.json --color-target 0 255 255 --subpixel --validate
```

## Documentation

- [SKILL.md](SKILL.md) — the extraction workflow and API (the single source of truth).
- [references/](references/) — precision & troubleshooting, morphological pipeline,
  special cases, full CLI reference.
- [CHANGELOG.md](CHANGELOG.md) — release notes.
- [app/README.md](app/README.md) — the desktop app (in development).

## License

MIT — see [LICENSE](LICENSE).
