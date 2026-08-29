import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from src.config import config

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.database_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn

def init_db() -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Table: attendees
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            phone TEXT,
            organization TEXT,
            title TEXT,
            source TEXT DEFAULT 'google_forms',
            notes TEXT,
            zenfolio_gallery_id INTEGER,
            zenfolio_gallery_url TEXT,
            zenfolio_upload_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Ensure autoincrement starts at 1001 for clean 4-digit IDs
        cursor.execute("""
        INSERT INTO sqlite_sequence (name, seq) 
        SELECT 'attendees', 1000 
        WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = 'attendees')
        """)
        
        # Table: sessions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendee_id INTEGER NOT NULL,
            session_number INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (attendee_id) REFERENCES attendees(id) ON DELETE CASCADE
        )
        """)
        
        # Table: delivery_records
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS delivery_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendee_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT,
            zenfolio_photo_id INTEGER,
            status TEXT DEFAULT 'QUEUED', -- QUEUED, UPLOADED, SENT, FAILED, HELD
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            uploaded_at TIMESTAMP,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (attendee_id) REFERENCES attendees(id) ON DELETE CASCADE
        )
        """)
        
        # Table: system_state
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Default state
        cursor.execute("INSERT OR IGNORE INTO system_state (key, value) VALUES ('active_attendee_id', '')")
        cursor.execute("INSERT OR IGNORE INTO system_state (key, value) VALUES ('last_google_sync', '')")
        conn.commit()

# --- Attendee Operations ---

