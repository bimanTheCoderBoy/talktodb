@echo off
REM ============================================================================
REM  Build wheels + requirements for backend services.
REM
REM  Usage (run from repo root or any directory):
REM    setup\scripts\local-build\local-build.bat [-asp] [-langgraph] [-pipeline] [-download] [-all] [-deps]
REM
REM  Each flag builds:
REM    shared-server-libs wheel (if the target depends on it) +
REM    project wheel  -->  <project>/dist/
REM
REM  The -deps flag forces re-export of requirements.txt even if uv.lock
REM  hasn't changed.  Without -deps, requirements.txt is only regenerated
REM  when uv.lock changes — this preserves Docker layer cache for the
REM  expensive pip-install layer.
REM ============================================================================

setlocal enabledelayedexpansion

REM --- Locate repo root (script lives in setup\scripts\local-build\) ---
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\.."
set "REPO=%CD%"
popd
cd /d "%REPO%"

set "BUILD_ASP=0"
set "BUILD_LANGGRAPH=0"
set "BUILD_PIPELINE=0"
set "BUILD_DOWNLOAD=0"
set "BUILD_RAG=0"
set "FORCE_DEPS=0"

if "%~1"=="" (
    echo Usage: local-build.bat [-asp] [-langgraph] [-pipeline] [-download] [-rag] [-all] [-deps]
    echo.
    echo   -asp        Build shared-server-libs + asp_server wheels into asp_server\dist
    echo   -langgraph  Build shared-server-libs + agent_server wheels into agent_server\dist
    echo   -pipeline   Build shared-server-libs + pipeline wheels into pipeline\dist
    echo   -download   Build download-service wheel into download_service\dist
    echo   -rag        Build shared-server-libs + rag_retrieval_server wheels into rag_retrieval_server\dist
    echo   -all        Build everything
    echo   -deps       Force re-export of requirements.txt even if uv.lock is unchanged
    echo.
    echo You can combine flags: local-build.bat -asp -langgraph -pipeline -download -rag
    exit /b 1
)

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="-asp" set "BUILD_ASP=1"
if /i "%~1"=="-langgraph" set "BUILD_LANGGRAPH=1"
if /i "%~1"=="-pipeline" set "BUILD_PIPELINE=1"
if /i "%~1"=="-download" set "BUILD_DOWNLOAD=1"
if /i "%~1"=="-rag" set "BUILD_RAG=1"
if /i "%~1"=="-deps" set "FORCE_DEPS=1"
if /i "%~1"=="-all" (
    set "BUILD_ASP=1"
    set "BUILD_LANGGRAPH=1"
    set "BUILD_PIPELINE=1"
    set "BUILD_DOWNLOAD=1"
    set "BUILD_RAG=1"
)
shift
goto :parse_args
:done_args

if "%BUILD_ASP%"=="0" if "%BUILD_LANGGRAPH%"=="0" if "%BUILD_PIPELINE%"=="0" if "%BUILD_DOWNLOAD%"=="0" if "%BUILD_RAG%"=="0" (
    echo ERROR: No valid build target specified.
    exit /b 1
)

echo.
echo ===============================================================
echo   AAN Local Build
echo   Repo: %REPO%
echo ===============================================================
echo.

REM =====================================================================
REM  Compute uv.lock hash to decide whether requirements.txt needs
REM  regeneration.  Each service stores the hash it was last exported
REM  against in dist\.lock-hash.
REM =====================================================================
set "LOCK_FILE=%REPO%\uv.lock"
set "CURRENT_LOCK_HASH="
for /f "skip=1 delims=" %%H in ('certutil -hashfile "%LOCK_FILE%" SHA256 2^>nul') do (
    if not defined CURRENT_LOCK_HASH set "CURRENT_LOCK_HASH=%%H"
)
if not defined CURRENT_LOCK_HASH (
    echo WARNING: Could not hash uv.lock — will force requirements export
    set "FORCE_DEPS=1"
)

