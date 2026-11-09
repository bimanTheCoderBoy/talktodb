@echo off
setlocal EnableDelayedExpansion

:: ============================================================================
:: Dev runner (uv workspace) - bare minimum stack
::
::   run.bat -base    postgres, redis, langgraph dev, frontend, rag
::   (phoenix disabled — using LangSmith for tracing)
:: ============================================================================

set "ROOT=%~dp0..\.."
pushd "%ROOT%" && set "ROOT=%CD%" && popd

echo.
echo [dev] Reset dev session file (PIDs for dev:stop / dev:status) ...
set "DEV_SESSION=%~dp0dev-session.properties"
(
  echo # talkToDB dev session - cleared on each poe dev
  echo started_at=%DATE% %TIME%
) > "%DEV_SESSION%"

if /I not "%~1"=="-base" (
    echo Usage: run.bat -base
    exit /b 1
)

:: ============================== STEP 1 : AUTH ==============================
echo.
echo [1/4] Checking Keycloak auth server ...
docker inspect -f "{{.State.Status}}" keycloak-server 2>nul | findstr /C:"running" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   [FAIL] keycloak-server is NOT running.
    echo          Start it first:
    echo            cd "%ROOT%\auth_server" ^&^& docker compose up -d
    echo.
    exit /b 1
)
echo   [OK] keycloak-server is running.

:: ============================== STEP 2 : COMPOSE ===========================
echo.
echo [2/4] Docker compose services ^(detached^) ...

echo   Starting: postgres, redis
docker compose -f "%ROOT%\docker-compose.yml" up -d postgres redis
REM echo   Starting: postgres, redis, phoenix
REM docker compose -f "%ROOT%\docker-compose.yml" up -d postgres redis phoenix
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] compose start failed. & exit /b 1 )

echo   Waiting for postgres ...
:wp
docker inspect -f "{{.State.Health.Status}}" postgres 2>nul | findstr /C:"healthy" >nul 2>&1
if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wp )
echo   [OK] postgres healthy.

echo   Waiting for redis ...
:wr
docker inspect -f "{{.State.Health.Status}}" redis 2>nul | findstr /C:"healthy" >nul 2>&1
if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wr )
echo   [OK] redis healthy.

REM echo   Waiting for phoenix ...
REM :wph
REM docker inspect -f "{{.State.Status}}" phoenix 2>nul | findstr /C:"running" >nul 2>&1
REM if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wph )
REM echo   [OK] phoenix running.

:: ============================== STEP 3 : CORE ==============================
echo.
echo [3/4] Core stack ...

echo   -^> new terminals: Backend, Frontend, RAG ^(PIDs saved to setup/dev/dev-session.properties^)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-invoke.ps1" -Action StartLocal -Root "%ROOT%"
if errorlevel 1 ( echo   [FAIL] could not start local services. & exit /b 1 )

:: ============================== SUMMARY ====================================
echo.
echo ==========================================
echo   talkToDB dev environment
echo ==========================================
echo   Auth     : https://localhost:8443
echo   Postgres : localhost:5432
echo   Redis    : localhost:6379
REM echo   Phoenix  : localhost:6006
echo   Backend  : localhost:2024  ^(langgraph dev^)
echo   Frontend : localhost:5173
echo   RAG      : localhost:8010
echo ==========================================

endlocal
