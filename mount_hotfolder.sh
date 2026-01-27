#!/bin/bash
CIPHER_DIR="/home/chris/projects/video-compressor/.hotfolder_cipher"
MOUNT_POINT="/home/chris/projects/video-compressor/hotfolder"

echo "🔓 Unlocking Hot Folder..."

# Create mount point if missing
mkdir -p "$MOUNT_POINT"

# 1. Check if already mounted
if mountpoint -q "$MOUNT_POINT"; then
    echo "⚡ Already mounted."
    exit 0
fi

# 2. Clean junk files that prevent mounting (e.g. macOS/Windows metadata)
# Only delete known junk to avoid data loss if user accidentally put real files here.
find "$MOUNT_POINT" -maxdepth 1 -name ".DS_Store" -delete
find "$MOUNT_POINT" -maxdepth 1 -name "._.DS_Store" -delete
find "$MOUNT_POINT" -maxdepth 1 -name "Thumbs.db" -delete

# Mount with allow_other for Samba access
# Note: You might need to edit /etc/fuse.conf and uncomment 'user_allow_other'
gocryptfs -allow_other "$CIPHER_DIR" "$MOUNT_POINT"

if [ $? -eq 0 ]; then
    # Create structure immediately
    mkdir -p "$MOUNT_POINT/input"
    mkdir -p "$MOUNT_POINT/output"
    echo "✅ Successfully unlocked! Network share is live."
else
    echo "❌ Failed to mount."
fi