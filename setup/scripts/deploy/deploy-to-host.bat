@echo off
REM ============================================================================
REM  Deploy AAN stack to a new hostname (Windows).
REM
REM  Usage:
REM    setup\scripts\deploy\deploy-to-host.bat <hostname> <smb-user> <smb-password> [options]
REM
REM  Options:
REM    --network_bill <path>     Override network BIL share path
REM    --eds_url <host:port>     Override EDS API host:port
REM    --cwe_url <host:port>     Override CWE API host:port
REM
REM  Example:
REM    setup\scripts\deploy\deploy-to-host.bat grgd-scm-vm01.ap.teo.earth chandan MyP@ss
REM    setup\scripts\deploy\deploy-to-host.bat host.domain user pass --eds_url newhost:8687
REM
REM  Prerequisites:
REM    - Run setup\scripts\local-build\local-build.bat -all  FIRST
REM      (builds wheels + requirements into each service's dist/ folder)
REM
REM  Steps:
REM    1.  docker compose down  (auth_server)
REM    2.  docker compose down  (root / core services)
REM    3.  Check required ports are free
REM    4.  Generate TLS certificate for new hostname
REM    5.  (reserved — Keycloak volume removal, currently disabled)
REM    6.  Rewrite hostname / credentials in .env files
REM    7.  docker compose build (builds images from pre-built dist/ wheels)
REM    8.  docker compose up -d (auth_server — Keycloak first, creates external network)
REM    9.  docker compose up -d (root — core services)
REM ============================================================================

setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM --- Validate minimum arguments ---
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage

REM --- Locate repo root (script lives in setup\scripts\deploy\) ---
set "SCRIPT_DIR=%~dp0"
echo "SCRIPT_DIR: %SCRIPT_DIR%"
pushd "%SCRIPT_DIR%..\..\.."
set "REPO=%CD%"
popd

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



echo ===============================================================
echo   AAN Deploy-to-Host  (Windows)
echo   Hostname : %NEW_HOST%
echo   SMB User : %SMB_USER%
echo   Repo     : %REPO%
if not "%OPT_NETWORK_BILL%"=="" echo   Network BIL : %OPT_NETWORK_BILL%
if not "%OPT_EDS_URL%"=="" echo   EDS URL     : %OPT_EDS_URL%
if not "%OPT_CWE_URL%"=="" echo   CWE URL     : %OPT_CWE_URL%
echo ===============================================================
echo.

REM =====================================================================
REM  PRE-FLIGHT — Verify dist/ folders exist (local-build.bat must run first)
REM =====================================================================
echo [pre-flight] Checking that wheel artifacts exist...
set "PREFLIGHT_OK=1"
for %%D in (agent_server rag_retrieval_server) do (
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
REM  STEP 1 — docker compose down (auth_server)
REM =====================================================================
echo [1/9] Stopping auth_server containers...
docker compose -f "%REPO%\auth_server\docker-compose.yml" --env-file "%REPO%\auth_server\.env" down
if errorlevel 1 (
    echo        WARNING: auth_server compose down returned an error (may already be stopped^)
) else (
    echo        OK
)
echo.

REM =====================================================================
REM  STEP 2 — docker compose down (core services)
REM =====================================================================
echo [2/9] Stopping core-service containers...
docker compose -f "%REPO%\docker-compose.yml" --env-file "%REPO%\.env" down
if errorlevel 1 (
    echo        WARNING: core compose down returned an error (may already be stopped^)
) else (
    echo        OK
)
echo.

REM =====================================================================
REM  STEP 3 — Check required ports are free
REM =====================================================================
echo [3/9] Checking required ports are free...
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
echo        OK — all ports free
echo.

REM =====================================================================
REM  STEP 4 — Generate TLS certificate
REM =====================================================================
echo [4/9] Generating TLS certificate for %NEW_HOST%...
set "CERT_SCRIPT=%REPO%\setup\certs\generate-certs.ps1"
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
REM  STEP 5 — Remove Keycloak Postgres volume (force realm re-import)
REM =====================================================================
@REM echo [5/9] Removing Keycloak DB volume (forces fresh realm import)...
@REM docker volume rm aana_auth_server_keycloak_postgres_data >nul 2>nul
@REM if errorlevel 1 (
@REM     echo        WARNING: Volume not found or already removed — continuing
@REM ) else (
@REM     echo        OK — volume removed
@REM )
@REM echo.

REM =====================================================================
REM  STEP 6 — Rewrite .env files
REM =====================================================================
echo [6/9] Updating environment files...

REM --- 6a) .env (root) ---
echo        6a) .env  (SMB_USERNAME, SMB_PASSWORD, VITE_KEYCLOAK_URL, TEOCO_DATA_DIR)
set "ENV_FILE=%REPO%\.env"
powershell -ExecutionPolicy Bypass -Command ^
  "$f = Get-Content '%ENV_FILE%' -Raw;" ^
  "$f = $f -replace '(?m)^SMB_USERNAME=.*$',  'SMB_USERNAME=%SMB_USER%';" ^
  "$f = $f -replace '(?m)^SMB_PASSWORD=.*$',  'SMB_PASSWORD=%SMB_PASS%';" ^
  "$f = $f -replace '(?m)^VITE_KEYCLOAK_URL=.*$', 'VITE_KEYCLOAK_URL=https://%NEW_HOST%:8443';" ^
  "$f = $f -replace '(?m)^TEOCO_DATA_DIR=.*$', 'TEOCO_DATA_DIR=$${USERPROFILE}/teoco_data_store';" ^
  "[IO.File]::WriteAllText('%ENV_FILE%', $f)"
