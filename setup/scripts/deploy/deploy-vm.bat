@echo off
REM ============================================================================
REM  Full VM deployment from Windows — push code, ship .env files, run remote.
REM
REM  Requirements:
REM    - Git for Windows (provides ssh + scp)
REM    - SSH access to the VM (key-based recommended, or will prompt for password)
REM    - Repo already cloned on the VM at <remote-path>
REM
REM  Usage:
REM    setup\scripts\deploy\deploy-vm.bat <ssh-user> <smb-user> <smb-password> [host] [remote-path]
REM
REM  Examples:
REM    setup\scripts\deploy\deploy-vm.bat chandan dasbi MyP@ss
REM    setup\scripts\deploy\deploy-vm.bat chandan dasbi MyP@ss grgd-scm-vm01.ap.teo.earth
REM    setup\scripts\deploy\deploy-vm.bat chandan dasbi MyP@ss grgd-scm-vm01.ap.teo.earth /opt/aan01
REM
REM  Steps:
REM    1/6  git push from Windows
REM    2/6  scp .env files to VM (gitignored, must be shipped manually)
REM    3/6  git pull on VM
REM    4/6  Run deploy-to-host.sh on VM (the full 9-step local deploy)
REM    5/6  Check container status (auth_server)
REM    6/6  Check container status (core services)
REM ============================================================================

setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM --- Validate required arguments ---
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage

set "SSHUSER=%~1"
set "SMB_USER=%~2"
set "SMB_PASS=%~3"

set "VMHOST=%~4"
if "%VMHOST%"=="" set "VMHOST=grgd-scm-vm01.ap.teo.earth"

set "REMOTE=%~5"
if "%REMOTE%"=="" set "REMOTE=/opt/aan01"

set "TARGET=%SSHUSER%@%VMHOST%"

REM --- Locate repo root (script lives in setup\scripts\deploy\) ---
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\.."
set "REPO=%CD%"
popd
cd /d "%REPO%"

echo ===============================================================
echo   AAN Remote VM Deploy  (Windows -^> Linux)
echo.
echo   SSH Target  : %TARGET%
echo   VM Hostname : %VMHOST%
echo   Remote Path : %REMOTE%
echo   SMB User    : %SMB_USER%
echo   Local Repo  : %REPO%
echo ===============================================================
echo.