REM === Build shared-server-libs + wheels (preserve dist/requirements.txt) ===

if "%BUILD_ASP%"=="1" (
    echo === [shared-server-libs] Building for asp_server ===
    if not exist "asp_server\dist" mkdir "asp_server\dist"
    del /q "asp_server\dist\*.whl" 2>nul
    uv build shared_server_libs --wheel --out-dir asp_server\dist
    if !errorlevel! neq 0 (
        echo FAILED: shared-server-libs build ^(for asp^)
        exit /b 1
    )
)

if "%BUILD_LANGGRAPH%"=="1" (
    echo === [shared-server-libs] Building for agent_server ===
    if not exist "agent_server\dist" mkdir "agent_server\dist"
    del /q "agent_server\dist\*.whl" 2>nul
    uv build shared_server_libs --wheel --out-dir agent_server\dist
    if !errorlevel! neq 0 (
        echo FAILED: shared-server-libs build ^(for langgraph^)
        exit /b 1
    )
)

if "%BUILD_PIPELINE%"=="1" (
    echo === [shared-server-libs] Building for pipeline ===
    if not exist "pipeline\dist" mkdir "pipeline\dist"
    del /q "pipeline\dist\*.whl" 2>nul
    uv build shared_server_libs --wheel --out-dir pipeline\dist
    if !errorlevel! neq 0 (
        echo FAILED: shared-server-libs build ^(for pipeline^)
        exit /b 1
    )
)

if "%BUILD_DOWNLOAD%"=="1" (
    echo === [download-service] Preparing dist ===
    if not exist "download_service\dist" mkdir "download_service\dist"
    del /q "download_service\dist\*.whl" 2>nul
)

if "%BUILD_RAG%"=="1" (
    echo === [shared-server-libs] Building for rag_retrieval_server ===
    if not exist "rag_retrieval_server\dist" mkdir "rag_retrieval_server\dist"
    del /q "rag_retrieval_server\dist\*.whl" 2>nul
    uv build shared_server_libs --wheel --out-dir rag_retrieval_server\dist
    if !errorlevel! neq 0 (
        echo FAILED: shared-server-libs build ^(for rag^)
        exit /b 1
    )
)

REM === Build ASP (asp_server) ===
if "%BUILD_ASP%"=="1" (
    echo.
    echo === Building asp-server wheel ===
    uv build asp_server --wheel --out-dir asp_server\dist
    if !errorlevel! neq 0 (
        echo FAILED: asp-server wheel build
        exit /b 1
    )
    call :maybe_export_reqs asp_server asp-server "asp_server\dist"
    if !errorlevel! neq 0 exit /b 1
    echo.
    echo [ASP] Build artifacts:
    dir /b asp_server\dist\*.whl
    echo requirements.txt: asp_server\dist\requirements.txt
    echo.
)

REM === Build LangGraph (agent_server) ===
if "%BUILD_LANGGRAPH%"=="1" (
    echo.
    echo === Building agent_server wheel ===
    uv build agent_server --wheel --out-dir agent_server\dist
    if !errorlevel! neq 0 (
        echo FAILED: agent_server wheel build
        exit /b 1
    )
    call :maybe_export_reqs agent_server agent-server "agent_server\dist"
    if !errorlevel! neq 0 exit /b 1
    echo.
    echo [LangGraph] Build artifacts:
    dir /b agent_server\dist\*.whl
    echo requirements.txt: agent_server\dist\requirements.txt
    echo.
)

REM === Build Pipeline ===
if "%BUILD_PIPELINE%"=="1" (
    echo.
    echo === Building pipeline wheel ===
    uv build pipeline --wheel --out-dir pipeline\dist
    if !errorlevel! neq 0 (
        echo FAILED: pipeline wheel build
        exit /b 1
    )
    call :maybe_export_reqs pipeline eds-pipeline "pipeline\dist"
    if !errorlevel! neq 0 exit /b 1
    echo.
    echo [Pipeline] Build artifacts:
    dir /b pipeline\dist\*.whl
    echo requirements.txt: pipeline\dist\requirements.txt
    echo.
)

