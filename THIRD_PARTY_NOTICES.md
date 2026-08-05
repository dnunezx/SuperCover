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

## PyInstaller

The portable Windows build is created with PyInstaller:

- Project: <https://pyinstaller.org/>
- Source: <https://github.com/pyinstaller/pyinstaller>
- Role: build-time freezer and executable bootloader
- License: GNU General Public License with the PyInstaller bootloader exception

PyInstaller's exception permits distributing the generated application under
SuperCover's own GPL-3.0-or-later license. PyInstaller is pinned for reproducible
builds and is not otherwise used by the source application.

## SuperCover application icon

The original SuperCover application icon was generated for this project with
OpenAI's built-in image generation tool and locally converted into transparent
PNG and Windows ICO formats. It contains no third-party logo or game artwork.

## Libretro thumbnails

SuperCover can download user-selected artwork from the Libretro thumbnail
service but does not redistribute a thumbnail pack. Provider and source URLs
are recorded in each export manifest:

<https://github.com/libretro-thumbnails/Nintendo_-_Game_Boy_Advance>
