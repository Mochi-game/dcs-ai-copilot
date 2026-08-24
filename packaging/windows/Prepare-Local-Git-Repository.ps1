param(
    [string]$Version = "2.0",
    [Parameter(Mandatory = $true)]
    [string]$GitUserName,
    [Parameter(Mandatory = $true)]
    [string]$GitUserEmail,
    [Parameter(Mandatory = $true)]
    [string]$GitHubUser,
    [string]$RepositoryName = "dcs-ai-copilot",
    [string]$RemoteName = "origin",
    [switch]$Push
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Test-GitCommand {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & git @Arguments *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
}

function Get-GitOutputOrEmpty {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $Output = & git @Arguments 2>$null
        if ($LASTEXITCODE -eq 0) {
            return ($Output -join "`n").Trim()
        }
        return ""
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found. Install Git for Windows before preparing the repository."
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".git"))) {
    Invoke-Git init
}

$RemoteUrl = "https://github.com/$GitHubUser/$RepositoryName.git"
$TagName = "v$Version"

Invoke-Git config user.name $GitUserName
Invoke-Git config user.email $GitUserEmail

Write-Host "Running release readiness check before staging..."
python main.py --release-check --release-version $Version
if ($LASTEXITCODE -ne 0) {
    throw "Release readiness check failed. Fix the reported issue before committing."
}

Invoke-Git add .

$StagedFiles = @(git diff --cached --name-only)
$Forbidden = @(
    ".env",
    "config.local.ini"
)
$ForbiddenStaged = @(
    $StagedFiles | Where-Object {
        $name = $_ -replace "\\", "/"
        $Forbidden -contains $name -or
            ($name.StartsWith(".env.") -and $name -ne ".env.example") -or
            $name.StartsWith("release/") -or
            $name.StartsWith("dist/") -or
            $name.StartsWith("build/") -or
            $name.StartsWith("build-meta/") -or
            $name.StartsWith(".build-venv/")
    }
)
if ($ForbiddenStaged.Count -gt 0) {
    throw "Refusing to commit ignored/private/build files: $($ForbiddenStaged -join ', ')"
}

$HasHead = Test-GitCommand rev-parse --verify HEAD

if ($StagedFiles.Count -gt 0) {
    if ($HasHead) {
        Invoke-Git commit -m "Prepare DCS AI Copilot $Version release"
    } else {
        Invoke-Git commit -m "Initial DCS AI Copilot release"
    }
} else {
    Write-Host "No staged source changes to commit."
}

$ExistingRemote = ""
$ExistingRemote = Get-GitOutputOrEmpty remote get-url $RemoteName
if ($ExistingRemote) {
    Write-Host "Remote $RemoteName already exists: $ExistingRemote"
} else {
    Invoke-Git remote add $RemoteName $RemoteUrl
}

if (Test-GitCommand rev-parse $TagName) {
    Write-Host "Tag $TagName already exists."
} else {
    Invoke-Git tag $TagName
}

Write-Host ""
Write-Host "Local repository is ready."
Write-Host "Remote: $RemoteUrl"
Write-Host "Tag: $TagName"

if ($Push) {
    Invoke-Git push -u $RemoteName main
    Invoke-Git push $RemoteName $TagName
} else {
    Write-Host ""
    Write-Host "Push manually when the GitHub repository exists:"
    Write-Host "git push -u $RemoteName main"
    Write-Host "git push $RemoteName $TagName"
}

Write-Host ""
Write-Host "Upload these release files to GitHub Release ${TagName}:"
Write-Host "release\DCS-AI-Copilot-Setup-$Version.exe"
Write-Host "release\DCS-AI-Copilot-portable-$Version.zip"
Write-Host "release\RELEASE_NOTES-$Version.md"
