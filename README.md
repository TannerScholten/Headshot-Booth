# Headshot Booth & Automated Delivery System

An automated, operator-friendly workflow system for high-volume professional conference headshot stations (~400 attendees). Connects attendee intake (Google Forms & on-site walk-ins) with tethered captures in Adobe Lightroom Classic, automated Zenfolio gallery creation, and personalized email notifications via Gmail.

---

## Features
- **In-Booth Operator HUD:** High-contrast 42pt+ active subject display, instant type-ahead search, and quick walk-in registration (`Alt+N`).
- **Native Lightroom Classic Plugin (`HeadshotBooth.lrplugin`):** Direct 1-click export and delivery (`Ctrl+Shift+E`) with native progress tracking and custom metadata tagset.
- **Google Sheets Live Sync:** Background worker automatically imports attendee registrations every 30 seconds.
- **Zenfolio Private Gallery Automation:** Automatically creates attendee galleries and uploads keeper photos via Zenfolio Classic API.
- **Rate-Limited Gmail Dispatcher:** Dispatches personalized HTML delivery emails with a 1.8-second spacing delay to protect email sender reputation.
- **Multi-Session Handling:** Handles returning attendees / outfit changes without overwriting past captures.
- **Optional Zero-Cost SMS Delivery:** Automated SMS gallery delivery via Google Messages Web (Playwright) for attendees who provide mobile numbers (100% fail-soft & decoupled).
- **Visual Email Template Editor:** In-app template customizer with live mobile/desktop previews at `/templates-editor`.

---

## Quick Start

1. Copy `config.example.json` to `config.json` and fill in your details (Google Sheet CSV URL, Gmail App Password, Zenfolio credentials).
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. *(Optional)* Set up Zero-Cost SMS Delivery:
   ```bash
   playwright install chromium
   python -m src.sms_service --setup
   ```
   Scan the QR code with your Android Google Messages app, then set `"sms": { "enabled": true }` in `config.json`.
4. Launch the local booth HUD:
   - Double-click `run_booth.bat` or run:
     ```bash
     python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
     ```
   - Open [http://localhost:8000](http://localhost:8000) in your browser.
5. Install the Lightroom Plugin:
   - In Lightroom Classic, go to **File > Plug-in Manager > Add**, and select the `HeadshotBooth.lrplugin` folder.

---

## Testing & Simulation

Run the offline mock shoot harness:
```bash
python mock_shoot.py
```
