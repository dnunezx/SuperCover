# SuperCover Game Plan

## Goal

SuperCover will be a portable Windows application that turns a folder of GBA
ROMs into a ready-to-use SuperFW cover library. It will identify each game,
find appropriate box art from a curated online source, convert the image to
SuperFW's `.sfcov` format, and place it under `/.superfw/covers/` using the
ROM's exact filename.

SuperCover will never modify, rename, upload, or delete ROM files.

## Intended user experience

1. Select a folder containing `.gba` files.
2. Let SuperCover scan and identify the games.
3. Download exact artwork automatically and review uncertain matches.
4. Preview the converted square covers.
5. Select an SD card or output folder.
6. Install the covers into `/.superfw/covers/`.

The installed cover must keep the ROM's original basename. For example:

```text
Metal Slug Advance (USA).gba
/.superfw/covers/Metal Slug Advance (USA).sfcov
```

## Matching safety rules

- Prefer deterministic evidence: exact normalized names and ROM checksums.
- Use CRC-32 and SHA-1 to recognize correctly dumped ROMs even if renamed.
- Treat fuzzy title matches as suggestions that require user review.
- Flag conflicting name and checksum results instead of guessing.
- Keep the original ROM basename for the output, regardless of the catalog or
  artwork provider's title.
- Do not use generic image search in the automatic workflow.

## Planned artwork sources

The first online provider will be the curated Libretro Game Boy Advance
thumbnail collection. A current No-Intro catalog will provide canonical ROM
names and checksums. Additional providers, such as ScreenScraper, can be added
later behind the same provider interface.

SuperCover will download artwork only. ROM contents and checksums remain on the
user's PC.

## Development phases

### Phase 1: Offline scanner and matcher

- Recursively find `.gba` files in a selected folder.
- Read files in chunks and calculate CRC-32 and SHA-1 without loading an entire
  ROM into memory.
- Load a small local JSON catalog.
- Match by checksum and normalized filename.
- Produce fuzzy suggestions for manual review.
- Report conflicts and unmatched games clearly.
- Provide a command-line interface for testing the engine before a GUI exists.

Acceptance criteria:

- Scanning does not change any ROM or other file.
- Nested folders and case-insensitive `.gba` extensions are supported.
- Exact-name and unique checksum matches are deterministic.
- Fuzzy matches are never silently accepted.
- Automated tests use synthetic data and pass offline.

### Phase 2: Online artwork provider

- Add the Libretro GBA box-art index and download client.
- Map canonical catalog titles to provider filenames safely.
- Add local caching, timeouts, retries, cancellation, and offline behavior.
- Record the artwork source for every result.

Acceptance criteria:

- Known games find their correct curated artwork.
- Network failures leave ROMs and existing covers untouched.
- Downloads are validated as supported image files before use.

### Phase 3: Conversion and installation

- Reuse SuperFW's tested 72-by-72 `.sfcov` converter.
- Preview the final GBA colors.
- Name output files after the exact original ROM basename.
- Install to `/.superfw/covers/` using temporary files and atomic replacement.
- Support Skip, Replace, and Keep Both policies for existing artwork.

Acceptance criteria:

- Installed covers pass the existing `.sfcov` validator.
- A failed conversion cannot leave a partial cover file.
- ROM files remain byte-for-byte unchanged.

### Phase 4: Windows graphical interface

- Build a simple Tkinter/ttk interface around the tested engine.
- Show scan, match, download, conversion, and installation progress.
- Provide a review screen for ambiguous and fuzzy results.
- Allow individual games to be skipped or corrected.

Acceptance criteria:

- A nontechnical user can complete the workflow without a terminal.
- The interface remains responsive during scans and downloads.
- Every automatic and manual choice is visible before installation.

### Phase 5: Portable application

- Package SuperCover as a single Windows 10/11 x64 executable.
- Require no Python installation, installer, administrator rights, or registry
  changes.
- Add version information, application icon, licenses, and acknowledgements.
- Build the executable in a clean continuous-integration environment.

Acceptance criteria:

- The executable runs from a normal folder and removable drive.
- It works on a clean supported Windows system.
- Removing the executable and its optional cache fully removes the program.

### Phase 6: Library and hardware verification

- Test a representative library of at least 25-50 clean, renamed, regional,
  revision, homebrew, unmatched, and ambiguous ROM filenames.
- Verify generated covers in Browse and Recent Games on a physical SuperCard SD.
- Confirm normal game launching and save handling after installation.

Acceptance criteria:

- No incorrect fuzzy match is installed without approval.
- Exact and checksum matches achieve a high success rate on the test library.
- Installed covers render correctly and games continue to boot and save.

## Phase status

| Phase | Status |
| --- | --- |
| 1: Offline scanner and matcher | Complete |
| 2: Online artwork provider | Complete |
| 3: Conversion and installation | Complete |
| 4: Windows graphical interface | Complete |
| 5: Portable application | Planned |
| 6: Library and hardware verification | Planned |

## Phase 1 result

Phase 1 produced a standalone, dependency-free Python engine and command-line
test harness. It recursively inventories `.gba` files, calculates CRC-32 and
SHA-1 incrementally, validates a local JSON catalog, and classifies matches as
automatic, review, conflict, or unmatched. Twelve offline tests cover nested
and non-recursive scans, hash accuracy, malformed catalogs, exact-name matches,
renamed-ROM checksum matches, conflicting evidence, fuzzy review, and unrelated
games. The scanner never opens a ROM for writing.

## Phase 2 result

