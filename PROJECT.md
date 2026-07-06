# FigDataX — project overview

This repository ships **two products** from one codebase:

1. **The FigDataX skill** (repo root) — a Claude Code skill + Python engine for
   high-precision scientific figure data extraction. This is what loads when the folder
   lives at `~/.claude/skills/FigDataX`.
2. **The FigDataX desktop app** (`app/`) — a PySide6 macOS GUI that reuses the same
   engine and adds a PDF full-text pipeline (detect data-bearing figures/tables, extract
   them, export to Excel, and surface important data mentions with their in-document
   location). Under active development.

## Layout

```
FigDataX/
├── SKILL.md                 # skill manifest + core workflow (must stay at root)
├── scripts/
│   ├── figdatax/            # the extraction engine (Python package)
│   └── setup.sh             # skill-local .venv bootstrap (uv)
├── references/              # progressive-disclosure docs loaded on demand
├── examples/                # demo figure + expected output
├── tests/                   # pytest suite (synthetic ground truth)
├── app/                     # desktop GUI (PySide6) — reuses the engine
├── requirements.txt         # engine/skill runtime deps
└── CHANGELOG.md             # per-product changelog (Skill / App sections)
```

The engine lives at `scripts/figdatax/` and is imported as `from scripts.figdatax import ...`
after putting the repo root on `sys.path`. The app imports the very same engine, so there
is a single source of truth.

## Versioning & releases

The skill and the app version independently, distinguished by tag prefix:

- Skill releases: `skill-vX.Y.Z` (source install).
- App releases: `app-vX.Y.Z` (unsigned `.dmg` / `.app.zip`; see [app/README.md](app/README.md)
  for the Gatekeeper "right-click → Open" instructions).

## Getting started

- **Use the skill**: see [SKILL.md](SKILL.md) (run `bash scripts/setup.sh`, then
  `.venv/bin/python -m scripts.figdatax self-test`).
- **Run the app from source**: see [app/README.md](app/README.md).
