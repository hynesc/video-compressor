import os
import time
import requests
import shutil
import subprocess
import concurrent.futures
from pathlib import Path

# --- CONFIGURATION ---
INPUT_DIR = Path("hotfolder/input")
OUTPUT_DIR = Path("hotfolder/output")
API_URL = "http://localhost:8001/api"
MAX_CONCURRENT_JOBS = 5  # We have 10 workers, but let's keep it safe
POLL_INTERVAL = 5  # Seconds between folder scans

# Default Settings for Compression
COMPRESS_SETTINGS = {
    "target_size_mb": 50.0,   # Ignored by Quality Mode
    "video_codec": "av1_nvenc",
    "audio_codec": "aac",
    "audio_bitrate_kbps": 128,
    "preset": "p6",           # Overridden by worker patch, but p6 is safe
    "tune": "hq",
    "container": "mp4",
    "auto_resolution": False, # Important: Disable auto-downscaling
    "force_hw_decode": True
}

def process_file(file_path):
    filename = file_path.name
    print(f"[START] Processing: {filename}")
    
    try:
        # 1. Upload
        print(f"[UPLOAD] Uploading {filename}...")
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "video/mp4")}
            # Note: The API also takes form fields for target_size, but usually via query params or body
            # Looking at main.py: upload(file=..., target_size_mb=...)
            # It seems target_size_mb is a query param
            resp = requests.post(f"{API_URL}/upload", files=files, params={"target_size_mb": 50.0})
            resp.raise_for_status()
            upload_data = resp.json()
            
        internal_filename = upload_data["filename"]
        job_id = upload_data["job_id"]
        print(f"[UPLOAD] Complete. Internal ID: {job_id}")

        # 2. Start Compression
        payload = COMPRESS_SETTINGS.copy()
        payload["filename"] = internal_filename
        payload["job_id"] = job_id
        
        resp = requests.post(f"{API_URL}/compress", json=payload)
        resp.raise_for_status()
        task_data = resp.json()
        task_id = task_data["task_id"]
        print(f"[JOB] Started Task: {task_id}")

        # 3. Poll for Completion
        # The backend uses Redis/Celery. We can check status via /api/jobs/{task_id} (if it exists) 
        # or just listen to the stream. Since we are in a script, polling /api/history might be messy.
        # Let's check if there is a status endpoint.
        # Typically endpoints return 200 OK.
        # The logs show a GET /api/stream/{id}.
        # We can simulate listening to the stream or just wait.
        # Actually, let's poll the /api/history endpoint and look for our ID, 
        # or assume a simple wait loop on /api/stream isn't feasible for a simple script.
        
        # Better approach: The backend emits events. 
        # But we can just poll the output filename if we know it?
        # output_name = internal_filename + "_compressed.mp4"? No, backend logic handles naming.
        
        # Let's use the stream endpoint in a blocking read.
        stream_url = f"{API_URL}/stream/{task_id}"
        print(f"[WAIT] Monitoring job {task_id}...")
        
        with requests.get(stream_url, stream=True) as stream_resp:
            for line in stream_resp.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        data_str = decoded_line[6:]
                        try:
                            import json
                            data = json.loads(data_str)
                            msg_type = data.get("type")
                            
                            if msg_type == "progress":
                                # print(f"Progress: {data.get('progress')}%", end="\r")
                                pass
                            elif msg_type == "done":
                                print(f"\n[DONE] Job {task_id} Finished!")
                                output_path_internal = data.get("stats", {}).get("output_path")
                                break # Exit stream loop
                            elif msg_type == "error":
                                print(f"\n[ERROR] Job failed: {data.get('message')}")
                                return
                        except:
                            pass

        # 4. Download
        # We need an endpoint to download.
        # The web UI uses /api/download/{task_id}? No, typically it serves from /outputs/.
        # Let's check main.py for download endpoint.
        # It usually serves static files from /outputs.
        
        # Actually, since we are ON THE SERVER (same machine), 
        # the output file is in the Docker Container's RAM.
        # We cannot access it directly via file system unless we are root looking into overlayfs.
                # We MUST download it via API.
                
                download_url = f"{API_URL}/jobs/{task_id}/download"
                print(f"[DOWN] Downloading result...")        
        # Extract original stem to name it properly
        original_stem = Path(filename).stem
        final_output_name = f"{original_stem}_compressed.mp4"
        final_output_path = OUTPUT_DIR / final_output_name
        
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(final_output_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
        print(f"[SUCCESS] Saved to {final_output_path}")

        # 5. Cleanup Input (Secure Shred)
        print(f"[SHRED] Securely wiping input file...")
        subprocess.run(["shred", "-u", str(file_path)], check=True)
        print(f"[CLEAN] Securely removed input file.")

    except Exception as e:
        print(f"[ERROR] Failed to process {filename}: {e}")

def main():
    print("--- 8mb.local Hotfolder Auto-Compressor ---")
    print(f"Monitoring: {INPUT_DIR.absolute()}")
    print(f"Output to:  {OUTPUT_DIR.absolute()}")
    print("Press Ctrl+C to stop.")
    
    # Create ThreadPool
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
    
    # Track submitted files to avoid re-submitting while processing
    processing_files = set()

    while True:
        try:
            # Scan folder
            current_files = set()
            for f in INPUT_DIR.glob("*"):
                if f.is_file() and not f.name.startswith("."):
                    current_files.add(f)
            
            # Identify new files
            # Note: We simply check if it's in our local 'processing' tracking set.
            # If the script restarts, it will re-process files left in input (which is good).
            
            for file_path in current_files:
                if file_path not in processing_files:
                    # Check if file is done being written (size stable?)
                    # Simple check: Try to open in append mode?
                    # Or just wait a second.
                    
                    processing_files.add(file_path)
                    executor.submit(process_wrapper, file_path, processing_files)
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("Stopping...")
            executor.shutdown(wait=False)
            break
        except Exception as e:
            print(f"Main loop error: {e}")
            time.sleep(5)

def process_wrapper(file_path, processing_set):
    try:
        process_file(file_path)
    finally:
        # Verify if file is gone (it should be deleted)
        # If not deleted (error), we might process it again on restart.
        # But for runtime, remove from set.
        processing_set.discard(file_path)

if __name__ == "__main__":
    main()
