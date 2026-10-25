$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$PidFile = Join-Path $RuntimeDir "dcs-ai-copilot.pid"
$RunId = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$StartLog = Join-Path $RuntimeDir "start-$RunId.log"
$StdOutLog = Join-Path $RuntimeDir "dcs-ai-copilot-$RunId.out.log"
$StdErrLog = Join-Path $RuntimeDir "dcs-ai-copilot-$RunId.err.log"
$MainPy = Join-Path $ProjectRoot "main.py"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

try {
    $PortOwner = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($PortOwner) {
        $Owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($PortOwner.OwningProcess)"
        if ([string]$Owner.CommandLine -like "*$MainPy*") {
            try {
                $ExistingState = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/state' -TimeoutSec 3
                if ($null -eq $ExistingState.voice -or $null -eq $ExistingState.app) {
                    throw "Unexpected dashboard response."
                }
            } catch {
                throw "AI Copilot is running but the dashboard is not responding. Stop AI Copilot and start it again. No process was stopped."
            }
            $Owner.ProcessId | Set-Content -LiteralPath $PidFile -Encoding ascii
            "DCS AI Copilot already running. PID: $($Owner.ProcessId)" | Set-Content -LiteralPath $StartLog -Encoding utf8
            exit 0
        }
        throw "Port 8765 is already used by another program. No process was stopped."
    }

    # Explorer may have a different PATH than an interactive terminal.
    $Python = $null
    foreach ($RelativePython in @('.venv\Scripts\python.exe', '.build-venv\Scripts\python.exe')) {
        $Candidate = Join-Path $ProjectRoot $RelativePython
        if (Test-Path -LiteralPath $Candidate) {
            $Python = $Candidate
            break
        }
    }
    if (-not $Python) {
        $PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($PythonCommand) { $Python = $PythonCommand.Source }
    }
    if (-not $Python) { throw "Python not found. Install dependencies in .venv first." }

    Set-Location -LiteralPath $ProjectRoot
    $Process = Start-Process `
        -FilePath $Python `
        -ArgumentList @('"' + $MainPy + '"', '--background') `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdOutLog `
        -RedirectStandardError $StdErrLog `
        -PassThru
    $Ready = $false
    $Deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $Deadline) {
        $Process.Refresh()
        if ($Process.HasExited) {
            throw "AI Copilot exited during startup. Details: $StdErrLog"
        }
        try {
            $State = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/state' -TimeoutSec 1
            if ($null -ne $State.voice -and $null -ne $State.app) {
                $Ready = $true
                break
            }
        } catch { }
        Start-Sleep -Milliseconds 200
    }
    if (-not $Ready) { throw "Dashboard did not respond within 20 seconds. Details: $StdErrLog" }

    # A venv launcher can spawn a child Python; stop must address the server PID.
    $Listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen |
        Select-Object -First 1
    $ListenerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($Listener.OwningProcess)"
    if ([string]$ListenerProcess.CommandLine -notlike "*$MainPy*") {
        throw "Port 8765 is not owned by this AI Copilot. No process was stopped."
    }
    $Listener.OwningProcess | Set-Content -LiteralPath $PidFile -Encoding ascii

    @(
        "Started DCS AI Copilot. PID: $($Listener.OwningProcess)"
        "OpenKneeboard URL: http://127.0.0.1:8765"
        "stdout: $StdOutLog"
        "stderr: $StdErrLog"
        "Python: $Python"
    ) | Set-Content -LiteralPath $StartLog -Encoding utf8
} catch {
    "Failed to start DCS AI Copilot: $($_.Exception.Message)" | Set-Content -LiteralPath $StartLog -Encoding utf8
    Write-Error $_ -ErrorAction Continue
    exit 1
}
