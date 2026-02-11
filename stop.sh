#!/bin/bash
set -euo pipefail

# Get the absolute path of the directory containing this script
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$BASE_DIR"

MOUNT_POINT="$BASE_DIR/hotfolder"
PID_FILE="$BASE_DIR/.auto_compressor.pid"

echo "🔒 Locking (Unmounting) Hot Folder..."

# 1. Stop Auto-Compressor
if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "${PID:-}" ]; then
        echo "🤖 Stopping auto-compressor script (PID $PID)..."
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null || true
            # Wait a bit for graceful shutdown, then hard kill.
            for _ in {1..10}; do
                if ! kill -0 "$PID" 2>/dev/null; then
                    break
                fi
                sleep 0.5
            done
            if kill -0 "$PID" 2>/dev/null; then
                echo "⚠️  Auto-compressor did not exit, sending SIGKILL..."
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi
    fi
    rm -f "$PID_FILE"
else
    # Fallback if PID file missing
    pkill -f "auto_compressor.py" 2>/dev/null || true
fi

# 2. Stop Docker Services
echo "🐳 Stopping Docker containers..."
docker compose down || true

# 3. Check if mounted
if ! mountpoint -q "$MOUNT_POINT"; then
    echo "⚠️  Folder is not mounted."
    exit 0
fi

# 4. Wipe all data before locking (including hidden files)
echo "🧹 Wiping all data from hotfolder..."
# Use find to delete everything INSIDE the mount point to be safe
if ! find "$MOUNT_POINT" -mindepth 1 -delete; then
    echo "⚠️  Warning: wipe step failed or was incomplete (folder may have been busy)."
fi

# 5. Unmount
# Try standard unmount first
FUSERMOUNT="$(command -v fusermount || command -v fusermount3 || true)"
if [ -n "${FUSERMOUNT:-}" ]; then
    "$FUSERMOUNT" -u "$MOUNT_POINT" || true
else
    umount "$MOUNT_POINT" 2>/dev/null || true
fi

if mountpoint -q "$MOUNT_POINT"; then
    echo "⚠️  Standard unmount failed (busy). Trying lazy unmount..."
    # Lazy unmount detaches the filesystem now, even if it's busy.
    if [ -n "${FUSERMOUNT:-}" ]; then
        "$FUSERMOUNT" -uz "$MOUNT_POINT" || true
    else
        umount -l "$MOUNT_POINT" 2>/dev/null || true
    fi
fi

if ! mountpoint -q "$MOUNT_POINT"; then
    # Final cleanup of the mount point directory itself
    rm -rf "$MOUNT_POINT"
    mkdir -p "$MOUNT_POINT"
    echo "✅ Successfully locked and all data wiped!"
else
    echo "❌ Failed to unmount even with lazy mode."
    echo "Check 'lsof +D $MOUNT_POINT' to see what is still using it."
fi
