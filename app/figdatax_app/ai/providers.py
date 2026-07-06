"""AI providers: subscription CLIs (claude, codex) and OpenAI-compatible APIs.

All providers implement one method::

    complete(prompt, images=None, system=None, timeout=120) -> str

``images`` is a list of PNG/JPG file paths. CLI providers pass the paths in the prompt
(both CLIs can read workspace files); the API provider embeds them as data URLs.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from typing import List, Optional


class AIError(Exception):
    """A provider failed: not installed, not authenticated, bad response, timeout."""


def _run(cmd: List[str], timeout: float, cwd: Optional[str] = None) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
    except FileNotFoundError as exc:
        raise AIError(f"{cmd[0]} not found on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AIError(f"{cmd[0]} timed out after {timeout:.0f}s.") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-500:]
        raise AIError(f"{cmd[0]} exited {proc.returncode}: {detail}")
    return proc.stdout.strip()


class ClaudeCliProvider:
    """Claude Max/Pro subscription via the local ``claude`` CLI (headless ``-p``)."""

    kind = "claude-cli"
    label = "Claude (订阅 / subscription CLI)"

    def __init__(self, model: str = ""):
        self.model = model

    @staticmethod
    def available() -> bool:
        return shutil.which("claude") is not None

    def complete(self, prompt: str, images: Optional[List[str]] = None,
                 system: Optional[str] = None, timeout: float = 180) -> str:
        full = prompt
        if images:
            names = "\n".join(os.path.abspath(p) for p in images)
            full = f"Read the image file(s):\n{names}\n\n{prompt}"
        cmd = ["claude", "-p", full, "--output-format", "text"]
        if images:
            cmd += ["--allowedTools", "Read"]
        if system:
            cmd += ["--append-system-prompt", system]
        if self.model:
            cmd += ["--model", self.model]
        # run from a neutral cwd so no project CLAUDE.md leaks into the context
        return _run(cmd, timeout, cwd=tempfile.gettempdir())


class CodexCliProvider:
    """ChatGPT Plus subscription via the local ``codex`` CLI (``codex exec``)."""

    kind = "codex-cli"
    label = "Codex / ChatGPT (订阅 / subscription CLI)"

    def __init__(self, model: str = ""):
        self.model = model

    @staticmethod
    def available() -> bool:
        return shutil.which("codex") is not None

    def complete(self, prompt: str, images: Optional[List[str]] = None,
                 system: Optional[str] = None, timeout: float = 180) -> str:
        full = f"{system}\n\n{prompt}" if system else prompt
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "last.txt")
            cmd = ["codex", "exec", "--skip-git-repo-check",
                   "--output-last-message", out]
            if self.model:
                cmd += ["--model", self.model]
            for p in images or []:
                cmd += ["--image", os.path.abspath(p)]
            cmd += [full]
            stdout = _run(cmd, timeout, cwd=d)
            if os.path.exists(out):
                with open(out, "r", encoding="utf-8") as fh:
                    text = fh.read().strip()
                if text:
                    return text
            return stdout


class OpenAICompatProvider:
    """Any OpenAI-compatible chat-completions endpoint (DeepSeek, Qwen, Ollama, …)."""

    kind = "openai-compat"
    label = "OpenAI 兼容 API (DeepSeek 等)"

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    @staticmethod
    def available() -> bool:
        return True   # availability is just configuration

    def complete(self, prompt: str, images: Optional[List[str]] = None,
                 system: Optional[str] = None, timeout: float = 120) -> str:
        if not (self.base_url and self.model):
            raise AIError("API base URL / model not configured (AI settings).")
        content: object
        if images:
            content = [{"type": "text", "text": prompt}]
            for p in images:
                with open(p, "rb") as fh:
                    b64 = base64.b64encode(fh.read()).decode("ascii")
                ext = os.path.splitext(p)[1].lstrip(".").lower() or "png"
                content.append({"type": "image_url",
                                "image_url": {"url": f"data:image/{ext};base64,{b64}"}})
        else:
            content = prompt
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})

        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps({"model": self.model, "messages": messages}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise AIError(f"API HTTP {exc.code}: {exc.read().decode()[:300]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AIError(f"API unreachable: {exc}") from exc
        try:
            return body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError) as exc:
            raise AIError(f"Unexpected API response: {str(body)[:300]}") from exc


class FakeProvider:
    """Deterministic offline provider for tests: returns canned responses."""

    kind = "fake"
    label = "Fake (tests)"

    def __init__(self, response: str = "", by_keyword: Optional[dict] = None):
        self.response = response
        self.by_keyword = by_keyword or {}
        self.calls: List[dict] = []

    @staticmethod
    def available() -> bool:
        return True

    def complete(self, prompt: str, images=None, system=None, timeout=0) -> str:
        self.calls.append({"prompt": prompt, "images": list(images or [])})
        for kw, resp in self.by_keyword.items():
            if kw in prompt:
                return resp
        return self.response
