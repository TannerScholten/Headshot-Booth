import csv
import io
import time
import threading
import urllib.request
import ssl
from datetime import datetime
from typing import Dict, Any, List, Tuple
from src.config import config
from src import db

class GoogleFormsSync:
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def fetch_and_sync(self) -> Tuple[int, int, str]:
        """
        Fetches published CSV from Google Sheet and syncs attendees into SQLite.
        Returns: (new_or_updated_count, total_rows, message)
        """
        csv_url = config.google_sheet_csv_url
        if not csv_url:
            return 0, 0, "No Google Sheet CSV URL configured."

        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                csv_url,
                headers={"User-Agent": "HeadshotBooth/1.0"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                content = resp.read().decode("utf-8-sig")

            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
            
            synced_count = 0
            for row in rows:
                # Find columns regardless of slight naming differences
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
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop_background_poller(self) -> None:
        self._running = False

    def _run_loop(self) -> None:
        while self._running:
            try:
                self.fetch_and_sync()
            except Exception as e:
                print(f"[GoogleFormsSync] Background poll error: {e}")
            
            # Sleep in 1-second chunks to allow rapid shutdown
            interval = config.poll_interval_seconds
            for _ in range(max(5, interval)):
                if not self._running:
                    break
                time.sleep(1)

# Global sync instance
forms_sync = GoogleFormsSync()
