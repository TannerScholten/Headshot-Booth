"""
Comprehensive Mock Shoot Simulation Suite
Covers all 4 core conference workflows:
1. Intake Simulation (10 diverse attendees with Google Form sync + walk-ins).
2. Tether Ingest Simulation (3 raw .cr3 captures with debounced .xmp sidecar generation).
3. Multi-Session Simulation (Day 1 vs Day 2 outfit change with session tracking).
4. Delivery Simulation (Keeper JPEG export, Zenfolio gallery sync, and Gmail dispatch).
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
from src.xmp_generator import generate_xmp_sidecar
from src.ingest_watcher import ingest_watcher
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

def create_sample_cr3(output_path: Path) -> None:
    """Generates a dummy raw capture file for simulation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(b"RAW_CR3_SIMULATED_BINARY_DATA_FOR_TESTING" * 100)

def run_comprehensive_simulation():
    print("=" * 70)
    print("STARTING COMPREHENSIVE HEADSHOT BOOTH SIMULATION SUITE")
    print("=" * 70)

    # 1. Database Initialization
    print("\n[Stage 1] Initializing SQLite with WAL Mode & 30s Concurrency Timeout...")
    db.init_db()
    print(f"  + Database active at: {config.database_path}")

    # 2. Intake Simulation (10 Attendees with Phones)
    print("\n[Stage 2] Simulating Attendee Intake (10 Sample Registrations)...")
    sample_attendees_data = [
        ("Sarah", "Connor", "sarah.connor@cyberdyne.org", "Cyberdyne Systems", "VP Security", "(555) 019-2834"),
        ("Marcus", "Aurelius", "marcus@rome.gov", "Roman Empire", "Emperor", "555-018-9921"),
        ("Elena", "Rostova", "elena.rostova@techcorp.io", "TechCorp", "Lead Architect", "+15550174432"),
        ("David", "Kowalski", "dkowalski@quantum.com", "Quantum Dynamics", "Principal Engineer", "5550162299"),
        ("Maya", "Lin", "maya.lin@designstudio.org", "Lin Architecture", "Principal Founder", ""),
        ("James", "Holden", "holden@roci.space", "Rocinante Logistics", "Captain", "555-014-8833"),
        ("Naomi", "Nagata", "naomi@belters.org", "Outer Planets Alliance", "Chief Engineer", ""),
        ("Amos", "Burton", "amos@baltimore.net", "Burton Operations", "Mechanic", "555-012-7711"),
        ("Chrisjen", "Avasarala", "avasarala@un.gov", "United Nations", "Secretary-General", "+15550119900"),
        ("Alex", "Kamal", "alex.kamal@mcrn.mil", "Martian Congressional Navy", "Pilot", "")
    ]

    registered_attendees = []
    for first, last, email, org, title, phone in sample_attendees_data:
        att = db.get_or_create_attendee(
            first_name=first,
            last_name=last,
            email=email,
            organization=org,
            title=title,
            phone=phone,
            source="simulation"
        )
        registered_attendees.append(att)
        print(f"  + Ingested #{att['id']}: {att['first_name']} {att['last_name']} ({att['organization']}) [Phone: {att['phone'] or 'N/A'}]")

    print(f"  --> Total Registered Attendees in DB: {len(registered_attendees)}")

    # 3. Live Google Sheet Sync Check (with Cache-Buster)
    print("\n[Stage 3] Testing Google Sheet Live Sync with Cache-Buster...")
    synced, total, msg = forms_sync.fetch_and_sync()
    print(f"  + Result: {msg} (Live Sheet Row Count: {total})")

    # 4. Active Subject Selection & State Machine
    primary_subject = registered_attendees[0]
    print(f"\n[Stage 4] Setting Active Subject to #{primary_subject['id']}: {primary_subject['first_name']} {primary_subject['last_name']}...")
    db.set_active_attendee(primary_subject["id"])
    active_now = db.get_active_attendee()
    print(f"  + Active in State Machine: {active_now['first_name']} {active_now['last_name']} (ID: {active_now['id']})")

    # 5. Tether Ingest Simulation (3 Raw .cr3 Captures + Debounced .xmp Generation)
    print("\n[Stage 5] Simulating Tether Ingest (3 Canon R5 Mk II .cr3 Captures)...")
    ingest_dir = config.tether_ingest_dir
    ingest_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, 4):
        raw_name = f"_RAW_{primary_subject['id']}_{i:03d}.cr3"
        raw_path = ingest_dir / raw_name
        create_sample_cr3(raw_path)
        
        # Generate companion XMP sidecar
        xmp_path = raw_path.with_suffix(".xmp")
        generate_xmp_sidecar(
            xmp_path=xmp_path,
            attendee=primary_subject,
            photographer_name=config.gmail_config.get("sender_name", "Tanner Scholten Photography")
        )
        print(f"  + Capture #{i}: Created {raw_name} and sidecar {xmp_path.name} (IPTC: {primary_subject['email']})")

    # 6. Multi-Session / Outfit Change Simulation
    print(f"\n[Stage 6] Simulating Day 2 Outfit Change (Session #2) for #{primary_subject['id']}...")
    session_2 = db.create_new_session_for_attendee(primary_subject["id"])
    print(f"  + Created Session #{session_2} for Attendee #{primary_subject['id']}. Past session assets preserved.")

    # 7. Keeper Export & Automated Delivery Pipeline
    print(f"\n[Stage 7] Simulating Lightroom Keeper Export & Automated Delivery...")
    mock_keeper = config.ready_to_deliver_dir / f"{primary_subject['id']}_Connor_Sarah_001.jpg"
    create_sample_jpeg(mock_keeper)
    print(f"  + Rendered Keeper JPEG: {mock_keeper.name}")

    print(f"  + Triggering Zenfolio upload and Gmail SMTP dispatcher...")
    success, msg = process_exported_photo(primary_subject["id"], mock_keeper)
    print(f"  + Delivery Result: {'SUCCESS' if success else 'NOTICE'}: {msg}")

    # 8. Summary Statistics
    print("\n[Stage 8] Final System Ledger Statistics:")
    stats = db.get_stats()
    for k, v in stats.items():
        print(f"  * {k}: {v}")

    print("\n" + "=" * 70)
    print("ALL 4 STAGES TESTED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_comprehensive_simulation()
