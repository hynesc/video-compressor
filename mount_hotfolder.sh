#!/bin/bash
# Mounts the encrypted hotfolder

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

CIPHER_DIR="$SCRIPT_DIR/.hotfolder_cipher"
MOUNT_POINT="$SCRIPT_DIR/hotfolder"

# Check if vault is initialized
if [ ! -f "$CIPHER_DIR/gocryptfs.conf" ]; then
    echo "Error: Vault not initialized."
    echo "Run this command first to set your password:"
    echo "  gocryptfs -init \"$CIPHER_DIR\""
    exit 1
fi

echo "Mounting Encrypted Hotfolder..."
gocryptfs "$CIPHER_DIR" "$MOUNT_POINT"

echo "Done. Access your files in '$MOUNT_POINT'."
