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
from .converter import (
    cover_to_image,
    image_bytes_to_cover,
    image_file_to_cover,
    image_to_cover,
)
from .exporter import (
    ExistingFilePolicy,
    ExportCollision,
    ExportError,
    ExportRequest,
    ExportResult,
    ExportStatus,
    export_covers,
)
from .libretro import LibretroProvider, thumbnail_filename
from .matching import match_rom, match_roms, normalize_title
from .models import CatalogEntry, MatchResult, MatchStatus, RomFile
from .network import DownloadCancelled, HttpClient, HttpStatusError, NetworkError
from .scanner import scan_roms
from .sfcov import Cover, CoverFormatError
from .version import __version__

__all__ = [
    "ArtworkCandidate",
    "ArtworkDownload",
    "ArtworkError",
    "ArtworkNotFound",
    "CatalogEntry",
    "Cover",
    "CoverFormatError",
    "DownloadCancelled",
    "HttpClient",
    "HttpStatusError",
    "ExistingFilePolicy",
    "ExportCollision",
    "ExportError",
    "ExportRequest",
    "ExportResult",
    "ExportStatus",
    "InvalidArtwork",
    "LibretroProvider",
    "MatchResult",
    "MatchStatus",
    "NetworkError",
    "OfflineUnavailable",
    "RomFile",
    "load_catalog",
    "cover_to_image",
    "export_covers",
    "image_bytes_to_cover",
    "image_file_to_cover",
    "image_to_cover",
    "match_rom",
    "match_roms",
    "normalize_title",
    "scan_roms",
    "thumbnail_filename",
    "validate_png",
    "__version__",
]
