# -*- mode: python ; coding: utf-8 -*-
# Copyright (C) 2026 Danny Nunez (dnunezx)

from pathlib import Path
import sys


project_root = Path(SPECPATH).parent

# The desktop agent's Python distribution keeps Tcl/Tk binaries but omits the
# matching script libraries. When that local runtime cache is present, include
# it explicitly; normal Python/CI installations continue to use PyInstaller's
# standard Tcl/Tk discovery.
local_tk_runtime = project_root / "build" / "local-tk-runtime"
runtime_binaries = []
runtime_datas = []
python_tkinter = Path(sys.base_prefix) / "Lib" / "tkinter"
tkinter_datas = [(str(python_tkinter), "tkinter")] if python_tkinter.is_dir() else []
if local_tk_runtime.is_dir():
    runtime_binaries = [
        (str(local_tk_runtime / name), ".")
        for name in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll", "zlib1.dll")
        if (local_tk_runtime / name).is_file()
    ]
    runtime_datas = [
        (str(local_tk_runtime / name), name)
        for name in ("_tcl_data", "_tk_data")
        if (local_tk_runtime / name).is_dir()
    ]

a = Analysis(
    [str(project_root / "packaging" / "supercover_entry.py")],
    pathex=[str(project_root / "src")],
    binaries=runtime_binaries,
    datas=[
        (str(project_root / "assets" / "supercover.ico"), "assets"),
        (str(project_root / "LICENSE"), "legal"),
        (str(project_root / "THIRD_PARTY_NOTICES.md"), "legal"),
        *tkinter_datas,
        *runtime_datas,
    ],
    hiddenimports=[
        "_tkinter",
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.ttk",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SuperCover",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "assets" / "supercover.ico"),
    version=str(project_root / "packaging" / "windows-version.txt"),
)
