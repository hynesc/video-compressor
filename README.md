# 8mb.local Video Compressor

This is a self-hosted instance of [8mb.local](https://github.com/JMS1717/8mb.local), a GPU-accelerated video compressor.

## Status & Access

- **URL:** http://localhost:8001 (or `http://<your-ip>:8001` on your LAN)
- **Status:** Running (Docker)
- **Data:**
  - `uploads/`: Temporary storage for uploaded source videos.
  - `outputs/`: Storage for compressed videos.
  - `.env`: Configuration file (environment variables).

## Management Commands

Run these commands from the project directory.

### Start
Start the service in the background:
```bash
sudo docker compose up -d
```

### Stop
Stop the service:
```bash
sudo docker compose down
```

### Restart
Restart the service (useful after changing configuration):
```bash
sudo docker compose restart
```

### View Logs
Watch the logs in real-time (press `Ctrl+C` to exit):
```bash
sudo docker compose logs -f
```

## Configuration

### File Retention
By default, files are deleted **1 hour** after creation. 

To change this, add the following line to your `.env` file (e.g., for 24 hours):
```bash
FILE_RETENTION_HOURS=24
```
Then restart the container:
```bash
sudo docker compose restart
```

*Note: You can also change this dynamically in the Web UI Settings.*

### GPU Support
This instance is configured to use **NVIDIA GPUs** automatically.
To verify GPU access inside the container:
```bash
sudo docker exec -it 8mblocal nvidia-smi
```
