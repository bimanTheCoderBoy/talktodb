@echo off
REM ============================================================================
REM  AAN Start — Load Docker images and launch the full stack.
REM
REM  Usage:
REM    start.bat <hostname> <smb-user> <smb-password> [options]
REM
REM  Options:
REM    --network_bill <path>     Override network BIL share path
REM    --eds_url <host:port>     Override EDS API host:port
REM    --cwe_url <host:port>     Override CWE API host:port
REM
REM  Example:
REM    start.bat grgd-scm-vm01.ap.teo.earth chandan MyP@ss
REM    start.bat grgd-scm-vm01.ap.teo.earth chandan MyP@ss --eds_url newhost:8687
REM
REM  Prerequisites:
REM    - Docker Desktop running
REM    - This folder was created by create-dist.bat
REM ============================================================================

setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM --- Validate minimum arguments ---
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage

set "NEW_HOST=%~1"
set "SMB_USER=%~2"
set "SMB_PASS=%~3"

REM --- Initialize optional flags (empty = use defaults) ---
set "OPT_NETWORK_BILL="
set "OPT_EDS_URL="
set "OPT_CWE_URL="

REM --- Parse optional flags starting from arg 4 ---
shift & shift & shift
:parse_opts
if "%~1"=="" goto :done_opts
if /i "%~1"=="--network_bill" (
    set "OPT_NETWORK_BILL=%~2"
    shift & shift
    goto :parse_opts
)
if /i "%~1"=="--eds_url" (
    set "OPT_EDS_URL=%~2"
    shift & shift
    goto :parse_opts
)
if /i "%~1"=="--cwe_url" (
    set "OPT_CWE_URL=%~2"
    shift & shift
    goto :parse_opts
)
echo WARNING: Unknown option "%~1" — ignoring
shift
goto :parse_opts
:done_opts

REM --- Locate dist root (start.bat lives at dist root) ---
set "DIST=%~dp0"
REM Remove trailing backslash
if "%DIST:~-1%"=="\" set "DIST=%DIST:~0,-1%"

echo ===============================================================
echo   AAN Start  (Windows)
echo   Hostname : %NEW_HOST%
echo   SMB User : %SMB_USER%
echo   Dist     : %DIST%
if not "%OPT_NETWORK_BILL%"=="" echo   Network BIL : %OPT_NETWORK_BILL%
if not "%OPT_EDS_URL%"=="" echo   EDS URL     : %OPT_EDS_URL%
if not "%OPT_CWE_URL%"=="" echo   CWE URL     : %OPT_CWE_URL%
echo ===============================================================
echo.

REM =====================================================================
REM  STEP 1 — Stop any running containers
REM =====================================================================
echo [1/10] Stopping auth_server containers (if running)...
docker compose -f "%DIST%\auth_server\docker-compose.yml" --env-file "%DIST%\auth_server\.env" down 2>nul
echo        OK
echo.

echo [2/10] Stopping core-service containers (if running)...
docker compose -f "%DIST%\docker-compose.yml" --env-file "%DIST%\.env" down 2>nul
echo        OK
echo.

REM =====================================================================
REM  STEP 3 — Check required ports are free
REM =====================================================================
echo [3/10] Checking required ports are free...
set "PORTS=8443 8001 80 443 8502 4317 6006 9999 5432 8003 8009 6379 5433 8002 8010"
set "BLOCKED="
for %%P in (%PORTS%) do (
    netstat -ano 2>nul | findstr /R "LISTENING" | findstr ":%%P " >nul 2>nul
    if not errorlevel 1 (
        echo        BLOCKED: port %%P is in use
        set "BLOCKED=1"
    )
)
if defined BLOCKED (
    echo.
    echo        ERROR: One or more required ports are occupied. Free them and retry.
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 4 — Generate TLS certificate for the hostname
REM =====================================================================
echo [4/10] Generating TLS certificate for %NEW_HOST%...
set "CERT_SCRIPT=%DIST%\setup\certs\generate-certs.ps1"
if not exist "%CERT_SCRIPT%" (
    echo        ERROR: %CERT_SCRIPT% not found
    exit /b 1
)
powershell -ExecutionPolicy Bypass -File "%CERT_SCRIPT%" -Hostname "%NEW_HOST%" -Days 365
if errorlevel 1 (
    echo        ERROR: Certificate generation failed
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 5 — Rewrite .env files with hostname and SMB credentials
REM =====================================================================
echo [5/10] Updating environment files for %NEW_HOST%...

REM --- 5a) .env (root) ---
echo        5a) .env  (SMB_USERNAME, SMB_PASSWORD, VITE_KEYCLOAK_URL, TEOCO_DATA_DIR)
set "ENV_FILE=%DIST%\.env"
powershell -ExecutionPolicy Bypass -Command ^
  "$f = Get-Content '%ENV_FILE%' -Raw;" ^
  "$f = $f -replace '(?m)^SMB_USERNAME=.*$',    'SMB_USERNAME=%SMB_USER%';" ^
  "$f = $f -replace '(?m)^SMB_PASSWORD=.*$',    'SMB_PASSWORD=%SMB_PASS%';" ^
  "$f = $f -replace '(?m)^VITE_KEYCLOAK_URL=.*$','VITE_KEYCLOAK_URL=https://%NEW_HOST%:8443';" ^
  "$f = $f -replace '(?m)^TEOCO_DATA_DIR=.*$',  'TEOCO_DATA_DIR=$${USERPROFILE}/teoco_data_store';" ^
  "[IO.File]::WriteAllText('%ENV_FILE%', $f)"
