import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from supercover import (  # noqa: E402
    ArtworkCandidate,
    ArtworkDownload,
    CatalogEntry,
    Cover,
    ExistingFilePolicy,
    ExportCollision,
    ExportError,
    ExportRequest,
    ExportStatus,
    MatchResult,
    MatchStatus,
    RomFile,
    cover_to_image,
    export_covers,
)
from supercover.exporter import MANIFEST_FILENAME  # noqa: E402
from supercover.sfcov import HEIGHT, LEGACY_SIZE, MAX_PALETTE_COLORS, WIDTH  # noqa: E402


class ExporterTest(unittest.TestCase):
    def make_request(
        self,
        root: Path,
        *,
        rom_name: str = "Metal Slug Advance (USA).gba",
        title: str = "Metal Slug Advance (USA)",
        artwork_name: str = "artwork.png",
        size: tuple[int, int] = (256, 229),
        color: tuple[int, int, int] = (220, 30, 20),
    ) -> ExportRequest:
        rom_path = root / "roms" / rom_name
        rom_path.parent.mkdir(parents=True, exist_ok=True)
        if not rom_path.exists():
            rom_path.write_bytes(b"synthetic ROM data")
        rom_data = rom_path.read_bytes()
        rom = RomFile(
            path=rom_path,
            relative_path=Path(rom_name),
            filename=rom_name,
            stem=Path(rom_name).stem,
            size=len(rom_data),
            crc32="1234ABCD",
            sha1=hashlib.sha1(rom_data).hexdigest().upper(),
        )
        entry = CatalogEntry(title)
        match = MatchResult(
            rom=rom,
            status=MatchStatus.AUTOMATIC,
            entry=entry,
            method="exact name",
            score=1.0,
            message="Exact normalized filename match.",
        )
        artwork_path = root / "cache" / artwork_name
        artwork_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color).save(artwork_path, format="PNG")
        candidate = ArtworkCandidate(
            provider="Libretro GBA Thumbnails",
            title=title,
            filename=f"{title}.png",
            url=f"https://thumbnails.example/{artwork_name}",
            provider_url="https://github.com/libretro-thumbnails/example",
        )
        artwork = ArtworkDownload(candidate, artwork_path, True, size[0], size[1])
        return ExportRequest(match, artwork)

    def test_exports_exact_rom_name_only_to_user_selected_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self.make_request(root)
            selected = root / "the folder I selected"
            rom_before = request.match.rom.path.read_bytes()

            result = export_covers([request], selected)[0]

            self.assertEqual(result.status, ExportStatus.EXPORTED)
            self.assertEqual(
                result.path,
                selected.resolve() / "Metal Slug Advance (USA).sfcov",
            )
            self.assertTrue(result.path.is_file())
            self.assertEqual(request.match.rom.path.read_bytes(), rom_before)
            cover = Cover.read(result.path)
            self.assertEqual((cover.width, cover.height), (WIDTH, HEIGHT))
            self.assertLessEqual(len(cover.palette), MAX_PALETTE_COLORS)

    def test_manifest_records_rom_artwork_conversion_and_checksum(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self.make_request(root)
            selected = root / "exports"
            result = export_covers([request], selected)[0]

            manifest = json.loads(
                (selected / MANIFEST_FILENAME).read_text(encoding="utf-8")
            )
            record = manifest["exports"][result.path.name]
            self.assertEqual(record["rom_filename"], request.match.rom.filename)
            self.assertEqual(record["artwork_provider"], "Libretro GBA Thumbnails")
            self.assertEqual(record["artwork_source_url"], request.artwork.candidate.url)
            self.assertEqual(record["format_version"], 2)
            self.assertEqual((record["width"], record["height"]), (77, 77))
            self.assertEqual(
                record["cover_sha256"],
                hashlib.sha256(result.path.read_bytes()).hexdigest().upper(),
            )

    def test_optional_preview_uses_exact_final_gba_colors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self.make_request(root, size=(300, 100))
            result = export_covers(
                [request],
                root / "exports",
                preview_dir=root / "previews",
                mode="contain",
            )[0]

            self.assertEqual(
                result.preview_path,
                (root / "previews" / "Metal Slug Advance (USA).png").resolve(),
            )
            with Image.open(result.preview_path) as preview:
                self.assertEqual(preview.size, (WIDTH, HEIGHT))
                self.assertEqual(
                    preview.convert("RGB").tobytes(),
                    cover_to_image(Cover.read(result.path)).tobytes(),
                )

    def test_legacy_72_pixel_export_is_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self.make_request(root)

            result = export_covers(
                [request],
                root / "exports",
                preview_dir=root / "previews",
                size=LEGACY_SIZE,
            )[0]

            cover = Cover.read(result.path)
            self.assertEqual((cover.width, cover.height), (72, 72))
            with Image.open(result.preview_path) as preview:
                self.assertEqual(preview.size, (72, 72))

    def test_skip_policy_preserves_existing_cover_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self.make_request(root)
            selected = root / "exports"
            selected.mkdir()
            existing = selected / "Metal Slug Advance (USA).sfcov"
            existing.write_bytes(b"user's existing cover")

            result = export_covers([request], selected)[0]

            self.assertEqual(result.status, ExportStatus.SKIPPED)
            self.assertEqual(existing.read_bytes(), b"user's existing cover")
            self.assertFalse((selected / MANIFEST_FILENAME).exists())

    def test_replace_policy_atomically_writes_a_valid_cover(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self.make_request(root)
            selected = root / "exports"
            selected.mkdir()
            existing = selected / "Metal Slug Advance (USA).sfcov"
            existing.write_bytes(b"old")

            result = export_covers(
                [request], selected, existing=ExistingFilePolicy.REPLACE
            )[0]

            self.assertEqual(result.status, ExportStatus.EXPORTED)
            Cover.read(existing)
            self.assertEqual(list(selected.glob("*.tmp")), [])

    def test_keep_both_uses_a_distinct_non_firmware_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self.make_request(root)
            selected = root / "exports"
            previews = root / "previews"
            selected.mkdir()
            previews.mkdir()
            (selected / "Metal Slug Advance (USA).sfcov").write_bytes(b"existing")
            (previews / "Metal Slug Advance (USA) (1).png").write_bytes(b"existing")

            result = export_covers(
                [request],
                selected,
                preview_dir=previews,
                existing=ExistingFilePolicy.KEEP_BOTH,
            )[0]

            self.assertEqual(result.path.name, "Metal Slug Advance (USA) (2).sfcov")
            self.assertEqual(result.preview_path.name, "Metal Slug Advance (USA) (2).png")
            self.assertEqual(
                (selected / "Metal Slug Advance (USA).sfcov").read_bytes(),
                b"existing",
            )

    def test_duplicate_firmware_names_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = self.make_request(root, artwork_name="one.png")
            second = self.make_request(
                root,
                rom_name="metal slug advance (usa).GBA",
                title="Metal Slug Advance Alternate",
                artwork_name="two.png",
            )
            selected = root / "exports"

            with self.assertRaises(ExportCollision):
                export_covers([first, second], selected)
            self.assertFalse(selected.exists())

    def test_one_bad_image_prevents_every_conversion_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid = self.make_request(root, artwork_name="valid.png")
            invalid = self.make_request(
                root,
                rom_name="Another Game (USA).gba",
                title="Another Game (USA)",
                artwork_name="invalid.png",
            )
            invalid.artwork.path.write_bytes(b"broken download")
            selected = root / "exports"

            with self.assertRaises(ExportError):
                export_covers([valid, invalid], selected)
            self.assertFalse(selected.exists())

    def test_mismatched_artwork_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = self.make_request(root)
            wrong_candidate = ArtworkCandidate(
                provider=request.artwork.candidate.provider,
                title="Wrong Game",
                filename="Wrong Game.png",
                url=request.artwork.candidate.url,
                provider_url=request.artwork.candidate.provider_url,
            )
            wrong = ExportRequest(
                request.match,
                ArtworkDownload(
                    wrong_candidate,
                    request.artwork.path,
                    True,
                    request.artwork.width,
                    request.artwork.height,
                ),
            )

            with self.assertRaisesRegex(ExportError, "does not match"):
                export_covers([wrong], root / "exports")


if __name__ == "__main__":
    unittest.main()
