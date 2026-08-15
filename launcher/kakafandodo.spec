# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import (
    collect_submodules,
)


ROOT = Path(SPECPATH).resolve().parent
BACKEND = ROOT / "backend"
GODOT_BUILD = ROOT / "build" / "godot"
LAUNCHER = ROOT / "launcher"


# Permet à PyInstaller et collect_submodules()
# de trouver le package backend/app.
sys.path.insert(
    0,
    str(BACKEND),
)


hiddenimports = []

# Toutes les stratégies et routes backend.
hiddenimports += collect_submodules(
    "app"
)

# Uvicorn charge certains composants
# dynamiquement.
hiddenimports += collect_submodules(
    "uvicorn"
)

# python-multipart utilisé par les uploads.
hiddenimports += collect_submodules(
    "multipart"
)


datas = [
    (
        str(
            GODOT_BUILD
            / "kakafandodo2d.exe"
        ),
        "godot",
    ),
    (
        str(
            GODOT_BUILD
            / "kakafandodo2d.pck"
        ),
        "godot",
    ),
]


a = Analysis(
    [
        str(
            LAUNCHER
            / "main.py"
        )
    ],
    pathex=[
        str(BACKEND),
        str(ROOT),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)


pyz = PYZ(
    a.pure
)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="kakafandodo2d-ikom",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)