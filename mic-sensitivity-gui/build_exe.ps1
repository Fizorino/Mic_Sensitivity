Param(
  [switch]$OneFile = $true,
  [switch]$Windowed = $true
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = 'C:/Python310/python.exe'

# Generate icon (if Pillow is available)
& $py "mic-sensitivity-gui/tools/make_icon.py" | Out-Host

$iconPath = Join-Path $root 'mic-sensitivity-gui\assets\app.ico'
$versionFile = Join-Path $root 'mic-sensitivity-gui\version_info.txt'

# Output name
$appName = 'MicSensitivityGUI'

# Use a dedicated work directory to avoid file-lock issues in PyInstaller's default build folder.
$workPath = Join-Path $root ('build\\_pyi_work_' + $appName)
$specPath = Join-Path $root ('build\\_pyi_spec_' + $appName)

function Remove-TreeWithRetry([string]$PathToRemove, [int]$Retries = 6, [int]$DelayMs = 750) {
  if (-not (Test-Path $PathToRemove)) { return }
  for ($i = 1; $i -le $Retries; $i++) {
    try {
      Remove-Item -LiteralPath $PathToRemove -Recurse -Force -ErrorAction Stop
      return
    } catch {
      if ($i -eq $Retries) { throw }
      Start-Sleep -Milliseconds $DelayMs
    }
  }
}

Remove-TreeWithRetry -PathToRemove $workPath
Remove-TreeWithRetry -PathToRemove $specPath

# Build args
$args = @(
  '-m','PyInstaller',
  '--noconfirm',
  '--clean',
  '--name', $appName,
  '--paths', 'mic-sensitivity-gui/src',
  '--workpath', $workPath,
  '--specpath', $specPath
)

if ($OneFile) { $args += '--onefile' }
if ($Windowed) { $args += '--windowed' }

# Include the JSON config/presets next to the exe.
# (At runtime the app reads these from the exe folder.)
$settingsJson = Join-Path $root 'settings.json'
$configJson = Join-Path $root 'config.json'
$mainSettingsJson = Join-Path $root 'main_settings.json'

if (Test-Path $settingsJson) { $args += @('--add-data', "$settingsJson;.") }
if (Test-Path $configJson) { $args += @('--add-data', "$configJson;.") }
if (Test-Path $mainSettingsJson) { $args += @('--add-data', "$mainSettingsJson;.") }

# Matplotlib: this app uses Tkinter; avoid bundling Qt/PySide6.
$args += @(
  '--exclude-module', 'PySide6',
  '--exclude-module', 'PyQt6',
  '--exclude-module', 'PyQt5'
)

# pkg_resources (setuptools) depends on jaraco.*; explicitly bundle it for portability
$args += @(
  '--collect-submodules', 'jaraco'
)

# pkg_resources also expects appdirs in some environments
$args += @(
  '--hidden-import', 'appdirs'
)

# Windows metadata + icon
if (Test-Path $versionFile) {
  $args += @('--version-file', $versionFile)
}
if (Test-Path $iconPath) {
  $args += @('--icon', $iconPath)
}

# Entrypoint
$args += 'mic-sensitivity-gui/src/main.py'

& $py @args

# Copy all top-level *.json presets next to the exe for convenience
$distDir = Join-Path $root 'dist'
$exeDir = Join-Path $distDir $appName
if ($OneFile) { $exeDir = $distDir }

Get-ChildItem -Path $root -Filter '*.json' | ForEach-Object {
  Copy-Item $_.FullName -Destination $exeDir -Force
}

Write-Host "Built to: $exeDir"