if errorlevel 1 (
    echo        ERROR writing .env
    exit /b 1
)
echo        OK

REM --- 5b) auth_server\.env ---
echo        5b) auth_server\.env  (KC_HOSTNAME)
set "AUTH_ENV=%DIST%\auth_server\.env"
if exist "%AUTH_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%AUTH_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^KC_HOSTNAME=.*$', 'KC_HOSTNAME=%NEW_HOST%';" ^
      "[IO.File]::WriteAllText('%AUTH_ENV%', $f)"
    if errorlevel 1 (
        echo        ERROR writing auth_server\.env
        exit /b 1
    )
    echo        OK
) else (
    echo        SKIP — auth_server\.env not found
)

REM --- 5c) setup\prod_envs\agent_server\.env ---
echo        5c) setup\prod_envs\agent_server\.env  (KEYCLOAK_ISSUER)
set "BE_ENV=%DIST%\setup\prod_envs\agent_server\.env"
if exist "%BE_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%BE_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^KEYCLOAK_ISSUER=.*$', 'KEYCLOAK_ISSUER=https://%NEW_HOST%:8443';" ^
      "[IO.File]::WriteAllText('%BE_ENV%', $f)"
    if errorlevel 1 (
        echo        ERROR writing backend .env
        exit /b 1
    )
    echo        OK
) else (
    echo        SKIP — file not found
)

REM --- 5d) setup\prod_envs\asp_backend\.env ---
echo        5d) setup\prod_envs\asp_backend\.env  (KEYCLOAK_ISSUER)
set "ACSS_ENV=%DIST%\setup\prod_envs\asp_backend\.env"
if exist "%ACSS_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%ACSS_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^KEYCLOAK_ISSUER=.*$', 'KEYCLOAK_ISSUER=https://%NEW_HOST%:8443';" ^
      "[IO.File]::WriteAllText('%ACSS_ENV%', $f)"
    if errorlevel 1 (
        echo        ERROR writing asp_backend .env
        exit /b 1
    )
    echo        OK
) else (
    echo        SKIP — file not found
)

REM =====================================================================
REM  STEP 5e — Apply optional overrides (--network_bill, --eds_url, --cwe_url)
REM =====================================================================
if not "%OPT_NETWORK_BILL%"=="" (
    echo        5e - Applying --network_bill override: %OPT_NETWORK_BILL%
    call :apply_network_bill "%OPT_NETWORK_BILL%"
)

if not "%OPT_EDS_URL%"=="" (
    echo        5f - Applying --eds_url override: %OPT_EDS_URL%
    call :apply_eds_url "%OPT_EDS_URL%"
)

if not "%OPT_CWE_URL%"=="" (
    echo        5g - Applying --cwe_url override: %OPT_CWE_URL%
    call :apply_cwe_url "%OPT_CWE_URL%"
)
echo.

