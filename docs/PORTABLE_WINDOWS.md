# Portable Windows release

SuperCover 0.5.0 is packaged as a single Windows 10/11 x64 executable. It does
not need an installer, Python, administrator rights, or registry changes.

## Download and run

1. Open the repository's **Actions** page.
2. Open a successful **Build portable Windows app** run.
3. Download `SuperCover-0.5.0-windows-x64.zip` from its Artifacts section.
4. Extract the ZIP to a normal folder or removable drive.
5. Double-click `SuperCover.exe`.

The archive also contains `LICENSE.txt`, `THIRD_PARTY_NOTICES.md`, the README,
and `SHA256SUMS.txt` for checking the executable. Keep those files when sharing
the application.

The executable is currently unsigned. Windows SmartScreen or security software
may ask for confirmation because it has no publisher certificate. Download only
from the SuperCover repository and verify the workflow completed successfully.

## Portable data

The optional `.supercover-cache` folder is created beside `SuperCover.exe` when
artwork is downloaded. SuperCover does not install services, change the
registry, write to system folders, or require elevation.

To remove SuperCover completely:

1. Close the application.
2. Delete `SuperCover.exe` and the accompanying documentation.
3. Delete `.supercover-cache` if it exists.

Exported `.sfcov` files and preview images are user-created output and are not
removed automatically.

## Reproducible build

The Windows build uses the version pinned in `requirements-build.txt`. From a
Windows PowerShell prompt in the repository:

```powershell
python -m pip install . -r requirements-build.txt
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The result is `dist\SuperCover.exe`. The build is deliberately windowed,
one-file, and does not use UPX. It embeds the SuperCover icon, GPL license,
third-party notices, and Windows product/version metadata.

For automated verification, the executable accepts an internal packaging test:

```powershell
$report = Join-Path $env:TEMP "supercover-self-test.json"
Start-Process .\dist\SuperCover.exe `
  -ArgumentList @("--self-test", $report) -Wait
Get-Content $report
```

This verifies that the frozen executable can load its embedded Python, Tkinter,
Pillow, and `.sfcov` conversion code without relying on a separately installed
Python environment.
