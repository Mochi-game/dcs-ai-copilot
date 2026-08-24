$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$PidFile = Join-Path $RuntimeDir "dcs-ai-copilot.pid"
$MainPy = Join-Path $ProjectRoot "main.py"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
    if ($ExistingPid -and (Get-Process -Id ([int]$ExistingPid) -ErrorAction SilentlyContinue)) {
        Write-Host "DCS AI Copilot verkar redan kora. PID: $ExistingPid"
        Write-Host "OpenKneeboard URL: http://127.0.0.1:8765"
        return
    }
}

Set-Location -LiteralPath $ProjectRoot
$Process = Start-Process -FilePath "python" -ArgumentList @($MainPy) -WorkingDirectory $ProjectRoot -PassThru
$Process.Id | Set-Content -LiteralPath $PidFile -Encoding ascii

Write-Host "Startade DCS AI Copilot. PID: $($Process.Id)"
Write-Host "OpenKneeboard URL: http://127.0.0.1:8765"
