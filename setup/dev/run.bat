@echo off
setlocal EnableDelayedExpansion

:: ============================================================================
:: Dev runner (uv workspace) — bare minimum stack
::
::   run.bat -base    postgres, redis, phoenix, langgraph dev, frontend, rag
:: ============================================================================

set "ROOT=%~dp0..\.."
pushd "%ROOT%" && set "ROOT=%CD%" && popd

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

echo   Starting: postgres, redis, phoenix
docker compose -f "%ROOT%\docker-compose.yml" up -d postgres redis phoenix
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] compose start failed. & exit /b 1 )

echo   Waiting for postgres ...
:wp
docker inspect -f "{{.State.Health.Status}}" app_postgres 2>nul | findstr /C:"healthy" >nul 2>&1
if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wp )
echo   [OK] postgres healthy.

echo   Waiting for redis ...
:wr
docker inspect -f "{{.State.Health.Status}}" app_redis 2>nul | findstr /C:"healthy" >nul 2>&1
if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wr )
echo   [OK] redis healthy.

echo   Waiting for phoenix ...
:wph
docker inspect -f "{{.State.Status}}" phoenix 2>nul | findstr /C:"running" >nul 2>&1
if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wph )
echo   [OK] phoenix running.

:: ============================== STEP 3 : CORE ==============================
echo.
echo [3/4] Core stack ...

echo   -^> new terminal: Backend  ^(langgraph dev^)
start "talkToDB-Backend" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- Backend (langgraph dev) ---' -Fore Cyan; uv run --package agent-server --directory agent_server langgraph dev"

echo   -^> new terminal: Frontend ^(npm run dev^)
start "AAN-Frontend" powershell -NoExit -Command ^
  "cd '%ROOT%\frontend'; Write-Host '--- Frontend (npm run dev) ---' -Fore Cyan; npm run dev"

echo   -^> new terminal: RAG Retrieval Server
start "RAG-Retrieval" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- RAG Retrieval Server ---' -Fore Cyan; uv run --package rag-retrieval-server --directory rag_retrieval_server python -m retrieval_app.server"

:: ============================== SUMMARY ====================================
echo.
echo ==========================================
echo   talkToDB dev environment
echo ==========================================
echo   Auth     : https://localhost:8443
echo   Postgres : localhost:5432
echo   Redis    : localhost:6379
echo   Phoenix  : localhost:6006
echo   Backend  : localhost:2024  ^(langgraph dev^)
echo   Frontend : localhost:5173
echo   RAG      : localhost:8010
echo ==========================================

endlocal
