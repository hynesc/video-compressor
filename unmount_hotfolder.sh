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

# Unmount
fusermount -u "$MOUNT_POINT"

if [ $? -eq 0 ]; then
    echo "✅ Successfully locked! Data is now encrypted in .hotfolder_cipher"
else
    echo "❌ Failed to unmount. Is a file open?"
    echo "Try closing Explorer windows or stopping the auto_compressor.py script."
fi
