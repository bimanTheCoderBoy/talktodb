# Shared helpers for talkToDB dev (poe dev / dev:stop / dev:status)

$script:DevSessionFile = Join-Path $PSScriptRoot "dev-session.properties"

function Reset-DevSession {
    $started = (Get-Date).ToString("o")
    @"
# talkToDB dev session - cleared on each poe dev; used by dev:stop / dev:status
started_at=$started
"@ | Set-Content -Path $script:DevSessionFile -Encoding UTF8
}

function Read-DevSession {
    $map = @{}
    if (-not (Test-Path $script:DevSessionFile)) { return $map }
    Get-Content $script:DevSessionFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        $map[$key] = $val
    }
    return $map
}

function Add-DevSessionEntry {
    param(
        [Parameter(Mandatory)][string]$Key,
        [Parameter(Mandatory)][string]$Value
    )
    Add-Content -Path $script:DevSessionFile -Encoding UTF8 -Value "${Key}=${Value}"
}

function Start-DevTerminal {
    param(
        [Parameter(Mandatory)][string]$Title,
        [Parameter(Mandatory)][string]$SessionKey,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$Command
    )
    $inner = "Write-Host '--- $Title ---' -Fore Cyan; $Command"
    $p = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -WorkingDirectory $WorkingDirectory `
        -ArgumentList @("-NoExit", "-Command", $inner) `
        -PassThru -WindowStyle Normal
    Add-DevSessionEntry -Key $SessionKey -Value $p.Id
    return $p.Id
}

function Test-TcpPortOpen {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne(300)
        if (-not $wait) { $client.Close(); return $false }
        $client.EndConnect($async)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Get-ContainerHostPorts {
    param([string]$ContainerName)
    $out = cmd /c "docker port $ContainerName 2>nul"
    if (-not $out) { return "-" }
    $hostPorts = [System.Collections.Generic.List[string]]::new()
    foreach ($line in ($out -split "`r?`n")) {
        if ($line -match "->\s*[\d\.]+:(\d+)\s*$") {
            [void]$hostPorts.Add($matches[1])
        }
    }
    if ($hostPorts.Count -eq 0) { return "-" }
    return ($hostPorts | Sort-Object { [int]$_ } -Unique) -join ", "
}

function Get-ContainerReport {
    param([string]$ContainerName)
    $fmt = "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}{{end}}"
    $raw = cmd /c "docker inspect -f ""$fmt"" $ContainerName 2>nul"
    if (-not $raw -or $raw.Trim() -eq "") {
        return [PSCustomObject]@{ On = $false; Detail = "off" }
    }
    $parts = $raw.Trim() -split "\|", 2
    $state = $parts[0]
    $health = if ($parts.Length -gt 1) { $parts[1] } else { "" }
    if ($state -ne "running") {
        $detail = if ($state) { $state } else { "off" }
        return [PSCustomObject]@{ On = $false; Detail = $detail }
    }
    if ($health -and $health -ne "") {
        return [PSCustomObject]@{ On = $true; Detail = $health }
    }
    return [PSCustomObject]@{ On = $true; Detail = "running" }
}

function New-DockerStatusRow {
    param(
        [Parameter(Mandatory)][string]$Service,
        [Parameter(Mandatory)][string]$ContainerName
    )
    $report = Get-ContainerReport -ContainerName $ContainerName
    $ports = if ($report.On) { Get-ContainerHostPorts -ContainerName $ContainerName } else { "-" }
    [PSCustomObject]@{
        On      = $report.On
        Service = $Service
        Kind    = "docker"
        Ports   = $ports
        Detail  = $report.Detail
    }
}

function Get-LocalDevReport {
    param(
        [string]$SessionKey,
        [int]$Port,
        [hashtable]$Session
    )
    $pidStr = $Session[$SessionKey]
    $pidNum = 0
    if ($pidStr -match '^\d+$') { [void][int]::TryParse($pidStr, [ref]$pidNum) }
    $procAlive = $false
    if ($pidNum -gt 0) {
        $procAlive = $null -ne (Get-Process -Id $pidNum -ErrorAction SilentlyContinue)
    }
    $portOpen = Test-TcpPortOpen -Port $Port
    $portLabel = "localhost:$Port"

    if ($procAlive) {
        $detail = "pid $pidNum (terminal)"
        return [PSCustomObject]@{ On = $true; Detail = $detail; Ports = $portLabel }
    }
    if ($portOpen) {
        return [PSCustomObject]@{
            On     = $true
            Detail = "listening (pid not tracked)"
            Ports  = $portLabel
        }
    }
    if ($pidNum -gt 0) {
        return [PSCustomObject]@{
            On     = $false
            Detail = "off (stale pid $pidNum)"
            Ports  = $portLabel
        }
    }
    return [PSCustomObject]@{ On = $false; Detail = "off"; Ports = $portLabel }
}

function Get-ListenerPidsForPort {
    param([int]$Port)
    $pids = [System.Collections.Generic.HashSet[int]]::new()
    $portPattern = ":$Port\s"
    foreach ($line in (netstat -ano -p tcp 2>$null)) {
        if ($line -notmatch "LISTENING") { continue }
        if ($line -notmatch $portPattern) { continue }
        if ($line -match "LISTENING\s+(\d+)\s*$") {
            [void]$pids.Add([int]$matches[1])
        }
    }
    return @($pids)
}

function Stop-ProcessTree {
    param([int]$ProcessId, [string]$Label)
    if ($ProcessId -le 0) { return $false }
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) { return $false }
    Write-Host "  [stop] $Label - taskkill /T /PID $ProcessId"
    & taskkill.exe /T /F /PID $ProcessId 2>&1 | ForEach-Object { Write-Host "         $_" }
    return ($LASTEXITCODE -eq 0)
}

