import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from supercover import (  # noqa: E402
    ArtworkNotFound,
    DownloadCancelled,
    HttpClient,
    InvalidArtwork,
    LibretroProvider,
    NetworkError,
    OfflineUnavailable,
    thumbnail_filename,
    validate_png,
)
from supercover.libretro import BOXART_INDEX_URL, parse_boxart_index  # noqa: E402


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def make_png(width: int = 2, height: int = 1) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = b"\x00" + b"\x20\x40\x60" * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(pixels * height))
        + png_chunk(b"IEND", b"")
    )


class FakeResponse:
    def __init__(self, data: bytes, url: str = "https://example.test/data", headers=None):
        self.stream = io.BytesIO(data)
        self.url = url
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1):
        return self.stream.read(size)

    def geturl(self):
        return self.url


class ScriptedOpener:
    def __init__(self, *results):
        self.results = list(results)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request.full_url, timeout))
        if not self.results:
            raise AssertionError("unexpected network request")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


INDEX_HTML = """<!doctype html><html><body>
<a href="Metal%20Slug%20Advance%20%28USA%29.png">Metal Slug Advance (USA).png</a>
<a href="Legend%20of%20Zelda%2C%20The%20-%20The%20Minish%20Cap%20%28USA%29.png">
Legend of Zelda, The - The Minish Cap (USA).png</a>
<a href="Lilo%20_%20Stitch%202%20%28USA%29.png">Lilo _ Stitch 2 (USA).png</a>
</body></html>""".encode()