REM === Build Download Service ===
if "%BUILD_DOWNLOAD%"=="1" (
    echo.
    echo === Building download-service wheel ===
    uv build download_service --wheel --out-dir download_service\dist
    if !errorlevel! neq 0 (
        echo FAILED: download-service wheel build
        exit /b 1
    )
    call :maybe_export_reqs download_service download-service "download_service\dist"
    if !errorlevel! neq 0 exit /b 1
    echo.
    echo [Download] Build artifacts:
    dir /b download_service\dist\*.whl
    echo requirements.txt: download_service\dist\requirements.txt
    echo.
)

REM === Build RAG Retrieval Server ===
if "%BUILD_RAG%"=="1" (
    echo.
    echo === Building rag_retrieval_server wheel ===
    uv build rag_retrieval_server --wheel --out-dir rag_retrieval_server\dist
    if !errorlevel! neq 0 (
        echo FAILED: rag_retrieval_server wheel build
        exit /b 1
    )
    call :maybe_export_reqs rag_retrieval_server rag-retrieval-server "rag_retrieval_server\dist"
    if !errorlevel! neq 0 exit /b 1
    echo.
    echo [RAG] Build artifacts:
    dir /b rag_retrieval_server\dist\*.whl
    echo requirements.txt: rag_retrieval_server\dist\requirements.txt
    echo.
)

echo.
echo ===============================================================
echo   Build complete! Next steps:
echo ===============================================================
if "%BUILD_ASP%"=="1"       echo   ASP:       docker compose build acss_api
if "%BUILD_LANGGRAPH%"=="1" echo   LangGraph: docker compose build agent_server
if "%BUILD_PIPELINE%"=="1"  echo   Pipeline:  docker compose build pipeline_streamlit
if "%BUILD_DOWNLOAD%"=="1"  echo   Download:  docker compose build download_api
if "%BUILD_RAG%"=="1"       echo   RAG:       docker compose build rag_retrieval_server
echo.
echo   Or run deploy-to-host.bat to build images and deploy.
echo ===============================================================
echo.

endlocal
exit /b 0

REM =====================================================================
REM  :maybe_export_reqs  <service_dir>  <uv_package_name>  <dist_dir>
REM
REM  Re-exports requirements.txt only when uv.lock has changed since the
REM  last export (or when -deps was passed).  Saves the lock hash into
REM  dist\.lock-hash so subsequent builds skip the export and preserve
REM  the Docker layer cache.
REM =====================================================================
:maybe_export_reqs
set "_SVC_DIR=%~1"
set "_PKG_NAME=%~2"
set "_DIST_DIR=%~3"
set "_MARKER=%_DIST_DIR%\.lock-hash"

set "_NEED_EXPORT=0"
if "%FORCE_DEPS%"=="1" set "_NEED_EXPORT=1"
if not exist "%_DIST_DIR%\requirements.txt" set "_NEED_EXPORT=1"

if "!_NEED_EXPORT!"=="0" (
    set "_OLD_HASH="
    if exist "%_MARKER%" set /p _OLD_HASH=<"%_MARKER%"
    if "!_OLD_HASH!" neq "!CURRENT_LOCK_HASH!" set "_NEED_EXPORT=1"
)

if "!_NEED_EXPORT!"=="1" (
    echo === Exporting %_SVC_DIR% requirements.txt  (deps changed^) ===
    uv export --no-hashes --no-dev --no-emit-project --no-emit-workspace --package %_PKG_NAME% -o "%_DIST_DIR%\requirements.txt"
    if !errorlevel! neq 0 (
        echo FAILED: %_SVC_DIR% requirements export
        exit /b 1
    )
    echo !CURRENT_LOCK_HASH!> "%_MARKER%"
) else (
    echo === Skipping %_SVC_DIR% requirements.txt  (uv.lock unchanged — Docker cache preserved^) ===
)
exit /b 0
