"""Conservative offline matching for SuperCover."""

from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import re
import unicodedata
from typing import Iterable

from .models import CatalogEntry, MatchResult, MatchStatus, RomFile


METADATA_SUFFIX = re.compile(r"(?:\s*[\[(][^\])]*[\])])+$")
NON_ALPHANUMERIC = re.compile(r"[^\w]+", re.UNICODE)
FUZZY_REVIEW_THRESHOLD = 0.72
MAX_ALTERNATIVES = 3


def normalize_title(value: str, *, strip_metadata: bool = False) -> str:
    """Normalize harmless filename differences while retaining title words."""

    title = Path(value).stem if Path(value).suffix.casefold() == ".gba" else value
    if strip_metadata:
        title = METADATA_SUFFIX.sub("", title)
    title = unicodedata.normalize("NFKC", title).casefold().replace("&", " and ")
    return " ".join(NON_ALPHANUMERIC.sub(" ", title).split())


def _index_catalog(entries: Iterable[CatalogEntry]):
    names: dict[str, list[CatalogEntry]] = defaultdict(list)
    crc32s: dict[str, list[CatalogEntry]] = defaultdict(list)
    sha1s: dict[str, list[CatalogEntry]] = defaultdict(list)
    catalog = tuple(entries)
    for entry in catalog:
        names[normalize_title(entry.name)].append(entry)
        if entry.crc32:
            crc32s[entry.crc32.upper()].append(entry)
        if entry.sha1:
            sha1s[entry.sha1.upper()].append(entry)
    return catalog, names, crc32s, sha1s


def _unique(items: Iterable[CatalogEntry]) -> CatalogEntry | None:
    candidates = tuple(items)
    return candidates[0] if len(candidates) == 1 else None


def _fuzzy_candidates(rom: RomFile, entries: Iterable[CatalogEntry]):
    full = normalize_title(rom.stem)
    base = normalize_title(rom.stem, strip_metadata=True)
    scored: list[tuple[float, CatalogEntry]] = []
    for entry in entries:
        entry_full = normalize_title(entry.name)
        entry_base = normalize_title(entry.name, strip_metadata=True)
        score = max(
            SequenceMatcher(None, full, entry_full).ratio(),
            SequenceMatcher(None, base, entry_base).ratio(),
        )
        if score >= FUZZY_REVIEW_THRESHOLD:
            scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], normalize_title(item[1].name)))
    return scored[:MAX_ALTERNATIVES]


def match_rom(rom: RomFile, entries: Iterable[CatalogEntry]) -> MatchResult:
    """Match one ROM, never auto-accepting ambiguous or fuzzy evidence."""

    catalog, names, crc32s, sha1s = _index_catalog(entries)
    name_match = _unique(names.get(normalize_title(rom.stem), ()))
    sha1_match = _unique(sha1s.get(rom.sha1.upper(), ()))
    crc32_match = _unique(crc32s.get(rom.crc32.upper(), ()))

    hash_matches = {match for match in (sha1_match, crc32_match) if match is not None}
    hash_match = next(iter(hash_matches)) if len(hash_matches) == 1 else None
    conflicting_hashes = len(hash_matches) > 1

    if conflicting_hashes or (name_match and hash_match and name_match != hash_match):
        alternatives = tuple(
            dict.fromkeys(
                match for match in (sha1_match, crc32_match, name_match) if match is not None
            )
        )
        return MatchResult(
            rom=rom,
            status=MatchStatus.CONFLICT,
            entry=None,
            method="conflicting evidence",
            score=0.0,
            message="Filename and checksum evidence point to different games.",
            alternatives=alternatives,
        )

    if hash_match is not None:
        method = "SHA-1" if sha1_match == hash_match else "CRC-32"
        return MatchResult(
            rom=rom,
            status=MatchStatus.AUTOMATIC,
            entry=hash_match,
            method=method,
            score=1.0,
            message=f"Unique {method} match.",
        )

    if name_match is not None:
        return MatchResult(
            rom=rom,
            status=MatchStatus.AUTOMATIC,
            entry=name_match,
            method="exact name",
            score=1.0,
            message="Exact normalized filename match.",
        )

    fuzzy = _fuzzy_candidates(rom, catalog)
    if fuzzy:
        best_score, best_entry = fuzzy[0]
        return MatchResult(
            rom=rom,
            status=MatchStatus.REVIEW,
            entry=best_entry,
            method="fuzzy name",
            score=best_score,
            message="Possible title match; user approval is required.",
            alternatives=tuple(entry for _, entry in fuzzy[1:]),
        )

    return MatchResult(
        rom=rom,
        status=MatchStatus.UNMATCHED,
        entry=None,
        method=None,
        score=0.0,
        message="No catalog match found.",
    )


def match_roms(roms: Iterable[RomFile], entries: Iterable[CatalogEntry]) -> list[MatchResult]:
    """Match an inventory while safely reusing a one-shot catalog iterable."""

    catalog = tuple(entries)
    return [match_rom(rom, catalog) for rom in roms]
