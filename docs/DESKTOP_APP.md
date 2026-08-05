# SuperCover desktop app

Phase 4 adds a Windows interface around the same tested scanner, matcher,
artwork provider, converter, and exporter used by the command-line harness.

## Start the app during development

From the SuperCover repository root:

```powershell
$env:PYTHONPATH = "src"
python -m supercover
```

Phase 5 will replace this development command with a portable `.exe`.

## Workflow

1. Choose the folder containing `.gba` games.
2. Choose an export destination. This field deliberately starts blank. Select
   a staging folder or the mounted SD card's exact `.superfw\covers` folder.
3. Optionally choose a trusted SuperCover JSON catalog for checksum matching.
   Without one, the app safely matches against titles in Libretro's curated GBA
   box-art list.
4. Leave **Export size** at the default 77 x 77, or choose 72 x 72 for legacy
   compatibility.
5. Select **Scan and Match Games**.
6. Review the table before downloading anything:
   - Automatic exact-name or checksum matches start included.
   - Fuzzy, conflicting, and unmatched games start skipped.
   - Select a row to approve its suggestion, type a corrected artwork title,
     include it, or skip it.
7. Select **Prepare Selected Artwork**. Downloads and conversion previews run
   in the background, and each row reports whether its artwork is ready.
8. Inspect the final GBA-color preview at the selected export size for each
   prepared game.
9. Select **Export Covers**. SuperCover writes only to the selected destination
   and shows a completion summary.

## Existing cover choices

- **Preserve existing covers** is the default and leaves their bytes unchanged.
- **Replace existing covers** atomically replaces them with the prepared files.
- **Keep both (comparison only)** adds numbered filenames. Those comparison
  names will not automatically match the ROM in SuperFW.

Optional preview PNGs are placed in `SuperCover Previews` inside the selected
export folder. The firmware `.sfcov` files remain directly in the exact folder
the user selected.

## Safety and responsiveness

The destination is never guessed. Export remains unavailable until artwork has
been prepared and the destination is non-empty. Games needing judgment are not
included until the user explicitly approves an artwork title.

Scanning, hashing, index loading, downloads, preview conversion, and exports run
on a background worker so the window remains responsive. Cancel requests are
checked during network operations and between artwork downloads. The existing
atomic exporter prevents partially written `.sfcov` files.

ROMs are opened only for read-only scanning and hashing. The interface never
renames, writes, uploads, copies, or deletes ROM files.
