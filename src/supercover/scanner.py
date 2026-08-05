"""Read-only GBA ROM discovery and hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable
import zlib

from .models import RomFile


ROM_EXTENSION = ".gba"
DEFAULT_CHUNK_SIZE = 1024 * 1024


def iter_rom_paths(root: Path, recursive: bool = True) -> Iterable[Path]:
    """Yield GBA files in stable relative-path order."""

    candidates = root.rglob("*") if recursive else root.glob("*")
    return iter(
        sorted(
            (
                path
                for path in candidates
                if path.is_file() and path.suffix.casefold() == ROM_EXTENSION
            ),
            key=lambda path: str(path.relative_to(root)).casefold(),
        )
    )


def identify_rom(path: Path, root: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> RomFile:
    """Hash one ROM incrementally without changing or loading all of it."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    crc32 = 0
    sha1 = hashlib.sha1()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            size += len(chunk)
            crc32 = zlib.crc32(chunk, crc32)
            sha1.update(chunk)

    return RomFile(
        path=path,
        relative_path=path.relative_to(root),
        filename=path.name,
        stem=path.stem,
        size=size,
        crc32=f"{crc32 & 0xFFFFFFFF:08X}",
        sha1=sha1.hexdigest().upper(),
    )


def scan_roms(
    folder: str | Path,
    *,
    recursive: bool = True,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> list[RomFile]:
    """Inventory every GBA ROM under a folder in a deterministic order."""

    root = Path(folder).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"ROM folder does not exist: {root}")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return [identify_rom(path, root, chunk_size) for path in iter_rom_paths(root, recursive)]
