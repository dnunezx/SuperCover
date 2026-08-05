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
| 2: Online artwork provider | Planned |
| 3: Conversion and installation | Planned |
| 4: Windows graphical interface | Planned |
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

## Distribution and licensing

SuperCover will distribute code and conversion support, not a copyrighted cover
pack. Artwork remains attributable to its provider and original rights holders.
The project will retain the licenses and notices required by SuperFW and any
reused components.
