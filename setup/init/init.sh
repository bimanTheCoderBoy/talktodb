#!/bin/bash
# Create local talktodb_data layout (LanceDB, document RAG, computer agent files).

DEST_DIR="${TALKTODB_DATA_DIR:-${TEOCO_DATA_STORE:-$HOME/talktodb_data}}"

echo "Creating talkToDB data store at: $DEST_DIR"

mkdir -p "$DEST_DIR/document_rag/data"
mkdir -p "$DEST_DIR/document_rag/raw_embedding_models"
mkdir -p "$DEST_DIR/document_rag/catalog_store"
mkdir -p "$DEST_DIR/catalog_lance"
mkdir -p "$DEST_DIR/computer/skills"
mkdir -p "$DEST_DIR/computer/users"

echo "Done. Set TALKTODB_DATA_DIR in .env and STORAGE_BASE_PATH=/app/talktodb_data in RAG prod env."
