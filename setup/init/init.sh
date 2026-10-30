#!/bin/bash
# Create local teoco_data_store layout for LanceDB, document RAG, and computer agent files.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${TEOCO_DATA_STORE:-$HOME/teoco_data_store}"

echo "Creating data store at: $DEST_DIR"

mkdir -p "$DEST_DIR/document_rag/data"
mkdir -p "$DEST_DIR/document_rag/raw_embedding_models"
mkdir -p "$DEST_DIR/catalog_lance"
mkdir -p "$DEST_DIR/computer/skills"
mkdir -p "$DEST_DIR/computer/users"

echo "Done. Point TECO_DATA_DIR / file-system tool base_dir at this path in agent_server and rag_retrieval_server .env files."
