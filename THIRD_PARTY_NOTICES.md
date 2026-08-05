# Third-Party Notices

## SuperFW cover format and converter

The `.sfcov` format implementation and GBA palette conversion in
`src/supercover/sfcov.py` and `src/supercover/converter.py` are derived from the
SuperFW project by davidgf and contributors:

<https://github.com/davidgfnet/superfw>

SuperFW describes its original code as published under the GNU General Public
License. SuperCover is distributed under the GNU General Public License as
described in this repository's `LICENSE` file. Source-derived files carry an
additional notice in their module documentation.

## Pillow

SuperCover uses Pillow for desktop image decoding, resizing, quantization, and
preview encoding:

<https://python-pillow.github.io/>

Pillow is distributed under the HPND License.

## Libretro thumbnails

SuperCover can download user-selected artwork from the Libretro thumbnail
service but does not redistribute a thumbnail pack. Provider and source URLs
are recorded in each export manifest:

<https://github.com/libretro-thumbnails/Nintendo_-_Game_Boy_Advance>
