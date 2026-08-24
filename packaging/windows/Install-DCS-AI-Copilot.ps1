param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\DCS AI Copilot",
    [switch]$NoDesktopShortcut,
    [switch]$NoStartMenuShortcuts,
    [switch]$NoLaunchSetup
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExePath = Join-Path $SourceDir "DCS-AI-Copilot.exe"
if (-not (Test-Path $ExePath)) {
    throw "DCS-AI-Copilot.exe was not found next to this installer script. Extract the portable ZIP first, then run this script from the extracted folder."
}

$ResolvedInstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$AllowedRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "Programs"))
if (-not $ResolvedInstallDir.StartsWith($AllowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InstallDir must be inside $AllowedRoot for this per-user installer."
}

New-Item -ItemType Directory -Force -Path $ResolvedInstallDir | Out-Null
Get-ChildItem -LiteralPath $SourceDir -Force |
    Where-Object { $_.FullName -ne $MyInvocation.MyCommand.Path } |
    Copy-Item -Destination $ResolvedInstallDir -Recurse -Force

$InstalledExe = Join-Path $ResolvedInstallDir "DCS-AI-Copilot.exe"

$Shell = New-Object -ComObject WScript.Shell
function New-AppShortcut {
    param(
        [string]$Path,
        [string]$Arguments = ""
    )
    $Shortcut = $Shell.CreateShortcut($Path)
    $Shortcut.TargetPath = $InstalledExe
    $Shortcut.Arguments = $Arguments
    $Shortcut.WorkingDirectory = $ResolvedInstallDir
    $Shortcut.Save()
}

if (-not $NoStartMenuShortcuts) {
    $StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\DCS AI Copilot"
    New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null

    New-AppShortcut -Path (Join-Path $StartMenuDir "DCS AI Copilot.lnk")
    New-AppShortcut -Path (Join-Path $StartMenuDir "First-time Setup.lnk") -Arguments "--setup"
    New-AppShortcut -Path (Join-Path $StartMenuDir "Setup Help.lnk") -Arguments "--setup-help"
    New-AppShortcut -Path (Join-Path $StartMenuDir "Check Installation.lnk") -Arguments "--doctor"
    New-AppShortcut -Path (Join-Path $StartMenuDir "DCS-BIOS Setup Help.lnk") -Arguments "--dcs-bios-help"
    New-AppShortcut -Path (Join-Path $StartMenuDir "Joystick Diagnostics.lnk") -Arguments "--diagnose-joysticks"
    New-AppShortcut -Path (Join-Path $StartMenuDir "Audio Diagnostics.lnk") -Arguments "--diagnose-audio"
    New-AppShortcut -Path (Join-Path $StartMenuDir "License Help.lnk") -Arguments "--license-help"
    New-AppShortcut -Path (Join-Path $StartMenuDir "Release Check.lnk") -Arguments "--release-check"
    New-AppShortcut -Path (Join-Path $StartMenuDir "Uninstall Help.lnk") -Arguments "--uninstall-help"

    $UninstallScript = Join-Path $ResolvedInstallDir "Uninstall-DCS-AI-Copilot.ps1"
    $UninstallShortcut = $Shell.CreateShortcut((Join-Path $StartMenuDir "Uninstall DCS AI Copilot.lnk"))
    $UninstallShortcut.TargetPath = "powershell.exe"
    $UninstallShortcut.Arguments = "-ExecutionPolicy Bypass -File `"$UninstallScript`""
    $UninstallShortcut.WorkingDirectory = $ResolvedInstallDir
    $UninstallShortcut.Save()
}

if (-not $NoDesktopShortcut) {
    New-AppShortcut -Path (Join-Path ([Environment]::GetFolderPath("Desktop")) "DCS AI Copilot.lnk")
}

Write-Host "DCS AI Copilot installed to: $ResolvedInstallDir"
if ($NoLaunchSetup) {
    Write-Host "First-time setup was not started because -NoLaunchSetup was set."
} else {
    Write-Host "Starting first-time setup..."
    Start-Process -FilePath $InstalledExe -ArgumentList "--setup" -WorkingDirectory $ResolvedInstallDir
}
