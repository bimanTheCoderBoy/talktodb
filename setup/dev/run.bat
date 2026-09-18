@echo off
setlocal EnableDelayedExpansion

:: ============================================================================
:: AAN Dev Runner  (uv workspace)
::
::   run.bat -base              postgres, phoenix, agent_server, frontend, rag
::   run.bat -asp               base + redis, acss-api, acss-worker
::   run.bat -pipeline          base + pipeline (streamlit)
::   run.bat -download          base + redis, download-api, download-worker
::   run.bat -all               everything
::
:: Flags are combinable:  run.bat -asp -pipeline
:: ============================================================================

set "ROOT=%~dp0..\.."
pushd "%ROOT%" && set "ROOT=%CD%" && popd

set "BASE=0"
set "ASP=0"
set "PIPE=0"
set "DL=0"
set "RAG=0"

:args
if "%~1"=="" goto :validate
if /I "%~1"=="-base"      ( set "BASE=1" & set "RAG=1" & shift & goto :args )
if /I "%~1"=="-asp"       ( set "ASP=1"  & shift & goto :args )
if /I "%~1"=="-pipeline"  ( set "PIPE=1" & shift & goto :args )
if /I "%~1"=="-download"  ( set "DL=1"   & shift & goto :args )
if /I "%~1"=="-rag"       ( set "RAG=1"  & shift & goto :args )
if /I "%~1"=="-all"       ( set "ASP=1"  & set "PIPE=1" & set "DL=1" & set "RAG=1" & shift & goto :args )
echo [ERR] Unknown flag: %~1
echo Usage: run.bat -base ^| -asp ^| -pipeline ^| -download ^| -rag ^| -all
exit /b 1

:validate
if "%BASE%"=="0" if "%ASP%"=="0" if "%PIPE%"=="0" if "%DL%"=="0" if "%RAG%"=="0" (
    echo [ERR] No flag provided.
    echo Usage: run.bat -base ^| -asp ^| -pipeline ^| -download ^| -rag ^| -all
    exit /b 1
)

:: -asp / -pipeline / -download / -rag imply base (RAG is part of base)
if "%ASP%"=="1"  ( set "BASE=1" & set "RAG=1" )
if "%PIPE%"=="1" ( set "BASE=1" & set "RAG=1" )
if "%DL%"=="1"   ( set "BASE=1" & set "RAG=1" )
if "%RAG%"=="1"  set "BASE=1"

:: Determine whether redis is needed
set "NEED_REDIS=0"
if "%ASP%"=="1" set "NEED_REDIS=1"
if "%DL%"=="1"  set "NEED_REDIS=1"

:: ============================== STEP 1 : AUTH ==============================
echo.
echo [1/5] Checking Keycloak auth server ...
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
echo [2/5] Docker compose services ^(detached^) ...

:: --- Postgres ---
echo   Starting: postgres
docker compose -f "%ROOT%\docker-compose.yml" up -d postgres
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] postgres start failed. & exit /b 1 )

echo   Waiting for postgres ...
:wp
docker inspect -f "{{.State.Health.Status}}" app_postgres 2>nul | findstr /C:"healthy" >nul 2>&1
if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wp )
echo   [OK] postgres healthy.

:: --- Phoenix ---
echo   Starting: phoenix
docker compose -f "%ROOT%\docker-compose.yml" up -d phoenix
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] phoenix start failed. & exit /b 1 )

echo   Waiting for phoenix ...
:wph
docker inspect -f "{{.State.Status}}" phoenix 2>nul | findstr /C:"running" >nul 2>&1
if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wph )
echo   [OK] phoenix running.

:: --- Redis (when ASP or Download is requested) ---
if "%NEED_REDIS%"=="0" goto :compose_done

echo   Starting: redis
docker compose -f "%ROOT%\docker-compose.yml" up -d redis
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] redis start failed. & exit /b 1 )

echo   Waiting for redis ...
:wr
docker inspect -f "{{.State.Health.Status}}" app_redis 2>nul | findstr /C:"healthy" >nul 2>&1
if %ERRORLEVEL% NEQ 0 ( timeout /t 2 /nobreak >nul & goto :wr )
echo   [OK] redis healthy.

