import smtplib
import time
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from jinja2 import Template
from src.config import config, PROJECT_ROOT

DEFAULT_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "email_template.html"

class EmailService:
    def __init__(self):
        self._last_send_time = 0.0

    def get_template_content(self) -> str:
        if DEFAULT_TEMPLATE_PATH.exists():
            with open(DEFAULT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
                return f.read()
        return """<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2>Your Professional Headshots are Ready!</h2>
    <p>Hi {{ first_name }},</p>
    <p>Thank you for stopping by the headshot booth at {{ event_name }}. Your photos have been professionally retouched and uploaded to your private gallery.</p>
    <div style="text-align: center; margin: 30px 0;">
        <a href="{{ gallery_url }}" style="background-color: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">View & Download Your Headshots</a>
    </div>
    <p>From your gallery, you can download full high-resolution copies for print or web-optimized sizes for LinkedIn and company directories.</p>
    <p style="margin-top: 30px;">Best regards,<br><strong>{{ sender_name }}</strong></p>
</body>
</html>"""

    def save_template_content(self, content: str) -> None:
        DEFAULT_TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DEFAULT_TEMPLATE_PATH, "w", encoding="utf-8") as f:
            f.write(content)

    def render_email(self, attendee: Dict[str, Any], custom_template: Optional[str] = None) -> Tuple[str, str]:
        """
        Returns (subject, html_body)
        """
        template_str = custom_template or self.get_template_content()
        jinja_tpl = Template(template_str)
        
        ctx = {
            "first_name": attendee.get("first_name", "there"),
            "last_name": attendee.get("last_name", ""),
            "full_name": f"{attendee.get('first_name', '')} {attendee.get('last_name', '')}".strip(),
            "organization": attendee.get("organization", ""),
            "title": attendee.get("title", ""),
            "gallery_url": attendee.get("zenfolio_gallery_url", "https://www.tannereli.com/headshots2026"),
            "event_name": config.event_name,
            "sender_name": config.gmail_config.get("sender_name", "Tanner Scholten Photography")
        }
        
        html_body = jinja_tpl.render(ctx)
        subject = f"Your Professional Headshots from {config.event_name}"
        return subject, html_body

    def send_delivery_email(self, attendee: Dict[str, Any], custom_template: Optional[str] = None) -> Tuple[bool, str]:
        gmail_cfg = config.gmail_config
        sender_email = gmail_cfg.get("sender_email")
        sender_name = gmail_cfg.get("sender_name", "Tanner Scholten Photography")
        app_password = gmail_cfg.get("app_password", "").replace(" ", "")
        recipient_email = attendee.get("email", "").strip()

        if not sender_email or not app_password:
            return False, "Gmail credentials not configured."
        if not recipient_email or "@" not in recipient_email:
            return False, f"Invalid recipient email: '{recipient_email}'"

        # Enforce rate-limit interval
        now = time.time()
        elapsed = now - self._last_send_time
        required_delay = config.email_rate_limit_seconds
        if elapsed < required_delay:
            time.sleep(required_delay - elapsed)

        subject, html_content = self.render_email(attendee, custom_template)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = recipient_email
        msg.attach(MIMEText(html_content, "html"))

        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP(gmail_cfg.get("smtp_server", "smtp.gmail.com"), int(gmail_cfg.get("smtp_port", 587)), timeout=15)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            server.quit()
            self._last_send_time = time.time()
            return True, f"Email sent successfully to {recipient_email}"
        except Exception as e:
            return False, f"SMTP Error sending to {recipient_email}: {str(e)}"

# Global instance
email_service = EmailService()
