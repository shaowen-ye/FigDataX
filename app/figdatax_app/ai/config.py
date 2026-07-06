"""AI configuration: persistence (QSettings) + provider factory.

Keeps the UI and the provider classes decoupled — the settings dialog writes a dict,
``build_provider`` reads it. API keys live in the Keychain, not in settings.
"""

from __future__ import annotations

from typing import Optional

from .keystore import get_api_key
from .providers import (ClaudeCliProvider, CodexCliProvider, FakeProvider,
                        OpenAICompatProvider)

KINDS = ["claude-cli", "codex-cli", "openai-compat"]
_KEY_ACCOUNT = "openai-compat"


def default_config() -> dict:
    return {"kind": "claude-cli", "model": "", "base_url": "https://api.deepseek.com/v1",
            "api_model": "deepseek-chat"}


def load_config(settings) -> dict:
    cfg = default_config()
    cfg["kind"] = settings.value("ai/kind", cfg["kind"], type=str)
    cfg["model"] = settings.value("ai/model", cfg["model"], type=str)
    cfg["base_url"] = settings.value("ai/base_url", cfg["base_url"], type=str)
    cfg["api_model"] = settings.value("ai/api_model", cfg["api_model"], type=str)
    return cfg


def save_config(settings, cfg: dict):
    settings.setValue("ai/kind", cfg.get("kind", "claude-cli"))
    settings.setValue("ai/model", cfg.get("model", ""))
    settings.setValue("ai/base_url", cfg.get("base_url", ""))
    settings.setValue("ai/api_model", cfg.get("api_model", ""))


def build_provider(cfg: dict, api_key: Optional[str] = None):
    """Instantiate the configured provider. ``api_key`` overrides the Keychain (used by
    the settings 'Test' button before the key is saved). Raises nothing here; provider
    calls raise AIError at use time."""
    kind = cfg.get("kind", "claude-cli")
    if kind == "claude-cli":
        return ClaudeCliProvider(model=cfg.get("model", ""))
    if kind == "codex-cli":
        return CodexCliProvider(model=cfg.get("model", ""))
    if kind == "openai-compat":
        key = api_key if api_key is not None else get_api_key(_KEY_ACCOUNT)
        return OpenAICompatProvider(cfg.get("base_url", ""), key,
                                    cfg.get("api_model", ""))
    if kind == "fake":
        return FakeProvider(response="{}")
    raise ValueError(f"Unknown provider kind: {kind}")


def provider_available(cfg: dict) -> bool:
    kind = cfg.get("kind", "claude-cli")
    if kind == "claude-cli":
        return ClaudeCliProvider.available()
    if kind == "codex-cli":
        return CodexCliProvider.available()
    return True
