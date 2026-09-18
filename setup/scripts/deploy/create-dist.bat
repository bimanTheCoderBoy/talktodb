@echo off
REM ============================================================================
REM  Build all Docker images and package them into a portable dist/ folder.
REM
REM  Usage:
REM    setup\scripts\deploy\create-dist.bat
REM
REM  Output:
REM    dist\               — ready-to-ship folder with everything QA needs
REM    dist\all-images.tar — every Docker image (built + pulled)
REM    dist\start.bat      — QA runs: start.bat <hostname> <smb-user> <smb-pass>
REM ============================================================================

setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM --- Locate repo root (script lives in setup\scripts\deploy\) ---
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\.."
set "REPO=%CD%"
popd

set "DIST=%REPO%\dist"

echo ===============================================================
echo   AAN Create-Dist  (Windows)
echo   Repo : %REPO%
echo   Dist : %DIST%
echo ===============================================================
echo.

REM =====================================================================
REM  PRE-FLIGHT — Verify dist/ folders exist (local-build.bat must run first)
REM =====================================================================
echo [pre-flight] Checking that wheel artifacts exist...
set "PREFLIGHT_OK=1"
for %%D in (asp_server agent_server pipeline download_service rag_retrieval_server) do (
    if not exist "%REPO%\%%D\dist\requirements.txt" (
        echo        MISSING: %%D\dist\requirements.txt
        set "PREFLIGHT_OK=0"
    )
)
if "%PREFLIGHT_OK%"=="0" (
    echo.
    echo        ERROR: One or more dist/ folders are missing.
    echo        Run  setup\scripts\local-build\local-build.bat -all  first.
    exit /b 1
)
echo        OK — all dist/ folders present
echo.

