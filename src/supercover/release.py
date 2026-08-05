"""Frozen-application entry point and portable build self-test."""

from __future__ import annotations

import json
from pathlib import Path
import platform
import sys

from PIL import Image

from .converter import image_to_cover
from .sfcov import Cover
from .storage import write_atomic
from .version import __version__


def run_self_test(report_path: str | Path) -> dict:
    """Verify imports and conversion inside a source or frozen application."""

    import tkinter

    sample = Image.new("RGB", (96, 80), (24, 116, 204))
    encoded = image_to_cover(sample).to_bytes()
    decoded = Cover.from_bytes(encoded)
    report = {
        "application": "SuperCover",
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "tk_version": str(tkinter.TkVersion),
        "cover_width": decoded.width,
        "cover_height": decoded.height,
        "cover_bytes": len(encoded),
        "status": "ok",
    }
    write_atomic(
        Path(report_path),
        json.dumps(report, indent=2, sort_keys=True).encode("utf-8"),
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--self-test":
        if len(args) != 2:
            return 2
        run_self_test(args[1])
        return 0
    if args:
        return 2

    from .gui import main as gui_main

    return gui_main()
