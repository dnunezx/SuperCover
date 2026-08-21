<!-- Copyright (C) 2026 Danny Nunez (dnunezx) -->

# SuperCover

SuperCover is the portable Windows cover-art companion built for
[SuperR7](https://github.com/dnunezx/SuperR7). It scans a folder of Game Boy
Advance ROMs, identifies each game, finds curated box art, converts it to
SuperR7's compact `.sfcov` format, and installs it with the exact filename the
firmware expects.

SuperCover is in early development. Phases 1-5 provide the safe ROM scanner,
matching engine, curated Libretro artwork provider, hardware-compatible
`.sfcov` exporter, responsive Windows desktop interface, and portable x64
executable. The user always chooses where exported files go.

The current `0.6.0-rc.2` preview introduces a full dark interface using
SuperCover's blue-and-gold identity while retaining the review-first workflow
and high-contrast match states.

## Safety principles

- ROMs are read only for their filename, size, CRC-32, and SHA-1.
- ROM files are never modified, renamed, deleted, copied, uploaded, or bundled.
- Exact names and unique checksums may be matched automatically.
- Fuzzy matches always require manual review.
- Conflicting evidence is reported instead of guessed.
- Cover art packs are not distributed with the application.

## Portable Windows app

The current preview release provides
`SuperCover-0.6.0-rc.2-windows-x64.zip`. Download and extract that archive,
then double-click `SuperCover.exe`. It needs no installer, Python installation,
administrator rights, or registry changes. See the
[portable Windows guide](docs/PORTABLE_WINDOWS.md).

SuperCover stores its optional `.supercover-cache` beside the executable. To
remove the program completely, delete `SuperCover.exe` and that cache folder.

The current build is not code-signed, so Windows may show an unfamiliar-app
warning. Download it only from this repository's GitHub Actions page and keep
the accompanying license and third-party notices.

## Run the desktop app from source

From the repository root, launch the graphical interface with:

```powershell
$env:PYTHONPATH = "src"
python -m supercover
```

The app guides the user through choosing a ROM folder, reviewing every match,
preparing artwork and final-color previews, and choosing the exact export
folder. The export destination always starts blank and Export remains disabled
until artwork is ready and a destination has been supplied.

Automatic matches start selected. Fuzzy, conflicting, and unmatched games
start skipped; select one to approve a suggested title, type a correction, or
leave it out. A trusted SuperCover JSON catalog can be selected for checksum
matching, but it is optional—the curated online cover list supplies the normal
title catalog. See [the desktop app guide](docs/DESKTOP_APP.md).

## Command-line test interface

Run the test suite from the repository root:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Scan a ROM folder without a catalog:

```powershell
$env:PYTHONPATH = "src"
python -m supercover "D:\GBA Games"
```

Match the scan against a small local JSON catalog:

```powershell
$env:PYTHONPATH = "src"
python -m supercover "D:\GBA Games" --catalog catalog.json
```

Download exact Libretro box art for automatic matches:

```powershell
$env:PYTHONPATH = "src"
python -m supercover "D:\GBA Games" --catalog catalog.json --fetch-artwork
```

Artwork and the provider index are cached under `.supercover-cache` by default.
Once downloaded, the same scan can run without network access:

```powershell
python -m supercover "D:\GBA Games" --catalog catalog.json --fetch-artwork --offline
```

Use `--cache-dir` to select another cache folder and `--refresh-artwork` to
refresh both the provider index and matched images. Fuzzy, conflicting, and
unmatched games are never downloaded automatically.

## Export hardware-ready covers

Supply `--export-dir` to choose the exact folder that receives `.sfcov` files.
There is deliberately no default export location:

```powershell
$env:PYTHONPATH = "src"
python -m supercover "D:\GBA Games" `
  --catalog catalog.json `
  --export-dir "C:\My SuperCover Export"
```

To install directly to a mounted SuperCard SD, select its canonical cover
folder yourself:

```powershell
python -m supercover "D:\GBA Games" `
  --catalog catalog.json `
  --export-dir "E:\.superfw\covers"
```

The drive letters above are examples only. SuperCover never guesses which
drive is an SD card.

Exports are version 3 at 76-by-76 by default. Use `--export-size 72` when you
need the legacy version 2 format for upstream SuperFW. `--preview-dir`
chooses a separate folder for PNG
previews at the selected export size using the final GBA colors. Existing
covers are preserved by default. The available
policies are `--existing skip`, `--existing replace`, and
`--existing keep-both`. A Keep Both filename is useful for comparison but does
not automatically match the ROM in SuperR7 until the user renames it.

Exports retain the ROM's exact basename and add only `.sfcov`. A hidden
`.supercover-export.json` manifest records the ROM identity, artwork source,
conversion settings, and final cover checksum. See
[the export guide](docs/EXPORTING.md) for the safety rules and examples.

The current catalog format is intentionally simple:

```json
[
  {
    "name": "Metal Slug Advance (USA)",
    "crc32": "00000000",
    "sha1": "0000000000000000000000000000000000000000"
  }
]
```

Hashes are optional. Placeholder zero hashes above demonstrate the format only;
use values from a trusted catalog for real matching.

## Roadmap

The complete six-phase plan is in [GAME_PLAN.md](GAME_PLAN.md):

1. Offline scanner and matcher
2. Curated online artwork provider
3. `.sfcov` conversion and user-selected export
4. Windows graphical interface
5. Portable executable packaging
6. Library and SuperCard SD hardware verification

## Relationship to SuperR7 and SuperFW

SuperCover is built and maintained specifically for SuperR7. It is distributed
as a separate companion application and does not bundle SuperR7 firmware or
copyrighted game artwork. Its legacy version 2 compatibility and portions of
its conversion logic retain attribution to the upstream
[SuperFW](https://github.com/davidgfnet/superfw) project.

## Artwork provider

Online artwork comes from the curated
[Libretro Game Boy Advance thumbnail repository](https://github.com/libretro-thumbnails/Nintendo_-_Game_Boy_Advance)
and its public `Named_Boxarts` service. SuperCover records the provider page,
exact source URL, and source filename for every successful download. It does
not redistribute a cover pack.

## License

Original SuperCover work is Copyright (C) 2026 Danny Nunez (dnunezx).

SuperCover is free software licensed under the GNU General Public License,
version 3 or later. See [LICENSE](LICENSE).

Third-party components and adapted code are documented in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
