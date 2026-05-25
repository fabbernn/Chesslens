# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for ChessLens.

Build with:
    pyinstaller ChessLens.spec
The result is dist/ChessLens.exe (windowed, no console) with the icon
embedded.
"""
from PyInstaller.utils.hooks import (
    collect_submodules, collect_data_files, collect_dynamic_libs,
)

block_cipher = None

# Tell PyInstaller to ship the entire resources tree alongside the exe.
datas = [
    ("app/resources/sounds", "app/resources/sounds"),
    ("app/resources/icon",   "app/resources/icon"),
    ("app/resources/fonts",  "app/resources/fonts"),
    # Piece set SVGs (added Phase 11 — cburnett / merida / alpha sets)
    ("assets/pieces",        "assets/pieces"),
]

# These packages all ship JSON / data files that the .exe must carry,
# otherwise Kokoro fails to load. Each missing one shows up in voice.log
# as "FileNotFoundError: ..." — add it here and rebuild.
_DATA_PACKAGES = (
    "kokoro_onnx",
    "onnxruntime",
    "phonemizer",
    "phonemizer_fork",   # the actual package kokoro pulls in
    "espeakng_loader",   # ships espeak-ng-data (current blocker)
    "segments",
    "csvw",
    "language_tags",
    "babel",
    "jsonschema",
    "jsonschema_specifications",
    "referencing",
)
for pkg in _DATA_PACKAGES:
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

# Pull in onnxruntime's native .dlls AND espeak-ng's native binaries.
# Without these the AI voice can import but fails at first inference.
binaries = []
for pkg in ("onnxruntime", "kokoro_onnx", "espeakng_loader"):
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass

# Pull in stuff PyInstaller can't always see through the dynamic imports
hiddenimports = [
    "chess",
    "chess.engine",
    "chess.svg",
    "chess.pgn",
    "PySide6.QtSvg",
    "PySide6.QtMultimedia",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    # AI voice stack
    "kokoro_onnx",
    "onnxruntime",
    "onnxruntime.capi",
    "onnxruntime.capi._pybind_state",
    "soundfile",
    "numpy",
    "psutil",
    "phonemizer",
    "phonemizer_fork",
    "phonemizer.backend",
    "phonemizer.backend.segments",
    "espeakng_loader",
    "segments",
    "csvw",
    "language_tags",
]

# Be aggressive about pulling in every submodule of the AI voice stack so
# nothing trips on a dynamic import inside the .exe.
for mod in ("kokoro_onnx", "onnxruntime", "phonemizer", "segments",
            "csvw", "language_tags", "espeakng_loader"):
    try:
        hiddenimports += collect_submodules(mod)
    except Exception:
        pass

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "PIL.ImageQt",
        "PyQt5", "PyQt6",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ChessLens",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app/resources/icon/chesslens.ico",
)
