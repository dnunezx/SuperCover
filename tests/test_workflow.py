import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from supercover import (  # noqa: E402
    ArtworkCandidate,
    ArtworkDownload,
    ArtworkNotFound,
    CatalogEntry,
    MatchResult,
    MatchStatus,
    RomFile,
)
from supercover.workflow import (  # noqa: E402
    CoverSession,
    merge_catalogs,
    prepare_session_artwork,
)


def make_rom(name: str) -> RomFile:
    return RomFile(
        path=Path("C:/Games") / f"{name}.gba",
        relative_path=Path(f"{name}.gba"),
        filename=f"{name}.gba",
        stem=name,
        size=16,
        crc32="12345678",
        sha1="1" * 40,
    )


def automatic_match(name: str) -> MatchResult:
    entry = CatalogEntry(name)
    return MatchResult(
        make_rom(name),
        MatchStatus.AUTOMATIC,
        entry,
        "exact name",
        1.0,
        "Exact normalized filename match.",
    )


class FakeProvider:
    def __init__(self, image_path: Path, missing: set[str] | None = None):
        self.image_path = image_path
        self.missing = missing or set()
        self.requested = []

    def download_for_title(self, title: str):
        self.requested.append(title)
        if title in self.missing:
            raise ArtworkNotFound(f"no art for {title}")
        candidate = ArtworkCandidate("Test", title, f"{title}.png", "https://example/art", "https://example")
        return ArtworkDownload(candidate, self.image_path, False, 96, 80)


class DesktopWorkflowTest(unittest.TestCase):
    def test_automatic_games_start_included_but_reviews_start_skipped(self):
        automatic = automatic_match("Metal Slug Advance (USA)")
        suggestion = CatalogEntry("Legend of Zelda, The - The Minish Cap (USA)")
        review = MatchResult(
            make_rom("Minish Cap"),
            MatchStatus.REVIEW,
            suggestion,
            "fuzzy name",
            0.9,
            "Possible title match; user approval is required.",
        )

        session = CoverSession([automatic, review], [automatic.entry, suggestion])

        self.assertTrue(session.games[0].included)
        self.assertTrue(session.games[0].approved)
        self.assertFalse(session.games[1].included)
        self.assertFalse(session.games[1].approved)
        self.assertEqual(session.included_count, 1)

    def test_manual_title_approval_is_visible_and_exportable(self):
        match = MatchResult(
            make_rom("Unknown Name"),
            MatchStatus.UNMATCHED,
            None,
            None,
            0.0,
            "No catalog match found.",
        )
        session = CoverSession([match], [])

        session.approve_title(0, "Correct Game (USA)")
        approved = session.games[0].approved_match()

        self.assertTrue(session.games[0].included)
        self.assertEqual(session.games[0].status_label, "Approved")
        self.assertEqual(approved.entry.name, "Correct Game (USA)")
        self.assertEqual(approved.method, "user approved")
        self.assertEqual(approved.rom.filename, "Unknown Name.gba")

    def test_unapproved_game_cannot_be_included(self):
        match = MatchResult(
            make_rom("Unknown"),
            MatchStatus.UNMATCHED,
            None,
            None,
            0.0,
            "No catalog match found.",
        )
        session = CoverSession([match], [])

        with self.assertRaisesRegex(ValueError, "approve"):
            session.toggle_included(0)

    def test_trusted_catalog_replaces_provider_duplicate_and_retains_hashes(self):
        trusted = CatalogEntry("Metal Slug Advance (USA)", crc32="ABCDEF12", sha1="2" * 40)

        catalog = merge_catalogs(
            ["Metal Slug Advance (USA).png", "Another Game (USA).png"],
            [trusted],
        )

        by_name = {entry.name: entry for entry in catalog}
        self.assertEqual(len(catalog), 2)
        self.assertIs(by_name["Metal Slug Advance (USA)"], trusted)

    def test_preparation_downloads_only_selected_games_and_creates_previews(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "art.png"
            Image.new("RGB", (96, 80), (40, 120, 210)).save(image_path)
            first = automatic_match("Metal Slug Advance (USA)")
            second = automatic_match("Another Game (USA)")
            session = CoverSession([first, second], [first.entry, second.entry])
            session.games[1].set_included(False)
            provider = FakeProvider(image_path)

            summary = prepare_session_artwork(session, provider)

            self.assertEqual(summary.prepared, 1)
            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.skipped, 1)
            self.assertEqual(provider.requested, ["Metal Slug Advance (USA)"])
            self.assertTrue(session.games[0].preview_png.startswith(b"\x89PNG"))
            self.assertIsNone(session.games[1].artwork)
            self.assertEqual(len(session.export_requests()), 1)

    def test_one_missing_artwork_does_not_hide_other_ready_games(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "art.png"
            Image.new("RGB", (96, 80), (40, 120, 210)).save(image_path)
            first = automatic_match("Missing Game (USA)")
            second = automatic_match("Working Game (USA)")
            session = CoverSession([first, second], [first.entry, second.entry])
            provider = FakeProvider(image_path, {"Missing Game (USA)"})

            summary = prepare_session_artwork(session, provider)

            self.assertEqual(summary.prepared, 1)
            self.assertEqual(summary.failed, 1)
            self.assertTrue(session.games[0].artwork_message.startswith("Error:"))
            self.assertIsNotNone(session.games[1].artwork)
            self.assertEqual(len(session.export_requests()), 1)


if __name__ == "__main__":
    unittest.main()