REM =====================================================================
REM  STEP 6 — Load all Docker images from tar
REM =====================================================================
echo [6/10] Loading Docker images from all-images.tar (this may take a while)...
docker load -i "%DIST%\all-images.tar"
if errorlevel 1 (
    echo        ERROR: docker load failed
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 7 — Create TEOCO data store directory
REM =====================================================================
echo [7/10] Ensuring TEOCO data store directory exists...
if not exist "%USERPROFILE%\teoco_data_store" (
    mkdir "%USERPROFILE%\teoco_data_store"
    echo        Created %USERPROFILE%\teoco_data_store
) else (
    echo        Already exists
)
echo.

REM =====================================================================
REM  STEP 8 — Copy initial seed data into teoco_data_store
REM =====================================================================
echo [8/10] Copying initial config data to teoco_data_store...
set "INIT_BAT=%DIST%\setup\init\init.bat"
if exist "%INIT_BAT%" (
    call "%INIT_BAT%"
    if errorlevel 1 (
        echo        ERROR: init.bat failed
        exit /b 1
    )
    echo        OK
) else (
    echo        SKIP — init.bat not found
)
echo.

REM =====================================================================
REM  STEP 9 — Start auth_server (Keycloak must start first)
REM =====================================================================
echo [9/10] Starting auth_server (Keycloak)...
docker compose -f "%DIST%\auth_server\docker-compose.yml" --env-file "%DIST%\auth_server\.env" up -d
if errorlevel 1 (
    echo        ERROR: auth_server compose up failed
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 10 — Start core services
REM =====================================================================
echo [10/10] Starting core services...
docker compose -f "%DIST%\docker-compose.yml" --env-file "%DIST%\.env" up -d
if errorlevel 1 (
    echo        ERROR: core compose up failed
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  Done
REM =====================================================================
echo ===============================================================
echo   Deployment complete!
echo.
echo   Keycloak : https://%NEW_HOST%:8443
echo   Frontend : https://%NEW_HOST%
echo   Dozzle   : http://%NEW_HOST%:9999
echo   Pipeline : http://%NEW_HOST%:8502
echo   Phoenix  : http://%NEW_HOST%:6006
echo   RAG      : http://%NEW_HOST%:8010
echo.
echo   Tip: If you see certificate warnings, that's expected (self-signed).
echo   Tip: If you see stale Keycloak tokens, clear browser localStorage.
echo ===============================================================

endlocal
exit /b 0

REM =====================================================================
REM  SUBROUTINE: apply_network_bill
REM  Updates .env files for network BIL path (full path like //server/share)
REM =====================================================================
:apply_network_bill
set "_NET_PATH=%~1"
REM Convert forward slashes to UNC format for env files (backslashes)
set "_NET_UNC=%_NET_PATH:/=\%"

REM --- .env (root): NETWORK_BIL_PATH (used by docker-compose.yml) ---
if exist "%ENV_FILE%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%ENV_FILE%' -Raw;" ^
      "$f = $f -replace '(?m)^NETWORK_BIL_PATH=.*$', 'NETWORK_BIL_PATH=%_NET_PATH%';" ^
      "[IO.File]::WriteAllText('%ENV_FILE%', $f)"
    echo            .env NETWORK_BIL_PATH updated
)

REM --- setup\prod_envs\asp_backend\.env: COVERAGE_ROOT_OUTPUT_LOCATION ---
if exist "%ACSS_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%ACSS_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^COVERAGE_ROOT_OUTPUT_LOCATION=.*$', 'COVERAGE_ROOT_OUTPUT_LOCATION=%_NET_UNC%';" ^
      "[IO.File]::WriteAllText('%ACSS_ENV%', $f)"
    echo            asp_backend\.env COVERAGE_ROOT_OUTPUT_LOCATION updated
)

REM --- setup\prod_envs\agent_server\.env: ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION ---
if exist "%BE_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%BE_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION=.*$', 'ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION=%_NET_UNC%';" ^
      "[IO.File]::WriteAllText('%BE_ENV%', $f)"
    echo            agent_server\.env ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION updated
)
exit /b 0

REM =====================================================================
REM  SUBROUTINE: apply_eds_url
REM  Updates EDS API URLs in all relevant env files
REM =====================================================================
:apply_eds_url
set "_EDS_HOST=%~1"

REM --- setup\prod_envs\asp_backend\.env ---
if exist "%ACSS_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%ACSS_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^EDS_CREATE_URL=.*$', 'EDS_CREATE_URL=http://%_EDS_HOST%/v1/EDS/Create';" ^
      "$f = $f -replace '(?m)^EDS_DELETE_URL=.*$', 'EDS_DELETE_URL=http://%_EDS_HOST%/v1/EDS/Delete';" ^
      "[IO.File]::WriteAllText('%ACSS_ENV%', $f)"
    echo            asp_backend\.env EDS_CREATE_URL, EDS_DELETE_URL updated
)