:compose_done

:: ============================== STEP 3 : CORE ==============================
echo.
echo [3/5] Core stack ...

echo   -^> new terminal: Backend  ^(langgraph dev^)
start "AAN-Backend" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- Backend (langgraph dev) ---' -Fore Cyan; uv run --package agent-server --directory agent_server langgraph dev"

echo   -^> new terminal: Frontend ^(npm run dev^)
start "AAN-Frontend" powershell -NoExit -Command ^
  "cd '%ROOT%\frontend'; Write-Host '--- Frontend (npm run dev) ---' -Fore Cyan; npm run dev"

:: ============================== STEP 4 : ASP ===============================
if "%ASP%"=="0" goto :skip_asp

echo.
echo [4/5] ASP / ACSS services ...

echo   -^> new terminal: ACSS API
start "ACSS-API" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- ACSS API ---' -Fore Cyan; uv run --package asp-server --directory asp_server python -m asp_app.main"

echo   -^> new terminal: ACSS Worker ^(celery^)
start "ACSS-Worker" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- ACSS Worker ---' -Fore Cyan; uv run --package asp-server --directory asp_server celery -A asp_app.celery_app worker -Q acss_heavy -l info -c 2 -P solo"

:skip_asp

:: ============================== STEP 4b : DOWNLOAD =========================
if "%DL%"=="0" goto :skip_dl

echo.
echo [4/5] Download services ...

echo   -^> new terminal: Download API ^(uvicorn^)
start "Download-API" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- Download API ---' -Fore Cyan; uv run --package download-service --directory download_service uvicorn download_app.main:app --host 0.0.0.0 --port 8000"

echo   -^> new terminal: Download Worker ^(celery^)
start "Download-Worker" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- Download Worker ---' -Fore Cyan; uv run --package download-service --directory download_service celery -A download_app.tasks.celery_tasks:celery_app worker -Q download_fast -l info -c 4 -P solo"

:skip_dl

:: ============================== STEP 4c : RAG ==============================
if "%RAG%"=="0" goto :skip_rag

echo.
echo [4/5] RAG Retrieval services ...

echo   -^> new terminal: RAG Retrieval Server
start "RAG-Retrieval" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- RAG Retrieval Server ---' -Fore Cyan; uv run --package rag-retrieval-server --directory rag_retrieval_server python -m retrieval_app.server"

:skip_rag

:: ============================== STEP 5 : PIPELINE ==========================
if "%PIPE%"=="0" goto :skip_pipe

echo.
echo [5/5] Pipeline ^(Streamlit^) ...

echo   -^> new terminal: Pipeline ^(streamlit^)
start "AAN-Pipeline" powershell -NoExit -Command ^
  "cd '%ROOT%'; Write-Host '--- Pipeline Streamlit ---' -Fore Cyan; uv run --package eds-pipeline --directory pipeline python entrypoint.py"

:skip_pipe

:: ============================== SUMMARY ====================================
echo.
echo ==========================================
echo   AAN Dev Environment
echo ==========================================
echo   Auth     : https://localhost:8443
echo   Postgres : localhost:5432  ^(compose -d^)
echo   Phoenix  : localhost:6006  ^(compose -d^)
if "%NEED_REDIS%"=="1" echo   Redis    : localhost:6379  ^(compose -d^)
echo   Backend  : localhost:2024  ^(langgraph dev^)
echo   Frontend : localhost:5173  ^(vite dev^)
if "%ASP%"=="1" (
    echo   ACSS API : localhost:8001  ^(uvicorn^)
    echo   ACSS Wkr : celery acss_heavy
)
if "%DL%"=="1" (
    echo   Download : localhost:8000  ^(uvicorn^)
    echo   DL Wkr   : celery download_fast
)
if "%RAG%"=="1" echo   RAG      : localhost:8010  ^(uvicorn^)
if "%PIPE%"=="1" echo   Pipeline : localhost:8501  ^(streamlit^)
echo ==========================================

endlocal
