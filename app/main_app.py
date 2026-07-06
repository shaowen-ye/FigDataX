"""Frozen-app entry point (py2app).

py2app runs the bundle's main script as a top-level module with no package context, so a
relative import (``from .app import run``) fails. This script uses an absolute import of
the bundled ``figdatax_app`` package instead. For development, keep using
``python -m figdatax_app``.
"""

import sys

from figdatax_app.app import run

if __name__ == "__main__":
    sys.exit(run())
