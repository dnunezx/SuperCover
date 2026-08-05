"""Offline scanning and matching engine for SuperCover."""

from .catalog import load_catalog
from .matching import match_rom, match_roms, normalize_title
from .models import CatalogEntry, MatchResult, MatchStatus, RomFile
from .scanner import scan_roms

__all__ = [
    "CatalogEntry",
    "MatchResult",
    "MatchStatus",
    "RomFile",
    "load_catalog",
    "match_rom",
    "match_roms",
    "normalize_title",
    "scan_roms",
]
