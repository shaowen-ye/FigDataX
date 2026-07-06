"""py2app build config for FigDataX Desktop.

Build the unsigned .app with:  bash app/build.sh
"""

from setuptools import setup

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
