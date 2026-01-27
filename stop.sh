#!/bin/bash
# Get the absolute path of the directory containing this script
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
MOUNT_POINT="$BASE_DIR/hotfolder"
PID_FILE=".auto_compressor.pid"

echo "🔒 Locking (Unmounting) Hot Folder..."

# 1. Stop Auto-Compressor
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "🤖 Stopping auto-compressor script (PID $PID)..."
    kill "$PID" 2>/dev/null
    sleep 2
    rm -f "$PID_FILE"
else
    # Fallback if PID file missing
    pkill -f auto_compressor.py
fi

# 2. Stop Docker Services
echo "🐳 Stopping Docker containers..."
docker-compose down

# 3. Check if mounted
if ! mountpoint -q "$MOUNT_POINT"; then
    echo "⚠️  Folder is not mounted."
    exit 0
fi

# 4. Wipe all data before locking (including hidden files)
echo "🧹 Wiping all data from hotfolder..."
# Use find to delete everything INSIDE the mount point to be safe
find "$MOUNT_POINT" -mindepth 1 -delete

# 5. Unmount
# Try standard unmount first
fusermount -u "$MOUNT_POINT"

if [ $? -ne 0 ]; then
    echo "⚠️  Standard unmount failed (busy). Trying lazy unmount..."
    # Lazy unmount detaches the filesystem now, even if it's busy
    fusermount -uz "$MOUNT_POINT"
fi

if [ $? -eq 0 ]; then
    # Final cleanup of the mount point directory itself
    rm -rf "$MOUNT_POINT"
    mkdir -p "$MOUNT_POINT"
    echo "✅ Successfully locked and all data wiped!"
else
    echo "❌ Failed to unmount even with lazy mode."
    echo "Check 'lsof +D $MOUNT_POINT' to see what is still using it."
fi