"""Convert common desktop images into hardware-ready SuperFW covers.

The palette and quantization logic is derived from SuperFW's GPL-licensed,
physical-hardware-tested cover converter.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

from .sfcov import (
    Cover,
    MAX_PALETTE_COLORS,
    PALETTE_BASE,
    SUPPORTED_SIZES,
    WIDTH,
    bgr555_to_rgb888,
    rgb888_to_bgr555,
)


RESAMPLE = Image.Resampling.LANCZOS
DITHER_MODES = {
    "none": Image.Dither.NONE,
    "floyd-steinberg": Image.Dither.FLOYDSTEINBERG,
}
RESIZE_MODES = frozenset(("cover", "contain"))


def prepare_image(
    image: Image.Image,
    mode: str = "cover",
    background: tuple[int, int, int] = (0, 0, 0),
    size: int = WIDTH,
) -> Image.Image:
    """Flatten and resize an input image to a supported square canvas."""

    if mode not in RESIZE_MODES:
        raise ValueError(f"unsupported resize mode: {mode}")
    if len(background) != 3 or any(not 0 <= channel <= 255 for channel in background):
        raise ValueError("background must contain three channels from 0 to 255")
    if size not in SUPPORTED_SIZES:
        raise ValueError(f"unsupported export size: {size}")

    rgba = image.convert("RGBA")
    flattened = Image.new("RGBA", rgba.size, background + (255,))
    flattened.alpha_composite(rgba)
    rgb = flattened.convert("RGB")

    if mode == "cover":
        return ImageOps.fit(rgb, (size, size), method=RESAMPLE)

    contained = ImageOps.contain(rgb, (size, size), method=RESAMPLE)
    canvas = Image.new("RGB", (size, size), background)
    offset = ((size - contained.width) // 2, (size - contained.height) // 2)
    canvas.paste(contained, offset)
    return canvas


def image_to_cover(
    image: Image.Image,
    *,
    mode: str = "cover",
    background: tuple[int, int, int] = (0, 0, 0),
    dither: str = "floyd-steinberg",
    size: int = WIDTH,
) -> Cover:
    """Prepare, quantize, compact, and encode an image as a Cover."""

    if dither not in DITHER_MODES:
        raise ValueError(f"unsupported dither mode: {dither}")

    prepared = prepare_image(image, mode=mode, background=background, size=size)
    quantized = prepared.quantize(
        colors=MAX_PALETTE_COLORS,
        method=Image.Quantize.MEDIANCUT,
        dither=DITHER_MODES[dither],
    )
    source_palette = quantized.getpalette()
    if source_palette is None:
        raise ValueError("image quantization produced no palette")
    source_pixels = quantized.tobytes()

    source_to_compact: dict[int, int] = {}
    color_to_compact: dict[int, int] = {}
    compact_palette: list[int] = []
    for source_index in sorted(set(source_pixels)):
        offset = source_index * 3
        red, green, blue = source_palette[offset : offset + 3]
        gba_color = rgb888_to_bgr555(red, green, blue)
        compact_index = color_to_compact.get(gba_color)
        if compact_index is None:
            compact_index = len(compact_palette)
            color_to_compact[gba_color] = compact_index
            compact_palette.append(gba_color)
        source_to_compact[source_index] = compact_index

    pixels = bytes(
        PALETTE_BASE + source_to_compact[source_index]
        for source_index in source_pixels
    )
    return Cover(tuple(compact_palette), pixels, size)


def image_file_to_cover(
    path: str | Path,
    *,
    mode: str = "cover",
    background: tuple[int, int, int] = (0, 0, 0),
    dither: str = "floyd-steinberg",
    size: int = WIDTH,
) -> Cover:
    """Decode one local image and return a validated in-memory cover."""

    return image_bytes_to_cover(
        Path(path).read_bytes(),
        mode=mode,
        background=background,
        dither=dither,
        size=size,
    )


def image_bytes_to_cover(
    data: bytes,
    *,
    mode: str = "cover",
    background: tuple[int, int, int] = (0, 0, 0),
    dither: str = "floyd-steinberg",
    size: int = WIDTH,
) -> Cover:
    """Decode validated in-memory image bytes without a filesystem race."""

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return image_to_cover(
                image,
                mode=mode,
                background=background,
                dither=dither,
                size=size,
            )
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("image cannot be decoded safely") from exc


def cover_to_image(cover: Cover) -> Image.Image:
    """Render a cover with the exact 15-bit colors the GBA will display."""

    cover.validate()
    palette: list[int] = []
    for color in cover.palette:
        palette.extend(bgr555_to_rgb888(color))
    palette.extend([0] * (768 - len(palette)))

    relative_pixels = bytes(pixel - PALETTE_BASE for pixel in cover.pixels)
    preview = Image.new("P", (cover.width, cover.height))
    preview.putpalette(palette)
    preview.putdata(relative_pixels)
    return preview.convert("RGB")
