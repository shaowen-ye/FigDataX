"""Optional AI-assist layer.

Providers run on the user's existing subscriptions (Claude Max via the ``claude`` CLI,
ChatGPT Plus via the ``codex`` CLI) or any OpenAI-compatible API. Everything here is
suggestive: numbers only enter the dataset after the user confirms them, and the
extraction engine stays fully deterministic. See app/AI_INTEGRATION.md.
"""
