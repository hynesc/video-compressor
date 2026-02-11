#!/bin/bash
set -euo pipefail

# Get the absolute path of the directory containing this script
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$BASE_DIR"

CIPHER_DIR="$BASE_DIR/.hotfolder_cipher"
MOUNT_POINT="$BASE_DIR/hotfolder"
PID_FILE="$BASE_DIR/.auto_compressor.pid"

echo "🔓 Unlocking Hot Folder..."

# Basic dependency check (avoids a confusing no-op if gocryptfs isn't installed)
if ! command -v gocryptfs >/dev/null 2>&1; then
    echo "❌ gocryptfs is not installed. Install it with: sudo apt install gocryptfs"
    exit 1
fi

# Create mount point if missing
mkdir -p "$MOUNT_POINT"

# 1. Check if already mounted
if mountpoint -q "$MOUNT_POINT"; then
    echo "⚡ Already mounted."
else
    # 2. Clean junk files that prevent mounting (e.g. macOS/Windows metadata)
    # Only delete known junk to avoid data loss if user accidentally put real files here.
    find "$MOUNT_POINT" -maxdepth 1 -name ".DS_Store" -delete || true
    find "$MOUNT_POINT" -maxdepth 1 -name "._.DS_Store" -delete || true
    find "$MOUNT_POINT" -maxdepth 1 -name "Thumbs.db" -delete || true

    # Mount with allow_other for Samba access
    # Note: You might need to edit /etc/fuse.conf and uncomment 'user_allow_other'
    if ! gocryptfs -allow_other "$CIPHER_DIR" "$MOUNT_POINT"; then
        echo "❌ Failed to mount."
        exit 1
    fi
fi

# Create structure immediately (safe if already present)
mkdir -p "$MOUNT_POINT/input"
mkdir -p "$MOUNT_POINT/output"
echo "✅ Hot folder ready."

# 3. Start Docker Services
echo "🚀 Starting Docker containers..."
docker compose up -d

# 4. Start Auto-Compressor script in background (if not already running)
echo "🤖 Starting auto-compressor script..."
if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
        echo "⚡ Auto-compressor already running (PID $PID)."
        exit 0
    fi
fi

rm -f "$PID_FILE"
nohup python3 -u auto_compressor.py >> auto_compressor.log 2>&1 &
echo $! > "$PID_FILE"

echo "✨ All systems active! Network share is live."
