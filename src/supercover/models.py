"""Data shared by the SuperCover scanner and matching engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MatchStatus(str, Enum):
    """Whether a match is safe to automate or needs attention."""

    AUTOMATIC = "automatic"
    REVIEW = "review"
    CONFLICT = "conflict"
    UNMATCHED = "unmatched"


@dataclass(frozen=True)
class RomFile:
    """A read-only inventory record for one local GBA ROM."""

    path: Path
    relative_path: Path
    filename: str
    stem: str
    size: int
    crc32: str
    sha1: str


@dataclass(frozen=True)
class CatalogEntry:
    """A canonical game identity from a local catalog."""

    name: str
    crc32: str | None = None
    sha1: str | None = None


@dataclass(frozen=True)
class MatchResult:
    """The matching decision for a ROM."""

    rom: RomFile
    status: MatchStatus
    entry: CatalogEntry | None
    method: str | None
    score: float
    message: str
    alternatives: tuple[CatalogEntry, ...] = ()
