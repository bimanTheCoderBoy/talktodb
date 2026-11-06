# Called via: powershell -NoProfile -ExecutionPolicy Bypass -File dev-invoke.ps1 -Action ...
# Entry points: *.bat (CMD) and *.ps1 (PowerShell) - not for direct use unless debugging.

param(
    [Parameter(Mandatory)]
    [ValidateSet("StartLocal", "ShowStatus", "StopLocal")]
    [string]$Action,

    [string]$Root = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "dev-lib.ps1")

if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

switch ($Action) {
    "StartLocal" { Start-DevLocalServices -Root $Root }
    "ShowStatus" { Show-DevStatus -Root $Root }
    "StopLocal"  { Stop-DevLocalProcesses }
}
