# Exporting SuperFW Covers

Phase 3 converts validated artwork into the version 2 `.sfcov` format used by
the cover-art-enabled SuperFW firmware.

## The user chooses the destination

SuperCover has no default export directory and does not search for or guess an
SD-card drive. Conversion requires an explicit `--export-dir`:

```powershell
python -m supercover "C:\GBA Games" `
  --catalog "C:\catalog.json" `
  --export-dir "C:\My SuperCover Export"
```

The selected directory receives the cover files directly. To prepare a mounted
SD card in one step, select its actual canonical folder, for example:

```powershell
--export-dir "E:\.superfw\covers"
```

The correct drive letter depends on the user's computer.

## Exact filenames

SuperFW looks up covers by the ROM basename:

```text
Metal Slug Advance (USA).gba
Metal Slug Advance (USA).sfcov
```

SuperCover always uses the original ROM basename, even when a checksum match
identified a renamed game. Files are exported into one flat folder because
that is the firmware's lookup model. Two scanned ROMs whose basenames differ
only by case would require the same FAT filename, so SuperCover stops the batch
and asks the user to choose rather than overwriting either one.

## Existing files

`--existing skip` is the default and preserves an existing cover byte for byte.

`--existing replace` converts and validates the new cover first, writes it to a
temporary file in the selected directory, and atomically replaces the old file.

`--existing keep-both` leaves the original untouched and creates a numbered
filename such as `Game (1).sfcov`. This is useful for comparing conversions,
but the numbered file is not the exact ROM match and will not be selected by
SuperFW until it is deliberately renamed.

## Conversion modes

The default export size is 77-by-77. Pass `--export-size 72` for a legacy
72-by-72 cover. The default `--resize-mode cover` center-crops the source as
needed to fill the selected square. `--resize-mode contain` preserves the
entire source and adds black letterboxing where necessary.

The default `--dither floyd-steinberg` generally preserves gradients.
`--dither none` can look cleaner for flat illustrations and logos.

An optional `--preview-dir` writes a PNG at the selected export size, rendered
from the encoded cover's final 15-bit GBA colors. The preview folder is also
selected explicitly.

## Safety and manifest

Before writing the first cover in a batch, SuperCover:

1. Confirms every result was an automatic identity match.
2. Confirms the artwork title matches that game identity.
3. Revalidates the cached PNG and original dimensions.
4. Decodes and converts every requested image in memory.
5. Encodes and parses every `.sfcov` again using the strict format reader.

Only then are outputs written using same-directory temporary files and atomic
replacement. ROMs are never opened for writing.

The selected export folder contains `.supercover-export.json`, which records
the ROM filename and hashes, match method, artwork source, original dimensions,
conversion options, palette count, format version, timestamp, and final cover
SHA-256. This file is ignored by the firmware and allows an export to be audited
or reproduced later.