REM =====================================================================
REM  STEP 1/6 — git push from Windows
REM =====================================================================
echo [1/6] Pushing latest code from Windows...
git push
if errorlevel 1 (
    echo.
    echo        ERROR: git push failed. Commit your changes and try again.
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 2/6 — Transfer .env files via scp
REM  These are gitignored so they must be shipped manually.
REM  We send the files that Docker actually reads at runtime.
REM =====================================================================
echo [2/6] Transferring .env files to VM via scp...

REM Ensure remote directories exist
echo        Creating remote directories...
ssh -q "%TARGET%" "mkdir -p %REMOTE%/auth_server %REMOTE%/setup/prod_envs/agent_server %REMOTE%/setup/prod_envs/rag_retrieval_server"

set "SCP_FAIL=0"

REM --- .env (root) ---
if exist "%REPO%\.env" (
    echo        -^> .env
    scp -q "%REPO%\.env" "%TARGET%:%REMOTE%/.env" || set "SCP_FAIL=1"
) else (
    echo        -^> .env  (missing locally, SKIPPED^)
)

REM --- auth_server/.env ---
if exist "%REPO%\auth_server\.env" (
    echo        -^> auth_server/.env
    scp -q "%REPO%\auth_server\.env" "%TARGET%:%REMOTE%/auth_server/.env" || set "SCP_FAIL=1"
) else (
    echo        -^> auth_server/.env  (missing locally, SKIPPED^)
)

REM --- setup/prod_envs/agent_server/.env ---
if exist "%REPO%\setup\prod_envs\agent_server\.env" (
    echo        -^> setup/prod_envs/agent_server/.env
    scp -q "%REPO%\setup\prod_envs\agent_server\.env" "%TARGET%:%REMOTE%/setup/prod_envs/agent_server/.env" || set "SCP_FAIL=1"
) else (
    echo        -^> setup/prod_envs/agent_server/.env  (missing locally, SKIPPED^)
)

REM --- setup/prod_envs/rag_retrieval_server/.env ---
if exist "%REPO%\setup\prod_envs\rag_retrieval_server\.env" (
    echo        -^> setup/prod_envs/rag_retrieval_server/.env
    scp -q "%REPO%\setup\prod_envs\rag_retrieval_server\.env" "%TARGET%:%REMOTE%/setup/prod_envs/rag_retrieval_server/.env" || set "SCP_FAIL=1"
) else (
    echo        -^> setup/prod_envs/rag_retrieval_server/.env  (missing locally, SKIPPED^)
)

if "%SCP_FAIL%"=="1" (
    echo.
    echo        ERROR: One or more scp transfers failed.
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 3/6 — git pull on VM
REM =====================================================================
echo [3/6] Running git pull on VM...
ssh "%TARGET%" "cd %REMOTE% && git pull"
if errorlevel 1 (
    echo.
    echo        ERROR: git pull on VM failed. First time? SSH in and run:
    echo          cd /opt ^&^& git clone ^<your-git-url^> aan01
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 4/6 — Run deploy-to-host.sh on VM (the full 9-step deploy)
REM  This does: compose down, port check, certs, volume rm, env rewrite,
REM             compose build, compose up auth, compose up core.
REM =====================================================================
echo [4/6] Running deploy-to-host.sh on VM (this may take 5-10 min)...
ssh -t "%TARGET%" "cd %REMOTE% && chmod +x setup/scripts/deploy/deploy-to-host.sh setup/scripts/local-build/local-build.sh setup/certs/generate-certs.sh && bash setup/scripts/deploy/deploy-to-host.sh '%VMHOST%' '%SMB_USER%' '%SMB_PASS%'"
if errorlevel 1 (
    echo.
    echo        ERROR: deploy-to-host.sh failed on VM. Check logs:
    echo          ssh %TARGET% "cd %REMOTE% ^&^& docker compose logs --tail=50"
    exit /b 1
)
echo        OK
echo.

REM =====================================================================
REM  STEP 5/6 — Check auth_server container status
REM =====================================================================
echo [5/6] Checking auth_server container status on VM...
ssh "%TARGET%" "cd %REMOTE%/auth_server && docker compose ps"
echo.

REM =====================================================================
REM  STEP 6/6 — Check core-service container status
REM =====================================================================
echo [6/6] Checking core-service container status on VM...
ssh "%TARGET%" "cd %REMOTE% && docker compose ps"
echo.

REM =====================================================================
REM  Done
REM =====================================================================
echo ===============================================================
echo   Remote deployment complete!
echo.
echo   Keycloak : https://%VMHOST%:8443
echo   Frontend : https://%VMHOST%
echo.
echo   Tip: If you see stale Keycloak tokens, clear browser localStorage.
echo ===============================================================

endlocal
exit /b 0

:usage
echo Usage: %~nx0 ^<ssh-user^> ^<smb-user^> ^<smb-password^> [host] [remote-path]
echo.
echo Arguments:
echo   ssh-user      SSH username for the VM
echo   smb-user      SMB/network storage username (written to .env)
echo   smb-password  SMB/network storage password (written to .env)
echo   host          VM hostname (default: grgd-scm-vm01.ap.teo.earth)
echo   remote-path   Repo path on VM (default: /opt/aan01)
echo.
echo Examples:
echo   %~nx0 chandan dasbi MyP@ss
echo   %~nx0 chandan dasbi MyP@ss grgd-scm-vm01.ap.teo.earth
echo   %~nx0 chandan dasbi MyP@ss grgd-scm-vm01.ap.teo.earth /opt/aan01
exit /b 1