REM =====================================================================
REM  STEP 1 — Build all custom images from pre-built dist/ wheels
REM =====================================================================
echo [1/5] Building all Docker images from pre-built dist/ wheels...
docker compose -f "%REPO%\docker-compose.yml" --env-file "%REPO%\.env" build
if errorlevel 1 (
    echo        ERROR: docker compose build failed
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 2 — Pull third-party images
REM =====================================================================
echo [2/5] Ensuring third-party images are available...
for %%I in (
    "postgis/postgis:16-3.4"
    "redis:7-alpine"
    "amir20/dozzle:v10.7.1"
    "arizephoenix/phoenix:20.3.0"
    "postgres:16-alpine"
    "quay.io/keycloak/keycloak:25.0.2"
) do (
    docker image inspect %%~I >nul 2>nul
    if errorlevel 1 (
        echo        Pulling %%~I ...
        docker pull %%~I
        if errorlevel 1 (
            echo        ERROR: Failed to pull %%~I
            exit /b 1
        )
    ) else (
        echo        Already present: %%~I
    )
)
echo        OK
echo.

REM =====================================================================
REM  STEP 3 — Save all images into a single tar
REM =====================================================================
echo [3/5] Saving all images to all-images.tar (this may take a while)...

if exist "%DIST%" rmdir /s /q "%DIST%"
mkdir "%DIST%"

docker save -o "%DIST%\all-images.tar" ^
    aana_core_services-frontend ^
    aana_core_services-agent_server ^
    aana_core_services-download_api ^
    aana_core_services-download_worker ^
    aana_core_services-acss_api ^
    aana_core_services-acss_worker ^
    aana_core_services-pipeline_streamlit ^
    aana_core_services-rag_retrieval_server ^
    postgis/postgis:16-3.4 ^
    redis:7-alpine ^
    amir20/dozzle:v10.7.1 ^
    arizephoenix/phoenix:20.3.0 ^
    postgres:16-alpine ^
    quay.io/keycloak/keycloak:25.0.2
if errorlevel 1 (
    echo        ERROR: docker save failed
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 4 — Assemble config files into dist/
REM =====================================================================
echo [4/5] Copying config files to dist\ ...

REM --- Root compose + env ---
copy "%REPO%\docker-compose.yml" "%DIST%\docker-compose.yml" >nul
copy "%REPO%\.env"               "%DIST%\.env"               >nul

REM --- Auth server ---
mkdir "%DIST%\auth_server\realms" 2>nul
copy "%REPO%\auth_server\docker-compose.yml" "%DIST%\auth_server\docker-compose.yml" >nul
if exist "%REPO%\auth_server\.env" (
    copy "%REPO%\auth_server\.env" "%DIST%\auth_server\.env" >nul
)
xcopy "%REPO%\auth_server\realms" "%DIST%\auth_server\realms" /E /I /Q /Y >nul

REM --- TLS certs ---
mkdir "%DIST%\setup\certs" 2>nul
if exist "%REPO%\setup\certs\tls.crt" (
    copy "%REPO%\setup\certs\tls.crt" "%DIST%\setup\certs\tls.crt" >nul
    copy "%REPO%\setup\certs\tls.key" "%DIST%\setup\certs\tls.key" >nul
)
copy "%REPO%\setup\certs\generate-certs.ps1" "%DIST%\setup\certs\generate-certs.ps1" >nul
copy "%REPO%\setup\certs\generate-certs.sh" "%DIST%\setup\certs\generate-certs.sh" >nul

REM --- Prod env files ---
mkdir "%DIST%\setup\prod_envs\agent_server"      2>nul
mkdir "%DIST%\setup\prod_envs\asp_backend"   2>nul
mkdir "%DIST%\setup\prod_envs\pipeline"      2>nul
mkdir "%DIST%\setup\prod_envs\rag_retrieval_server" 2>nul
if exist "%REPO%\setup\prod_envs\agent_server\.env" (
    copy "%REPO%\setup\prod_envs\agent_server\.env"     "%DIST%\setup\prod_envs\agent_server\.env"     >nul
)
if exist "%REPO%\setup\prod_envs\asp_backend\.env" (
    copy "%REPO%\setup\prod_envs\asp_backend\.env"  "%DIST%\setup\prod_envs\asp_backend\.env"  >nul
)
if exist "%REPO%\setup\prod_envs\pipeline\.env" (
    copy "%REPO%\setup\prod_envs\pipeline\.env"     "%DIST%\setup\prod_envs\pipeline\.env"     >nul
)
if exist "%REPO%\setup\prod_envs\rag_retrieval_server\.env" (
    copy "%REPO%\setup\prod_envs\rag_retrieval_server\.env" "%DIST%\setup\prod_envs\rag_retrieval_server\.env" >nul
)

REM --- Postgres init scripts ---
mkdir "%DIST%\setup\scripts\postgres_init_scripts" 2>nul
xcopy "%REPO%\setup\scripts\postgres_init_scripts" "%DIST%\setup\scripts\postgres_init_scripts" /E /I /Q /Y >nul

REM --- Init config data (seed data for teoco_data_store) ---
mkdir "%DIST%\setup\init" 2>nul
copy "%REPO%\setup\init\init.bat" "%DIST%\setup\init\init.bat" >nul
copy "%REPO%\setup\init\init.sh" "%DIST%\setup\init\init.sh" >nul
xcopy "%REPO%\setup\init\init_config_setup" "%DIST%\setup\init\init_config_setup" /E /I /Q /Y >nul

echo        OK
echo.

REM =====================================================================
REM  STEP 5 — Copy start.bat into dist/
REM =====================================================================
echo [5/5] Copying start.bat into dist\ ...
copy "%REPO%\setup\scripts\deploy\start.bat" "%DIST%\start.bat" >nul
copy "%REPO%\setup\scripts\deploy\start.sh" "%DIST%\start.sh" >nul
echo        OK
echo.

REM =====================================================================
REM  Done
REM =====================================================================
echo ===============================================================
echo   dist\ folder is ready!
echo.
echo   Contents:
echo     dist\all-images.tar          — all Docker images
echo     dist\docker-compose.yml      — core services compose
echo     dist\.env                    — root env
echo     dist\auth_server\            — Keycloak compose, env, realm
echo     dist\setup\                  — certs, prod envs, storage init
echo     dist\start.bat               — QA runs this
echo     dist\start.sh                — QA runs this
echo.
echo   Ship the dist\ folder to the target machine.
echo   QA runs:  start.bat ^<hostname^> ^<smb-user^> ^<smb-password^>
echo ===============================================================

endlocal
exit /b 0