function Stop-DevLocalProcesses {
    $session = Read-DevSession
    $targets = @(
        @{ Key = "backend.terminal.pid"; Port = 2024; Name = "backend" },
        @{ Key = "frontend.terminal.pid"; Port = 5173; Name = "frontend" },
        @{ Key = "rag.terminal.pid"; Port = 8010; Name = "rag" }
    )

    foreach ($t in $targets) {
        $pidStr = $session[$t.Key]
        if ($pidStr -match '^\d+$') {
            $null = Stop-ProcessTree -ProcessId ([int]$pidStr) -Label $t.Key
        } else {
            Write-Host "  [skip] $($t.Key) - no pid in session file"
        }

        if (Test-TcpPortOpen -Port $t.Port) {
            foreach ($listenerPid in (Get-ListenerPidsForPort -Port $t.Port)) {
                if ($listenerPid -eq 0) { continue }
                $null = Stop-ProcessTree -ProcessId $listenerPid -Label "$($t.Name) port $($t.Port) listener"
            }
        }
    }
}

function Show-DevStatus {
    param([string]$Root)
    $session = Read-DevSession
    $started = if ($session["started_at"]) { $session["started_at"] } else { "(no session file - run poe dev)" }

    Write-Host ""
    Write-Host "talkToDB dev status"
    Write-Host "Session: $started"
    Write-Host ""

    $rows = @(
        (New-DockerStatusRow -Service "keycloak" -ContainerName "keycloak-server"),
        (New-DockerStatusRow -Service "keycloak postgres" -ContainerName "keycloak-postgres"),
        (New-DockerStatusRow -Service "postgres" -ContainerName "postgres"),
        (New-DockerStatusRow -Service "redis" -ContainerName "redis")
        # (New-DockerStatusRow -Service "phoenix" -ContainerName "phoenix")  # disabled — LangSmith tracing
    )

    $backend = Get-LocalDevReport -SessionKey "backend.terminal.pid" -Port 2024 -Session $session
    $frontend = Get-LocalDevReport -SessionKey "frontend.terminal.pid" -Port 5173 -Session $session
    $rag = Get-LocalDevReport -SessionKey "rag.terminal.pid" -Port 8010 -Session $session

    $rows += @(
        [PSCustomObject]@{
            On = $backend.On; Service = "backend (langgraph)"; Kind = "local"
            Ports = $backend.Ports; Detail = $backend.Detail
        },
        [PSCustomObject]@{
            On = $frontend.On; Service = "frontend (vite)"; Kind = "local"
            Ports = $frontend.Ports; Detail = $frontend.Detail
        },
        [PSCustomObject]@{
            On = $rag.On; Service = "rag retrieval"; Kind = "local"
            Ports = $rag.Ports; Detail = $rag.Detail
        }
    )

    $display = $rows | ForEach-Object {
        $state = if ($_.On) { "ON " } else { "OFF" }
        [PSCustomObject]@{
            State   = $state
            Service = $_.Service
            Kind    = $_.Kind
            Ports   = $_.Ports
            Detail  = $_.Detail
        }
    }
    $display | Format-Table -AutoSize
}

function Start-DevLocalServices {
    param([Parameter(Mandatory)][string]$Root)
    $backendCmd = "uv run --package agent-server --directory agent_server langgraph dev"
    $frontendCmd = "npm run dev"
    $ragCmd = "uv run --package rag-retrieval-server --directory rag_retrieval_server python -m retrieval_app.server"

    Start-DevTerminal -Title "Backend (langgraph dev)" -SessionKey "backend.terminal.pid" `
        -WorkingDirectory $Root -Command $backendCmd | Out-Null
    Start-DevTerminal -Title "Frontend (npm run dev)" -SessionKey "frontend.terminal.pid" `
        -WorkingDirectory (Join-Path $Root "frontend") -Command $frontendCmd | Out-Null
    Start-DevTerminal -Title "RAG Retrieval Server" -SessionKey "rag.terminal.pid" `
        -WorkingDirectory $Root -Command $ragCmd | Out-Null
}
