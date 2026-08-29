# MASTER BUILD SPECIFICATION: Automated Headshot Photobooth & Delivery System

## 1. Project Objective & Core Mission
Design and implement an automated, robust, and operator-friendly workflow system for a high-volume professional conference headshot station (~400 attendees over 3 days, ~133/day). 

The primary goal is to eliminate manual administrative bottlenecks—such as manual renaming, tracking spreadsheets, and individual email attachments—while connecting attendee registration data directly to tethered camera captures, facilitating fast in-booth culling, and automating delivery through a branded Zenfolio gallery experience with personalized email notifications.

The system must allow the photographer to focus on client interaction and rapid capture while background processes handle identification, metadata injection, queue state, and dispatch.

---

## 2. Hardware, Software & Environmental Constraints
* **Operating System:** Windows 11 (Development is initially performed on a Desktop PC; the final deployment runs on a moderately powered Windows laptop).
* **Camera System:** Canon EOS R5 Mark II tethered via USB-C, shooting in Compact RAW (C-RAW) format to balance 45MP resolution with file transfer speed and storage overhead.
* **Editing & Post-Processing Engine:** Adobe Lightroom Classic. Heavy operations (AI subject/background masking and color grading presets) must run only on selected/flagged keepers (`P` / 5-star rating) during batch intervals—never in real time on every raw ingest frame.
* **Platform Delivery:** Zenfolio (Classic tier with API access enabled; official Lightroom Publish Service plugin available).
* **Email Notification Channel:** Personal Gmail account (via Google App Passwords / SMTP or Gmail API) or a free-tier transactional service (e.g., Resend / Brevo) sending clean, responsive HTML notices with gallery links and access credentials.
* **Network Reliability:** Conference venue Wi-Fi may be intermittent. Core capture, metadata tagging, and local queue management must operate 100% offline. Network operations (email and gallery sync) must queue gracefully with auto-retry.

---

## 3. High-Level System Workflow
The implementation should support the following modular pipeline:

1. **Attendee Intake:** Attendees register on-site or beforehand via a web form (Google Forms, Microsoft Forms, or local intake). A CSV/live roster feeds into the system.
2. **Operator HUD & Active Subject Selection:** The photographer sets the "Active Subject" on an in-booth dashboard via rapid type-ahead search, roster click, or optional webcam QR scan. The active name is prominently displayed for verbal identity confirmation from 3–5 feet away.
3. **Tethered Capture & Metadata Tagging:** Raw captures (`.cr3`) land in a watched tether folder. The background engine immediately associates incoming frames with the active subject via `.xmp` sidecar creation or non-destructive naming convention.
4. **Culling & AI Development in Lightroom Classic:** The photographer reviews the 4–6 shot burst, applies basic exposure/color, and flags (`P`) 1–2 keepers. Unflagged frames are bypassed. Flagged files are batch-exported (with full IPTC/EXIF metadata) to a watched `Ready_To_Deliver/` folder.
5. **Zenfolio Sync & Email Dispatch:** Exported JPEGs trigger an automated delivery pipeline that uploads/syncs images to an unlisted, password-protected Zenfolio event gallery and dispatches a personalized notification email with the gallery URL and password.

---

## 4. Key Functional Requirements

### A. In-Booth UI & Heads-Up Display (HUD)
* **High-Contrast, Large Typography:** Display the active subject's **Full Name**, **Organization/Title**, and **Unique ID** in 36pt+ text for effortless reading from a standing position.
* **Rapid Type-Ahead Autocomplete:** Search by first name, last name, or organization with instant keyboard focus and `Enter`-to-activate.
* **Walk-In / Offline Modal:** A fast 5-second popup allowing manual entry (`First Name`, `Last Name`, `Email`, `Organization`) if someone didn't pre-register or network is down.
* **Sticky State Machine:** The active subject must persist across multiple shots until explicitly changed or cleared by the operator.
* **Multi-Session Support (Outfits & Multi-Day Visits):** When selecting an existing attendee who returns on Day 2/3 for an outfit change, create a new sub-session under their profile without overwriting previous sessions or assets.

