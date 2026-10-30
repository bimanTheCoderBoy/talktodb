@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\.."
set "REPO=%CD%"
popd
set "DIST=%REPO%\dist"

set "PREFLIGHT_OK=1"
for %%D in (agent_server rag_retrieval_server) do (
    if not exist "%REPO%\%%D\dist\requirements.txt" (
        echo MISSING: %%D\dist\requirements.txt
        set "PREFLIGHT_OK=0"
    )
)
if "%PREFLIGHT_OK%"=="0" (
    echo Run: setup\scripts\local-build\local-build.bat -all
    exit /b 1
)

docker compose -f "%REPO%\docker-compose.yml" --env-file "%REPO%\.env" build
if errorlevel 1 exit /b 1

for %%I in ("postgis/postgis:16-3.4" "redis:7-alpine" "arizephoenix/phoenix:20.3.0" "quay.io/keycloak/keycloak:25.0.2") do (
    docker image inspect %%~I >nul 2>nul || docker pull %%~I
)

if exist "%DIST%" rmdir /s /q "%DIST%"
mkdir "%DIST%"

docker save -o "%DIST%\all-images.tar" ^
    aana_core_services-frontend ^
    aana_core_services-agent_server ^
    aana_core_services-rag_retrieval_server ^
    postgis/postgis:16-3.4 ^
    redis:7-alpine ^
    arizephoenix/phoenix:20.3.0 ^
    quay.io/keycloak/keycloak:25.0.2

copy "%REPO%\docker-compose.yml" "%DIST%\docker-compose.yml" >nul
copy "%REPO%\.env" "%DIST%\.env" >nul

mkdir "%DIST%\auth_server\realms" 2>nul
copy "%REPO%\auth_server\docker-compose.yml" "%DIST%\auth_server\docker-compose.yml" >nul
if exist "%REPO%\auth_server\.env" copy "%REPO%\auth_server\.env" "%DIST%\auth_server\.env" >nul

mkdir "%DIST%\setup\certs" 2>nul
if exist "%REPO%\setup\certs\tls.crt" copy "%REPO%\setup\certs\tls.crt" "%DIST%\setup\certs\tls.crt" >nul
if exist "%REPO%\setup\certs\tls.key" copy "%REPO%\setup\certs\tls.key" "%DIST%\setup\certs\tls.key" >nul
copy "%REPO%\setup\certs\generate-certs.ps1" "%DIST%\setup\certs\generate-certs.ps1" >nul 2>nul

mkdir "%DIST%\setup\prod_envs\agent_server" 2>nul
mkdir "%DIST%\setup\prod_envs\rag_retrieval_server" 2>nul
if exist "%REPO%\setup\prod_envs\agent_server\.env" copy "%REPO%\setup\prod_envs\agent_server\.env" "%DIST%\setup\prod_envs\agent_server\.env" >nul
if exist "%REPO%\setup\prod_envs\rag_retrieval_server\.env" copy "%REPO%\setup\prod_envs\rag_retrieval_server\.env" "%DIST%\setup\prod_envs\rag_retrieval_server\.env" >nul

mkdir "%DIST%\setup\scripts\postgres_init_scripts" 2>nul
xcopy "%REPO%\setup\scripts\postgres_init_scripts" "%DIST%\setup\scripts\postgres_init_scripts\" /E /I /Y >nul 2>nul

mkdir "%DIST%\setup\init" 2>nul
copy "%REPO%\setup\init\init.sh" "%DIST%\setup\init\init.sh" >nul
copy "%REPO%\setup\scripts\deploy\start.bat" "%DIST%\start.bat" >nul

echo dist\ ready.
endlocal
