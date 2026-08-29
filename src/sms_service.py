"""
SMS Delivery Service via Google Messages Web (Playwright)
Provides optional, zero-cost SMS delivery using a persistent browser session.
Designed for 100% graceful degradation (fail-soft): never blocks core photography operations.
"""

import sys
import time
import threading
import queue
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from src.config import config
from src import db

# Safe Playwright import (graceful fallback if not installed)
try:
    from playwright.sync_api import sync_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = Exception

MESSAGES_WEB_URL = "https://messages.google.com/web"

class SmsService:
    def __init__(self):
        self._last_send_time = 0.0
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

    def is_available(self) -> bool:
        return PLAYWRIGHT_AVAILABLE and config.sms_enabled

    def start_worker(self) -> None:
        if self._running or not self.is_available():
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._queue_worker_loop, daemon=True)
        self._worker_thread.start()
        print("[SmsService] Background SMS queue worker started.")

    def stop_worker(self) -> None:
        self._running = False

    def queue_sms(self, delivery_id: int, phone: str, attendee_name: str, gallery_url: str) -> None:
        """
        Enqueues an SMS delivery task asynchronously to guarantee zero block on tethering/export.
        """
        if not phone:
            db.update_delivery_sms_status(delivery_id, "NOT_PROVIDED")
            return

        if not self.is_available():
            db.update_delivery_sms_status(delivery_id, "DISABLED")
            return

        db.update_delivery_sms_status(delivery_id, "QUEUED")
        self._queue.put({
            "delivery_id": delivery_id,
            "phone": phone,
            "name": attendee_name,
            "gallery_url": gallery_url
        })

    def _queue_worker_loop(self) -> None:
        while self._running:
            try:
                task = self._queue.get(timeout=2.0)
            except queue.Empty:
                continue

            try:
                delivery_id = task["delivery_id"]
                phone = task["phone"]
                first_name = task["name"].split()[0] if task["name"] else "there"
                event = config.event_name
                gal_url = task["gallery_url"]
                
                sms_text = f"Hi {first_name}! Your headshots from {event} are ready. View & download your private gallery here: {gal_url}"
                
                success, msg = self.send_sms(phone, sms_text)
                if success:
                    db.update_delivery_sms_status(delivery_id, "SENT")
                    print(f"[SmsService] SMS sent successfully to {phone} (Delivery #{delivery_id})")
                else:
                    db.update_delivery_sms_status(delivery_id, "FAILED", error_message=msg)
                    print(f"[SmsService] SMS failed for {phone}: {msg}")
            except Exception as e:
                print(f"[SmsService] Queue worker error: {e}")
            finally:
                self._queue.task_done()

    def send_sms(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """
        Sends an SMS message using Google Messages Web in a headless persistent Playwright session.
        Enforces strict timeouts and rate-limiting.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False, "Playwright package not installed. Run: pip install playwright && playwright install chromium"

        if not config.sms_enabled:
            return False, "SMS delivery is disabled in config.json"

        phone_clean = db.normalize_phone_number(phone_number)
        if not phone_clean:
            return False, f"Invalid phone number: '{phone_number}'"

        with self._lock:
            # Enforce rate-limit interval
            now = time.time()
            elapsed = now - self._last_send_time
            required_delay = config.sms_rate_limit_seconds
            if elapsed < required_delay:
                time.sleep(required_delay - elapsed)

            profile_dir = config.browser_profile_dir
            profile_dir.mkdir(parents=True, exist_ok=True)

            try:
                with sync_playwright() as p:
                    # Launch persistent Chromium context with saved profile
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=str(profile_dir),
                        headless=True,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox"
                        ],
                        timeout=15000
                    )
                    page = context.new_page()
                    page.set_default_timeout(10000)

                    # 1. Navigate to Google Messages Web
                    page.goto(MESSAGES_WEB_URL, wait_until="domcontentloaded")
                    
                    # Check if QR code / pairing is required
                    if page.locator("mw-qr-code, canvas, [aria-label*='QR']").is_visible():
                        context.close()
                        return False, "Google Messages session not paired. Run pairing setup: python -m src.sms_service --setup"

                    # 2. Click Start chat
                    start_chat_btn = page.locator("a[href*='conversations/new'], button:has-text('Start chat'), [data-e2e='start-chat-button']").first
                    start_chat_btn.wait_for(state="visible", timeout=8000)
                    start_chat_btn.click()

                    # 3. Input recipient phone number
                    phone_input = page.locator("input[type='text'], input[placeholder*='name, phone'], [data-e2e='contact-search-bar']").first
                    phone_input.wait_for(state="visible", timeout=8000)
                    phone_input.fill(phone_clean)
                    page.keyboard.press("Enter")
                    time.sleep(1.0)

                    # 4. Compose and send message
                    msg_box = page.locator("textarea[placeholder*='Text message'], div[contenteditable='true'][role='textbox']").first
                    msg_box.wait_for(state="visible", timeout=8000)
                    msg_box.fill(message)
                    page.keyboard.press("Enter")

                    # Also click send button if Enter didn't trigger
                    send_btn = page.locator("button[aria-label*='Send'], [data-e2e='send-message-button']").first
                    if send_btn.is_visible():
                        send_btn.click()

                    # Brief wait for dispatch confirmation
                    time.sleep(2.0)
                    context.close()

                    self._last_send_time = time.time()
                    return True, f"SMS dispatched successfully to {phone_clean}"

            except PlaywrightTimeoutError as te:
                return False, f"SMS Timeout (DOM selector or network delay): {str(te)}"
            except Exception as e:
                return False, f"Playwright SMS Error: {str(e)}"

    def run_interactive_setup(self) -> None:
        """
        Launches a non-headless visible Chromium window for 1-time QR pairing with Google Messages.
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("ERROR: Playwright is not installed.")
            print("Run: pip install playwright")
            print("     playwright install chromium")
            return

        profile_dir = config.browser_profile_dir
        profile_dir.mkdir(parents=True, exist_ok=True)

        print("=" * 65)
        print(" GOOGLE MESSAGES WEB 1-TIME PAIRING SETUP")
        print("=" * 65)
        print("Opening Chromium browser...")
        print(f"Profile storage: {profile_dir}")
        print()
        print("Instructions:")
        print(" 1. On your Android phone, open Google Messages.")
        print(" 2. Tap your profile icon -> 'Device pairing' -> 'QR code scanner'.")
        print(" 3. Scan the QR code displayed on the screen.")
        print(" 4. Enable 'Remember this computer'.")
        print(" 5. Once your conversations load, come back here and press ENTER.")
        print("=" * 65)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.new_page()
            page.goto(MESSAGES_WEB_URL)

            input("\n>>> Press ENTER here when you have finished pairing in the browser... <<<")
            print("\nSaving session cookies and closing browser...")
            context.close()

        print("=" * 65)
        print("SETUP COMPLETE! Google Messages session saved.")
        print("You can now enable SMS in config.json (\"sms\": {\"enabled\": true}).")
        print("=" * 65)

# Global service instance
sms_service = SmsService()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        sms_service.run_interactive_setup()
    else:
        print("Usage: python -m src.sms_service --setup")
