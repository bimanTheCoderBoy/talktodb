@echo off
setlocal EnableDelayedExpansion

echo.
echo [dev:stop] Stopping local dev terminals from last session ...
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-invoke.ps1" -Action StopLocal
if errorlevel 1 (
  echo   [FAIL] dev:stop encountered an error.
  exit /b 1
)

echo.
echo [dev:stop] Done. Docker services were not stopped.
endlocal
