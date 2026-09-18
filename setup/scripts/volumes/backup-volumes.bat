@echo off
REM ============================================================================
REM  Backup Docker named volumes (and optional TEOCO data dir) before rebuild.
REM
REM  Usage (from anywhere):
REM    setup\scripts\volumes\backup-volumes.bat
REM    setup\scripts\volumes\backup-volumes.bat -teoco
REM    setup\scripts\volumes\backup-volumes.bat -out D:\backups\aan
REM    setup\scripts\volumes\backup-volumes.bat -no-stop
REM
REM  Creates a timestamped folder under BACKUP_ROOT containing .tar.gz files
REM  for each named volume. Use restore-volumes.bat to bring them back.
REM
REM  Volumes backed up:
REM    aana_core_services_postgres_data
REM    aana_core_services_redis_data
REM    aana_core_services_phoenix_data
REM    aana_auth_server_keycloak_postgres_data
REM
REM  Skipped: network_bil_volume (remote CIFS/SMB mount — not local data)
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\.."
set "REPO=%CD%"
popd

set "BACKUP_ROOT=%REPO%\backups\docker-volumes"
set "INCLUDE_TEOCO=0"
set "STOP_SERVICES=1"
set "ALPINE_IMAGE=alpine:3.20"

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="-out" (
    if "%~2"=="" (
        echo ERROR: -out requires a directory path
        exit /b 1
    )
    set "BACKUP_ROOT=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="-teoco" (
    set "INCLUDE_TEOCO=1"
    shift
    goto :parse_args
)
if /i "%~1"=="-no-stop" (
    set "STOP_SERVICES=0"
    shift
    goto :parse_args
)
if /i "%~1"=="-h" goto :usage
if /i "%~1"=="--help" goto :usage
echo Unknown argument: %~1
goto :usage

:done_args