REM --- setup\prod_envs\agent_server\.env ---
if exist "%BE_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%BE_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^EDS_API_BASE_URL=.*$', 'EDS_API_BASE_URL=http://%_EDS_HOST%/v1/EDS/Update/';" ^
      "$f = $f -replace '(?m)^EDS_UPDATE_URL=.*$', 'EDS_UPDATE_URL=http://%_EDS_HOST%/v1/EDS/Update';" ^
      "[IO.File]::WriteAllText('%BE_ENV%', $f)"
    echo            agent_server\.env EDS_API_BASE_URL, EDS_UPDATE_URL updated
)

REM --- setup\prod_envs\pipeline\.env ---
set "PIPE_ENV=%DIST%\setup\prod_envs\pipeline\.env"
if exist "%PIPE_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%PIPE_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^EDS_API_BASE_URL=.*$', 'EDS_API_BASE_URL=http://%_EDS_HOST%/v1/EDS/Query/';" ^
      "[IO.File]::WriteAllText('%PIPE_ENV%', $f)"
    echo            pipeline\.env EDS_API_BASE_URL updated
)
exit /b 0

REM =====================================================================
REM  SUBROUTINE: apply_cwe_url
REM  Updates CWE (Coverage) API URLs in all relevant env files
REM =====================================================================
:apply_cwe_url
set "_CWE_HOST=%~1"

REM --- setup\prod_envs\asp_backend\.env ---
if exist "%ACSS_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%ACSS_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^COVERAGE_API_CREATE_ENDPOINT=.*$', 'COVERAGE_API_CREATE_ENDPOINT=http://%_CWE_HOST%/v1/CWE/create';" ^
      "$f = $f -replace '(?m)^COVERAGE_API_STATUS_ENDPOINT=.*$', 'COVERAGE_API_STATUS_ENDPOINT=http://%_CWE_HOST%/v1/CWE/query';" ^
      "[IO.File]::WriteAllText('%ACSS_ENV%', $f)"
    echo            asp_backend\.env COVERAGE_API_CREATE_ENDPOINT, COVERAGE_API_STATUS_ENDPOINT updated
)

REM --- setup\prod_envs\agent_server\.env ---
if exist "%BE_ENV%" (
    powershell -ExecutionPolicy Bypass -Command ^
      "$f = Get-Content '%BE_ENV%' -Raw;" ^
      "$f = $f -replace '(?m)^COVERAGE_API_CREATE_COVERAGE_ENDPOINT=.*$', 'COVERAGE_API_CREATE_COVERAGE_ENDPOINT=http://%_CWE_HOST%/v1/CWE/create';" ^
      "$f = $f -replace '(?m)^COVERAGE_API_STATUS_POLLING_ENDPOINT=.*$', 'COVERAGE_API_STATUS_POLLING_ENDPOINT=http://%_CWE_HOST%/v1/CWE/query/';" ^
      "[IO.File]::WriteAllText('%BE_ENV%', $f)"
    echo            agent_server\.env COVERAGE_API_CREATE_COVERAGE_ENDPOINT, COVERAGE_API_STATUS_POLLING_ENDPOINT updated
)
exit /b 0

:usage
echo ===============================================================
echo   AAN Start — Load images and launch the full stack
echo ===============================================================
echo.
echo   Usage: %~nx0 ^<hostname^> ^<smb-user^> ^<smb-password^> [options]
echo.
echo   Options:
echo     --network_bill ^<path^>     Override network BIL share path
echo                               e.g. //newserver.domain/Mapdata/Bil_files
echo     --eds_url ^<host:port^>     Override EDS API host:port
echo                               e.g. newhost.domain:8687
echo     --cwe_url ^<host:port^>     Override CWE API host:port
echo                               e.g. newhost.domain:9984
echo.
echo   Example:
echo     %~nx0 grgd-scm-vm01.ap.teo.earth chandan MyP@ss
echo     %~nx0 grgd-scm-vm01.ap.teo.earth chandan MyP@ss --eds_url newhost:8687
echo     %~nx0 host.domain user pass --network_bill //server/share --eds_url h:8687 --cwe_url h:9984
echo.
echo   The hostname is used for:
echo     - TLS certificate generation
echo     - Keycloak URL (https://^<hostname^>:8443)
echo     - Frontend Keycloak config (runtime injection)
echo     - Backend KEYCLOAK_ISSUER
echo.
echo   SMB credentials are used for the network map data volume.
exit /b 1
