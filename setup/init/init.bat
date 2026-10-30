@echo off
if not defined TALKTODB_DATA_DIR if not defined TECO_DATA_STORE set "TALKTODB_DATA_DIR=%USERPROFILE%\talktodb_data"
if not defined TALKTODB_DATA_DIR set "TALKTODB_DATA_DIR=%TECO_DATA_STORE%"
bash "%~dp0init.sh"
