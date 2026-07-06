"""py2app build config for FigDataX Desktop.

Build the unsigned .app with:  bash app/build.sh
"""

import os
import sys

from setuptools import setup

# The extraction engine (``scripts/figdatax``) lives at the repo root, one level up from
# this app/ directory. Put it on sys.path so py2app's modulegraph can find and bundle it;
# inside the frozen app it then imports as a normal top-level ``scripts`` package.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

APP = ["figdatax_app/__main__.py"]
DATA_FILES = [
    ("assets/sample", ["figdatax_app/assets/sample/sample_scatter.png"]),
]
OPTIONS = {
    "argv_emulation": False,
    "packages": ["cv2", "numpy", "pandas", "openpyxl", "scipy", "PySide6",
                 "pypdfium2", "pdfplumber", "scripts"],
    # Trim size: exclude Qt modules and heavy libs the app does not use.
    "excludes": ["matplotlib", "tkinter", "PySide6.QtWebEngine",
                 "PySide6.QtWebEngineCore", "PySide6.Qt3DCore",
                 "PySide6.QtMultimedia", "PySide6.QtQuick3D"],
    "plist": {
        "CFBundleName": "FigDataX",
        "CFBundleDisplayName": "FigDataX Desktop",
        "CFBundleIdentifier": "com.shaowen-ye.figdatax",
        "CFBundleVersion": open("VERSION").read().strip(),
        "CFBundleShortVersionString": open("VERSION").read().strip(),
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
