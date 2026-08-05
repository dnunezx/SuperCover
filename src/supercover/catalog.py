"""Loading and validation for SuperCover's small Phase 1 JSON catalog."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .models import CatalogEntry


CRC32_PATTERN = re.compile(r"^[0-9A-F]{8}$")
SHA1_PATTERN = re.compile(r"^[0-9A-F]{40}$")


def _optional_hash(record: dict[str, Any], field: str, pattern: re.Pattern[str]) -> str | None:
    value = record.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"catalog {field} must be a string")
    normalized = value.strip().upper()
    if not pattern.fullmatch(normalized):
        raise ValueError(f"catalog {field} has an invalid value: {value!r}")
    return normalized


def load_catalog(path: str | Path) -> list[CatalogEntry]:
    """Load a JSON array of game names and optional CRC-32/SHA-1 hashes."""

    catalog_path = Path(path)
    with catalog_path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, list):
        raise ValueError("catalog root must be a JSON array")

    entries: list[CatalogEntry] = []
    for index, record in enumerate(data):
        if not isinstance(record, dict):
            raise ValueError(f"catalog entry {index} must be an object")
        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"catalog entry {index} requires a non-empty name")
        entries.append(
            CatalogEntry(
                name=name.strip(),
                crc32=_optional_hash(record, "crc32", CRC32_PATTERN),
                sha1=_optional_hash(record, "sha1", SHA1_PATTERN),
            )
        )
    return entries
