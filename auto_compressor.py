from __future__ import annotations

import concurrent.futures
import json
import logging
import mimetypes
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent.resolve()
DEFAULT_INPUT_DIR = BASE_DIR / "hotfolder" / "input"
DEFAULT_OUTPUT_DIR = BASE_DIR / "hotfolder" / "output"

LOG = logging.getLogger("auto_compressor")


@dataclass(frozen=True)
class Config:
    api_url: str
    input_dir: Path
    output_dir: Path
    max_concurrent_jobs: int
    poll_interval_s: float
    ready_min_age_s: float
    request_timeout_s: float
    stream_read_timeout_s: float
    download_read_timeout_s: float
    upload_target_size_mb: float
    download_wait_s: float
    secure_delete: bool


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


CFG = Config(
    api_url=os.getenv("VC_API_URL", "http://localhost:8001/api").rstrip("/"),
    input_dir=Path(os.getenv("VC_INPUT_DIR", str(DEFAULT_INPUT_DIR))),
    output_dir=Path(os.getenv("VC_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))),
    max_concurrent_jobs=int(os.getenv("VC_MAX_CONCURRENT_JOBS", "5")),
    poll_interval_s=float(os.getenv("VC_POLL_INTERVAL_S", "5")),
    ready_min_age_s=float(os.getenv("VC_READY_MIN_AGE_S", "4")),
    request_timeout_s=float(os.getenv("VC_REQUEST_TIMEOUT_S", "60")),
    stream_read_timeout_s=float(os.getenv("VC_STREAM_READ_TIMEOUT_S", "600")),
    download_read_timeout_s=float(os.getenv("VC_DOWNLOAD_READ_TIMEOUT_S", "300")),
    upload_target_size_mb=float(os.getenv("VC_UPLOAD_TARGET_SIZE_MB", "50")),
    download_wait_s=float(os.getenv("VC_DOWNLOAD_WAIT_S", "2")),
    secure_delete=_env_bool("VC_SECURE_DELETE", False),
)

# Default Settings for Compression
COMPRESS_SETTINGS = {
    "target_size_mb": CFG.upload_target_size_mb,  # Ignored by Quality Mode (but required by API)
    "video_codec": "av1_nvenc",
    "audio_codec": "aac",
    "audio_bitrate_kbps": 128,
    "preset": "p6",           # Overridden by worker patch, but p6 is safe
    "tune": "hq",
    "container": "mp4",
    "auto_resolution": False, # Important: Disable auto-downscaling
    "force_hw_decode": True
}


def _configure_logging() -> None:
    level = os.getenv("VC_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _guess_content_type(path: Path) -> str:
    content_type, _enc = mimetypes.guess_type(str(path))
    return content_type or "application/octet-stream"


def _unique_output_path(output_dir: Path, desired_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    base = Path(desired_name).stem
    ext = Path(desired_name).suffix or ".mp4"
    candidate = output_dir / f"{base}{ext}"
    if not candidate.exists():
        return candidate
    for i in range(2, 1000):
        candidate = output_dir / f"{base}_{i}{ext}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Refusing to overwrite existing outputs for {desired_name}")


def _best_effort_secure_delete(path: Path) -> None:
    if not path.exists():
        return
    # Best-effort only: on CoW filesystems and FUSE layers this may not provide strong guarantees.
    try:
        subprocess.run(["shred", "-u", str(path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not path.exists():
            return
    except Exception:
        pass
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _make_session() -> "requests.Session":
    import requests

    s = requests.Session()
    # Conservative retry for transient failures.
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
    except Exception:
        pass
    return s


def _sse_events(resp: "requests.Response") -> Any:
    # Minimal SSE parser: only consume "data: {json}" lines.
    for raw in resp.iter_lines():
        if not raw:
            continue
        try:
            line = raw.decode("utf-8", errors="replace")
        except Exception:
            continue
        if not line.startswith("data: "):
            continue
        data_str = line[6:].strip()
        if not data_str:
            continue
        try:
            yield json.loads(data_str)
        except Exception:
            continue


def process_file(file_path: Path, session: "requests.Session", stop_event: threading.Event) -> None:
    filename = file_path.name
    LOG.info("START processing %s", filename)

    tmp_path: Path | None = None
    try:
        # Guard: file may have been moved/deleted after scheduling.
        if not file_path.exists():
            LOG.info("SKIP missing file %s", filename)
            return

        # 1. Upload
        LOG.info("UPLOAD %s", filename)
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, _guess_content_type(file_path))}
            resp = session.post(
                f"{CFG.api_url}/upload",
                files=files,
                params={"target_size_mb": CFG.upload_target_size_mb},
                timeout=CFG.request_timeout_s,
            )
            resp.raise_for_status()
            upload_data = resp.json()

        internal_filename = upload_data["filename"]
        job_id = upload_data["job_id"]
        LOG.info("UPLOAD complete job_id=%s", job_id)

        # 2. Start Compression
        payload = COMPRESS_SETTINGS.copy()
        payload["filename"] = internal_filename
        payload["job_id"] = job_id

        resp = session.post(f"{CFG.api_url}/compress", json=payload, timeout=CFG.request_timeout_s)
        resp.raise_for_status()
        task_data = resp.json()
        task_id = task_data["task_id"]

        LOG.info("JOB started task_id=%s", task_id)

        # 3. Wait for completion via SSE stream
        stream_url = f"{CFG.api_url}/stream/{task_id}"
        LOG.info("WAIT stream %s", stream_url)

        done = False
        with session.get(
            stream_url,
            stream=True,
            timeout=(CFG.request_timeout_s, CFG.stream_read_timeout_s),
        ) as stream_resp:
            stream_resp.raise_for_status()
            for event in _sse_events(stream_resp):
                if stop_event.is_set():
                    LOG.info("STOP requested, leaving stream for task_id=%s", task_id)
                    return
                msg_type = event.get("type")
                if msg_type == "done":
                    LOG.info("DONE task_id=%s", task_id)
                    done = True
                    break
                if msg_type == "error":
                    LOG.error("JOB error task_id=%s message=%s", task_id, event.get("message"))
                    return

        if not done:
            LOG.error("Stream ended without done/error for task_id=%s", task_id)
            return

        # 4. Download
        download_url = f"{CFG.api_url}/jobs/{task_id}/download"
        LOG.info("DOWN %s", download_url)

        # Extract original stem to name it properly (clean filenames)
        original_stem = Path(filename).stem
        final_output_name = f"{original_stem}_compressed.mp4"
        final_output_path = _unique_output_path(CFG.output_dir, final_output_name)

        tmp_path = final_output_path.with_suffix(final_output_path.suffix + ".part")
        with session.get(
            download_url,
            params={"wait": CFG.download_wait_s},
            stream=True,
            timeout=(CFG.request_timeout_s, CFG.download_read_timeout_s),
        ) as r:
            r.raise_for_status()
            with open(tmp_path, "wb") as out:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if stop_event.is_set():
                        LOG.info("STOP requested, aborting download for task_id=%s", task_id)
                        return
                    if not chunk:
                        continue
                    out.write(chunk)
        tmp_path.replace(final_output_path)
        LOG.info("SUCCESS saved %s", final_output_path)

        # 5. Cleanup Input
        if CFG.secure_delete:
            LOG.info("CLEAN secure_delete %s", file_path)
            _best_effort_secure_delete(file_path)
        else:
            LOG.info("CLEAN unlink %s", file_path)
            try:
                file_path.unlink()
            except FileNotFoundError:
                pass

    except Exception as e:
        LOG.exception("ERROR processing %s: %s", filename, e)
        # Best-effort cleanup of partial download.
        try:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass

def _is_candidate(path: Path) -> bool:
    return path.is_file() and not path.name.startswith(".")


def main() -> None:
    _configure_logging()
    CFG.input_dir.mkdir(parents=True, exist_ok=True)
    CFG.output_dir.mkdir(parents=True, exist_ok=True)

    LOG.info("--- 8mb.local Hotfolder Auto-Compressor ---")
    LOG.info("Monitoring: %s", CFG.input_dir.resolve())
    LOG.info("Output to:   %s", CFG.output_dir.resolve())

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: Any) -> None:
        LOG.info("Signal %s received, shutting down scan loop", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    session = _make_session()

    processing: set[Path] = set()
    snapshots: dict[Path, tuple[int, float]] = {}  # path -> (size, mtime)
    next_try_at: dict[Path, float] = {}  # naive per-file backoff

    def _submit(executor: concurrent.futures.ThreadPoolExecutor, p: Path) -> None:
        processing.add(p)
        executor.submit(process_wrapper, p, processing, next_try_at, session, stop_event)

    with concurrent.futures.ThreadPoolExecutor(max_workers=CFG.max_concurrent_jobs) as executor:
        while not stop_event.is_set():
            try:
                current: list[Path] = [p for p in CFG.input_dir.glob("*") if _is_candidate(p)]
                current_set = set(current)

                # Drop snapshot/backoff for removed files.
                for known in list(snapshots.keys()):
                    if known not in current_set:
                        snapshots.pop(known, None)
                        next_try_at.pop(known, None)

                now = time.time()
                for p in current:
                    if p in processing:
                        continue
                    if next_try_at.get(p, 0) > now:
                        continue
                    try:
                        st = p.stat()
                    except FileNotFoundError:
                        continue
                    prev = snapshots.get(p)
                    snapshots[p] = (st.st_size, st.st_mtime)

                    # Require at least one stable scan with minimum age before scheduling.
                    if prev is None:
                        continue
                    if prev != (st.st_size, st.st_mtime):
                        continue
                    if (now - st.st_mtime) < CFG.ready_min_age_s:
                        continue

                    _submit(executor, p)

                time.sleep(CFG.poll_interval_s)
            except Exception as e:
                LOG.exception("Main loop error: %s", e)
                time.sleep(5)


def process_wrapper(
    file_path: Path,
    processing_set: set[Path],
    next_try_at: dict[Path, float],
    session: "requests.Session",
    stop_event: threading.Event,
) -> None:
    try:
        process_file(file_path, session=session, stop_event=stop_event)
    except Exception:
        # process_file already logs exceptions; this is a hard backstop.
        pass
    finally:
        processing_set.discard(file_path)
        # If the input still exists, back off a bit to avoid tight failure loops.
        try:
            if file_path.exists():
                next_try_at[file_path] = time.time() + 30.0
        except Exception:
            pass

if __name__ == "__main__":
    main()
