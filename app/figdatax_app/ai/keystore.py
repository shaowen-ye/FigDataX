"""API-key storage in the macOS Keychain (via the ``security`` CLI, no extra deps).

Falls back to returning/holding nothing on other platforms — the settings dialog then
keeps the key only for the session and warns the user.
"""

from __future__ import annotations

import subprocess
import sys

_SERVICE = "FigDataX"


def keychain_available() -> bool:
    return sys.platform == "darwin"


def get_api_key(account: str) -> str:
    """Read a stored key; empty string when absent or unsupported."""
    if not keychain_available():
        return ""
    proc = subprocess.run(
        ["security", "find-generic-password", "-s", _SERVICE, "-a", account, "-w"],
        capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def set_api_key(account: str, key: str) -> bool:
    """Store (or update, or delete when empty) a key. Returns success."""
    if not keychain_available():
        return False
    if not key:
        subprocess.run(["security", "delete-generic-password", "-s", _SERVICE,
                        "-a", account], capture_output=True, text=True)
        return True
    proc = subprocess.run(
        ["security", "add-generic-password", "-U", "-s", _SERVICE,
         "-a", account, "-w", key],
        capture_output=True, text=True)
    return proc.returncode == 0
