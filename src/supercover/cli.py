#!/usr/bin/env python3
"""Command-line test interface for the SuperCover engine."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import (
    ArtworkError,
    LibretroProvider,
    MatchStatus,
    NetworkError,
    load_catalog,
    match_roms,
    scan_roms,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="SuperCover",
        description="Safely inventory GBA ROMs and match them to a local catalog",
    )
    parser.add_argument("rom_folder", type=Path, help="folder containing GBA ROMs")
    parser.add_argument("--catalog", type=Path, help="Phase 1 JSON game catalog")
    parser.add_argument("--no-recursive", action="store_true", help="scan only the selected folder")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument(
        "--fetch-artwork",
        action="store_true",
        help="download exact artwork for automatic catalog matches",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".supercover-cache"),
        help="artwork cache directory (default: .supercover-cache)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use cached provider data without making network requests",
    )
    parser.add_argument(
        "--refresh-artwork",
        action="store_true",
        help="refresh the Libretro index and cached images",
    )
    return parser


def _result_to_dict(result, artwork=None):
    payload = {
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
    if artwork is not None:
        payload["artwork"] = artwork
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.fetch_artwork and args.catalog is None:
        parser.error("--fetch-artwork requires --catalog")

    try:
        roms = scan_roms(args.rom_folder, recursive=not args.no_recursive)
        results = match_roms(roms, load_catalog(args.catalog)) if args.catalog else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    artwork_reports = {}
    artwork_failures = 0
    if args.fetch_artwork and results is not None:
        provider = LibretroProvider(args.cache_dir, offline=args.offline)
        refresh_index = args.refresh_artwork
        for result in results:
            key = result.rom.path
            if result.status != MatchStatus.AUTOMATIC or result.entry is None:
                artwork_reports[key] = {
                    "status": "skipped",
                    "message": "Artwork is fetched only for automatic matches.",
                }
                continue
            refresh_this_index = refresh_index
            refresh_index = False
            try:
                artwork = provider.download_for_title(
                    result.entry.name,
                    refresh_index=refresh_this_index,
                    refresh_artwork=args.refresh_artwork,
                )
                artwork_reports[key] = {
                    "status": "cached" if artwork.from_cache else "downloaded",
                    "provider": artwork.candidate.provider,
                    "provider_url": artwork.candidate.provider_url,
                    "source_url": artwork.candidate.url,
                    "source_filename": artwork.candidate.filename,
                    "cache_path": str(artwork.path),
                    "width": artwork.width,
                    "height": artwork.height,
                }
            except (ArtworkError, NetworkError, OSError) as exc:
                artwork_failures += 1
                artwork_reports[key] = {
                    "status": "error",
                    "message": str(exc),
                }

    if args.json:
        payload = (
            [
                _result_to_dict(result, artwork_reports.get(result.rom.path))
                for result in results
            ]
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
            artwork = artwork_reports.get(result.rom.path)
            if artwork:
                if artwork["status"] in ("cached", "downloaded"):
                    print(
                        f"    Artwork {artwork['status']} from {artwork['provider']}: "
                        f"{artwork['cache_path']}"
                    )
                else:
                    print(f"    Artwork {artwork['status']}: {artwork['message']}")
    return 2 if artwork_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
