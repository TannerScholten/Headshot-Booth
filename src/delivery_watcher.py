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
from src.sms_service import sms_service

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
    5. Asynchronously queues optional zero-cost SMS notification via Google Messages.
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

        # 4. Email Dispatch (Only send if the attendee hasn't already received their gallery link!)
        already_emailed = db.has_attendee_received_delivery(attendee_id)
        email_sent = False

        if config.auto_send_emails:
            if not already_emailed:
                success, msg = email_service.send_delivery_email(attendee)
                if success:
                    db.update_delivery_status(delivery_id, "SENT")
                    email_sent = True
                else:
                    db.update_delivery_status(delivery_id, "FAILED", error_message=msg)
            else:
                # Already received their permanent gallery link! Mark photo delivery as SENT without sending duplicate email.
                db.update_delivery_status(delivery_id, "SENT")
                email_sent = True
                print(f"[Delivery] Uploaded {filename} to {attendee.get('first_name')} {attendee.get('last_name')}'s gallery. Duplicate email suppressed (gallery already delivered).")
        else:
            db.update_delivery_status(delivery_id, "HELD")

        # 5. Optional SMS Dispatch (Only send on initial delivery)
        if not already_emailed:
            phone = attendee.get("phone", "")
            full_name = f"{attendee.get('first_name', '')} {attendee.get('last_name', '')}".strip()
            sms_service.queue_sms(delivery_id, phone, full_name, gallery_url)

        # 6. Auto-Archive processed file out of watch directory to prevent any duplicate re-processing
        try:
            archive_dir = file_path.parent / "_Delivered_Archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_target = archive_dir / filename
            if file_path.exists() and file_path != archive_target:
                if archive_target.exists():
                    archive_target.unlink()
                file_path.rename(archive_target)
        except Exception as move_err:
            print(f"[DeliveryWatcher] Notice moving to archive: {move_err}")

        if email_sent:
            return True, f"Successfully uploaded and delivered to {attendee['email']} ({gallery_url})"
        elif not config.auto_send_emails:
            return True, f"Uploaded to Zenfolio and queued for batch send ({gallery_url})"
        else:
            return False, f"Uploaded to Zenfolio, but email failed: {msg}"

    except Exception as e:
        error_msg = str(e)
        db.update_delivery_status(delivery_id, "FAILED", error_message=error_msg)
        return False, f"Delivery error for {attendee.get('first_name')}: {error_msg}"

def resolve_attendee_id_for_photo(file_path: Path) -> Optional[int]:
    """
    Robust Multi-Attendee Batch Resolution:
    1. Check embedded IPTC/EXIF metadata (Email) directly inside exported JPEG bytes
    2. Check companion XMP sidecar in 01_Tether_Ingest matching raw filename
    3. Check explicit ID pattern in filename (e.g. ID_1012.jpg or 1012_Name.jpg)
    4. Fall back to current active attendee on HUD (only for un-tagged files)
    """
    # 1. Check embedded email directly inside JPEG binary headers
    try:
        if file_path.exists():
            header = file_path.read_bytes()[:150000] # First 150KB contains EXIF/IPTC
            emails = re.findall(rb'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', header)
            for em in emails:
                em_str = em.decode('utf-8', errors='ignore').strip()
                att = db.get_attendee_by_email(em_str)
                if att:
                    return att["id"]
    except Exception as err:
        print(f"[DeliveryWatcher] IPTC extraction notice: {err}")

    # 2. Check companion XMP sidecar in tether ingest directory
    stem = file_path.stem.split('_')[0] + '_' + file_path.stem.split('_')[1] if '_' in file_path.stem else file_path.stem
    tether_dir = config.tether_ingest_dir
    if tether_dir.exists():
        for xmp_file in tether_dir.rglob(f"{stem}.xmp"):
            try:
                content = xmp_file.read_text(encoding="utf-8", errors="ignore")
                # Try finding attendee by headline name
                m_name = re.search(r'<photoshop:Headline>([^<]+)</photoshop:Headline>', content)
                if m_name:
                    headline = m_name.group(1).strip().lower()
                    for a in db.search_attendees(''):
                        if a['first_name'].lower() in headline and a['last_name'].lower() in headline:
                            return a['id']

                # Try finding attendee by ID
                xmp_match = re.search(r'Attendee_(\d+)_Session', content)
                if xmp_match:
                    att_id = int(xmp_match.group(1))
                    if db.get_attendee_by_id(att_id):
                        return att_id
            except Exception:
                pass

    # 3. Check explicit pattern like ID_1012 or 1012_
    match = re.search(r'(?:^|_)ID_?(\d{4})(?:_|$)', file_path.stem, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # 4. Fall back to current active attendee on HUD (only for un-tagged files)
    active = db.get_active_attendee()
    if active:
        return active["id"]

    return None

class ReadyToDeliverWatcher:
    """
    Background folder watcher for Ready_To_Deliver directory.
    Watches top-level directory and auto-archives processed files to _Delivered_Archive.
    """
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._processed_files = set()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    def _watch_loop(self) -> None:
        watch_dir = config.ready_to_deliver_dir
        while self._running:
            try:
                if watch_dir.exists():
                    # Top-level only, ignoring _Delivered_Archive subfolder
                    for file_path in sorted(watch_dir.glob("*.[jJ][pP][gG]")):
                        file_key = str(file_path.resolve())
                        if file_key in self._processed_files:
                            continue
                        
                        # Debounce file-write completion
                        if self._is_file_ready(file_path):
                            self._processed_files.add(file_key)
                            
                            # Resolve attendee via companion XMP or active attendee
                            att_id = resolve_attendee_id_for_photo(file_path)

                            if att_id:
                                success, msg = process_exported_photo(att_id, file_path)
                                if not success and file_path.exists():
                                    self._processed_files.discard(file_key)
                            else:
                                self._processed_files.discard(file_key)
            except Exception as e:
                print(f"[ReadyToDeliverWatcher] Error: {e}")

            if self._stop_event.wait(timeout=2.0):
                break

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
