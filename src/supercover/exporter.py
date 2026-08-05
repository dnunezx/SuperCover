"""Safe user-selected export of matched artwork as SuperFW cover files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import io
import json
from pathlib import Path
from typing import Iterable

from .artwork import ArtworkDownload, InvalidArtwork, validate_png
from .converter import cover_to_image, image_bytes_to_cover
from .models import MatchResult, MatchStatus
from .sfcov import Cover, VERSION, WIDTH
from .storage import write_atomic


MANIFEST_FILENAME = ".supercover-export.json"
MANIFEST_VERSION = 1


class ExportError(Exception):
    """A cover batch could not be exported safely."""


class ExportCollision(ExportError):
    """Multiple ROMs require the same firmware-visible cover filename."""


class ExistingFilePolicy(str, Enum):
    SKIP = "skip"
    REPLACE = "replace"
    KEEP_BOTH = "keep-both"


class ExportStatus(str, Enum):
    EXPORTED = "exported"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ExportRequest:
    match: MatchResult
    artwork: ArtworkDownload


@dataclass(frozen=True)
class ExportResult:
    request: ExportRequest
    status: ExportStatus
    path: Path
    preview_path: Path | None
    palette_colors: int | None
    file_size: int | None
    message: str


@dataclass(frozen=True)
class _ExportPlan:
    request: ExportRequest
    path: Path
    preview_path: Path | None
    skip: bool
    write_preview: bool


def _validate_request(request: ExportRequest) -> None:
    match = request.match
    if match.status != MatchStatus.AUTOMATIC or match.entry is None:
        raise ExportError("only automatic catalog matches may be exported")
    if request.artwork.candidate.title != match.entry.name:
        raise ExportError("artwork title does not match the identified game")


def _detect_rom_name_collisions(requests: tuple[ExportRequest, ...]) -> None:
    by_filename: dict[str, list[Path]] = {}
    for request in requests:
        filename = f"{request.match.rom.stem}.sfcov"
        by_filename.setdefault(filename.casefold(), []).append(
            request.match.rom.relative_path
        )
    collisions = {
        name: paths for name, paths in by_filename.items() if len(paths) > 1
    }
    if collisions:
        details = "; ".join(
            f"{name}: {', '.join(str(path) for path in paths)}"
            for name, paths in sorted(collisions.items())
        )
        raise ExportCollision(
            "multiple ROMs share a cover filename; choose which game to export: "
            + details
        )


def _choose_keep_both_path(
    export_dir: Path,
    preview_dir: Path | None,
    stem: str,
    reserved: set[str],
) -> tuple[Path, Path | None]:
    index = 1
    while True:
        alternate_stem = f"{stem} ({index})"
        cover = export_dir / f"{alternate_stem}.sfcov"
        preview = preview_dir / f"{alternate_stem}.png" if preview_dir else None
        keys = {str(cover).casefold()}
        if preview is not None:
            keys.add(str(preview).casefold())
        if (
            not cover.exists()
            and (preview is None or not preview.exists())
            and keys.isdisjoint(reserved)
        ):
            reserved.update(keys)
            return cover, preview
        index += 1


def _build_plans(
    requests: tuple[ExportRequest, ...],
    export_dir: Path,
    preview_dir: Path | None,
    policy: ExistingFilePolicy,
) -> tuple[_ExportPlan, ...]:
    reserved: set[str] = set()
    plans: list[_ExportPlan] = []
    for request in requests:
        stem = request.match.rom.stem
        cover = export_dir / f"{stem}.sfcov"
        preview = preview_dir / f"{stem}.png" if preview_dir else None

        if cover.exists() and policy == ExistingFilePolicy.SKIP:
            plans.append(_ExportPlan(request, cover, preview, True, False))
            continue
        if (
            policy == ExistingFilePolicy.KEEP_BOTH
            and (cover.exists() or (preview is not None and preview.exists()))
        ):
            cover, preview = _choose_keep_both_path(
                export_dir, preview_dir, stem, reserved
            )
        else:
            keys = {str(cover).casefold()}
            if preview is not None:
                keys.add(str(preview).casefold())
            if not keys.isdisjoint(reserved):
                raise ExportCollision(f"export destinations collide for {stem!r}")
            reserved.update(keys)

        write_preview = preview is not None and (
            policy != ExistingFilePolicy.SKIP or not preview.exists()
        )
        plans.append(_ExportPlan(request, cover, preview, False, write_preview))
    return tuple(plans)


def _read_manifest(path: Path) -> dict:
    if not path.exists():
        return {"version": MANIFEST_VERSION, "exports": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError(f"existing export manifest is unreadable: {path}") from exc
    if (
        not isinstance(data, dict)
        or data.get("version") != MANIFEST_VERSION
        or not isinstance(data.get("exports"), dict)
    ):
        raise ExportError(f"existing export manifest is unsupported: {path}")
    return data


def _preview_bytes(cover: Cover) -> bytes:
    stream = io.BytesIO()
    cover_to_image(cover).save(stream, format="PNG")
    return stream.getvalue()


def export_covers(
    requests: Iterable[ExportRequest],
    export_dir: str | Path,
    *,
    preview_dir: str | Path | None = None,
    existing: ExistingFilePolicy | str = ExistingFilePolicy.SKIP,
    mode: str = "cover",
    background: tuple[int, int, int] = (0, 0, 0),
    dither: str = "floyd-steinberg",
    size: int = WIDTH,
) -> list[ExportResult]:
    """Convert and export a batch only to the exact folders supplied by the user."""

    batch = tuple(requests)
    policy = ExistingFilePolicy(existing)
    destination = Path(export_dir).resolve()
    previews = Path(preview_dir).resolve() if preview_dir is not None else None
    for request in batch:
        _validate_request(request)
    _detect_rom_name_collisions(batch)

    manifest_path = destination / MANIFEST_FILENAME
    manifest = _read_manifest(manifest_path)
    plans = _build_plans(batch, destination, previews, policy)

    # Complete every decode and conversion before writing the first output.
    converted: dict[Path, tuple[Cover, bytes, bytes | None]] = {}
    try:
        for plan in plans:
            if plan.skip:
                continue
            source_data = plan.request.artwork.path.read_bytes()
            source_width, source_height = validate_png(source_data)
            if (source_width, source_height) != (
                plan.request.artwork.width,
                plan.request.artwork.height,
            ):
                raise ExportError("cached artwork dimensions changed after download")
            cover = image_bytes_to_cover(
                source_data,
                mode=mode,
                background=background,
                dither=dither,
                size=size,
            )
            encoded = cover.to_bytes()
            Cover.from_bytes(encoded)
            preview = _preview_bytes(cover) if plan.write_preview else None
            converted[plan.path] = (cover, encoded, preview)
    except ExportError:
        raise
    except (OSError, ValueError, InvalidArtwork) as exc:
        raise ExportError(f"cover conversion failed: {exc}") from exc

    exported_at = datetime.now(timezone.utc).isoformat()
    manifest_exports = dict(manifest["exports"])
    results: list[ExportResult] = []
    for plan in plans:
        if plan.skip:
            results.append(
                ExportResult(
                    plan.request,
                    ExportStatus.SKIPPED,
                    plan.path,
                    plan.preview_path,
                    None,
                    plan.path.stat().st_size if plan.path.is_file() else None,
                    "Existing cover preserved by the skip policy.",
                )
            )
            continue

        cover, encoded, preview = converted[plan.path]
        write_atomic(plan.path, encoded)
        if plan.preview_path is not None and preview is not None:
            write_atomic(plan.preview_path, preview)

        request = plan.request
        match = request.match
        artwork = request.artwork
        manifest_exports[plan.path.name] = {
            "rom_filename": match.rom.filename,
            "rom_relative_path": str(match.rom.relative_path),
            "rom_crc32": match.rom.crc32,
            "rom_sha1": match.rom.sha1,
            "match_title": match.entry.name,
            "match_method": match.method,
            "artwork_provider": artwork.candidate.provider,
            "artwork_provider_url": artwork.candidate.provider_url,
            "artwork_source_url": artwork.candidate.url,
            "artwork_source_filename": artwork.candidate.filename,
            "source_width": artwork.width,
            "source_height": artwork.height,
            "cover_sha256": hashlib.sha256(encoded).hexdigest().upper(),
            "format_version": VERSION,
            "width": cover.width,
            "height": cover.height,
            "palette_colors": len(cover.palette),
            "resize_mode": mode,
            "dither": dither,
            "exported_at": exported_at,
        }
        exact_name = plan.path.name == f"{match.rom.stem}.sfcov"
        message = (
            "Cover exported successfully."
            if exact_name
            else "Cover exported with a numbered comparison filename; it will not "
            "automatically match the ROM in SuperFW."
        )
        results.append(
            ExportResult(
                request,
                ExportStatus.EXPORTED,
                plan.path,
                plan.preview_path if preview is not None else None,
                len(cover.palette),
                len(encoded),
                message,
            )
        )

    if any(result.status == ExportStatus.EXPORTED for result in results):
        updated_manifest = {
            "version": MANIFEST_VERSION,
            "updated_at": exported_at,
            "exports": manifest_exports,
        }
        write_atomic(
            manifest_path,
            json.dumps(
                updated_manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8"),
        )
    return results