if errorlevel 1 (
    echo        ERROR writing .env
    exit /b 1
)
echo        OK

REM --- 6b) auth_server/.env ---
echo        6b) auth_server\.env  (KC_HOSTNAME)
set "AUTH_ENV=%REPO%\auth_server\.env"
powershell -ExecutionPolicy Bypass -Command ^
  "$f = Get-Content '%AUTH_ENV%' -Raw;" ^
  "$f = $f -replace '(?m)^KC_HOSTNAME=.*$', 'KC_HOSTNAME=%NEW_HOST%';" ^
  "[IO.File]::WriteAllText('%AUTH_ENV%', $f)"
if errorlevel 1 (
    echo        ERROR writing auth_server\.env
    exit /b 1
)
echo        OK

REM --- 6c) setup/prod_envs/agent_server/.env ---
echo        6c) setup\prod_envs\agent_server\.env  (KEYCLOAK_ISSUER)
set "BE_ENV=%REPO%\setup\prod_envs\agent_server\.env"
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

REM --- 6d) setup/prod_envs/asp_backend/.env ---
echo        6d) setup\prod_envs\asp_backend\.env  (KEYCLOAK_ISSUER)
set "ACSS_ENV=%REPO%\setup\prod_envs\asp_backend\.env"
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
REM  STEP 6e-g — Apply optional overrides (--network_bill, --eds_url, --cwe_url)
REM =====================================================================
if not "%OPT_NETWORK_BILL%"=="" (
    echo        6e - Applying --network_bill override: %OPT_NETWORK_BILL%
    call :apply_network_bill "%OPT_NETWORK_BILL%"
)

if not "%OPT_EDS_URL%"=="" (
    echo        6f - Applying --eds_url override: %OPT_EDS_URL%
    call :apply_eds_url "%OPT_EDS_URL%"
)

if not "%OPT_CWE_URL%"=="" (
    echo        6g - Applying --cwe_url override: %OPT_CWE_URL%
    call :apply_cwe_url "%OPT_CWE_URL%"
)
echo.

REM =====================================================================
REM  STEP 7 — docker compose build (core services)
REM  BuildKit is required for --mount=type=cache in Dockerfiles.
REM =====================================================================
echo [7/9] Building Docker images from pre-built dist/ wheels...
set "DOCKER_BUILDKIT=1"
set "COMPOSE_DOCKER_CLI_BUILD=1"
docker compose -f "%REPO%\docker-compose.yml" --env-file "%REPO%\.env" build
if errorlevel 1 (
    echo        ERROR: docker compose build failed
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 8 — docker compose up -d (auth_server — must start first)
REM =====================================================================
echo [8/9] Starting auth_server (Keycloak)...
docker compose -f "%REPO%\auth_server\docker-compose.yml" --env-file "%REPO%\auth_server\.env" up -d
if errorlevel 1 (
    echo        ERROR: auth_server compose up failed
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 9 — docker compose up -d (core services)
REM =====================================================================
echo [9/9] Starting core services...
docker compose -f "%REPO%\docker-compose.yml" --env-file "%REPO%\.env" up -d
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
set "PIPE_ENV=%REPO%\setup\prod_envs\pipeline\.env"
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
echo   AAN Deploy-to-Host — Build and deploy the full stack
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
echo     %~nx0 grgd-scm-vm01.ap.teo.earth jondoe MyP@ss
echo     %~nx0 host.domain user pass --eds_url newhost:8687
echo     %~nx0 host.domain user pass --network_bill //server/share --eds_url h:8687 --cwe_url h:9984
echo.
echo   Prerequisites:
echo     Run setup\scripts\local-build\local-build.bat -all FIRST
exit /b 1
