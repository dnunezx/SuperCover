param(
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $ProjectRoot "dist"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$WorkDirectory = Join-Path $ProjectRoot "build\pyinstaller"
$SpecFile = Join-Path $ProjectRoot "packaging\supercover.spec"

Push-Location $ProjectRoot
try {
    python -m PyInstaller `
        --clean `
        --noconfirm `
        --distpath $OutputDirectory `
        --workpath $WorkDirectory `
        $SpecFile
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    $Executable = Join-Path $OutputDirectory "SuperCover.exe"
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "Portable executable was not created: $Executable"
    }
    Write-Output $Executable
}
finally {
    Pop-Location
}
