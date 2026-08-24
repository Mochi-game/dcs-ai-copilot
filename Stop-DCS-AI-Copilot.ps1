$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$PidFile = Join-Path $RuntimeDir "dcs-ai-copilot.pid"
$MainPy = Join-Path $ProjectRoot "main.py"
$Stopped = $false

function Stop-IfCopilotProcess {
    param([int]$ProcessId)

    $ProcessInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $ProcessInfo) {
        return $false
    }

    $CommandLine = [string]$ProcessInfo.CommandLine
    if ($CommandLine -notlike "*$MainPy*") {
        Write-Host "PID $ProcessId finns, men verkar inte vara denna DCS AI Copilot."
        return $false
    }

    Stop-Process -Id $ProcessId -Force
    Write-Host "Stoppade DCS AI Copilot. PID: $ProcessId"
    return $true
}

if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
    if ($ExistingPid) {
        $Stopped = Stop-IfCopilotProcess -ProcessId ([int]$ExistingPid)
    }
}

if (-not $Stopped) {
    $Candidates = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -like "python*" -and
            [string]$_.CommandLine -like "*$MainPy*"
        }

    foreach ($Candidate in $Candidates) {
        $Stopped = (Stop-IfCopilotProcess -ProcessId ([int]$Candidate.ProcessId)) -or $Stopped
    }
}

if (-not $Stopped) {
    $PortOwners = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($OwnerPid in $PortOwners) {
        $ProcessInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $OwnerPid" -ErrorAction SilentlyContinue
        if (
            $ProcessInfo -and
            $ProcessInfo.Name -like "python*" -and
            [string]$ProcessInfo.CommandLine -like "*main.py*"
        ) {
            Stop-Process -Id ([int]$OwnerPid) -Force
            Write-Host "Stoppade DCS AI Copilot pa port 8765. PID: $OwnerPid"
            $Stopped = $true
        }
    }
}

if (Test-Path -LiteralPath $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force
}

if (-not $Stopped) {
    Write-Host "Ingen korande DCS AI Copilot-process hittades."
}
