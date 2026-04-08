$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$src  = Join-Path $PSScriptRoot 'src'
$entry = Join-Path $src 'main.py'
$py   = 'C:\Python310\python.exe'
$appName = 'MicSensitivityGUI'

# Build to a LOCAL temp folder first to avoid OneDrive sync/lock issues,
# then copy the final exe back into the repo.
$localBuild = Join-Path $env:LOCALAPPDATA "PyInstallerBuild\$appName"
$localDist  = Join-Path $localBuild 'dist'
$localWork  = Join-Path $localBuild 'work'

Write-Host "=== Building $appName ===" -ForegroundColor Cyan
Write-Host "Build dir (local): $localBuild"

# Ensure PyInstaller is installed
& $py -m pip install pyinstaller --quiet

# Collect all root-level .json preset files to bundle next to the exe
$datas = @()
foreach ($json in (Get-ChildItem -Path $root -Filter '*.json' -File)) {
    $datas += "--add-data"
    $datas += "$($json.FullName);."
}

# Build as --onefile so the exe is fully self-contained (no DLL sync issues)
& $py -m PyInstaller `
    --name $appName `
    --windowed `
    --onefile `
    --noconfirm `
    --clean `
    --paths $src `
    --collect-all setuptools `
    --collect-all pkg_resources `
    --collect-submodules jaraco `
    $datas `
    --distpath $localDist `
    --workpath $localWork `
    --specpath $localWork `
    $entry

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build FAILED" -ForegroundColor Red
    exit 1
}

# Copy the single exe back to the repo dist folder
$finalDir = Join-Path $root 'dist'
New-Item -ItemType Directory -Path $finalDir -Force | Out-Null
$src_exe = Join-Path $localDist "$appName.exe"
$dst_exe = Join-Path $finalDir "$appName.exe"
Copy-Item -Path $src_exe -Destination $dst_exe -Force

Write-Host ""
Write-Host "Build complete: $dst_exe" -ForegroundColor Green
Write-Host "You can run it by double-clicking the exe."
