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
*   **Profile:** **"Stable Web Optimized"** (NVENC)
    *   **Quality:** **CQ 28** (Significantly smaller files, Web-ready quality).
    *   **Preset:** **P6** (High Efficiency).
    *   **Multipass:** **1** (Quarter-Res Two-Pass).
    *   **Lookahead:** **32 Frames**.
*   **Recommendation:** UNCHECK "Auto" resolution to preserve 1080p/4K quality.
*   **Active Encoders:** This logic applies to NVENC (optimized), x264, x265, and QSV.

### 3. Clean Filenames
*   Output files are named: `OriginalName_compressed.mp4`

### 4. Batch Processing
*   The web interface supports **Concurrent Processing** (configured to 10 parallel jobs).
*   **To queue multiple videos:** Open the page in **multiple browser tabs** and upload one video per tab. They will process in parallel.

## 🔒 Security Architecture (Privacy & Encryption)

This project uses a hybrid privacy model:

1.  **Processing Engine (RAM-Only):**
    *   The Docker container runs on a RAM Disk (`tmpfs`).
    *   Video data *during compression* never touches the hard drive.
    *   If you use the Web UI directly, the entire pipeline is RAM-only.

2.  **Hot Folder (Encrypted Disk):**
    *   If you use the Batch/Network workflow, files reside in `hotfolder/`.
    *   **Storage:** This folder is an **Encrypted Vault** (`gocryptfs`).
    *   **At Rest:** When unmounted (locked), files are essentially random noise on the disk.
    *   **In Use:** When mounted (unlocked), files are visible to you and the compressor script.
    *   **Cleanup:** The script securely shreds the *input* file after uploading it to the RAM engine.

---

### 5. Network Hot Folder (The "Magic" Batch Mode)

#### Setup (One Time)
1.  **Install:** `sudo apt install gocryptfs`
2.  **Initialize:** `gocryptfs -init .hotfolder_cipher` (Set a strong password).

#### Unlock & Mount (To Start)
Run this to decrypt the folder and enable the network share:
```bash
./mount_hotfolder.sh
```

#### Connect (From Laptop)
*   **Address:** `\\<SERVER_IP>\VideoCompressor`
*   **User:** `chris`
*   **Password:** `video123`
*   **Usage:** Drop files in `input`, get results in `output`.

#### Lock & Unmount (To Finish)
Run this to close the vault and secure the data:
```bash
./unmount_hotfolder.sh
```
*(Note: You must stop accessing the folder over the network before locking)*

#### Start the Watcher
To automatically process files dropped in the folder:
```bash
nohup python3 auto_compressor.py > auto_compressor.log 2>&1 &
```
(View logs: `tail -f auto_compressor.log`)

## Access & Usage

- **URL:** [http://localhost:8001](http://localhost:8001) (or `http://<your-ip>:8001` on your LAN)
- **Status:** Running (Docker)

## GPU support

This instance is configured to use **NVIDIA GPUs** automatically.
To verify GPU access inside the container:
```bash
sudo docker exec -it 8mblocal nvidia-smi
```

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