Phase 2 added the curated Libretro Game Boy Advance `Named_Boxarts` provider.
SuperCover downloads and caches the provider's real index, applies Libretro's
documented unsafe-character replacement, and accepts only exact canonical title
matches. It never falls back to generic image search or silently downloads a
fuzzy match.

The dependency-free network layer provides bounded responses, timeouts,
temporary-error retries with backoff, a cancellation callback, and a clear
offline mode. The seven-day index cache falls back to a valid stale copy during
an outage. Images are written atomically only after PNG structure, dimensions,
chunk checksums, supported encoding, compressed data, and expansion limits have
been validated. Existing cached data is not replaced by a failed download.

Every successful result records the provider name and page, exact source URL
and filename, original dimensions, cache path, and whether the network or cache
was used. The command-line test interface fetches artwork only for automatic
matches and can emit the complete record as JSON.

Twenty-nine offline tests cover the Phase 1 engine plus index parsing and
caching, exact lookup, Libretro filename rules, stale and offline behavior,
missing and disappeared art, download attribution, retry and cancellation,
size limits, corrupt and incomplete PNG data, atomic failure behavior, and the
end-to-end command report. A live smoke test found and validated:

- `Metal Slug Advance (USA).png` at 256 by 229 pixels.
- `Legend of Zelda, The - The Minish Cap (USA).png` at 512 by 512 pixels.

Both images were then loaded successfully in strict offline mode from the local
cache. Phase 3 will crop or resize these source shapes into SuperFW's required
72-by-72 square `.sfcov` format.

## Phase 3 result

Phase 3 integrated SuperFW's proven version 2 `.sfcov` format and conversion
logic. Pillow performs desktop image decoding, resizing, and quantization;
SuperCover produces a fixed 72-by-72 indexed image with at most 220 GBA BGR555
colors, absolute palette indices 20-239, exact length validation, and a CRC-32
protected payload.

Export has no default destination. The command-line harness requires the user
to supply `--export-dir`, and the desktop GUI exposes the same decision as a
folder picker. The chosen path is used exactly: it can be a desktop staging
folder or a mounted SD card's `/.superfw/covers/` directory. An optional,
separately selected preview directory receives PNGs rendered with the final GBA
colors.

Output filenames retain the exact ROM basename and change only `.gba` to
`.sfcov`. Case-insensitive duplicate basenames are rejected before conversion
because SuperFW uses one flat cover directory. Existing-file policies are Skip
(default), Replace, and Keep Both. Skip preserves the existing bytes; Replace
uses atomic replacement; Keep Both chooses a numbered comparison filename and
reports that it will not automatically match the ROM in firmware.

Every batch validates its artwork identity and cached PNG, converts and
revalidates every requested cover before writing the first output, then uses
same-directory temporary files and atomic replacement. A failed image in a
batch therefore cannot leave partial conversion output. The user-selected
folder also receives an atomic `.supercover-export.json` manifest containing
ROM hashes, match evidence, artwork attribution, conversion settings, and the
SHA-256 of each final cover.

Forty-five offline tests now cover Phases 1-3, including strict format parsing,
palette bounds, CRC protection, exact export paths,
ROM immutability, firmware filenames, manifest attribution, previews, all three
existing-file policies, basename collisions, identity mismatches, batch failure
safety, and the complete command workflow. The two real cached test artworks
were also converted by both SuperCover and the original hardware-tested SuperFW
converter, producing byte-for-byte identical results:

- Metal Slug Advance: 5,634 bytes, 209 colors, SHA-256
  `AC9C9836FC2E7A18BC8D10E7FB014163607A24E4827D08F19D16DFF95EC91095`.
- The Minish Cap: 5,562 bytes, 173 colors, SHA-256
  `E8DAE4DC2E134B168DF504511F6AF2D1E993BD3720770A54335F5CE823A95D5E`.

## Phase 4 result

Phase 4 added a Windows Tkinter/ttk interface around the tested engine. The
normal `python -m supercover` entry point opens the desktop app when no command
arguments are supplied, while the command-line harness remains available for
development and automation.

The interface separates ROM selection from export selection and deliberately
starts with a blank export destination. A clear **Choose Export Folder** button
accepts either a staging directory or the mounted SD card's exact
`.superfw\covers` folder. Export remains disabled until at least one selected
game has prepared artwork and the user has supplied a destination.

The review table exposes the include/skip decision, original ROM filename,
match status, selected artwork title, and artwork/export state for every game.
Automatic matches start included. Fuzzy, conflicting, and unmatched games start
skipped; the user can approve a suggestion, type a correction, or leave the
game out. Manual approval is recorded as the match method while the output
continues to use the ROM's exact original basename.

The app can combine an optional trusted checksum catalog with the curated
Libretro title list, so ordinary exact-title matching does not require a user to
prepare JSON first. Scans, hashing, catalog loading, downloads, preview
conversion, and export run on a background worker. Network cancellation and
per-game artwork errors are visible without hiding covers that prepared
successfully.

Prepared games show their exact final 72-by-72 GBA-color preview. Existing-cover
policy, offline mode, recursive scanning, and optional preview PNGs are all
available without a terminal. Fifty-one offline tests cover Phases 1-4,
including the new review defaults, manual corrections, trusted/provider catalog
merging, selected-only preparation, final-color previews, and isolated download
failures. A Windows smoke test also verified the real 1180-by-780 window, blank
initial destination, disabled Export button, and enabled Scan button.

## Distribution and licensing

SuperCover will distribute code and conversion support, not a copyrighted cover
pack. Artwork remains attributable to its provider and original rights holders.
The project will retain the licenses and notices required by SuperFW and any
reused components.
