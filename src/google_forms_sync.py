import csv
import io
import time
import re
import threading
import urllib.request
import ssl
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from src.config import config
from src import db

def normalize_google_sheets_url(url: str) -> str:
    """
    Transforms any Google Sheets URL (sharing link, edit link, or /pub link)
    into the real-time Live Direct Export endpoint (/export?format=csv).
    Bypasses Google's 3-5 minute /pub CDN edge cache.
    """
    if not url:
        return ""
    
    url = url.strip()
    # Check if already an export URL
    if "/export?format=csv" in url or "/export?" in url:
        return url

    # Extract spreadsheet ID from /spreadsheets/d/{ID}
    match = re.search(r"/spreadsheets/d/(?:e/)?([a-zA-Z0-9-_]+)", url)
    if not match:
        return url

    sheet_id = match.group(1)

    # Extract gid (worksheet tab) if present
    gid_match = re.search(r"[?&#]gid=(\d+)", url)
    gid_param = f"&gid={gid_match.group(1)}" if gid_match else ""

    # Check if it's a published web URL (/pub)
    if "/pub" in url:
        return url

    # Standard spreadsheet ID -> Live Direct Export endpoint
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_param}"

class GoogleFormsSync:
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def fetch_and_sync(self) -> Tuple[int, int, str]:
        """
        Fetches CSV from Google Sheet (via Live Direct Export or published CSV)
        and syncs attendees into SQLite in real time.
        """
        raw_url = config.google_sheet_csv_url
        if not raw_url:
            return 0, 0, "No Google Sheet CSV URL configured."

        # Automatically normalize to Live Direct Export endpoint if applicable
        csv_url = normalize_google_sheets_url(raw_url)

        try:
            # Append epoch timestamp cache-buster to bypass any intermediate caching
            cache_busted_url = csv_url
            if "?" in csv_url:
                cache_busted_url = f"{csv_url}&_t={int(time.time())}"
            else:
                cache_busted_url = f"{csv_url}?_t={int(time.time())}"

            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                cache_busted_url,
                headers={
                    "User-Agent": "HeadshotBooth/1.0",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                final_url = resp.geturl()
                if "accounts.google.com" in final_url or "ServiceLogin" in final_url:
                    return 0, 0, "Permission Error: Set Google Sheet sharing to 'Anyone with the link can view'."
                content = resp.read().decode("utf-8-sig")

            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
            
            synced_count = 0
            for row in rows:
                first_name = row.get("First Name", "").strip()
                last_name = row.get("Last Name", "").strip()
                
                # Handle possible duplicate "Email Address" column in Google Forms
                email = ""
                for k, v in row.items():
                    if k and "email" in k.lower() and v.strip():
                        email = v.strip()
                        break

                org = row.get("Organization / Company", "") or row.get("Organization", "") or row.get("Company", "")
                title = row.get("Title / Role", "") or row.get("Title", "") or row.get("Role", "")
                phone = row.get("Mobile / Cell Phone", "") or row.get("Phone", "")

                if first_name and last_name and email:
                    db.get_or_create_attendee(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        organization=org,
                        title=title,
                        phone=phone,
                        source="google_forms"
                    )
                    synced_count += 1

            # Update last sync timestamp
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE system_state SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_google_sync'",
                    (datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),)
                )
                conn.commit()

            return synced_count, len(rows), f"Synced {synced_count} attendees successfully."
        except Exception as e:
            return 0, 0, f"Error syncing Google Sheet: {str(e)}"

    def start_background_poller(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop_background_poller(self) -> None:
        self._running = False
        self._stop_event.set()

    def _run_loop(self) -> None:
        while self._running:
            try:
                self.fetch_and_sync()
            except Exception as e:
                print(f"[GoogleFormsSync] Background poll error: {e}")
            
            # Event-based sleep allows instant graceful shutdown
            interval = max(5, config.poll_interval_seconds)
            if self._stop_event.wait(timeout=interval):
                break

# Global sync instance
forms_sync = GoogleFormsSync()

def submit_walkin_to_google_form(
    first_name: str,
    last_name: str,
    email: str,
    phone: str = "",
    organization: str = "",
    title: str = ""
) -> Tuple[bool, str]:
    """
    Submits walk-in registration data directly to the Google Form response endpoint
    so that walk-ins appear automatically in the linked Google Sheet for long-term records.
    """
    form_url = getattr(config, "google_form_response_url", None) or "https://docs.google.com/forms/d/e/1FAIpQLSctBIGjIJh8DcOSTLCBfnLn3tFRV9DNeqdpsGGlcrMTJ8azmQ/formResponse"
    
    payload = {
        "entry.1188454101": first_name.strip(),
        "entry.695863666": last_name.strip(),
        "entry.1656883919": email.strip(),
        "entry.991914779": phone.strip(),
        "entry.1871759233": organization.strip(),
        "entry.751008980": title.strip(),
    }
    
    try:
        import urllib.parse
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            form_url,
            data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            return True, "Successfully submitted walk-in to Google Form."
    except Exception as e:
        print(f"[GoogleFormsSync] Warning submitting walk-in to Google Form: {e}")
        return False, str(e)
