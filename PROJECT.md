# FigDataX — project overview

One product: a **Claude Code skill** (plus its Python engine) for high-precision
scientific figure data extraction. It loads when the folder lives at
`~/.claude/skills/FigDataX`.

The scope is deliberately narrow: the user provides figure images (cropped or
screenshotted from papers — single or multiple); the skill extracts the numbers,
verifies them visually, and delivers CSV/Excel with provenance. No PDF ingestion, no
table extraction, no text mining — those were tried and removed to keep the tool sharp.

## Layout

```
FigDataX/
├── SKILL.md                 # skill manifest + the autonomous extraction loop (root)
├── scripts/
│   ├── figdatax/            # the extraction engine (Python package)
│   └── setup.sh             # skill-local .venv bootstrap (uv)
├── references/              # progressive-disclosure docs loaded on demand
├── examples/                # demo figure + expected output
├── tests/                   # pytest suite (synthetic ground truth)
├── requirements.txt         # runtime deps
└── CHANGELOG.md             # release notes
```

The engine is imported as `from scripts.figdatax import ...` after putting the repo
root on `sys.path`.

## Versioning & releases

Skill releases are tagged `skill-vX.Y.Z` (source install; see README for setup).

## History

- A desktop app (PySide6; interactive digitizer, PDF pipeline, AI-assist layer) lived
  in `app/` through `app-v0.2.0`, then was discontinued: Claude Code natively covers
  what the GUI needed manual clicks for. Recover it with
  `git checkout app-v0.2.0 -- app/`.
- PDF ingestion / table extraction / data-mention mining existed briefly in the engine
  and were removed in the same spirit — the user crops figures themselves.

## Getting started

See [SKILL.md](SKILL.md): run `bash scripts/setup.sh`, then
`.venv/bin/python -m scripts.figdatax self-test`.
