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

This project is engineered for **Zero-Retention Privacy**:

1.  **RAM-Only Processing:**
    *   The core video compressor runs in Docker using a RAM Disk (`tmpfs`).
    *   Temporary video data *never* touches the hard drive.
    *   If power is lost, all active job data vanishes instantly.

2.  **Encrypted Hot Folder (At Rest):**
    *   The "Hot Folder" storage is encrypted using `gocryptfs`.
    *   **Encrypted:** `projects/video-compressor/.hotfolder_cipher` (On Disk).
    *   **Decrypted:** `projects/video-compressor/hotfolder` (Virtual Mount).
    *   **Access Control:** The folder is locked to your user (`chmod 700`), preventing other local users from peeking.

3.  **Secure Deletion (Shredding):**
    *   After a file is uploaded to the RAM disk, the original input file is **securely shredded**.
    *   The script uses `shred -u` to overwrite the file with random noise before deletion.
    *   Since the underlying storage is encrypted, this overwrites the *encrypted* blocks with *encrypted* noise, making recovery impossible.

---

### 5. Network Hot Folder (The "Magic" Batch Mode)
For seamless batch processing from another computer (e.g., your laptop):

1.  **Setup (One Time):**
    *   **Install:** `sudo apt install gocryptfs`
    *   **Initialize:** `gocryptfs -init .hotfolder_cipher` (Set a strong password).

2.  **Mount (Every Reboot):**
    *   Run: `./mount_hotfolder.sh`
    *   This mounts the folder and enables SMB sharing (`allow_other`) while keeping it private (`chmod 700`).

3.  **Connect to Share:**
    *   Connect to `\\<SERVER_IP>\VideoCompressor` (SMB).
    *   **User:** `chris` (You must connect as the user who mounted the folder).
    *   **Password:** `video123` (Default).

4.  **Usage:**
    *   Drop files into the `hotfolder/input` folder.
    *   Finished files appear in `hotfolder/output`.

5.  **Start the Watcher:**
    Run this on the server to start the background monitoring script:
    ```bash
    nohup python3 auto_compressor.py > auto_compressor.log 2>&1 &
    ```
    (View logs with `tail -f auto_compressor.log`)

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