# TLS for Nginx frontend + Keycloak (same as generate-certs.sh)
# Usage:  .\generate-certs.ps1
#         .\generate-certs.ps1 grgd-scm-vm01.ap.teo.earth 730

param(
    [string]$Hostname = "localhost",
    [int]$Days = 365
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CertDir = $ScriptDir

$openssl = $null
foreach ($c in @(
    "${env:ProgramFiles}\Git\usr\bin\openssl.exe",
    "${env:ProgramFiles(x86)}\Git\usr\bin\openssl.exe"
)) {
    if (Test-Path $c) { $openssl = $c; break }
}
if (-not $openssl) {
    $cmd = Get-Command openssl -ErrorAction SilentlyContinue
    if ($cmd) { $openssl = $cmd.Source }
}
if (-not $openssl) {
    Write-Error "OpenSSL not found. Install Git for Windows or add openssl to PATH."
}

New-Item -ItemType Directory -Force -Path $CertDir | Out-Null
$key = Join-Path $CertDir "tls.key"
$crt = Join-Path $CertDir "tls.crt"
$san = "DNS:$Hostname,DNS:localhost,DNS:keycloak-server,DNS:frontend,DNS:host.docker.internal,IP:127.0.0.1"

Write-Host "Generating certs in $CertDir for CN=$Hostname ($Days days)..."
& $openssl req -x509 -nodes -newkey rsa:2048 `
    -keyout $key -out $crt `
    -days $Days `
    -subj "/CN=$Hostname/O=TEOCO/OU=AANA" `
    -addext "subjectAltName=$san"

Write-Host "Done: $crt , $key"
Write-Host "Rebuild / restart:  docker compose build frontend && docker compose up -d frontend"
