@echo off
REM ============================================================================
REM  Restore Docker named volumes from a backup created by backup-volumes.bat.
REM
REM  Usage:
REM    setup\scripts\volumes\restore-volumes.bat
REM    setup\scripts\volumes\restore-volumes.bat "D:\path\to\backups\docker-volumes\20260723_171500"
REM    setup\scripts\volumes\restore-volumes.bat -latest
REM    setup\scripts\volumes\restore-volumes.bat -latest -teoco
REM    setup\scripts\volumes\restore-volumes.bat -latest -only postgres
REM
REM  WARNING: Restore overwrites existing volume contents. Containers that use
REM  those volumes are stopped first. Confirm before proceeding.
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\.."
set "REPO=%CD%"
popd

set "BACKUP_ROOT=%REPO%\backups\docker-volumes"
set "BACKUP_DIR="
set "USE_LATEST=0"
set "RESTORE_TEOCO=0"
set "ONLY="
set "ALPINE_IMAGE=alpine:3.20"
set "ASSUME_YES=0"

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="-latest" (
    set "USE_LATEST=1"
    shift
    goto :parse_args
)
if /i "%~1"=="-teoco" (
    set "RESTORE_TEOCO=1"
    shift
    goto :parse_args
)
if /i "%~1"=="-only" (
    if "%~2"=="" (
        echo ERROR: -only requires a name: postgres^|redis^|phoenix^|keycloak^|teoco
        exit /b 1
    )
    set "ONLY=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="-y" (
    set "ASSUME_YES=1"
    shift
    goto :parse_args
)
if /i "%~1"=="-h" goto :usage
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-out" (
    echo NOTE: -out is for backup only. Pass the backup folder path as the first argument.
    exit /b 1
)
REM First non-flag arg = backup directory
if not defined BACKUP_DIR (
    set "BACKUP_DIR=%~1"
    shift
    goto :parse_args
)
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

if "%USE_LATEST%"=="1" (
    if not exist "%BACKUP_ROOT%" (
        echo ERROR: no backups found at %BACKUP_ROOT%
        exit /b 1
    )
    for /f "delims=" %%D in ('powershell -NoProfile -Command "Get-ChildItem -Directory '%BACKUP_ROOT%' | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty FullName"') do set "BACKUP_DIR=%%D"
)

if not defined BACKUP_DIR (
    echo ERROR: pass a backup folder path, or use -latest
    echo.
    goto :usage
)

if not exist "%BACKUP_DIR%" (
    echo ERROR: backup folder not found: %BACKUP_DIR%
    exit /b 1
)

echo.
echo === Docker volume restore ===
echo Repo:       %REPO%
echo Backup dir: %BACKUP_DIR%
if defined ONLY echo Only:       %ONLY%
echo Restore TEOCO_DATA_DIR: %RESTORE_TEOCO%
echo.
echo WARNING: This will overwrite existing volume data.
echo.

if "%ASSUME_YES%"=="0" (
    set /p "CONFIRM=Type YES to continue: "
    if /i not "!CONFIRM!"=="YES" (
        echo Aborted.
        exit /b 1
    )
)

echo.
echo Stopping compose services...
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

if defined ONLY (
    if /i "%ONLY%"=="postgres" call :restore_volume aana_core_services_postgres_data postgres_data.tar.gz
    if /i "%ONLY%"=="redis" call :restore_volume aana_core_services_redis_data redis_data.tar.gz
    if /i "%ONLY%"=="phoenix" call :restore_volume aana_core_services_phoenix_data phoenix_data.tar.gz
    if /i "%ONLY%"=="keycloak" call :restore_volume aana_auth_server_keycloak_postgres_data keycloak_postgres_data.tar.gz
    if /i "%ONLY%"=="teoco" (
        set "RESTORE_TEOCO=1"
        call :restore_teoco
    )
    if errorlevel 1 goto :fail
) else (
    call :restore_volume aana_core_services_postgres_data postgres_data.tar.gz
    if errorlevel 1 goto :fail
    call :restore_volume aana_core_services_redis_data redis_data.tar.gz
    if errorlevel 1 goto :fail
    call :restore_volume aana_core_services_phoenix_data phoenix_data.tar.gz
    if errorlevel 1 goto :fail
    call :restore_volume aana_auth_server_keycloak_postgres_data keycloak_postgres_data.tar.gz
    if errorlevel 1 goto :fail
    if "%RESTORE_TEOCO%"=="1" (
        call :restore_teoco
        if errorlevel 1 goto :fail
    )
)

