"""
Mock Shoot Simulation Suite
Simulates the entire conference workflow offline on desktop:
1. Syncs Google Sheets responses into local SQLite database.
2. Simulates walk-in registrations.
3. Simulates active subject selection and outfit changes.
4. Simulates Lightroom keeper JPEG export and triggers the delivery pipeline.
"""

import os
import sys
import time
from pathlib import Path

# Safe UTF-8 console output for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import config
from src import db
from src.google_forms_sync import forms_sync
from src.delivery_watcher import process_exported_photo

def create_sample_jpeg(output_path: Path) -> None:
    """Generates a minimal valid 1x1 JPEG image for simulation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    jpeg_bytes = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F,
        0x00, 0xBF, 0x00, 0xFF, 0xD9
    ])
    with open(output_path, "wb") as f:
        f.write(jpeg_bytes)

def run_simulation():
    print("=" * 60)
    print("STARTING HEADSHOT BOOTH END-TO-END SIMULATION")
    print("=" * 60)

    # 1. Initialize Database
    print("\n[Step 1] Initializing SQLite database...")
    db.init_db()
    print(f"Database initialized at: {config.database_path}")

    # 2. Sync Google Form responses
    print("\n[Step 2] Testing Google Sheet Live CSV Sync...")
    synced, total, msg = forms_sync.fetch_and_sync()
    print(f"{msg} (Rows in sheet: {total})")

    # 3. Create Walk-In Attendees
    print("\n[Step 3] Simulating Walk-In Registrations...")
    test_walkins = [
        ("Sarah", "Connor", "sarah.connor@cyberdyne.org", "Cyberdyne Systems", "VP Security"),
        ("Marcus", "Aurelius", "marcus@rome.gov", "Roman Empire", "Emperor"),
    ]
    created_attendees = []
    for first, last, email, org, title in test_walkins:
        att = db.get_or_create_attendee(
            first_name=first,
            last_name=last,
            email=email,
            organization=org,
            title=title,
            source="walk_in"
        )
        created_attendees.append(att)
        print(f"  + Registered Attendee #{att['id']}: {att['first_name']} {att['last_name']} ({att['organization']})")

    # 4. Set Active Subject
    active_test = created_attendees[0]
    print(f"\n[Step 4] Setting Active Subject to #{active_test['id']}: {active_test['first_name']} {active_test['last_name']}")
    db.set_active_attendee(active_test["id"])
    curr_active = db.get_active_attendee()
    print(f"Active Subject in state machine: {curr_active['first_name']} {curr_active['last_name']} (ID: {curr_active['id']})")

    # 5. Simulate Outfit Change / Multi-Session
    print(f"\n[Step 5] Simulating Outfit Change (Session #2)...")
    new_seq = db.create_new_session_for_attendee(active_test["id"])
    print(f"Created Session #{new_seq} for Attendee #{active_test['id']}")

    # 6. Simulate Lightroom Keeper Export & Delivery
    print(f"\n[Step 6] Simulating Lightroom Keeper Export & Delivery Trigger...")
    mock_keeper = config.ready_to_deliver_dir / f"{active_test['id']}_Connor_Sarah_001.jpg"
    create_sample_jpeg(mock_keeper)
    print(f"Created mock exported JPEG: {mock_keeper.name}")

    # Process delivery
    print(f"Processing delivery pipeline for Attendee #{active_test['id']}...")
    success, msg = process_exported_photo(active_test["id"], mock_keeper)
    print(f"Result: {'SUCCESS' if success else 'NOTICE'}: {msg}")

    # 7. Print Final System Statistics
    print("\n[Step 7] Final System Ledger Statistics:")
    stats = db.get_stats()
    for k, v in stats.items():
        print(f"  * {k}: {v}")

    print("\n" + "=" * 60)
    print("SIMULATION TEST COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    run_simulation()
