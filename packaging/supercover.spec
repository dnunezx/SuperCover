# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).parent

a = Analysis(
    [str(project_root / "packaging" / "supercover_entry.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "assets" / "supercover.ico"), "assets"),
        (str(project_root / "LICENSE"), "legal"),
        (str(project_root / "THIRD_PARTY_NOTICES.md"), "legal"),
    ],
    hiddenimports=[],
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
