#!/bin/bash
MOUNT_POINT="/home/chris/projects/video-compressor/hotfolder"

echo "🔒 Locking (Unmounting) Hot Folder..."

# Check if mounted
if ! mountpoint -q "$MOUNT_POINT"; then
    echo "⚠️  Folder is not mounted."
    exit 0
fi

# Stop Samba to release locks (optional but safer)
# sudo systemctl stop smbd

# Wipe all data before locking (this also deletes the encrypted source files)
echo "🧹 Wiping all data from hotfolder..."
rm -rf "$MOUNT_POINT"/*

# Unmount
fusermount -u "$MOUNT_POINT"

if [ $? -eq 0 ]; then
    # Clean up any leftover files in the mount point directory itself (unencrypted residue)
    # This ensures the folder is empty for the next mount and no data is left behind.
    find "$MOUNT_POINT" -mindepth 1 -delete
    echo "✅ Successfully locked and all data wiped!"
else
    echo "❌ Failed to unmount. Is a file open?"
    echo "Try closing Explorer windows or stopping the auto_compressor.py script."
fi
