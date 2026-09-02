# 💻 Laptop Setup & Operator Deployment Guide
### Automated Headshot Photobooth & Delivery System

Follow these simple, step-by-step instructions to set up your laptop for the conference headshot station.

---

## 📋 Checklist Overview
- [ ] **Step 1:** Install Prerequisites (Python, Git, Lightroom Classic)
- [ ] **Step 2:** Download the Project Code
- [ ] **Step 3:** Install Python Dependencies
- [ ] **Step 4:** Configure `config.json` (Google Form, Gmail, Zenfolio)
- [ ] **Step 5:** *(Optional)* Pair Google Messages for Free SMS
- [ ] **Step 6:** Install the Lightroom Classic Plugin
- [ ] **Step 7:** Run the Pre-Shoot Verification Test
- [ ] **Step 8:** Day-of-Event Operating Instructions

---

## 🛠️ Step 1: Install Prerequisites

1. **Python 3.10+ (Windows 64-bit):**
   * Download from [python.org/downloads](https://www.python.org/downloads/).
   * ⚠️ **CRITICAL:** On the very first installer screen, check the box: **`☑ Add python.exe to PATH`**.
   * Click **Install Now**.
2. **Git for Windows (Recommended):**
   * Download from [gitforwindows.org](https://gitforwindows.org/) (use standard default options).
3. **Adobe Lightroom Classic:**
   * Ensure Lightroom Classic is installed and updated via Adobe Creative Cloud.

---

## 📂 Step 2: Download the Project

Open **Command Prompt** or **PowerShell** on your laptop and run:

```bash
git clone https://github.com/TannerScholten/Headshot-Booth.git
cd Headshot-Booth
```

*(Alternatively, download the repository as a ZIP from GitHub, extract it to your Documents or Desktop folder, and open a terminal inside that folder).*

---

## 📦 Step 3: Install Dependencies

In your project folder (`Headshot-Booth`), run:

```bash
pip install -r requirements.txt
```

*(This automatically installs FastAPI, Uvicorn, Requests, Jinja2, Pydantic, and Playwright).*

---

## ⚙️ Step 4: Configure `config.json`

Create your local `config.json` by copying `config.example.json` (or editing existing `config.json`):

```bash
copy config.example.json config.json
```

Open `config.json` in Notepad or VS Code and update your credentials:

```json
{
  "event_name": "Conference Headshots 2026",
  "google_sheet_csv_url": "https://docs.google.com/spreadsheets/d/.../pub?output=csv",
  "poll_interval_seconds": 30,
  "auto_send_emails": true,
  "email_rate_limit_seconds": 1.8,
  "gmail": {
    "sender_name": "Tanner Scholten Photography",
    "sender_email": "your_email@gmail.com",
    "app_password": "xxxx xxxx xxxx xxxx",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587
  },
  "zenfolio": {
    "username": "your_zenfolio_login_email@example.com",
    "password": "your_zenfolio_password",
    "master_group_url": "https://www.tannereli.com/headshots2026",
    "master_group_id": 140572127876386648
  },
  "sms": {
    "enabled": false,
    "rate_limit_seconds": 6.0,
    "browser_profile_dir": "data/browser_profile"
  },
  "paths": {
    "tether_ingest_dir": "C:/Users/tscho/Pictures/Headshots 2026/01_Tether_Ingest",
    "ready_to_deliver_dir": "C:/Users/tscho/Pictures/Headshots 2026/02_Ready_To_Deliver",
    "database_file": "data/booth.db"
  }
}
```

### 🔑 Credential Quick-Links:
* **Google Sheet CSV URL:** In your Google Sheet linked to the registration form $\rightarrow$ **File > Share > Publish to web** $\rightarrow$ Select **Entire Document (or Form Responses 1)** $\rightarrow$ Choose **Comma-separated values (.csv)** $\rightarrow$ Click **Publish** and copy the link.
* **Gmail 16-Character App Password:** Go to [myaccount.google.com/security](https://myaccount.google.com/security) $\rightarrow$ Ensure **2-Step Verification** is enabled $\rightarrow$ Search for **App passwords** $\rightarrow$ Create one named `"Headshot Booth"` $\rightarrow$ Paste the 16 letters into `app_password`.
* **Zenfolio:** Enter your standard Zenfolio login credentials and your target Master Group URL.

---

## 📱 Step 5: (Optional) Pair Google Messages for Zero-Cost SMS

If you want the booth to automatically text gallery links to attendees who enter a mobile number:

1. Install the Playwright Chromium browser binary:
   ```bash
   playwright install chromium
   ```
2. Launch the 1-time pairing window:
   ```bash
   python -m src.sms_service --setup
   ```
3. A Chromium browser window will open to `messages.google.com/web`.
4. On your Android phone, open the **Google Messages** app $\rightarrow$ Tap your profile picture $\rightarrow$ **Device pairing** $\rightarrow$ **QR code scanner**.
5. Scan the QR code on your laptop screen and check **"Remember this computer"**.
6. Once your messages appear, return to your terminal and press **Enter**.
7. In `config.json`, change `"enabled": false` to `"enabled": true` under `"sms"`.

---

## 🔌 Step 6: Install the Lightroom Classic Plugin

1. Open **Adobe Lightroom Classic**.
2. Go to the top menu: **File > Plug-in Manager...**
3. Click the **Add** button in the bottom-left corner of the dialog.
4. Navigate into your `Headshot-Booth` folder and select the **`HeadshotBooth.lrplugin`** folder.
5. Click **Select Folder**.
6. You should see a green circle indicating **"Installed and running"**. Click **Done**.

---

## 🧪 Step 7: Pre-Shoot Verification Test

Before heading to the venue, test the full pipeline offline on your laptop by running:

```bash
python mock_shoot.py
```

* This tests database initialization, attendee intake, tether folder watching, XMP sidecar generation, and Zenfolio/Gmail delivery simulation.
* You should see **`ALL 4 STAGES TESTED SUCCESSFULLY!`** at the end.

---

## 🚀 Step 8: Day of the Event — Operating the Booth

### 1. Start the Booth Server
* Double-click **`run_booth.bat`** in the `Headshot-Booth` folder (or run `python -m uvicorn src.app:app --host 0.0.0.0 --port 8000`).
* *Note: The application automatically prevents Windows Modern Standby from sleeping your USB ports during idle periods.*
* Open **`http://localhost:8000`** in Google Chrome or Microsoft Edge.

### 2. Configure Lightroom Classic Tethering
1. **Critical for Canon R5 Mark II:** In Lightroom Classic, go to **Edit > Preferences > General** tab $\rightarrow$ Check **"Use Canon SDK for Tethering Canon Cameras"** $\rightarrow$ Restart Lightroom.
2. Connect your **Canon EOS R5 Mark II** via USB-C.
3. In Lightroom Classic: **File > Tethered Capture > Start Tethered Capture...**
4. Set the **Destination Folder** to:  
   `C:\Users\tscho\Pictures\Headshots 2026\01_Tether_Ingest`
5. Set the **Session Name** to: `Day_1_Monday` (or current day).
6. Set File Naming to **Original Filename** (or default camera filename).

### 3. In-Booth Shooting Flow
1. **Intake / Selection:**
   * When an attendee walks up, type a few letters of their name in the HUD search box and press **Enter** (or press **Alt+N** for a walk-in registration).
   * Confirm the high-contrast **42pt name & organization** on screen.
2. **Capture:**
   * Snap 4–6 photos on the Canon R5 Mk II. Raw captures land in `01_Tether_Ingest` with instant `.xmp` metadata sidecars.
3. **Cull & Deliver:**
   * In Lightroom Classic, select your 1–2 keeper photos and press **`P`** (Flag as Pick).
   * Press **`Ctrl+Shift+E`** (or click **Export > Headshot Booth - Auto Zenfolio & Email Delivery**).
   * Lightroom displays an on-screen bezel: **`"Delivered to [Name]! 🚀"`**.
   * The attendee immediately receives their personalized email (and optional text message) with their private gallery link.
4. **Outfit Change / Session #2:**
   * If an attendee returns later for an outfit change, click **👔 Outfit Change / Session #2** on the HUD.

---

## 🛟 Troubleshooting & Quick Tips

* **Venue Wi-Fi dropped momentarily?**  
  Click the **`🔁 Retry Failed`** button in the HUD Recent Deliveries header once Wi-Fi reconnects to re-send all queued notices with 1 click.
* **Need to copy a gallery link on the spot?**  
  Click the **`📋 Copy Link`** button on the active subject card in the HUD.
* **Want to edit the delivery email copy?**  
  Click **`✉️ Email Template`** in the top bar to edit the template with live preview.
* **Silence sound cues in quiet rooms:**  
  Click **`🔔 Chime: ON`** in the top bar to toggle sound off.