### B. Ingest File Watcher & Metadata Injection
* **File-Lock Debounce:** Implement robust file-lock detection on incoming `.cr3` files to ensure transfers are 100% complete before sidecar generation or file operations.
* **XMP Sidecar Generation:** Generate `.xmp` sidecar files containing IPTC fields (`Creator`, `Job Identifier`, `Headline`, `Contact Email`, `Subject Name`) so Lightroom Classic automatically reads and embeds them upon catalog sync.
* **Deterministic File Naming:** Output clean, collisions-proof naming templates (e.g., `{ID}_{LastName}_{FirstName}_{YYYYMMDD}_{Seq}.cr3`).

### C. Delivery & Outbox Watcher
* **JPEG Export Watcher:** Monitor the `Ready_To_Deliver/` folder for newly rendered JPEGs containing embedded IPTC metadata.
* **Email Dispatcher with Rate Limiting:** Extract the client's email directly from EXIF/IPTC tags, render a personalized email template (`{{First_Name}}`, `{{Gallery_URL}}`, `{{Gallery_Password}}`), and dispatch with a 1.5–2.0 second inter-message delay to avoid Gmail rate-limiting.
* **Outbox Ledger & Crash Recovery:** Persist all queue states in a lightweight local ledger (`SQLite` or `session_state.json`). If the app or network restarts, un-sent items must resume automatically without duplicate deliveries.

---

## 5. Architectural Freedom for Exploration
You are encouraged to evaluate and propose the cleanest, most maintainable tools, libraries, and architectural patterns. Key areas to analyze:

* **Local UI Framework:** Evaluate lightweight options (e.g., Streamlit, FastHTML, Flask + HTMX, PyQt/PySide, or a lightweight web dashboard). Prioritize minimal latency, clean keyboard shortcuts, and simple setup.
* **File System Monitoring:** Evaluate Python `watchdog` vs. polling mechanisms for handling large raw files safely under Windows file-locking semantics.
* **Metadata & EXIF Tooling:** Assess `pyexiftool` (wrapper for Phil Harvey's ExifTool), `piexif`, `exifread`, or native XML templates for generating Lightroom-compliant `.xmp` sidecars.
* **Zenfolio Integration:** Evaluate whether to leverage Zenfolio's SOAP/REST API for direct programmatic uploads vs. utilizing the native Zenfolio Lightroom Publish Service plugin paired with a scripted email notification engine.
* **Intake & Form Sync:** Compare Google Sheets API / webhooks vs. periodic CSV imports vs. a standalone Google Apps Script bridge.

---

## 6. Portability & Development Roadmap
Because initial development occurs on a desktop PC prior to deployment on the shooting laptop:

1. **Environment & Path Abstraction:** All directory paths (tether folders, export folders, catalogs, database locations) must be defined via a central `config.json` or `.env` file using relative or path-agnostic handling (`pathlib.Path`).
2. **Mock Test Harness:** Include a simulation/mocking script (`mock_shoot.py`) that can simulate attendee intake, drop sample `.cr3`/`.jpg` images into the watch folder at set intervals, and verify the entire metadata $\rightarrow$ watcher $\rightarrow$ email flow offline on the desktop.
3. **Requirements & Setup:** Maintain a clean `requirements.txt` and a simple one-command runner script for cross-machine deployment.

---

## 7. Immediate Next Steps
1. Propose the recommended system architecture, UI framework, and folder structure.
2. Outline the local state machine and data schema (`Attendee`, `Session`, `PhotoRecord`).
3. Provide the minimal working prototype code for:
   * The Config loader & Local Database/Ledger.
   * The Local In-Booth UI/HUD.
   * The Tether Ingest Watcher & XMP Generator.
   * The Mock Shoot Test Suite.