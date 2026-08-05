"""Artwork records and strict image validation shared by providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_IMAGE_DIMENSION = 8192
MAX_DECOMPRESSED_BYTES = 64 * 1024 * 1024
VALID_BIT_DEPTHS = {
    0: {1, 2, 4, 8, 16},
    2: {8, 16},
    3: {1, 2, 4, 8},
    4: {8, 16},
    6: {8, 16},
}


class ArtworkError(Exception):
    """Base class for recoverable artwork-provider failures."""


class ArtworkNotFound(ArtworkError):
    """The curated provider has no exact artwork for a title."""


class InvalidArtwork(ArtworkError):
    """Downloaded or cached data is not a safe, complete PNG image."""


class OfflineUnavailable(ArtworkError):
    """Requested data is not cached while offline mode is active."""


@dataclass(frozen=True)
class ArtworkCandidate:
    """One exact artwork match exposed by a curated provider."""

    provider: str
    title: str
    filename: str
    url: str
    provider_url: str


@dataclass(frozen=True)
class ArtworkDownload:
    """Validated artwork in SuperCover's local cache."""

    candidate: ArtworkCandidate
    path: Path
    from_cache: bool
    width: int
    height: int


def validate_png(data: bytes) -> tuple[int, int]:
    """Validate PNG framing, chunk CRCs, dimensions, image data, and ending."""

    if not data.startswith(PNG_SIGNATURE):
        raise InvalidArtwork("artwork is not a PNG image")

    offset = len(PNG_SIGNATURE)
    width = height = 0
    saw_header = saw_image_data = saw_end = False
    compressed_image_data: list[bytes] = []
    chunk_number = 0
    while offset < len(data):
        if len(data) - offset < 12:
            raise InvalidArtwork("PNG has a truncated chunk header")
        length = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise InvalidArtwork("PNG has a truncated chunk")

        chunk_data = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
        actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise InvalidArtwork("PNG chunk checksum is invalid")

        if chunk_number == 0:
            if chunk_type != b"IHDR" or length != 13:
                raise InvalidArtwork("PNG must begin with a valid IHDR chunk")
            width, height = struct.unpack_from(">II", chunk_data)
            if not (1 <= width <= MAX_IMAGE_DIMENSION):
                raise InvalidArtwork("PNG width is outside the safe range")
            if not (1 <= height <= MAX_IMAGE_DIMENSION):
                raise InvalidArtwork("PNG height is outside the safe range")
            bit_depth, color_type, compression, filtering, interlace = chunk_data[8:]
            if bit_depth not in VALID_BIT_DEPTHS.get(color_type, set()):
                raise InvalidArtwork("PNG uses an unsupported color format")
            if compression != 0 or filtering != 0 or interlace not in (0, 1):
                raise InvalidArtwork("PNG uses unsupported encoding settings")
            saw_header = True
        elif chunk_type == b"IHDR":
            raise InvalidArtwork("PNG contains more than one IHDR chunk")

        if chunk_type == b"IDAT":
            saw_image_data = True
            compressed_image_data.append(chunk_data)
        elif chunk_type == b"IEND":
            if length != 0:
                raise InvalidArtwork("PNG IEND chunk must be empty")
            if chunk_end != len(data):
                raise InvalidArtwork("PNG has data after its IEND chunk")
            saw_end = True
            break

        offset = chunk_end
        chunk_number += 1

    if not (saw_header and saw_image_data and saw_end):
        raise InvalidArtwork("PNG is missing required image chunks")

    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(
            b"".join(compressed_image_data), MAX_DECOMPRESSED_BYTES + 1
        )
        if len(decoded) > MAX_DECOMPRESSED_BYTES or decompressor.unconsumed_tail:
            raise InvalidArtwork("PNG expands beyond the safe size limit")
        remaining = MAX_DECOMPRESSED_BYTES + 1 - len(decoded)
        decoded += decompressor.flush(remaining)
        if len(decoded) > MAX_DECOMPRESSED_BYTES:
            raise InvalidArtwork("PNG expands beyond the safe size limit")
        if not decompressor.eof or decompressor.unused_data:
            raise InvalidArtwork("PNG image data is incomplete or has trailing data")
    except zlib.error as exc:
        raise InvalidArtwork("PNG contains invalid compressed image data") from exc
    return width, height
