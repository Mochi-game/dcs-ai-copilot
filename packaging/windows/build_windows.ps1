param(
    [string]$Version = "2.0",
    [string]$BuyMeACoffeeUrl = "",
    [string]$Publisher = "Michael Johnlin",
    [string]$AppId = "{{3B6F0F84-7B89-4F6A-88F4-D6D816D78941}}",
    [switch]$RequireInstaller,
    [switch]$RequireLicense
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPath = Join-Path $ProjectRoot ".build-venv"
$DistPath = Join-Path $ProjectRoot "dist"
$ReleasePath = Join-Path $ProjectRoot "release"
$BuildMetaPath = Join-Path $ProjectRoot "build-meta"
$EntryPoint = Join-Path $ProjectRoot "main.py"
$TemplatePath = Join-Path $PSScriptRoot "DCS-AI-Copilot.iss.template"
$GeneratedIssPath = Join-Path $PSScriptRoot "DCS-AI-Copilot.generated.iss"
$BuildConfigPath = Join-Path $BuildMetaPath "config.ini"
$LicensePath = Join-Path $ProjectRoot "LICENSE"

Set-Location $ProjectRoot

New-Item -ItemType Directory -Force -Path $ReleasePath, $BuildMetaPath | Out-Null

if ($RequireLicense -and -not (Test-Path $LicensePath)) {
    throw "Final release build requires LICENSE. Choose your license, create LICENSE, then run again."
}

Copy-Item -Path (Join-Path $ProjectRoot "config.ini") -Destination $BuildConfigPath -Force
if ($BuyMeACoffeeUrl) {
    $ConfigText = Get-Content -Path $BuildConfigPath -Raw
    if ($ConfigText -notmatch "\[donation\]") {
        Add-Content -Path $BuildConfigPath -Value "`n[donation]`nbuy_me_a_coffee_url = $BuyMeACoffeeUrl"
    } else {
        $ConfigText = $ConfigText -replace "(?m)^buy_me_a_coffee_url\s*=.*$", "buy_me_a_coffee_url = $BuyMeACoffeeUrl"
        Set-Content -Path $BuildConfigPath -Value $ConfigText -Encoding UTF8
    }
}

if (-not (Test-Path $VenvPath)) {
    python -m venv $VenvPath
}

$Python = Join-Path $VenvPath "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
& $Python -m pip install pyinstaller

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --name "DCS-AI-Copilot" `
    --paths "src" `
    --collect-submodules "google.genai" `
    --collect-data "google.genai" `
    --add-data "$BuildConfigPath;." `
    --add-data "README.md;." `
    --add-data "docs;docs" `
    $EntryPoint

$PortableAppDir = Join-Path $DistPath "DCS-AI-Copilot"
Copy-Item -Path (Join-Path $PSScriptRoot "Install-DCS-AI-Copilot.ps1") -Destination $PortableAppDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "Uninstall-DCS-AI-Copilot.ps1") -Destination $PortableAppDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "Prepare-GitHub-Release.ps1") -Destination $PortableAppDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "Prepare-Local-Git-Repository.ps1") -Destination $PortableAppDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "Test-Release-Smoke.ps1") -Destination $PortableAppDir -Force
Copy-Item -Path (Join-Path $ProjectRoot "README.md") -Destination $PortableAppDir -Force
Copy-Item -Path (Join-Path $ProjectRoot ".env.example") -Destination $PortableAppDir -Force
Copy-Item -Path (Join-Path $ProjectRoot "docs") -Destination $PortableAppDir -Recurse -Force
if (Test-Path $LicensePath) {
    Copy-Item -Path $LicensePath -Destination $PortableAppDir -Force
}

$ZipPath = Join-Path $ReleasePath "DCS-AI-Copilot-portable-$Version.zip"
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $PortableAppDir "*") -DestinationPath $ZipPath

$ReleaseNotesPath = Join-Path $ReleasePath "RELEASE_NOTES-$Version.md"
@"
# DCS AI Copilot $Version

## Download

- Portable ZIP: `DCS-AI-Copilot-portable-$Version.zip`
- Windows installer: `DCS-AI-Copilot-Setup-$Version.exe` if built with Inno Setup

## First Run

Portable:

1. Extract the ZIP.
2. Run `DCS-AI-Copilot.exe --setup`.
3. Enter DCS paths, OpenAI API key and optional Gemini fallback API key.
4. Add OpenKneeboard Web Dashboard URL: http://127.0.0.1:8765
5. Run `DCS-AI-Copilot.exe --doctor` if anything is unclear.
6. Before publishing, run `DCS-AI-Copilot.exe --release-check --release-version $Version`.

Per-user install without admin:

1. Extract the ZIP.
2. Right-click `Install-DCS-AI-Copilot.ps1`.
3. Choose `Run with PowerShell`.
4. The script installs to `%LOCALAPPDATA%\Programs\DCS AI Copilot` and starts first-time setup.

## Safety

- DCS-BIOS integration is read-only.
- No cockpit commands are sent.
- DCS-BIOS setup help is available with `DCS-AI-Copilot.exe --dcs-bios-help`.
- No DCS graphics, OpenXR, PimaxXR, QuadViews or Pimax Play settings are changed.
- No hidden multiplayer/server data is read.
- License terms are included in `LICENSE` when a final license has been added.

## Known Limitations

- Requires OpenAI API key for primary speech-to-text.
- Optional Gemini API key can be used as cloud fallback for speech-to-text.
- Copy `.env.example` to `.env` only if manually configuring API keys outside the setup wizard.
- SRS and Discord audio are not integrated yet.
"@ | Set-Content -Path $ReleaseNotesPath -Encoding UTF8

$IssText = Get-Content -Path $TemplatePath -Raw
$IssText = $IssText.Replace("__APP_VERSION__", $Version)
$IssText = $IssText.Replace("__APP_PUBLISHER__", $Publisher)
$IssText = $IssText.Replace("__APP_ID__", $AppId)
$IssText | Set-Content -Path $GeneratedIssPath -Encoding UTF8

$IsccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$InstallerPath = Join-Path $ReleasePath "DCS-AI-Copilot-Setup-$Version.exe"
if ($Iscc) {
    & $Iscc $GeneratedIssPath
    if (-not (Test-Path $InstallerPath)) {
        throw "Inno Setup finished, but installer was not found: $InstallerPath"
    }
    Write-Host "Installer built with Inno Setup."
} else {
    if ($RequireInstaller) {
        throw "Inno Setup compiler not found, and -RequireInstaller was set."
    }
    Write-Host "Inno Setup compiler not found. Skipping installer EXE build."
    Write-Host "Install Inno Setup 6, then compile: $GeneratedIssPath"
}

Write-Host "Build complete."
Write-Host "Portable app folder: $PortableAppDir"
Write-Host "Portable ZIP: $ZipPath"
if (Test-Path $InstallerPath) {
    Write-Host "Windows installer: $InstallerPath"
}
Write-Host "Release notes: $ReleaseNotesPath"
Write-Host "Generated Inno Setup script: $GeneratedIssPath"
