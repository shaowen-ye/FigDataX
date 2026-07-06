"""Pytest fixtures — put the skill root on sys.path so `scripts.figdatax` imports."""

import os
import sys

import pytest

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)


@pytest.fixture
def artifacts(tmp_path):
    """A temp directory for generated chart images."""
    return tmp_path
