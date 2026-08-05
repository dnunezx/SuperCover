# Libretro Artwork Provider

SuperCover uses the curated
[Libretro Game Boy Advance thumbnails](https://github.com/libretro-thumbnails/Nintendo_-_Game_Boy_Advance)
as its first artwork provider. Box art is discovered through the public
[`Named_Boxarts` index](https://thumbnails.libretro.com/Nintendo%20-%20Game%20Boy%20Advance/Named_Boxarts/).

## Lookup

The matcher first identifies a ROM using SuperCover's catalog rules. Only an
automatic exact-name or checksum identity is eligible for automatic artwork
download. The provider maps that canonical title to Libretro's PNG filename,
replacing Libretro's unsafe filename characters with underscores, and verifies
that the exact filename exists in the downloaded index.

Fuzzy, conflicting, and unmatched identities are not sent to the provider.
ROM data and hashes are never uploaded.

## Cache and offline behavior

The cache contains:

- A versioned JSON copy of the Libretro GBA box-art index.
- Validated PNG files addressed by a SHA-256 digest of their source URL.

The index is considered fresh for seven days. When it is stale, SuperCover
tries to refresh it; if the service is unavailable, a valid stale index remains
usable. `--offline` prevents every network request and reports a clear error for
anything not already cached.

Temporary network and server failures are retried with a short exponential
backoff. Requests have time and size bounds and expose a cancellation callback
for the future graphical interface.

## Image validation

No response is cached merely because its filename ends in `.png`. SuperCover
checks the PNG signature, required chunk order, chunk lengths and CRC-32 values,
dimensions, color encoding, compression stream, ending, decompressed size, and
absence of trailing data. Cache writes use a temporary file followed by atomic
replacement, so an interruption or invalid response cannot leave a partial
image at the final cache path.

## Attribution record

Every successful lookup retains:

- Provider name and repository page.
- Canonical game title.
- Exact provider filename and download URL.
- Original image width and height.
- Local cache path and cache/network status.

SuperCover downloads artwork for personal conversion but does not ship a
copyrighted cover pack.
