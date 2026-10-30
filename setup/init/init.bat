@echo off
setlocal
if not defined TECO_DATA_STORE set "TECO_DATA_STORE=%USERPROFILE%\teoco_data_store"
set "DEST=%TECO_DATA_STORE%"

echo Creating data store at: %DEST%
mkdir "%DEST%\document_rag\data" 2>nul
mkdir "%DEST%\document_rag\raw_embedding_models" 2>nul
mkdir "%DEST%\catalog_lance" 2>nul
mkdir "%DEST%\computer\skills" 2>nul
mkdir "%DEST%\computer\users" 2>nul
echo Done. Configure TECO_DATA_DIR in .env and agent/RAG .env files.
endlocal
