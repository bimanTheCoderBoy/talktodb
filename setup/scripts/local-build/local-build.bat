@echo off
REM  Build wheels + requirements: local-build.bat [-langgraph] [-rag] [-all] [-deps]

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\.."
set "REPO=%CD%"
popd
cd /d "%REPO%"

set "BUILD_LANGGRAPH=0"
set "BUILD_RAG=0"
set "FORCE_DEPS=0"

if "%~1"=="" (
    echo Usage: local-build.bat [-langgraph] [-rag] [-all] [-deps]
    exit /b 1
)

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="-langgraph" set "BUILD_LANGGRAPH=1"
if /i "%~1"=="-rag" set "BUILD_RAG=1"
if /i "%~1"=="-deps" set "FORCE_DEPS=1"
if /i "%~1"=="-all" (
    set "BUILD_LANGGRAPH=1"
    set "BUILD_RAG=1"
)
shift
goto :parse_args
:done_args

if "%BUILD_LANGGRAPH%"=="0" if "%BUILD_RAG%"=="0" (
    echo ERROR: No valid build target specified.
    exit /b 1
)

set "LOCK_FILE=%REPO%\uv.lock"
set "CURRENT_LOCK_HASH="
for /f "skip=1 delims=" %%H in ('certutil -hashfile "%LOCK_FILE%" SHA256 2^>nul') do (
    if not defined CURRENT_LOCK_HASH set "CURRENT_LOCK_HASH=%%H"
)
if not defined CURRENT_LOCK_HASH set "FORCE_DEPS=1"

if "%BUILD_LANGGRAPH%"=="1" (
    if not exist "agent_server\dist" mkdir "agent_server\dist"
    del /q "agent_server\dist\*.whl" 2>nul
    uv build shared_server_libs --wheel --out-dir agent_server\dist
    uv build agent_server --wheel --out-dir agent_server\dist
    call :maybe_export_reqs agent_server agent-server "agent_server\dist"
)

if "%BUILD_RAG%"=="1" (
    if not exist "rag_retrieval_server\dist" mkdir "rag_retrieval_server\dist"
    del /q "rag_retrieval_server\dist\*.whl" 2>nul
    uv build shared_server_libs --wheel --out-dir rag_retrieval_server\dist
    uv build rag_retrieval_server --wheel --out-dir rag_retrieval_server\dist
    call :maybe_export_reqs rag_retrieval_server rag-retrieval-server "rag_retrieval_server\dist"
)

echo Build complete.
endlocal
exit /b 0

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
    uv export --no-hashes --no-dev --no-emit-project --no-emit-workspace --package %_PKG_NAME% -o "%_DIST_DIR%\requirements.txt"
    echo !CURRENT_LOCK_HASH!> "%_MARKER%"
)
exit /b 0
