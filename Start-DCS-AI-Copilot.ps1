$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$PidFile = Join-Path $RuntimeDir "dcs-ai-copilot.pid"
$StartLog = Join-Path $RuntimeDir "start.log"
$StdOutLog = Join-Path $RuntimeDir "dcs-ai-copilot.out.log"
$StdErrLog = Join-Path $RuntimeDir "dcs-ai-copilot.err.log"
$MainPy = Join-Path $ProjectRoot "main.py"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

try {
    if (Test-Path -LiteralPath $PidFile) {
        $ExistingPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
        if ($ExistingPid -and (Get-Process -Id ([int]$ExistingPid) -ErrorAction SilentlyContinue)) {
            "DCS AI Copilot already running. PID: $ExistingPid" | Set-Content -LiteralPath $StartLog -Encoding utf8
            return
        }
    }

    Set-Location -LiteralPath $ProjectRoot
    $Process = Start-Process `
        -FilePath "python" `
        -ArgumentList @($MainPy) `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdOutLog `
        -RedirectStandardError $StdErrLog `
        -PassThru
    $Process.Id | Set-Content -LiteralPath $PidFile -Encoding ascii

    @(
        "Started DCS AI Copilot. PID: $($Process.Id)"
        "OpenKneeboard URL: http://127.0.0.1:8765"
        "stdout: $StdOutLog"
        "stderr: $StdErrLog"
    ) | Set-Content -LiteralPath $StartLog -Encoding utf8
} catch {
    "Failed to start DCS AI Copilot: $($_.Exception.Message)" | Set-Content -LiteralPath $StartLog -Encoding utf8
    throw
}
