import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys
import zlib

# Keep the Phase 1 test suite runnable without installing the package first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from supercover import (  # noqa: E402
    CatalogEntry,
    MatchStatus,
    load_catalog,
    match_rom,
    normalize_title,
    scan_roms,
)


class SuperCoverTest(unittest.TestCase):
    def test_scanner_finds_nested_roms_and_hashes_in_chunks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_a = b"synthetic-metal-slug" * 13
            data_b = b"synthetic-minish-cap" * 17
            (root / "action").mkdir()
            (root / "action" / "Metal Slug Advance (USA).GBA").write_bytes(data_a)
            (root / "Legend of Zelda.gba").write_bytes(data_b)
            (root / "readme.txt").write_text("not a ROM", encoding="utf-8")

            roms = scan_roms(root, chunk_size=7)

            self.assertEqual(
                [rom.relative_path.as_posix() for rom in roms],
                ["action/Metal Slug Advance (USA).GBA", "Legend of Zelda.gba"],
            )
            self.assertEqual(roms[0].size, len(data_a))
            self.assertEqual(roms[0].crc32, f"{zlib.crc32(data_a):08X}")
            self.assertEqual(roms[0].sha1, hashlib.sha1(data_a).hexdigest().upper())

    def test_non_recursive_scan_ignores_nested_roms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "nested").mkdir()
            (root / "Top.gba").write_bytes(b"top")
            (root / "nested" / "Nested.gba").write_bytes(b"nested")
            self.assertEqual([rom.filename for rom in scan_roms(root, recursive=False)], ["Top.gba"])

    def test_scanner_rejects_missing_folder_and_bad_chunk_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(NotADirectoryError):
                scan_roms(root / "missing")
            with self.assertRaisesRegex(ValueError, "positive"):
                scan_roms(root, chunk_size=0)

    def test_catalog_loader_normalizes_hash_case(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "catalog.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "name": "Metal Slug Advance (USA)",
                            "crc32": "a1b2c3d4",
                            "sha1": "1" * 40,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            entry = load_catalog(path)[0]
            self.assertEqual(entry.crc32, "A1B2C3D4")
            self.assertEqual(entry.sha1, "1" * 40)

    def test_catalog_loader_rejects_malformed_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "catalog.json"
            path.write_text('[{"name": "Game", "crc32": "wrong"}]', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "crc32"):
                load_catalog(path)

    def _rom(self, name="Metal Slug Advance (USA).gba", crc32="11111111", sha1=None):
        from supercover import RomFile

        sha1 = sha1 or "2" * 40
        path = Path(name)
        return RomFile(path, path, path.name, path.stem, 123, crc32, sha1)

    def test_exact_normalized_name_is_automatic(self):
        rom = self._rom(name="METAL-SLUG advance (usa).gba")
        entry = CatalogEntry("Metal Slug Advance (USA)")
        result = match_rom(rom, [entry])
        self.assertEqual(result.status, MatchStatus.AUTOMATIC)
        self.assertEqual(result.entry, entry)
        self.assertEqual(result.method, "exact name")

    def test_sha1_recognizes_a_renamed_rom(self):
        rom = self._rom(name="my game.gba", sha1="A" * 40)
        entry = CatalogEntry("The Legend of Zelda - The Minish Cap (USA)", sha1="A" * 40)
        result = match_rom(rom, [entry])
        self.assertEqual(result.status, MatchStatus.AUTOMATIC)
        self.assertEqual(result.entry, entry)
        self.assertEqual(result.method, "SHA-1")

    def test_crc32_is_used_when_sha1_is_not_available(self):
        rom = self._rom(name="renamed.gba", crc32="ABCD1234")
        entry = CatalogEntry("Known Game", crc32="ABCD1234")
        result = match_rom(rom, [entry])
        self.assertEqual(result.status, MatchStatus.AUTOMATIC)
        self.assertEqual(result.method, "CRC-32")

    def test_conflicting_name_and_hash_require_review(self):
        rom = self._rom(name="Game One (USA).gba", sha1="F" * 40)
        by_name = CatalogEntry("Game One (USA)")
        by_hash = CatalogEntry("Game Two (USA)", sha1="F" * 40)
        result = match_rom(rom, [by_name, by_hash])
        self.assertEqual(result.status, MatchStatus.CONFLICT)
        self.assertIsNone(result.entry)
        self.assertEqual(set(result.alternatives), {by_name, by_hash})

    def test_fuzzy_match_is_never_automatic(self):
        rom = self._rom(name="Legend Zelda Minish Cap.gba")
        entry = CatalogEntry("Legend of Zelda, The - The Minish Cap (USA)")
        result = match_rom(rom, [entry])
        self.assertEqual(result.status, MatchStatus.REVIEW)
        self.assertEqual(result.entry, entry)
        self.assertEqual(result.method, "fuzzy name")

    def test_unrelated_game_is_unmatched(self):
        result = match_rom(self._rom(name="Completely Different.gba"), [CatalogEntry("Known Game")])
        self.assertEqual(result.status, MatchStatus.UNMATCHED)
        self.assertIsNone(result.entry)

    def test_normalization_handles_extension_punctuation_and_ampersand(self):
        self.assertEqual(normalize_title("Rock & Roll.GBA"), "rock and roll")


if __name__ == "__main__":
    unittest.main()
