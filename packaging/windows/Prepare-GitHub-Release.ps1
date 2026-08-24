param(
    [string]$Version = "2.0",
    [Parameter(Mandatory = $true)]
    [string]$BuyMeACoffeeUrl,
    [string]$GitHubUser = "YOUR_GITHUB_USER",
    [string]$RepositoryName = "dcs-ai-copilot"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot

$LicensePath = Join-Path $ProjectRoot "LICENSE"
if (-not (Test-Path -LiteralPath $LicensePath)) {
    throw "LICENSE is missing. Choose your final license, create LICENSE, then run this script again."
}

if (-not $BuyMeACoffeeUrl.StartsWith("https://buymeacoffee.com/")) {
    throw "BuyMeACoffeeUrl must start with https://buymeacoffee.com/"
}

Write-Host "Running tests..."
python -m unittest discover -s tests

Write-Host "Building final Windows release artifacts..."
& (Join-Path $PSScriptRoot "build_windows.ps1") `
    -Version $Version `
    -BuyMeACoffeeUrl $BuyMeACoffeeUrl `
    -RequireInstaller `
    -RequireLicense

Write-Host "Running release readiness check..."
python main.py --release-check --release-version $Version

$TagName = "v$Version"
$RemoteUrl = "https://github.com/$GitHubUser/$RepositoryName.git"

Write-Host ""
Write-Host "Release artifacts are ready if the checks above passed."
Write-Host ""
Write-Host "Prepare the local Git commit/tag with:"
Write-Host ".\packaging\windows\Prepare-Local-Git-Repository.ps1 -Version `"$Version`" -GitUserName `"YOUR_GIT_NAME`" -GitUserEmail `"YOUR_GIT_EMAIL`" -GitHubUser `"$GitHubUser`""
Write-Host ""
Write-Host "Then push when the GitHub repository exists:"
Write-Host "git push -u origin main"
Write-Host "git push origin $TagName"
Write-Host ""
Write-Host "Upload these files to the GitHub Release for ${TagName}:"
Write-Host "release\DCS-AI-Copilot-Setup-$Version.exe"
Write-Host "release\DCS-AI-Copilot-portable-$Version.zip"
Write-Host "release\RELEASE_NOTES-$Version.md"
