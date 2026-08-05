"""State and background operations shared by the SuperCover desktop app."""

from __future__ import annotations

from dataclasses import dataclass, replace
import io
from pathlib import Path
from typing import Callable, Iterable

from .artwork import ArtworkDownload, ArtworkError
from .converter import cover_to_image, image_bytes_to_cover
from .exporter import ExportRequest, ExportResult
from .libretro import LibretroProvider
from .matching import normalize_title
from .models import CatalogEntry, MatchResult, MatchStatus
from .network import DownloadCancelled, NetworkError


ProgressCallback = Callable[[int, int, str], None]
CancelledCallback = Callable[[], bool]


@dataclass
class GameChoice:
    """One visible game decision in the desktop review screen."""

    original: MatchResult
    selected_entry: CatalogEntry | None
    approved: bool
    included: bool
    artwork: ArtworkDownload | None = None
    preview_png: bytes | None = None
    artwork_message: str = "Not prepared"
    export_result: ExportResult | None = None

    @classmethod
    def from_match(cls, match: MatchResult) -> "GameChoice":
        automatic = match.status == MatchStatus.AUTOMATIC and match.entry is not None
        return cls(
            original=match,
            selected_entry=match.entry,
            approved=automatic,
            included=automatic,
        )

    @property
    def status_label(self) -> str:
        if self.approved and self.original.status != MatchStatus.AUTOMATIC:
            return "Approved"
        return self.original.status.value.title()

    def choose(self, entry: CatalogEntry) -> None:
        """Approve a visible manual selection and invalidate old artwork."""

        self.selected_entry = entry
        self.approved = True
        self.included = True
        self.artwork = None
        self.preview_png = None
        self.artwork_message = "Ready to prepare"
        self.export_result = None

    def set_included(self, included: bool) -> None:
        if included and (not self.approved or self.selected_entry is None):
            raise ValueError("Choose and approve an artwork title first.")
        self.included = included
        if not included:
            self.export_result = None

    def approved_match(self) -> MatchResult:
        if not self.included or not self.approved or self.selected_entry is None:
            raise ValueError("game is not approved for artwork preparation")
        if (
            self.original.status == MatchStatus.AUTOMATIC
            and self.selected_entry == self.original.entry
        ):
            return self.original
        return replace(
            self.original,
            status=MatchStatus.AUTOMATIC,
            entry=self.selected_entry,
            method="user approved",
            score=1.0,
            message="Artwork title approved by the user.",
            alternatives=(),
        )


class CoverSession:
    """Testable review state that contains no Tkinter objects."""

    def __init__(
        self,
        matches: Iterable[MatchResult],
        catalog: Iterable[CatalogEntry],
    ):
        self.games = [GameChoice.from_match(match) for match in matches]
        self.catalog = tuple(catalog)
        self._entries_by_title = {
            entry.name.casefold(): entry for entry in self.catalog
        }
        self.titles = tuple(
            sorted(
                (entry.name for entry in self._entries_by_title.values()),
                key=str.casefold,
            )
        )

    def approve_title(self, index: int, title: str) -> None:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("Enter or select an artwork title.")
        entry = self._entries_by_title.get(cleaned.casefold(), CatalogEntry(cleaned))
        self.games[index].choose(entry)

    def toggle_included(self, index: int) -> None:
        game = self.games[index]
        game.set_included(not game.included)

    @property
    def included_count(self) -> int:
        return sum(game.included for game in self.games)

    @property
    def prepared_count(self) -> int:
        return sum(game.included and game.artwork is not None for game in self.games)

    def export_requests(self) -> list[ExportRequest]:
        return [
            ExportRequest(game.approved_match(), game.artwork)
            for game in self.games
            if game.included and game.artwork is not None
        ]


def merge_catalogs(
    provider_filenames: Iterable[str],
    trusted_entries: Iterable[CatalogEntry] = (),
) -> list[CatalogEntry]:
    """Combine provider titles and a trusted catalog, preferring trusted hashes."""

    entries: dict[str, CatalogEntry] = {}
    for filename in provider_filenames:
        title = Path(filename).stem.strip()
        if title:
            entries.setdefault(normalize_title(title), CatalogEntry(title))
    for entry in trusted_entries:
        entries[normalize_title(entry.name)] = entry
    return sorted(entries.values(), key=lambda entry: entry.name.casefold())


def _preview_bytes(artwork: ArtworkDownload) -> bytes:
    source = artwork.path.read_bytes()
    cover = image_bytes_to_cover(source)
    stream = io.BytesIO()
    cover_to_image(cover).save(stream, format="PNG")
    return stream.getvalue()


@dataclass(frozen=True)
class PreparationSummary:
    prepared: int
    failed: int
    skipped: int


def prepare_session_artwork(
    session: CoverSession,
    provider: LibretroProvider,
    *,
    progress: ProgressCallback | None = None,
    cancelled: CancelledCallback | None = None,
) -> PreparationSummary:
    """Download and preview approved games while isolating per-game failures."""

    selected = [game for game in session.games if game.included]
    prepared = failed = 0
    is_cancelled = cancelled or (lambda: False)
    for position, game in enumerate(selected, start=1):
        if is_cancelled():
            raise DownloadCancelled("artwork preparation cancelled")
        assert game.selected_entry is not None
        if progress:
            progress(position - 1, len(selected), game.original.rom.filename)
        game.artwork = None
        game.preview_png = None
        game.export_result = None
        try:
            artwork = provider.download_for_title(game.selected_entry.name)
            game.artwork = artwork
            game.preview_png = _preview_bytes(artwork)
            game.artwork_message = "Ready (cached)" if artwork.from_cache else "Ready"
            prepared += 1
        except DownloadCancelled:
            raise
        except (ArtworkError, NetworkError, OSError, ValueError) as exc:
            game.artwork_message = f"Error: {exc}"
            failed += 1
    if progress:
        progress(len(selected), len(selected), "Artwork preparation complete")
    return PreparationSummary(
        prepared=prepared,
        failed=failed,
        skipped=len(session.games) - len(selected),
    )


def assign_export_results(
    session: CoverSession,
    results: Iterable[ExportResult],
) -> None:
    """Attach completed exports to their visible game rows."""

    by_rom = {result.request.match.rom.path: result for result in results}
    for game in session.games:
        game.export_result = by_rom.get(game.original.rom.path)
