#!/bin/bash

# Directory where this script exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SOURCE_DIR="$SCRIPT_DIR/init_config_setup"
DEST_DIR="$HOME/teoco_data_store"

echo "======================================"
echo "Starting Configuration Copy"
echo "Source      : $SOURCE_DIR"
echo "Destination : $DEST_DIR"
echo "======================================"

# Check source exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "[ERROR] Source directory does not exist:"
    echo "        $SOURCE_DIR"
    exit 1
fi

# Create destination if needed
if [ ! -d "$DEST_DIR" ]; then
    echo "[INFO] Creating destination directory..."
    mkdir -p "$DEST_DIR"

    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create destination directory."
        exit 1
    fi
fi

echo
echo "[INFO] Copying files and folders..."
echo "[INFO] Existing files will be overwritten."
echo

cp -rvf "$SOURCE_DIR/"* "$DEST_DIR/"

if [ $? -eq 0 ]; then
    echo
    echo "[SUCCESS] Copy completed successfully."
    echo "[INFO] Files copied to:"
    echo "       $DEST_DIR"
else
    echo
    echo "[ERROR] Copy operation failed."
    exit 1
fi

echo
echo "======================================"
echo "Final Contents:"
echo "======================================"
find "$DEST_DIR"

echo
echo "Done."
exit 0