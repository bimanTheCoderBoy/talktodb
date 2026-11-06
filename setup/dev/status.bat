@echo off
setlocal

set "ROOT=%~dp0..\.."
pushd "%ROOT%" && set "ROOT=%CD%" && popd

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-invoke.ps1" -Action ShowStatus -Root "%ROOT%"

endlocal
