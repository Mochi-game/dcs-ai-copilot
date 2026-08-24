param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\DCS AI Copilot",
    [switch]$KeepUserConfig
)

$ErrorActionPreference = "Stop"

$ResolvedInstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$AllowedRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "Programs"))
if (-not $ResolvedInstallDir.StartsWith($AllowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to uninstall outside $AllowedRoot"
}

$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\DCS AI Copilot"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "DCS AI Copilot.lnk"

if (Test-Path $StartMenuDir) {
    Remove-Item -LiteralPath $StartMenuDir -Recurse -Force
}
if (Test-Path $DesktopShortcut) {
    Remove-Item -LiteralPath $DesktopShortcut -Force
}
if (Test-Path $ResolvedInstallDir) {
    Remove-Item -LiteralPath $ResolvedInstallDir -Recurse -Force
}

if (-not $KeepUserConfig) {
    $ConfigDir = Join-Path $env:APPDATA "DCS AI Copilot"
    if (Test-Path $ConfigDir) {
        Remove-Item -LiteralPath $ConfigDir -Recurse -Force
    }
}

Write-Host "DCS AI Copilot has been removed."
if ($KeepUserConfig) {
    Write-Host "User config was kept in: $(Join-Path $env:APPDATA 'DCS AI Copilot')"
}
