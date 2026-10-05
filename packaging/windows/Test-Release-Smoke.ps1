param(
    [string]$Version = "2.1.0",
    [switch]$KeepTemp
)

$ErrorActionPreference = "Stop"

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Name
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Name is missing: $Path"
    }
}

function Assert-TextContains {
    param(
        [string]$Text,
        [string]$Needle,
        [string]$Name
    )
    if ($Text -notlike "*$Needle*") {
        throw "$Name did not contain expected text: $Needle"
    }
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Name,
        [string]$WorkingDirectory
    )
    $Output = & $FilePath @Arguments 2>&1
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "$Name failed with exit code $ExitCode.`n$($Output -join "`n")"
    }
    return ($Output -join "`n")
}

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ReleaseRoot = Join-Path $ProjectRoot "release"
$ZipPath = Join-Path $ReleaseRoot "DCS-AI-Copilot-portable-$Version.zip"
$InstallerPath = Join-Path $ReleaseRoot "DCS-AI-Copilot-Setup-$Version.exe"
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("dcs-ai-copilot-smoke-" + [Guid]::NewGuid().ToString("N"))
$ExtractDir = Join-Path $TempRoot "portable"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\DCS AI Copilot Smoke Test"

Assert-PathExists -Path $ZipPath -Name "Portable ZIP"
Assert-PathExists -Path $InstallerPath -Name "Windows installer"

try {
    New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force

    $RequiredFiles = @(
        "DCS-AI-Copilot.exe",
        ".env.example",
        "LICENSE",
        "README.md",
        "docs\LICENSE_HELP.md",
        "docs\USER_SETUP_GUIDE.md",
        "Install-DCS-AI-Copilot.ps1",
        "Uninstall-DCS-AI-Copilot.ps1",
        "Prepare-GitHub-Release.ps1",
        "Prepare-Local-Git-Repository.ps1",
        "Test-Release-Smoke.ps1"
    )
    foreach ($RelativePath in $RequiredFiles) {
        Assert-PathExists -Path (Join-Path $ExtractDir $RelativePath) -Name $RelativePath
    }

    if (Test-Path -LiteralPath (Join-Path $ExtractDir ".env")) {
        throw "Portable ZIP must not contain a real .env file."
    }

    $ExePath = Join-Path $ExtractDir "DCS-AI-Copilot.exe"
    $Help = Invoke-Checked -FilePath $ExePath -Arguments @("--help") -Name "built --help" -WorkingDirectory $ExtractDir
    foreach ($Needle in @("--setup", "--setup-help", "--doctor", "--backup-dcs", "--diagnose-audio", "--diagnose-joysticks", "--release-check")) {
        Assert-TextContains -Text $Help -Needle $Needle -Name "built --help"
    }

    $SetupHelp = Invoke-Checked -FilePath $ExePath -Arguments @("--setup-help") -Name "built --setup-help" -WorkingDirectory $ExtractDir
    foreach ($Needle in @("http://127.0.0.1:8765", "PTT", "backup", "does not change VR settings")) {
        Assert-TextContains -Text $SetupHelp -Needle $Needle -Name "built --setup-help"
    }

    $LicenseHelp = Invoke-Checked -FilePath $ExePath -Arguments @("--license-help") -Name "built --license-help" -WorkingDirectory $ExtractDir
    Assert-TextContains -Text $LicenseHelp -Needle "MIT License" -Name "built --license-help"

    Invoke-Checked `
        -FilePath $ExePath `
        -Arguments @("--release-check", "--release-version", $Version, "--release-project-root", $ProjectRoot) `
        -Name "built --release-check" `
        -WorkingDirectory $ExtractDir | Out-Null

    $InstallScript = Join-Path $ExtractDir "Install-DCS-AI-Copilot.ps1"
    if (Test-Path -LiteralPath $InstallDir) {
        & (Join-Path $ExtractDir "Uninstall-DCS-AI-Copilot.ps1") -InstallDir $InstallDir -KeepUserConfig | Out-Null
    }
    & powershell -ExecutionPolicy Bypass -File $InstallScript `
        -InstallDir $InstallDir `
        -NoDesktopShortcut `
        -NoStartMenuShortcuts `
        -NoLaunchSetup | Out-Null
    $InstalledExe = Join-Path $InstallDir "DCS-AI-Copilot.exe"
    Assert-PathExists -Path $InstalledExe -Name "installed executable"
    Invoke-Checked -FilePath $InstalledExe -Arguments @("--setup-help") -Name "installed --setup-help" -WorkingDirectory $InstallDir | Out-Null
    & (Join-Path $InstallDir "Uninstall-DCS-AI-Copilot.ps1") -InstallDir $InstallDir -KeepUserConfig | Out-Null
    if (Test-Path -LiteralPath $InstallDir) {
        throw "Uninstall did not remove smoke-test install directory: $InstallDir"
    }

    Write-Host "Release smoke test passed."
    Write-Host "Portable ZIP: $ZipPath"
    Write-Host "Installer: $InstallerPath"
} finally {
    if (-not $KeepTemp -and (Test-Path -LiteralPath $TempRoot)) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force
    } elseif ($KeepTemp) {
        Write-Host "Smoke-test temp folder kept: $TempRoot"
    }
}
