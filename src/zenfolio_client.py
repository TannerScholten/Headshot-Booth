import json
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from src.config import config
from src import db

class ZenfolioClient:
    API_URL = "https://api.zenfolio.com/api/1.8/zfapi.asmx"

    def __init__(self):
        self.token: Optional[str] = None
        self._ctx = ssl.create_default_context()

    def _call(self, method: str, params: list) -> Any:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "HeadshotBooth/1.0"
        }
        if self.token:
            headers["X-Zenfolio-Token"] = self.token

        payload = {
            "method": method,
            "params": params,
            "id": 1
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.API_URL, data=data, headers=headers)
        
        with urllib.request.urlopen(req, context=self._ctx, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("error"):
                raise RuntimeError(f"Zenfolio API Error [{method}]: {body['error']}")
            return body.get("result")

    def authenticate(self) -> str:
        zf_cfg = config.zenfolio_config
        username = zf_cfg.get("username", "")
        password = zf_cfg.get("password", "")
        if not username or not password:
            raise ValueError("Zenfolio credentials missing from config.json")

        self.token = self._call("AuthenticatePlain", [username, password])
        return self.token

    def ensure_authenticated(self) -> None:
        if not self.token:
            self.authenticate()

    def resolve_master_group_id(self) -> int:
        zf_cfg = config.zenfolio_config
        group_id = zf_cfg.get("master_group_id")
        if group_id:
            return int(group_id)

        self.ensure_authenticated()
        master_url = zf_cfg.get("master_group_url", "")
        if not master_url:
            raise ValueError("Zenfolio master_group_url not configured")

        res = self._call("ResolveUrl", [master_url])
        if res and res.get("Group"):
            group_id = int(res["Group"]["Id"])
            # Save resolved ID back into config for speed
            config.data.setdefault("zenfolio", {})["master_group_id"] = group_id
            config.save()
            return group_id
        raise RuntimeError(f"Could not resolve Zenfolio group for URL: {master_url}")

    def get_or_create_attendee_gallery(self, attendee: Dict[str, Any]) -> Tuple[int, str, str]:
        """
        Returns (gallery_id, gallery_page_url, upload_url)
        Reuses existing gallery if attendee already has one.
        """
        # Check if already cached in attendee record
        if attendee.get("zenfolio_gallery_id") and attendee.get("zenfolio_gallery_url") and attendee.get("zenfolio_upload_url"):
            return (
                int(attendee["zenfolio_gallery_id"]),
                attendee["zenfolio_gallery_url"],
                attendee["zenfolio_upload_url"]
            )

        self.ensure_authenticated()
        parent_group_id = self.resolve_master_group_id()

        full_name = f"{attendee['first_name']} {attendee['last_name']}".strip()
        gallery_title = f"{full_name} - {attendee['id']}"
        caption = f"Complimentary Headshots for {full_name}"
        if attendee.get("organization"):
            caption += f" ({attendee['organization']})"

        updater = {
            "Title": gallery_title,
            "Caption": caption
        }

        photoset = self._call("CreatePhotoSet", [parent_group_id, "Gallery", updater])
        if not photoset or not photoset.get("Id"):
            raise RuntimeError(f"Failed to create Zenfolio gallery for {full_name}")

        gallery_id = int(photoset["Id"])
        page_url = photoset.get("PageUrl", "")
        upload_url = photoset.get("UploadUrl", "")

        # Persist in DB
        db.update_attendee_zenfolio(attendee["id"], gallery_id, page_url, upload_url)
        return gallery_id, page_url, upload_url

    def upload_photo(self, upload_url: str, file_path: Path, filename: str) -> Optional[int]:
        """
        Uploads an image file to the Zenfolio upload URL.
        Returns the new Zenfolio photo ID if available.
        """
        self.ensure_authenticated()
        if not file_path.exists():
            raise FileNotFoundError(f"Photo file not found: {file_path}")

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Zenfolio upload endpoint accepts binary body with file headers
        headers = {
            "User-Agent": "HeadshotBooth/1.0",
            "X-Zenfolio-Token": self.token,
            "X-Zenfolio-Filename": filename,
            "Content-Type": "image/jpeg",
            "Content-Length": str(len(file_bytes))
        }

        req = urllib.request.Request(upload_url, data=file_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, context=self._ctx, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            # Zenfolio upload response is XML/JSON with Photo ID
            try:
                data = json.loads(body)
                return data.get("Id") or data.get("result")
            except Exception:
                return None

# Global client
zenfolio = ZenfolioClient()
