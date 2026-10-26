<#
.SYNOPSIS
Starts, stops or shows the backend (uvicorn --reload) and frontend (next dev) of this checkout.

.DESCRIPTION
-Port is the frontend port; the backend gets Port + 5000 (3000 -> 8000, 3001 -> 8001), and the two
are wired to each other through NEXT_PUBLIC_API_URL and CORS_ORIGINS. Pid and log files go to .dev/,
one set per port. stop only stops a pair this script started (it has a pid file), so it never hits
a dev server someone started by hand.

.EXAMPLE
scripts/dev.ps1 start -Port 3001
scripts/dev.ps1 status -Port 3001
scripts/dev.ps1 stop -Port 3001
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "status")]
    [string]$Action,
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$devDir = Join-Path $root ".dev"
$backendPort = $Port + 5000

function Get-Services {
    @(
        @{ Name = "backend"; Port = $backendPort },
        @{ Name = "frontend"; Port = $Port }
    )
}

function Get-PidFile($service) { Join-Path $devDir "$($service.Name)-$($service.Port).pid" }

function Get-Listener([int]$port) {
    try {
        Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
            Select-Object -First 1 -ExpandProperty OwningProcess
    } catch {
        $null
    }
}

function Stop-Tree([int]$processId) {
    # /T takes the children too: uvicorn's reload worker and next dev's server outlive their parent.
    & taskkill.exe /PID $processId /T /F 2>&1 | Out-Null
}

function Start-Pair {
    New-Item -ItemType Directory -Force $devDir | Out-Null
    foreach ($service in Get-Services) {
        $listener = Get-Listener $service.Port
        if ($listener) {
            throw "Port $($service.Port) is already in use (pid $listener). Pick another -Port or stop it first."
        }
    }

    # The root .env addresses LM Studio from inside Docker; this runs on the host.
    $env:LOCAL_LLM_BASE_URL = "http://localhost:1234/v1"
    $env:CORS_ORIGINS = "[`"http://localhost:$Port`"]"
    $env:NEXT_PUBLIC_API_URL = "http://localhost:$backendPort"
    # A dev backend must not rewrite the store with the nightly label update.
    $env:LABEL_UPDATE_SCHEDULE = "0"

    $commands = @{
        backend  = @{
            File = "uv"
            Args = @("run", "uvicorn", "molecula.main:app", "--reload", "--port", "$backendPort")
            Dir  = Join-Path $root "backend"
        }
        frontend = @{
            File = "npm.cmd"
            Args = @("run", "dev", "--", "--port", "$Port")
            Dir  = Join-Path $root "frontend"
        }
    }

    foreach ($service in Get-Services) {
        $command = $commands[$service.Name]
        $log = Join-Path $devDir "$($service.Name)-$($service.Port)"
        $process = Start-Process -FilePath $command.File -ArgumentList $command.Args `
            -WorkingDirectory $command.Dir -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput "$log.log" -RedirectStandardError "$log.err.log"
        Set-Content -Path (Get-PidFile $service) -Value $process.Id -Encoding ascii
        Write-Output "$($service.Name): started pid $($process.Id) for port $($service.Port), logs in .dev\$($service.Name)-$($service.Port).log and .err.log"
    }

    $deadline = (Get-Date).AddSeconds(180)
    foreach ($service in Get-Services) {
        while (-not (Get-Listener $service.Port) -and (Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 2
        }
        if (Get-Listener $service.Port) {
            Write-Output "$($service.Name): listening on http://localhost:$($service.Port)"
        } else {
            Write-Output "$($service.Name): not listening on $($service.Port) after 180 s, see its logs"
        }
    }
}

function Stop-Pair {
    foreach ($service in Get-Services) {
        $pidFile = Get-PidFile $service
        if (-not (Test-Path $pidFile)) {
            Write-Output "$($service.Name): no pid file for port $($service.Port), not started by this script; left alone"
            continue
        }
        Stop-Tree ([int](Get-Content $pidFile))
        $listener = Get-Listener $service.Port
        if ($listener) { Stop-Tree $listener }
        Remove-Item $pidFile
        Write-Output "$($service.Name): stopped (port $($service.Port))"
    }
}

function Show-Status {
    foreach ($service in Get-Services) {
        $pidFile = Get-PidFile $service
        $started = if (Test-Path $pidFile) { "started by dev.ps1 as pid $(Get-Content $pidFile)" } else { "no pid file" }
        $listener = Get-Listener $service.Port
        $state = if ($listener) { "listening on $($service.Port) (pid $listener)" } else { "not listening on $($service.Port)" }
        Write-Output "$($service.Name): $state, $started"
    }
}

switch ($Action) {
    "start" { Start-Pair }
    "stop" { Stop-Pair }
    "status" { Show-Status }
}
