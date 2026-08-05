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
    ExistingFilePolicy,
    ExportError,
    ExportRequest,
    ExportStatus,
    LibretroProvider,
    MatchStatus,
    NetworkError,
    export_covers,
    load_catalog,
    match_roms,
    scan_roms,
)
from .sfcov import LEGACY_SIZE, WIDTH


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
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="user-selected folder that will receive .sfcov files",
    )
    parser.add_argument(
        "--preview-dir",
        type=Path,
        help="optional user-selected folder for final GBA-color PNG previews",
    )
    parser.add_argument(
        "--existing",
        choices=tuple(policy.value for policy in ExistingFilePolicy),
        default=ExistingFilePolicy.SKIP.value,
        help="existing cover policy: skip, replace, or keep-both (default: skip)",
    )
    parser.add_argument(
        "--export-size",
        type=int,
        choices=(WIDTH, LEGACY_SIZE),
        default=WIDTH,
        help=f"square cover size in pixels (default: {WIDTH})",
    )
    parser.add_argument(
        "--resize-mode",
        choices=("cover", "contain"),
        default="cover",
        help="crop to fill or letterbox the square cover (default: cover)",
    )
    parser.add_argument(
        "--dither",
        choices=("floyd-steinberg", "none"),
        default="floyd-steinberg",
        help="color-reduction mode (default: floyd-steinberg)",
    )
    return parser


def _result_to_dict(result, artwork=None, export=None):
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
    if export is not None:
        payload["export"] = export
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    fetch_artwork = args.fetch_artwork or args.export_dir is not None
    if fetch_artwork and args.catalog is None:
        parser.error("artwork fetching and export require --catalog")
    if args.preview_dir is not None and args.export_dir is None:
        parser.error("--preview-dir requires --export-dir")

    try:
        roms = scan_roms(args.rom_folder, recursive=not args.no_recursive)
        results = match_roms(roms, load_catalog(args.catalog)) if args.catalog else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    artwork_reports = {}
    artwork_downloads = {}
    artwork_failures = 0
    if fetch_artwork and results is not None:
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
                artwork_downloads[key] = artwork
            except (ArtworkError, NetworkError, OSError) as exc:
                artwork_failures += 1
                artwork_reports[key] = {
                    "status": "error",
                    "message": str(exc),
                }

    export_reports = {}
    export_failures = 0
    if args.export_dir is not None and results is not None:
        requests = [
            ExportRequest(result, artwork_downloads[result.rom.path])
            for result in results
            if result.rom.path in artwork_downloads
        ]
        try:
            exported = export_covers(
                requests,
                args.export_dir,
                preview_dir=args.preview_dir,
                existing=args.existing,
                mode=args.resize_mode,
                dither=args.dither,
                size=args.export_size,
            )
            for item in exported:
                exact_firmware_name = (
                    item.path.name
                    == f"{item.request.match.rom.stem}.sfcov"
                )
                export_reports[item.request.match.rom.path] = {
                    "status": item.status.value,
                    "path": str(item.path),
                    "preview_path": (
                        str(item.preview_path) if item.preview_path else None
                    ),
                    "palette_colors": item.palette_colors,
                    "file_size": item.file_size,
                    "exact_firmware_name": exact_firmware_name,
                    "message": item.message,
                }
        except (ExportError, OSError, ValueError) as exc:
            export_failures = max(1, len(requests))
            for request in requests:
                export_reports[request.match.rom.path] = {
                    "status": "error",
                    "message": str(exc),
                }

        for result in results:
            if result.rom.path not in export_reports:
                export_reports[result.rom.path] = {
                    "status": "skipped",
                    "message": "No validated automatic artwork match was available.",
                }

    if args.json:
        payload = (
            [
                _result_to_dict(
                    result,
                    artwork_reports.get(result.rom.path),
                    export_reports.get(result.rom.path),
                )
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
        return 2 if artwork_failures or export_failures else 0

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
            export = export_reports.get(result.rom.path)
            if export:
                if export["status"] in (
                    ExportStatus.EXPORTED.value,
                    ExportStatus.SKIPPED.value,
                ) and "path" in export:
                    print(f"    Export {export['status']}: {export['path']}")
                    if not export.get("exact_firmware_name", True):
                        print(
                            "    Warning: this numbered comparison filename will not "
                            "automatically match the ROM in SuperFW."
                        )
                else:
                    print(f"    Export {export['status']}: {export['message']}")
    return 2 if artwork_failures or export_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