where docker >nul 2>&1
if errorlevel 1 (
    echo ERROR: docker is not on PATH.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker daemon is not running.
    exit /b 1
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"
set "BACKUP_DIR=%BACKUP_ROOT%\%STAMP%"

echo.
echo === Docker volume backup ===
echo Repo:        %REPO%
echo Backup dir:  %BACKUP_DIR%
echo Stop stacks: %STOP_SERVICES%
echo Include TEOCO_DATA_DIR: %INCLUDE_TEOCO%
echo.

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
if errorlevel 1 (
    echo ERROR: could not create backup directory.
    exit /b 1
)

if "%STOP_SERVICES%"=="1" (
    echo Stopping compose services for a consistent snapshot...
    if exist "%REPO%\docker-compose.yml" (
        pushd "%REPO%"
        docker compose stop
        popd
    )
    if exist "%REPO%\auth_server\docker-compose.yml" (
        pushd "%REPO%\auth_server"
        docker compose stop
        popd
    )
    echo.
)

call :backup_volume aana_core_services_postgres_data postgres_data.tar.gz
if errorlevel 1 goto :fail
call :backup_volume aana_core_services_redis_data redis_data.tar.gz
if errorlevel 1 goto :fail
call :backup_volume aana_core_services_phoenix_data phoenix_data.tar.gz
if errorlevel 1 goto :fail
call :backup_volume aana_auth_server_keycloak_postgres_data keycloak_postgres_data.tar.gz
if errorlevel 1 goto :fail

if "%INCLUDE_TEOCO%"=="1" (
    call :backup_teoco
    if errorlevel 1 goto :fail
)

(
    echo stamp=%STAMP%
    echo created=%DATE% %TIME%
    echo repo=%REPO%
    echo volumes=postgres_data,redis_data,phoenix_data,keycloak_postgres_data
    echo include_teoco=%INCLUDE_TEOCO%
) > "%BACKUP_DIR%\manifest.txt"

echo.
echo Writing checksums...
pushd "%BACKUP_DIR%"
powershell -NoProfile -Command "Get-ChildItem -File | ForEach-Object { $h = Get-FileHash $_.FullName -Algorithm SHA256; '{0}  {1}' -f $h.Hash, $_.Name } | Set-Content -Encoding ascii checksums.sha256"
popd

if "%STOP_SERVICES%"=="1" (
    echo.
    echo Restarting compose services...
    if exist "%REPO%\auth_server\docker-compose.yml" (
        pushd "%REPO%\auth_server"
        docker compose start
        popd
    )
    if exist "%REPO%\docker-compose.yml" (
        pushd "%REPO%"
        docker compose start
        popd
    )
)

echo.
echo Backup complete.
echo Location: %BACKUP_DIR%
echo.
echo To restore later:
echo   setup\scripts\volumes\restore-volumes.bat "%BACKUP_DIR%"
echo.
exit /b 0

:fail
echo.
echo Backup FAILED. Partial files may exist in:
echo   %BACKUP_DIR%
if "%STOP_SERVICES%"=="1" (
    echo Attempting to restart services...
    if exist "%REPO%\auth_server\docker-compose.yml" (
        pushd "%REPO%\auth_server"
        docker compose start
        popd
    )
    if exist "%REPO%\docker-compose.yml" (
        pushd "%REPO%"
        docker compose start
        popd
    )
)
exit /b 1

:usage
echo.
echo Usage: backup-volumes.bat [options]
echo.
echo   -out DIR     Backup root directory (default: ^<repo^>\backups\docker-volumes)
echo   -teoco       Also archive TEOCO_DATA_DIR from .env (host bind mount)
echo   -no-stop     Do not stop/start compose services (faster, less consistent)
echo   -h           Show this help
echo.
exit /b 1

REM --------------------------------------------------------------------------
:backup_volume
set "VOL_NAME=%~1"
set "OUT_FILE=%~2"

docker volume inspect "%VOL_NAME%" >nul 2>&1
if errorlevel 1 (
    echo SKIP  volume not found: %VOL_NAME%
    exit /b 0
)

echo BACKUP %VOL_NAME%  -^>  %OUT_FILE%
docker run --rm ^
  -v "%VOL_NAME%:/volume:ro" ^
  -v "%BACKUP_DIR%:/backup" ^
  %ALPINE_IMAGE% ^
  tar czf "/backup/%OUT_FILE%" -C /volume .
if errorlevel 1 (
    echo ERROR: failed to archive %VOL_NAME%
    exit /b 1
)
for %%F in ("%BACKUP_DIR%\%OUT_FILE%") do echo        size: %%~zF bytes
exit /b 0

REM --------------------------------------------------------------------------
:backup_teoco
set "TEOCO_DIR="
set "TEOCO_RAW="
if exist "%REPO%\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /c:"TEOCO_DATA_DIR=" "%REPO%\.env"`) do set "TEOCO_RAW=%%B"
)

if not defined TEOCO_RAW (
    echo SKIP  TEOCO_DATA_DIR not set in .env
    exit /b 0
)

REM Expand ${USERPROFILE} placeholders via PowerShell
for /f "delims=" %%P in ('powershell -NoProfile -Command "$p='%TEOCO_RAW%'; $p=$p -replace '\$\{USERPROFILE\}',$env:USERPROFILE -replace '%%USERPROFILE%%',$env:USERPROFILE; [Environment]::ExpandEnvironmentVariables($p)"') do set "TEOCO_DIR=%%P"

if not exist "%TEOCO_DIR%" (
    echo SKIP  TEOCO_DATA_DIR does not exist: %TEOCO_DIR%
    exit /b 0
)

echo BACKUP TEOCO_DATA_DIR  -^>  teoco_data_store.tar.gz
echo        from: %TEOCO_DIR%
docker run --rm ^
  -v "%TEOCO_DIR%:/data:ro" ^
  -v "%BACKUP_DIR%:/backup" ^
  %ALPINE_IMAGE% ^
  tar czf /backup/teoco_data_store.tar.gz -C /data .
if errorlevel 1 (
    echo ERROR: failed to archive TEOCO_DATA_DIR
    exit /b 1
)
echo %TEOCO_DIR%> "%BACKUP_DIR%\teoco_data_store.source.txt"
for %%F in ("%BACKUP_DIR%\teoco_data_store.tar.gz") do echo        size: %%~zF bytes
exit /b 0
