"""Offline scanning and matching engine for SuperCover."""

from .artwork import (
    ArtworkCandidate,
    ArtworkDownload,
    ArtworkError,
    ArtworkNotFound,
    InvalidArtwork,
    OfflineUnavailable,
    validate_png,
)
from .catalog import load_catalog
from .libretro import LibretroProvider, thumbnail_filename
from .matching import match_rom, match_roms, normalize_title
from .models import CatalogEntry, MatchResult, MatchStatus, RomFile
from .network import DownloadCancelled, HttpClient, HttpStatusError, NetworkError
from .scanner import scan_roms

__all__ = [
    "ArtworkCandidate",
    "ArtworkDownload",
    "ArtworkError",
    "ArtworkNotFound",
    "CatalogEntry",
    "DownloadCancelled",
    "HttpClient",
    "HttpStatusError",
    "InvalidArtwork",
    "LibretroProvider",
    "MatchResult",
    "MatchStatus",
    "NetworkError",
    "OfflineUnavailable",
    "RomFile",
    "load_catalog",
    "match_rom",
    "match_roms",
    "normalize_title",
    "scan_roms",
    "thumbnail_filename",
    "validate_png",
]