def get_or_create_attendee(
    first_name: str,
    last_name: str,
    email: str,
    organization: str = "",
    title: str = "",
    phone: str = "",
    source: str = "google_forms"
) -> Dict[str, Any]:
    first_name = first_name.strip()
    last_name = last_name.strip()
    email = email.strip().lower()
    organization = organization.strip()
    title = title.strip()
    phone = phone.strip()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attendees WHERE email = ?", (email,))
        row = cursor.fetchone()
        
        if row:
            # Update existing attendee if info changed
            cursor.execute("""
            UPDATE attendees 
            SET first_name = ?, last_name = ?, organization = ?, title = ?, phone = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (first_name or row["first_name"], last_name or row["last_name"], organization or row["organization"], title or row["title"], phone or row["phone"], row["id"]))
            conn.commit()
            cursor.execute("SELECT * FROM attendees WHERE id = ?", (row["id"],))
            return dict(cursor.fetchone())
        else:
            cursor.execute("""
            INSERT INTO attendees (first_name, last_name, email, phone, organization, title, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (first_name, last_name, email, phone, organization, title, source))
            attendee_id = cursor.lastrowid
            
            # Create Session #1
            cursor.execute("""
            INSERT INTO sessions (attendee_id, session_number, is_active)
            VALUES (?, 1, 1)
            """, (attendee_id,))
            conn.commit()
            
            cursor.execute("SELECT * FROM attendees WHERE id = ?", (attendee_id,))
            return dict(cursor.fetchone())

def search_attendees(query: str = "", limit: int = 30) -> List[Dict[str, Any]]:
    query = f"%{query.strip()}%"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT a.*, 
               (SELECT COUNT(*) FROM delivery_records WHERE attendee_id = a.id) as photo_count,
               (SELECT COUNT(*) FROM sessions WHERE attendee_id = a.id) as session_count
        FROM attendees a
        WHERE a.first_name LIKE ? OR a.last_name LIKE ? OR (a.first_name || ' ' || a.last_name) LIKE ? OR a.email LIKE ? OR a.organization LIKE ? OR CAST(a.id AS TEXT) LIKE ?
        ORDER BY a.updated_at DESC
        LIMIT ?
        """, (query, query, query, query, query, query, limit))
        return [dict(r) for r in cursor.fetchall()]

def get_attendee_by_id(attendee_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attendees WHERE id = ?", (attendee_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_attendee_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attendees WHERE email = ? COLLATE NOCASE", (email.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_attendee_zenfolio(attendee_id: int, gallery_id: int, gallery_url: str, upload_url: str) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE attendees 
        SET zenfolio_gallery_id = ?, zenfolio_gallery_url = ?, zenfolio_upload_url = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (gallery_id, gallery_url, upload_url, attendee_id))
        conn.commit()

# --- Active Subject State Machine ---

def set_active_attendee(attendee_id: Optional[int]) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        val = str(attendee_id) if attendee_id else ""
        cursor.execute("""
        INSERT INTO system_state (key, value, updated_at)
        VALUES ('active_attendee_id', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """, (val,))
        conn.commit()
    return get_active_attendee()

def get_active_attendee() -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key = 'active_attendee_id'")
        row = cursor.fetchone()
        if row and row["value"]:
            try:
                attendee_id = int(row["value"])
                return get_attendee_by_id(attendee_id)
            except ValueError:
                return None
    return None

def create_new_session_for_attendee(attendee_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(session_number) as max_seq FROM sessions WHERE attendee_id = ?", (attendee_id,))
        row = cursor.fetchone()
        next_seq = (row["max_seq"] or 0) + 1
        
        cursor.execute("UPDATE sessions SET is_active = 0 WHERE attendee_id = ?", (attendee_id,))
        cursor.execute("""
        INSERT INTO sessions (attendee_id, session_number, is_active)
        VALUES (?, ?, 1)
        """, (attendee_id, next_seq))
        conn.commit()
        return next_seq

# --- Delivery & Outbox Ledger ---

def record_delivery_queued(attendee_id: int, filename: str, file_path: str = "") -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO delivery_records (attendee_id, filename, file_path, status)
        VALUES (?, ?, ?, 'QUEUED')
        """, (attendee_id, filename, file_path))
        conn.commit()
        return cursor.lastrowid

def update_delivery_status(
    delivery_id: int, 
    status: str, 
    zenfolio_photo_id: Optional[int] = None, 
    error_message: Optional[str] = None
) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        
        if status == 'UPLOADED':
            cursor.execute("""
            UPDATE delivery_records 
            SET status = ?, zenfolio_photo_id = ?, uploaded_at = ?, error_message = NULL
            WHERE id = ?
            """, (status, zenfolio_photo_id, now, delivery_id))
        elif status == 'SENT':
            cursor.execute("""
            UPDATE delivery_records 
            SET status = ?, delivered_at = ?, error_message = NULL
            WHERE id = ?
            """, (status, now, delivery_id))
        elif status == 'FAILED':
            cursor.execute("""
            UPDATE delivery_records 
            SET status = ?, error_message = ?, retry_count = retry_count + 1
            WHERE id = ?
            """, (status, error_message, delivery_id))
        else:
            cursor.execute("UPDATE delivery_records SET status = ? WHERE id = ?", (status, delivery_id))
        conn.commit()

def get_pending_deliveries() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT d.*, a.first_name, a.last_name, a.email, a.organization, a.zenfolio_gallery_url, a.zenfolio_upload_url
        FROM delivery_records d
        JOIN attendees a ON d.attendee_id = a.id
        WHERE d.status IN ('QUEUED', 'UPLOADED', 'FAILED')
        ORDER BY d.created_at ASC
        """)
        return [dict(r) for r in cursor.fetchall()]

def get_recent_deliveries(limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT d.*, a.first_name, a.last_name, a.email, a.organization, a.zenfolio_gallery_url
        FROM delivery_records d
        JOIN attendees a ON d.attendee_id = a.id
        ORDER BY d.created_at DESC
        LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

def get_stats() -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM attendees")
        total_attendees = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM delivery_records WHERE status = 'SENT'")
        sent_deliveries = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM delivery_records WHERE status IN ('QUEUED', 'UPLOADED')")
        pending_deliveries = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM delivery_records WHERE status = 'FAILED'")
        failed_deliveries = cursor.fetchone()["count"]
        
        cursor.execute("SELECT value FROM system_state WHERE key = 'last_google_sync'")
        last_sync = cursor.fetchone()["value"]
        
        return {
            "total_attendees": total_attendees,
            "sent_deliveries": sent_deliveries,
            "pending_deliveries": pending_deliveries,
            "failed_deliveries": failed_deliveries,
            "last_google_sync": last_sync
        }

# Initialize tables on import
init_db()
