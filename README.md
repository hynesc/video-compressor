# 8mb.local Video Compressor (Custom Quality Edition)

This is a customized self-hosted instance of [8mb.local](https://github.com/JMS1717/8mb.local). It has been modified for **maximum privacy**, **RAM-only operation**, and **Quality-Based compression**.

## ⚠️ Important Changes

### 1. Privacy First (RAM Disk)
*   **No Hard Drive Storage:** `uploads/` and `outputs/` are stored in **RAM (tmpfs)**.
*   **Auto-Wipe:** All videos are instantly deleted if the container stops or the computer restarts.
*   **Host Folders:** The local `uploads/` and `outputs/` folders in this directory are unused and empty.
*   **Workflow:** You MUST download your files via the Web UI immediately after processing.

### 2. Quality Mode (Ignore Target Size)
*   **Target Size is Ignored:** The "Target Size (MB)" box in the UI has no effect on file size.
*   **Constant Quality:** All encodes use **CRF 23** (Medium/High Quality) or equivalent.
    *   Files will be as large as they need to be to maintain quality.
    *   **Recommendation:** UNCHECK "Auto" resolution to preserve 1080p/4K quality.
*   **Active Encoders:** This logic applies to NVENC, x264, x265, and QSV.

### 3. Clean Filenames
*   Output files are named: `OriginalName_compressed.mp4`

## Access & usage

- **URL:** http://localhost:8001
- **Status:** Running (Docker)

## Management Commands

### Start
```bash
sudo docker compose up -d
```

### Stop (Wipes all data)
```bash
sudo docker compose down
```

### Restart (Applies patches)
```bash
sudo docker compose restart
```

### View Logs
```bash
sudo docker compose logs -f
```

## Configuration

The configuration is managed via patched files mounted into the Docker container:
- `docker-compose.yml`: Defines the RAM disk and volume mounts.
- `patches/worker/worker.py`: Contains the Quality Mode logic (CRF 23).
- `patches/backend/main.py`: Contains the `_compressed` naming logic.
- `patches/frontend-build/index.html`: Contains the red warning banner.