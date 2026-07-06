# AI model integration — design blueprint (App Phase 2)

FigDataX Desktop will offer an optional AI-assist layer that can run on the user's
existing subscriptions (no extra API cost) or on any configurable API endpoint.

## Providers

| Provider | Mechanism | Cost | Vision |
|----------|-----------|------|--------|
| **Claude (Max/Pro subscription)** | Shell out to the locally-installed `claude` CLI in headless mode (`claude -p`, JSON output). Uses the login's subscription quota. | subscription | ✅ images |
| **Codex / ChatGPT (Plus subscription)** | Shell out to the `codex` CLI (`codex exec`). Uses ChatGPT-plan quota. | subscription | model-dependent |
| **OpenAI-compatible API** | Direct HTTPS to a configurable `base_url` + `api_key` + `model` — covers DeepSeek, Qwen, GLM, Moonshot, local Ollama, etc. | per-token | model-dependent |

Architecture: `app/figdatax_app/ai/` with a small provider interface

```python
class AIProvider(Protocol):
    def complete(self, prompt: str, images: list[Path] | None = None,
                 system: str | None = None, timeout: float = 120) -> str: ...
```

implemented by `ClaudeCliProvider`, `CodexCliProvider`, `OpenAICompatProvider`.
Provider + model are chosen in a Settings panel; API keys are stored in the macOS
Keychain (never in the project file). CLI providers detect availability by probing the
executable and logged-in state, and degrade with a clear message if absent.

## What the AI layer is used for

1. **AI-assisted axis calibration** (replaces the earlier OCR plan, strictly better):
   send the cropped axis region to a vision model → get tick pixel/value pairs as
   candidates → user confirms in the calibration table. Human verification is kept —
   the M1 accuracy doctrine is unchanged.
2. **Chart-type classification** of detected PDF figures (scatter/bar/box/photo/…),
   improving the "digitizable figures" suggestions.
3. **Data-mention summarization**: turn the regex-flagged passages into a concise,
   sourced list ("Table 3, p.7: mean CPUE 4.2±0.8 …").
4. **Table cleanup**: normalize headers/units of extracted PDF tables before Excel export.

## Boundaries

- AI output is always **suggestive**: numeric values enter the dataset only after user
  confirmation (or are clearly flagged as AI-derived in the provenance column).
- The extraction engine itself stays fully deterministic — AI never replaces the
  calibrated pixel measurement, it only assists setup and interpretation.
- All AI features are optional; the app is fully functional with no provider configured.
