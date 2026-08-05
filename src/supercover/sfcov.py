"""Read and write the version 2 SuperFW cover format.

Derived from SuperFW's GPL-licensed ``tools/sfcov.py``. The header carries the
dimensions, allowing both the current 77-pixel size and legacy 72-pixel covers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib


MAGIC = b"SFCV"
VERSION = 2
HEADER_SIZE = 32
WIDTH = 77
HEIGHT = 77
PIXEL_COUNT = WIDTH * HEIGHT
LEGACY_SIZE = 72
SUPPORTED_SIZES = (WIDTH, LEGACY_SIZE)
PALETTE_BASE = 20
MAX_PALETTE_COLORS = 220
MAX_PIXEL_INDEX = PALETTE_BASE + MAX_PALETTE_COLORS - 1

HEADER = struct.Struct("<4sBBHHHHBBIIII")
assert HEADER.size == HEADER_SIZE


class CoverFormatError(ValueError):
    """Raised when a cover does not conform to the version 2 format."""


def rgb888_to_bgr555(red: int, green: int, blue: int) -> int:
    """Convert 8-bit RGB channels to the GBA's 15-bit color format."""

    for channel in (red, green, blue):
        if not 0 <= channel <= 255:
            raise ValueError("RGB channels must be between 0 and 255")
    return (red >> 3) | ((green >> 3) << 5) | ((blue >> 3) << 10)


def bgr555_to_rgb888(color: int) -> tuple[int, int, int]:
    """Expand a GBA BGR555 color to display-friendly 8-bit RGB channels."""

    if not 0 <= color <= 0x7FFF:
        raise ValueError("BGR555 color must fit in 15 bits")

    def expand(value: int) -> int:
        return (value << 3) | (value >> 2)

    return (
        expand(color & 0x1F),
        expand((color >> 5) & 0x1F),
        expand((color >> 10) & 0x1F),
    )


@dataclass(frozen=True)
class Cover:
    """A validated, framebuffer-ready cover."""

    palette: tuple[int, ...]
    pixels: bytes
    size: int = WIDTH

    @property
    def width(self) -> int:
        return self.size

    @property
    def height(self) -> int:
        return self.size

    def validate(self) -> None:
        if self.size not in SUPPORTED_SIZES:
            supported = ", ".join(f"{size}x{size}" for size in SUPPORTED_SIZES)
            raise CoverFormatError(f"cover dimensions must be one of: {supported}")
        if not 1 <= len(self.palette) <= MAX_PALETTE_COLORS:
            raise CoverFormatError(
                f"palette must contain 1..{MAX_PALETTE_COLORS} colors"
            )
        pixel_count = self.width * self.height
        if len(self.pixels) != pixel_count:
            raise CoverFormatError(
                f"pixel payload must contain exactly {pixel_count} bytes"
            )
        if any(not 0 <= color <= 0x7FFF for color in self.palette):
            raise CoverFormatError("palette colors must be 15-bit BGR555 values")

        first = PALETTE_BASE
        last = PALETTE_BASE + len(self.palette) - 1
        if any(pixel < first or pixel > last for pixel in self.pixels):
            raise CoverFormatError(
                f"pixel indices must be between {first} and {last}"
            )

    def to_bytes(self) -> bytes:
        self.validate()
        palette_data = struct.pack(f"<{len(self.palette)}H", *self.palette)
        payload = palette_data + self.pixels
        checksum = zlib.crc32(payload) & 0xFFFFFFFF
        header = HEADER.pack(
            MAGIC,
            VERSION,
            HEADER_SIZE,
            0,
            self.width,
            self.height,
            len(self.palette),
            PALETTE_BASE,
            0,
            len(palette_data),
            len(self.pixels),
            checksum,
            0,
        )
        return header + payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "Cover":
        if len(data) < HEADER_SIZE:
            raise CoverFormatError("cover is shorter than the 32-byte header")

        (
            magic,
            version,
            header_size,
            flags,
            width,
            height,
            palette_count,
            palette_base,
            reserved_byte,
            palette_bytes,
            pixel_bytes,
            expected_crc,
            reserved_word,
        ) = HEADER.unpack_from(data)

        if magic != MAGIC:
            raise CoverFormatError("invalid cover magic")
        if version != VERSION:
            raise CoverFormatError(f"unsupported cover version {version}")
        if header_size != HEADER_SIZE:
            raise CoverFormatError("unsupported cover header size")
        if flags != 0 or reserved_byte != 0 or reserved_word != 0:
            raise CoverFormatError("unsupported flags or non-zero reserved fields")
        if width != height or width not in SUPPORTED_SIZES:
            supported = ", ".join(f"{size}x{size}" for size in SUPPORTED_SIZES)
            raise CoverFormatError(
                f"version {VERSION} covers must be one of: {supported}"
            )
        if palette_base != PALETTE_BASE:
            raise CoverFormatError(
                f"version {VERSION} palette base must be {PALETTE_BASE}"
            )
        if not 1 <= palette_count <= MAX_PALETTE_COLORS:
            raise CoverFormatError("palette count is out of range")
        if palette_bytes != palette_count * 2:
            raise CoverFormatError("palette byte length does not match its count")
        if pixel_bytes != width * height:
            raise CoverFormatError("pixel byte length is invalid")

        expected_size = HEADER_SIZE + palette_bytes + pixel_bytes
        if len(data) != expected_size:
            raise CoverFormatError(
                f"cover length is {len(data)} bytes; expected {expected_size}"
            )

        payload = data[HEADER_SIZE:]
        actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise CoverFormatError("cover payload CRC-32 does not match")

        palette_end = HEADER_SIZE + palette_bytes
        palette = struct.unpack(
            f"<{palette_count}H", data[HEADER_SIZE:palette_end]
        )
        pixels = data[palette_end:]
        cover = cls(tuple(palette), pixels, width)
        cover.validate()
        return cover

    @classmethod
    def read(cls, path: str | Path) -> "Cover":
        return cls.from_bytes(Path(path).read_bytes())
