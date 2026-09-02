import time
import threading
from pathlib import Path
from typing import Optional, Set
from datetime import datetime

from src.config import config
from src import db
from src.xmp_generator import generate_xmp_sidecar

class IngestWatcher:
    """
    Watches 01_Tether_Ingest folder for new raw captures (.cr3).
    When file transfer completes, generates matching XMP sidecar with active attendee metadata.
    Leaves original raw filename intact to prevent file-locking conflicts with Lightroom Classic.
    """
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._processed: Set[str] = set()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    def _run_loop(self) -> None:
        watch_dir = config.tether_ingest_dir
        while self._running:
            try:
                if watch_dir.exists():
                    for raw_file in watch_dir.rglob("*.[cC][rR]3"):
                        file_key = str(raw_file.resolve())
                        if file_key in self._processed:
                            continue
                        
                        if self._is_file_ready(raw_file):
                            self._processed.add(file_key)
                            self._process_raw_capture(raw_file)
            except Exception as e:
                print(f"[IngestWatcher] Error: {e}")

            if self._stop_event.wait(timeout=1.5):
                break

    def _is_file_ready(self, file_path: Path) -> bool:
        """
        Multi-stage debounce for camera USB-C raw writes:
        1. Check file size > 0.
        2. Wait 500ms and ensure size is stable (unchanged).
        3. Attempt non-blocking handle open.
        """
        try:
            if not file_path.exists():
                return False
            initial_size = file_path.stat().st_size
            if initial_size == 0:
                return False
            
            # Brief wait to ensure camera is not actively streaming bytes
            time.sleep(0.5)
            
            if not file_path.exists():
                return False
            final_size = file_path.stat().st_size
            if final_size != initial_size or final_size == 0:
                return False

            # Test non-blocking read
            with open(file_path, "rb") as f:
                f.seek(0, 2)
            return True
        except (IOError, PermissionError, OSError):
            return False

    def _process_raw_capture(self, raw_file: Path) -> None:
        active = db.get_active_attendee()
        if not active:
            # No active attendee, skip XMP generation
            return

        xmp_file = raw_file.with_suffix(".xmp")
        if not xmp_file.exists():
            generate_xmp_sidecar(
                xmp_path=xmp_file,
                attendee=active,
                photographer_name=config.gmail_config.get("sender_name", "Tanner Scholten Photography")
            )
            print(f"[IngestWatcher] Generated XMP sidecar: {xmp_file.name} for {active['first_name']} {active['last_name']}")

ingest_watcher = IngestWatcher()
