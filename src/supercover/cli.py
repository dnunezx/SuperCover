#!/usr/bin/env python3
"""Phase 1 command-line interface for the SuperCover engine."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import load_catalog, match_roms, scan_roms


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="SuperCover",
        description="Safely inventory GBA ROMs and match them to a local catalog",
    )
    parser.add_argument("rom_folder", type=Path, help="folder containing GBA ROMs")
    parser.add_argument("--catalog", type=Path, help="Phase 1 JSON game catalog")
    parser.add_argument("--no-recursive", action="store_true", help="scan only the selected folder")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser


def _result_to_dict(result):
    return {
        "rom": {
            **asdict(result.rom),
            "path": str(result.rom.path),
            "relative_path": str(result.rom.relative_path),
        },
        "status": result.status.value,
        "match": result.entry.name if result.entry else None,
        "method": result.method,
        "score": round(result.score, 4),
        "message": result.message,
        "alternatives": [entry.name for entry in result.alternatives],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        roms = scan_roms(args.rom_folder, recursive=not args.no_recursive)
        results = match_roms(roms, load_catalog(args.catalog)) if args.catalog else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = (
            [_result_to_dict(result) for result in results]
            if results is not None
            else [
                {
                    **asdict(rom),
                    "path": str(rom.path),
                    "relative_path": str(rom.relative_path),
                }
                for rom in roms
            ]
        )
        print(json.dumps(payload, indent=2))
        return 0

    print(f"SuperCover found {len(roms)} GBA ROM(s).")
    if results is None:
        for rom in roms:
            print(f"  {rom.relative_path}  CRC32 {rom.crc32}  SHA1 {rom.sha1}")
    else:
        for result in results:
            match = result.entry.name if result.entry else "No match"
            print(f"  [{result.status.value.upper()}] {result.rom.relative_path} -> {match}")
            print(f"    {result.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
