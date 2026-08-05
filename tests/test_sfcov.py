import sys
import unittest
from pathlib import Path
import zlib

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from supercover import Cover, CoverFormatError, image_to_cover  # noqa: E402
from supercover.sfcov import (  # noqa: E402
    HEADER,
    HEADER_SIZE,
    HEIGHT,
    MAX_PALETTE_COLORS,
    PALETTE_BASE,
    PIXEL_COUNT,
    VERSION,
    WIDTH,
)


class SuperFwCoverFormatTest(unittest.TestCase):
    def make_cover(self):
        image = Image.new("RGB", (96, 144))
        image.putdata(
            [
                ((x * 255) // 95, (y * 255) // 143, (x * 3 + y * 5) & 255)
                for y in range(144)
                for x in range(96)
            ]
        )
        return image_to_cover(image)

    def test_fixed_format_round_trip(self):
        cover = self.make_cover()
        encoded = cover.to_bytes()
        decoded = Cover.from_bytes(encoded)

        self.assertEqual(decoded, cover)
        self.assertEqual((decoded.width, decoded.height), (WIDTH, HEIGHT))
        self.assertEqual(len(decoded.pixels), PIXEL_COUNT)
        self.assertEqual(len(encoded), HEADER_SIZE + len(cover.palette) * 2 + PIXEL_COUNT)

    def test_crc_corruption_is_rejected(self):
        encoded = bytearray(self.make_cover().to_bytes())
        encoded[-1] ^= 1
        with self.assertRaisesRegex(CoverFormatError, "CRC-32"):
            Cover.from_bytes(bytes(encoded))

    def test_wrong_version_and_dimensions_are_rejected(self):
        encoded = bytearray(self.make_cover().to_bytes())
        fields = list(HEADER.unpack_from(encoded))
        fields[1] = VERSION + 1
        encoded[:HEADER_SIZE] = HEADER.pack(*fields)
        with self.assertRaisesRegex(CoverFormatError, "version"):
            Cover.from_bytes(bytes(encoded))

        encoded = bytearray(self.make_cover().to_bytes())
        fields = list(HEADER.unpack_from(encoded))
        fields[4] = WIDTH + 1
        encoded[:HEADER_SIZE] = HEADER.pack(*fields)
        with self.assertRaisesRegex(CoverFormatError, "exactly"):
            Cover.from_bytes(bytes(encoded))

    def test_trailing_bytes_are_rejected(self):
        with self.assertRaisesRegex(CoverFormatError, "expected"):
            Cover.from_bytes(self.make_cover().to_bytes() + b"extra")

    def test_out_of_range_pixel_is_rejected_even_with_valid_crc(self):
        encoded = bytearray(self.make_cover().to_bytes())
        fields = list(HEADER.unpack_from(encoded))
        palette_bytes = fields[9]
        encoded[HEADER_SIZE + palette_bytes] = PALETTE_BASE + fields[6]
        payload = bytes(encoded[HEADER_SIZE:])
        fields[11] = zlib.crc32(payload) & 0xFFFFFFFF
        encoded[:HEADER_SIZE] = HEADER.pack(*fields)
        with self.assertRaisesRegex(CoverFormatError, "pixel indices"):
            Cover.from_bytes(bytes(encoded))

    def test_converter_stays_inside_reserved_palette_range(self):
        cover = self.make_cover()
        self.assertLessEqual(len(cover.palette), MAX_PALETTE_COLORS)
        self.assertGreaterEqual(min(cover.pixels), PALETTE_BASE)
        self.assertLessEqual(
            max(cover.pixels), PALETTE_BASE + len(cover.palette) - 1
        )
        self.assertTrue(all(color <= 0x7FFF for color in cover.palette))


if __name__ == "__main__":
    unittest.main()
