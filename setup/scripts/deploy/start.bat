@echo off
setlocal EnableDelayedExpansion
REM talkToDB — load dist images and start stack (Windows dist folder).
REM Usage: start.bat <hostname>

if "%~1"=="" (
  echo Usage: start.bat ^<hostname^>
  exit /b 1
)
set "NEW_HOST=%~1"
set "DIST=%~dp0"
set "DIST=%DIST:~0,-1%"

echo ===============================================================
echo   talkToDB start
echo   Hostname: %NEW_HOST%
echo   Dist:     %DIST%
echo ===============================================================

echo [1/8] Stopping containers...
docker compose -f "%DIST%\auth_server\docker-compose.yml" --env-file "%DIST%\auth_server\.env" down >nul 2>&1
docker compose -f "%DIST%\docker-compose.yml" --env-file "%DIST%\.env" down >nul 2>&1

echo [2/8] TLS certificate...
powershell -NoProfile -ExecutionPolicy Bypass -File "%DIST%\setup\certs\generate-certs.ps1" -Hostname "%NEW_HOST%" -Days 365
if errorlevel 1 exit /b 1

echo [3/8] Updating .env files...
powershell -NoProfile -Command ^
  "$f='%DIST%\.env';" ^
  "$h='%NEW_HOST%';" ^
  "$c=Get-Content $f -Raw;" ^
  "$c=$c -replace '(?m)^VITE_KEYCLOAK_URL=.*','VITE_KEYCLOAK_URL=https://'+$h+':8443';" ^
  "$c=$c -replace '(?m)^TALKTODB_DATA_DIR=.*','TALKTODB_DATA_DIR=$${USERPROFILE}/talktodb_data';" ^
  "Set-Content $f $c"

if exist "%DIST%\setup\prod_envs\agent_server\.env" (
  powershell -NoProfile -Command ^
    "$f='%DIST%\setup\prod_envs\agent_server\.env'; $h='%NEW_HOST%';" ^
    "$c=Get-Content $f -Raw;" ^
    "$c=$c -replace '(?m)^KEYCLOAK_ISSUER=.*','KEYCLOAK_ISSUER=https://'+$h+':8443';" ^
    "Set-Content $f $c"
)
if exist "%DIST%\auth_server\.env" (
  powershell -NoProfile -Command ^
    "$f='%DIST%\auth_server\.env'; $h='%NEW_HOST%';" ^
    "$c=Get-Content $f -Raw;" ^
    "$c=$c -replace '(?m)^KC_HOSTNAME=.*','KC_HOSTNAME='+$h;" ^
    "Set-Content $f $c"
)

echo [4/8] Loading images...
docker load -i "%DIST%\all-images.tar"
if errorlevel 1 exit /b 1

echo [5/8] Data store...
if not exist "%USERPROFILE%\talktodb_data" mkdir "%USERPROFILE%\talktodb_data"
if exist "%DIST%\setup\init\init.sh" bash "%DIST%\setup\init\init.sh"

echo [6/8] Keycloak...
docker compose -f "%DIST%\auth_server\docker-compose.yml" --env-file "%DIST%\auth_server\.env" up -d
if errorlevel 1 exit /b 1

echo [7/8] Core stack...
docker compose -f "%DIST%\docker-compose.yml" --env-file "%DIST%\.env" up -d
if errorlevel 1 exit /b 1

echo [8/8] Done.
echo   Keycloak : https://%NEW_HOST%:8443
echo   Frontend : https://%NEW_HOST%
exit /b 0
