import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Form, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.config import config, PROJECT_ROOT
from src import db
from src.google_forms_sync import forms_sync
from src.delivery_watcher import process_exported_photo, delivery_watcher
from src.email_service import email_service

app = FastAPI(title="Headshot Booth & Delivery System", version="1.0.0")

# Mount static and template directories
static_dir = PROJECT_ROOT / "static"
templates_dir = PROJECT_ROOT / "templates"
static_dir.mkdir(parents=True, exist_ok=True)
templates_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Lifecycle: start background workers on startup
@app.on_event("startup")
def on_startup():
    db.init_db()
    forms_sync.start_background_poller()
    delivery_watcher.start()

@app.on_event("shutdown")
def on_shutdown():
    forms_sync.stop_background_poller()
    delivery_watcher.stop()

# --- Web UI Routes ---

@app.get("/", response_class=HTMLResponse)
async def index_hud(request: Request):
    active = db.get_active_attendee()
    stats = db.get_stats()
    recent_attendees = db.search_attendees("", limit=15)
    return templates.TemplateResponse(
        request=request,
        name="hud.html",
        context={
            "event_name": config.event_name,
            "active_attendee": active,
            "stats": stats,
            "recent_attendees": recent_attendees,
            "auto_send_emails": config.auto_send_emails
        }
    )

@app.get("/templates-editor", response_class=HTMLResponse)
async def template_editor(request: Request):
    content = email_service.get_template_content()
    active = db.get_active_attendee() or {
        "first_name": "Jane",
        "last_name": "Smith",
        "organization": "Acme Global",
        "title": "Director of Communications",
        "email": "jane.smith@example.com",
        "zenfolio_gallery_url": "https://www.tannereli.com/p829497399"
    }
    _, preview_html = email_service.render_email(active, content)
    return templates.TemplateResponse(
        request=request,
        name="template_editor.html",
        context={
            "event_name": config.event_name,
            "template_content": content,
            "preview_html": preview_html,
            "sample_attendee": active
        }
    )

# --- JSON API Endpoints ---

class WalkInRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    organization: Optional[str] = ""
    title: Optional[str] = ""
    phone: Optional[str] = ""

@app.get("/api/active")
async def api_get_active():
    return {
        "active": db.get_active_attendee(),
        "stats": db.get_stats()
    }

@app.post("/api/active/{attendee_id}")
async def api_set_active(attendee_id: int):
    attendee = db.get_attendee_by_id(attendee_id)
    if not attendee:
        raise HTTPException(status_code=404, detail="Attendee not found")
    active = db.set_active_attendee(attendee_id)
    return {"status": "success", "active": active}

@app.post("/api/active/clear")
async def api_clear_active():
    db.set_active_attendee(None)
    return {"status": "success", "active": None}

@app.post("/api/session/new/{attendee_id}")
async def api_new_session(attendee_id: int):
    new_seq = db.create_new_session_for_attendee(attendee_id)
    db.set_active_attendee(attendee_id)
    return {"status": "success", "session_number": new_seq, "active": db.get_active_attendee()}

@app.get("/api/search")
async def api_search(q: str = ""):
    results = db.search_attendees(q, limit=25)
    return {"results": results}

@app.post("/api/walkin")
async def api_walkin(data: WalkInRequest):
    attendee = db.get_or_create_attendee(
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        organization=data.organization or "",
        title=data.title or "",
        phone=data.phone or "",
        source="walk_in"
    )
    # Set as active subject immediately
    db.set_active_attendee(attendee["id"])
    return {"status": "success", "attendee": attendee}

@app.post("/api/sync")
async def api_sync_google():
    synced, total, msg = forms_sync.fetch_and_sync()
    return {
        "status": "success" if synced >= 0 else "error",
        "synced": synced,
        "total": total,
        "message": msg,
        "stats": db.get_stats()
    }

@app.get("/api/stats")
async def api_stats():
    return db.get_stats()

@app.get("/api/outbox")
async def api_outbox():
    return {
        "pending": db.get_pending_deliveries(),
        "recent": db.get_recent_deliveries(limit=30)
    }

@app.post("/api/outbox/send-batch")
async def api_send_batch():
    pending = db.get_pending_deliveries()
    sent_count = 0
    failures = []
    
    for item in pending:
        attendee = db.get_attendee_by_id(item["attendee_id"])
        if attendee:
            success, msg = email_service.send_delivery_email(attendee)
            if success:
                db.update_delivery_status(item["id"], "SENT")
                sent_count += 1
            else:
                db.update_delivery_status(item["id"], "FAILED", error_message=msg)
                failures.append(f"{attendee.get('first_name')}: {msg}")

    return {
        "status": "success" if not failures else "partial",
        "sent_count": sent_count,
        "failed_count": len(failures),
        "failures": failures
    }

# --- Lightroom Plugin Delivery Endpoint ---

@app.post("/api/deliver")
async def api_deliver_from_lr(
    file: Optional[UploadFile] = File(None),
    file_path: Optional[str] = Form(None),
    attendee_id: Optional[int] = Form(None),
    attendee_email: Optional[str] = Form(None)
):
    """
    Lightroom plugin calls this endpoint to deliver a rendered keeper photo.
    """
    # 1. Resolve Attendee
    target_attendee = None
    if attendee_id:
        target_attendee = db.get_attendee_by_id(attendee_id)
    elif attendee_email:
        target_attendee = db.get_attendee_by_email(attendee_email)
    
    if not target_attendee:
        target_attendee = db.get_active_attendee()

    if not target_attendee:
        raise HTTPException(
            status_code=400, 
            detail="No active attendee selected in booth HUD, and no attendee ID provided."
        )

    # 2. Resolve File
    saved_path = None
    filename = "keeper.jpg"

    if file:
        filename = file.filename or "keeper.jpg"
        save_dir = config.ready_to_deliver_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        saved_path = save_dir / filename
        with open(saved_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    elif file_path:
        saved_path = Path(file_path)
        filename = saved_path.name

    if not saved_path or not saved_path.exists():
        raise HTTPException(status_code=400, detail=f"Image file not accessible at: {file_path}")

    # 3. Process delivery
    success, message = process_exported_photo(target_attendee["id"], saved_path, filename)
    
    # Reload attendee to return updated gallery URL
    updated_att = db.get_attendee_by_id(target_attendee["id"])
    
    return {
        "success": success,
        "message": message,
        "attendee_id": target_attendee["id"],
        "attendee_name": f"{target_attendee['first_name']} {target_attendee['last_name']}",
        "gallery_url": updated_att.get("zenfolio_gallery_url") if updated_att else ""
    }

# --- Email Template Endpoints ---

class TemplateUpdateRequest(BaseModel):
    content: str

@app.post("/api/templates/save")
async def api_save_template(data: TemplateUpdateRequest):
    email_service.save_template_content(data.content)
    return {"status": "success", "message": "Email template saved successfully."}

@app.post("/api/templates/preview")
async def api_preview_template(data: TemplateUpdateRequest):
    active = db.get_active_attendee() or {
        "first_name": "Jane",
        "last_name": "Smith",
        "organization": "Acme Global",
        "title": "Director of Communications",
        "email": "jane.smith@example.com",
        "zenfolio_gallery_url": "https://www.tannereli.com/p829497399"
    }
    subject, html = email_service.render_email(active, data.content)
    return {"subject": subject, "html": html}
