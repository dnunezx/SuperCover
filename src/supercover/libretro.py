"""Curated Libretro Game Boy Advance box-art provider."""

from __future__ import annotations

import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from urllib.parse import quote, unquote, urlsplit

from .artwork import (
    ArtworkCandidate,
    ArtworkDownload,
    ArtworkNotFound,
    InvalidArtwork,
    OfflineUnavailable,
    validate_png,
)
from .network import DownloadCancelled, HttpClient, HttpStatusError, NetworkError
from .storage import write_atomic


PROVIDER_NAME = "Libretro GBA Thumbnails"
PROVIDER_URL = "https://github.com/libretro-thumbnails/Nintendo_-_Game_Boy_Advance"
BOXART_INDEX_URL = (
    "https://thumbnails.libretro.com/"
    "Nintendo%20-%20Game%20Boy%20Advance/Named_Boxarts/"
)
INDEX_CACHE_VERSION = 1
DEFAULT_INDEX_MAX_AGE = 7 * 24 * 60 * 60
INDEX_MAX_BYTES = 8 * 1024 * 1024
INVALID_THUMBNAIL_CHARACTERS = frozenset('&*/:`"<>?\\|')


class _IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.filenames: list[str] = []
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "a":
            return
        href = next((value for name, value in attrs if name.casefold() == "href"), None)
        if not href:
            return
        path = urlsplit(href).path
        filename = unescape(unquote(path.rsplit("/", 1)[-1]))
        if filename.casefold().endswith(".png") and filename not in self._seen:
            self._seen.add(filename)
            self.filenames.append(filename)


def thumbnail_filename(title: str) -> str:
    """Map a canonical game title to Libretro's safe PNG filename."""

    stripped = title[:-4] if title.casefold().endswith(".gba") else title
    safe_title = "".join(
        "_" if character in INVALID_THUMBNAIL_CHARACTERS else character
        for character in stripped
    )
    return f"{safe_title}.png"


def parse_boxart_index(html: bytes) -> tuple[str, ...]:
    """Extract PNG filenames from Libretro's directory listing."""

    try:
        text = html.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NetworkError("Libretro artwork index is not valid UTF-8") from exc
    parser = _IndexParser()
    parser.feed(text)
    parser.close()
    if not parser.filenames:
        raise NetworkError("Libretro artwork index contains no PNG files")
    return tuple(parser.filenames)


class LibretroProvider:
    """Lookup and cache exact GBA box-art matches from Libretro."""

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        http: HttpClient | None = None,
        offline: bool = False,
        index_max_age: int = DEFAULT_INDEX_MAX_AGE,
        clock=time.time,
    ):
        if index_max_age < 0:
            raise ValueError("index_max_age cannot be negative")
        self.cache_dir = Path(cache_dir)
        self.http = http or HttpClient()
        self.offline = offline
        self.index_max_age = index_max_age
        self.clock = clock
        self.index_cache_path = self.cache_dir / "libretro-gba-boxarts.json"
        self.artwork_cache_dir = self.cache_dir / "artwork" / "libretro-gba"
        self._loaded_index: tuple[str, ...] | None = None
        self._filename_lookup: dict[str, str] | None = None

    def _remember_index(self, filenames: tuple[str, ...]) -> tuple[str, ...]:
        self._loaded_index = filenames
        self._filename_lookup = {
            filename.casefold(): filename for filename in filenames
        }
        return filenames

    def _read_cached_index(self) -> tuple[float, tuple[str, ...]] | None:
        try:
            data = json.loads(self.index_cache_path.read_text(encoding="utf-8"))
            if data.get("version") != INDEX_CACHE_VERSION:
                return None
            fetched_at = float(data["fetched_at"])
            filenames = tuple(data["filenames"])
            if not filenames or not all(
                isinstance(name, str) and name.casefold().endswith(".png")
                for name in filenames
            ):
                return None
            return fetched_at, filenames
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def _write_index(self, filenames: tuple[str, ...]) -> None:
        payload = json.dumps(
            {
                "version": INDEX_CACHE_VERSION,
                "source": BOXART_INDEX_URL,
                "fetched_at": self.clock(),
                "filenames": list(filenames),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        write_atomic(self.index_cache_path, payload)

    def load_index(self, *, refresh: bool = False) -> tuple[str, ...]:
        """Load a fresh index, falling back to a valid stale cache on failure."""

        if self._loaded_index is not None and not refresh:
            return self._loaded_index

        cached = self._read_cached_index()
        if self.offline:
            if cached is None:
                raise OfflineUnavailable("Libretro index is not available in the local cache")
            return self._remember_index(cached[1])

        if cached is not None and not refresh:
            fetched_at, filenames = cached
            if self.clock() - fetched_at <= self.index_max_age:
                return self._remember_index(filenames)

        try:
            payload = self.http.get(BOXART_INDEX_URL, max_bytes=INDEX_MAX_BYTES)
            filenames = parse_boxart_index(payload.data)
            self._write_index(filenames)
            return self._remember_index(filenames)
        except DownloadCancelled:
            raise
        except NetworkError:
            if cached is not None:
                return self._remember_index(cached[1])
            raise

    def find(self, title: str, *, refresh_index: bool = False) -> ArtworkCandidate:
        """Find an exact curated box-art entry for a canonical title."""

        expected = thumbnail_filename(title)
        self.load_index(refresh=refresh_index)
        assert self._filename_lookup is not None
        actual = self._filename_lookup.get(expected.casefold())
        if actual is None:
            raise ArtworkNotFound(f"Libretro has no exact box art for {title!r}")
        return ArtworkCandidate(
            provider=PROVIDER_NAME,
            title=title,
            filename=actual,
            url=BOXART_INDEX_URL + quote(actual, safe=""),
            provider_url=PROVIDER_URL,
        )

    def _artwork_path(self, candidate: ArtworkCandidate) -> Path:
        digest = hashlib.sha256(candidate.url.encode("utf-8")).hexdigest()
        return self.artwork_cache_dir / f"{digest}.png"

    def download(
        self,
        candidate: ArtworkCandidate,
        *,
        refresh: bool = False,
    ) -> ArtworkDownload:
        """Return validated cached artwork or atomically cache a download."""

        path = self._artwork_path(candidate)
        if path.is_file() and not refresh:
            try:
                data = path.read_bytes()
                width, height = validate_png(data)
                return ArtworkDownload(candidate, path, True, width, height)
            except (OSError, InvalidArtwork):
                if self.offline:
                    raise InvalidArtwork("cached artwork is unreadable or invalid")

        if self.offline:
            raise OfflineUnavailable(f"artwork is not cached for {candidate.title!r}")

        try:
            payload = self.http.get(candidate.url)
        except HttpStatusError as exc:
            if exc.status == 404:
                raise ArtworkNotFound(
                    f"Libretro artwork disappeared for {candidate.title!r}"
                ) from exc
            raise
        width, height = validate_png(payload.data)
        write_atomic(path, payload.data)
        return ArtworkDownload(candidate, path, False, width, height)

    def download_for_title(
        self,
        title: str,
        *,
        refresh_index: bool = False,
        refresh_artwork: bool = False,
    ) -> ArtworkDownload:
        candidate = self.find(title, refresh_index=refresh_index)
        return self.download(candidate, refresh=refresh_artwork)
