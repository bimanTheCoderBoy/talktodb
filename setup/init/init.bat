@echo off
setlocal enabledelayedexpansion


:: Directory where the batch file exists
set "SCRIPT_DIR=%~dp0"

:: Remove trailing slash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "SOURCE_DIR=%SCRIPT_DIR%\init_config_setup"
set "DEST_DIR=%USERPROFILE%\teoco_data_store"


echo ======================================
echo Starting Configuration Copy
echo Source      : %SOURCE_DIR%
echo Destination : %DEST_DIR%
echo ======================================

:: Check source exists
if not exist "%SOURCE_DIR%" (
    echo [ERROR] Source directory does not exist:
    echo         %SOURCE_DIR%
    exit /b 1
)

:: Create destination if needed
if not exist "%DEST_DIR%" (
    echo [INFO] Destination does not exist. Creating...
    mkdir "%DEST_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create destination directory.
        exit /b 1
    )
)

echo.
echo [INFO] Copying files and folders...
echo [INFO] Existing files will be overwritten.
echo.

robocopy "%SOURCE_DIR%" "%DEST_DIR%" /E /R:1 /W:1 /NFL /NDL /NP

set RC=%ERRORLEVEL%

:: Robocopy exit codes 0-7 are considered success
if %RC% LEQ 7 (
    echo.
    echo [SUCCESS] Copy completed successfully.
    echo [INFO] Files copied to:
    echo        %DEST_DIR%
) else (
    echo.
    echo [ERROR] Copy failed. Robocopy exit code: %RC%
    exit /b %RC%
)

echo.
echo ======================================
echo Final Contents:
echo ======================================
dir "%DEST_DIR%" /s

echo.
echo Done.
exit /b 0