echo.
echo Starting compose services...
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

echo.
echo Restore complete from:
echo   %BACKUP_DIR%
echo.
exit /b 0

:fail
echo.
echo Restore FAILED.
echo Services were left stopped. Start manually when ready:
echo   cd auth_server ^&^& docker compose start
echo   cd .. ^&^& docker compose start
exit /b 1

:usage
echo.
echo Usage: restore-volumes.bat [BACKUP_DIR] [options]
echo.
echo   BACKUP_DIR   Folder created by backup-volumes.bat
echo   -latest      Use the newest folder under ^<repo^>\backups\docker-volumes
echo   -teoco       Also restore teoco_data_store.tar.gz into TEOCO_DATA_DIR
echo   -only NAME   Restore only one: postgres^|redis^|phoenix^|keycloak^|teoco
echo   -y           Skip confirmation prompt
echo   -h           Show this help
echo.
echo Examples:
echo   restore-volumes.bat -latest
echo   restore-volumes.bat "D:\Biman\aan\backups\docker-volumes\20260723_171500"
echo   restore-volumes.bat -latest -only postgres
echo.
exit /b 1

REM --------------------------------------------------------------------------
:restore_volume
set "VOL_NAME=%~1"
set "IN_FILE=%~2"
set "ARCHIVE=%BACKUP_DIR%\%IN_FILE%"

if not exist "%ARCHIVE%" (
    echo SKIP  archive missing: %IN_FILE%
    exit /b 0
)

echo RESTORE %IN_FILE%  -^>  %VOL_NAME%

docker volume inspect "%VOL_NAME%" >nul 2>&1
if errorlevel 1 (
    echo        creating missing volume...
    docker volume create "%VOL_NAME%" >nul
    if errorlevel 1 (
        echo ERROR: could not create volume %VOL_NAME%
        exit /b 1
    )
)

REM Clear existing contents, then extract archive
docker run --rm ^
  -v "%VOL_NAME%:/volume" ^
  -v "%BACKUP_DIR%:/backup:ro" ^
  %ALPINE_IMAGE% ^
  sh -c "find /volume -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar xzf /backup/%IN_FILE% -C /volume"
if errorlevel 1 (
    echo ERROR: failed to restore %VOL_NAME%
    exit /b 1
)
echo        OK
exit /b 0

REM --------------------------------------------------------------------------
:restore_teoco
set "ARCHIVE=%BACKUP_DIR%\teoco_data_store.tar.gz"
if not exist "%ARCHIVE%" (
    echo SKIP  teoco_data_store.tar.gz not in backup
    exit /b 0
)

set "TEOCO_DIR="
set "TEOCO_RAW="

if exist "%BACKUP_DIR%\teoco_data_store.source.txt" (
    set /p TEOCO_DIR=<"%BACKUP_DIR%\teoco_data_store.source.txt"
)

if not defined TEOCO_DIR (
    if exist "%REPO%\.env" (
        for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /c:"TEOCO_DATA_DIR=" "%REPO%\.env"`) do set "TEOCO_RAW=%%B"
    )
    if defined TEOCO_RAW (
        for /f "delims=" %%P in ('powershell -NoProfile -Command "$p='%TEOCO_RAW%'; $p=$p -replace '\$\{USERPROFILE\}',$env:USERPROFILE -replace '%%USERPROFILE%%',$env:USERPROFILE; [Environment]::ExpandEnvironmentVariables($p)"') do set "TEOCO_DIR=%%P"
    )
)

if not defined TEOCO_DIR (
    echo ERROR: cannot determine TEOCO_DATA_DIR for restore
    exit /b 1
)

if not exist "%TEOCO_DIR%" mkdir "%TEOCO_DIR%"

echo RESTORE teoco_data_store.tar.gz  -^>  %TEOCO_DIR%
docker run --rm ^
  -v "%TEOCO_DIR%:/data" ^
  -v "%BACKUP_DIR%:/backup:ro" ^
  %ALPINE_IMAGE% ^
  sh -c "find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar xzf /backup/teoco_data_store.tar.gz -C /data"
if errorlevel 1 (
    echo ERROR: failed to restore TEOCO_DATA_DIR
    exit /b 1
)
echo        OK
exit /b 0
