import os
import re
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from src.config import config
from src import db
from src.zenfolio_client import zenfolio
from src.email_service import email_service

def process_exported_photo(
    attendee_id: int, 
    file_path: Path, 
    filename: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Core delivery orchestrator:
    1. Queues record in DB.
    2. Creates/resolves Zenfolio private gallery.
    3. Uploads image to Zenfolio.
    4. Dispatches personalized Gmail notification if auto_send is enabled.
    """
    filename = filename or file_path.name
    attendee = db.get_attendee_by_id(attendee_id)
    if not attendee:
        return False, f"Attendee ID {attendee_id} not found in database."

    # 1. Record in DB
    delivery_id = db.record_delivery_queued(attendee_id, filename, str(file_path))

    try:
        # 2. Zenfolio Gallery
        gallery_id, gallery_url, upload_url = zenfolio.get_or_create_attendee_gallery(attendee)
        
        # Refresh attendee dict with latest Zenfolio fields
        attendee = db.get_attendee_by_id(attendee_id)

        # 3. Upload Photo
        photo_id = zenfolio.upload_photo(upload_url, file_path, filename)
        db.update_delivery_status(delivery_id, "UPLOADED", zenfolio_photo_id=photo_id)

        # 4. Email Dispatch
        if config.auto_send_emails:
            success, msg = email_service.send_delivery_email(attendee)
            if success:
                db.update_delivery_status(delivery_id, "SENT")
                return True, f"Successfully uploaded and delivered to {attendee['email']} ({gallery_url})"
            else:
                db.update_delivery_status(delivery_id, "FAILED", error_message=msg)
                return False, f"Uploaded to Zenfolio, but email failed: {msg}"
        else:
            db.update_delivery_status(delivery_id, "HELD")
            return True, f"Uploaded to Zenfolio and queued for batch send ({gallery_url})"

    except Exception as e:
        error_msg = str(e)
        db.update_delivery_status(delivery_id, "FAILED", error_message=error_msg)
        return False, f"Delivery error for {attendee.get('first_name')}: {error_msg}"

def parse_attendee_id_from_filename(filename: str) -> Optional[int]:
    """
    Parses attendee ID from standard filenames like:
    - 1001_Jane_Smith_01.jpg
    - Jane_Smith_1001.jpg
    - 1001.jpg
    """
    match = re.search(r'\b(1\d{3,4})\b', filename)
    if match:
        return int(match.group(1))
    return None

class ReadyToDeliverWatcher:
    """
    Background folder watcher for Ready_To_Deliver directory.
    Useful when exporting via standard Lightroom export presets.
    """
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._processed_files = set()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _watch_loop(self) -> None:
        watch_dir = config.ready_to_deliver_dir
        while self._running:
            try:
                if watch_dir.exists():
                    for file_path in watch_dir.glob("*.[jJ][pP][gG]"):
                        if file_path.name in self._processed_files:
                            continue
                        
                        # Debounce file-write completion
                        if self._is_file_ready(file_path):
                            self._processed_files.add(file_path.name)
                            
                            # Parse attendee ID or use active attendee
                            att_id = parse_attendee_id_from_filename(file_path.name)
                            if not att_id:
                                active = db.get_active_attendee()
                                if active:
                                    att_id = active["id"]

                            if att_id:
                                process_exported_photo(att_id, file_path)
            except Exception as e:
                print(f"[ReadyToDeliverWatcher] Error: {e}")

            time.sleep(2)

    def _is_file_ready(self, file_path: Path) -> bool:
        """
        Ensures Lightroom has completely finished rendering the JPEG:
        1. Check file size > 0.
        2. Wait 500ms and ensure size is stable (unchanged).
        3. Attempt non-blocking handle check.
        """
        try:
            if not file_path.exists():
                return False
            # Ignore temporary Lightroom export files (.tmp)
            if file_path.suffix.lower() in [".tmp", ".crdownload", ".partial"]:
                return False

            initial_size = file_path.stat().st_size
            if initial_size == 0:
                return False

            time.sleep(0.5)

            if not file_path.exists():
                return False
            final_size = file_path.stat().st_size
            if final_size != initial_size or final_size == 0:
                return False

            with open(file_path, "ab") as f:
                pass
            return True
        except (IOError, PermissionError, OSError):
            return False

delivery_watcher = ReadyToDeliverWatcher()