class LibretroProviderTest(unittest.TestCase):
    def client(self, opener, **kwargs):
        return HttpClient(opener=opener, sleeper=lambda _: None, **kwargs)

    def test_thumbnail_filename_follows_libretro_character_rules(self):
        self.assertEqual(
            thumbnail_filename("Lilo & Stitch 2 (USA).gba"),
            "Lilo _ Stitch 2 (USA).png",
        )
        self.assertEqual(
            thumbnail_filename('Game: "One"? (USA)'),
            "Game_ _One__ (USA).png",
        )

    def test_index_parser_decodes_png_links_and_ignores_other_files(self):
        names = parse_boxart_index(INDEX_HTML + b'<a href="readme.txt">readme</a>')
        self.assertEqual(
            names,
            (
                "Metal Slug Advance (USA).png",
                "Legend of Zelda, The - The Minish Cap (USA).png",
                "Lilo _ Stitch 2 (USA).png",
            ),
        )

    def test_find_fetches_and_caches_the_curated_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            opener = ScriptedOpener(
                FakeResponse(INDEX_HTML, BOXART_INDEX_URL, {"Content-Type": "text/html"})
            )
            provider = LibretroProvider(temp_dir, http=self.client(opener), clock=lambda: 1000)
            candidate = provider.find("Metal Slug Advance (USA)")

            self.assertEqual(candidate.filename, "Metal Slug Advance (USA).png")
            self.assertIn("Metal%20Slug%20Advance", candidate.url)
            self.assertEqual(len(opener.requests), 1)

            offline = LibretroProvider(temp_dir, offline=True, clock=lambda: 2000)
            cached_candidate = offline.find("Metal Slug Advance (USA)")
            self.assertEqual(cached_candidate, candidate)

    def test_stale_index_is_used_when_refresh_network_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "libretro-gba-boxarts.json"
            cache.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "source": BOXART_INDEX_URL,
                        "fetched_at": 1,
                        "filenames": ["Metal Slug Advance (USA).png"],
                    }
                ),
                encoding="utf-8",
            )
            opener = ScriptedOpener(URLError("offline"))
            provider = LibretroProvider(
                temp_dir,
                http=self.client(opener, retries=0),
                index_max_age=0,
                clock=lambda: 1000,
            )
            self.assertEqual(
                provider.find("Metal Slug Advance (USA)").filename,
                "Metal Slug Advance (USA).png",
            )

    def test_cancellation_is_not_hidden_by_a_stale_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "libretro-gba-boxarts.json"
            cache.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "source": BOXART_INDEX_URL,
                        "fetched_at": 1,
                        "filenames": ["Metal Slug Advance (USA).png"],
                    }
                ),
                encoding="utf-8",
            )
            opener = ScriptedOpener(FakeResponse(INDEX_HTML))
            provider = LibretroProvider(
                temp_dir,
                http=self.client(opener, cancelled=lambda: True),
                index_max_age=0,
                clock=lambda: 1000,
            )
            with self.assertRaises(DownloadCancelled):
                provider.find("Metal Slug Advance (USA)")
            self.assertEqual(opener.requests, [])

    def test_offline_without_an_index_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(OfflineUnavailable):
                LibretroProvider(temp_dir, offline=True).find("Metal Slug Advance (USA)")

    def test_missing_exact_title_is_not_fuzzily_guessed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            opener = ScriptedOpener(FakeResponse(INDEX_HTML))
            provider = LibretroProvider(temp_dir, http=self.client(opener))
            with self.assertRaises(ArtworkNotFound):
                provider.find("Metal Slug Advance European Edition")

    def test_artwork_download_is_validated_cached_and_attributed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            png = make_png(2, 1)
            opener = ScriptedOpener(FakeResponse(INDEX_HTML), FakeResponse(png))
            provider = LibretroProvider(temp_dir, http=self.client(opener))
            downloaded = provider.download_for_title("Metal Slug Advance (USA)")

            self.assertFalse(downloaded.from_cache)
            self.assertEqual((downloaded.width, downloaded.height), (2, 1))
            self.assertEqual(downloaded.path.read_bytes(), png)
            self.assertEqual(downloaded.candidate.provider, "Libretro GBA Thumbnails")

            offline = LibretroProvider(temp_dir, offline=True)
            cached = offline.download(downloaded.candidate)
            self.assertTrue(cached.from_cache)
            self.assertEqual(cached.path, downloaded.path)

    def test_invalid_download_never_creates_a_cache_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            opener = ScriptedOpener(FakeResponse(INDEX_HTML), FakeResponse(b"not a PNG"))
            provider = LibretroProvider(temp_dir, http=self.client(opener))
            with self.assertRaises(InvalidArtwork):
                provider.download_for_title("Metal Slug Advance (USA)")
            artwork_dir = Path(temp_dir) / "artwork"
            self.assertEqual(list(artwork_dir.rglob("*.png")) if artwork_dir.exists() else [], [])

    def test_disappeared_artwork_returns_not_found_without_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            error = HTTPError("https://example.test/missing", 404, "missing", {}, None)
            opener = ScriptedOpener(FakeResponse(INDEX_HTML), error)
            provider = LibretroProvider(temp_dir, http=self.client(opener))
            with self.assertRaises(ArtworkNotFound):
                provider.download_for_title("Metal Slug Advance (USA)")
            self.assertEqual(len(opener.requests), 2)

    def test_png_validation_rejects_corrupt_checksum_and_trailing_data(self):
        valid = make_png()
        validate_png(valid)
        corrupt = bytearray(valid)
        corrupt[-5] ^= 1
        with self.assertRaisesRegex(InvalidArtwork, "checksum"):
            validate_png(bytes(corrupt))
        with self.assertRaisesRegex(InvalidArtwork, "after"):
            validate_png(valid + b"extra")

    def test_png_validation_rejects_bad_compressed_data_with_valid_chunk_crc(self):
        header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        invalid = (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", header)
            + png_chunk(b"IDAT", b"not zlib data")
            + png_chunk(b"IEND", b"")
        )
        with self.assertRaisesRegex(InvalidArtwork, "compressed"):
            validate_png(invalid)

    def test_http_client_retries_temporary_errors(self):
        opener = ScriptedOpener(
            URLError("temporary one"),
            URLError("temporary two"),
            FakeResponse(b"success"),
        )
        payload = self.client(opener, retries=2).get("https://example.test/data")
        self.assertEqual(payload.data, b"success")
        self.assertEqual(len(opener.requests), 3)

    def test_http_client_cancellation_prevents_network_access(self):
        opener = ScriptedOpener(FakeResponse(b"unused"))
        client = self.client(opener, cancelled=lambda: True)
        with self.assertRaises(DownloadCancelled):
            client.get("https://example.test/data")
        self.assertEqual(opener.requests, [])

    def test_http_client_rejects_oversized_response_before_reading(self):
        opener = ScriptedOpener(
            FakeResponse(b"small", headers={"Content-Length": "999"})
        )
        with self.assertRaisesRegex(NetworkError, "exceeds"):
            self.client(opener, max_bytes=10).get("https://example.test/data")

    def test_http_client_rejects_zero_per_request_limit(self):
        opener = ScriptedOpener(FakeResponse(b"unused"))
        with self.assertRaisesRegex(ValueError, "positive"):
            self.client(opener).get("https://example.test/data", max_bytes=0)
        self.assertEqual(opener.requests, [])


if __name__ == "__main__":
    unittest.main()
