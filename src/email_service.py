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

    def render_email(self, attendee: Dict[str, Any], custom_template: Optional[str] = None) -> Tuple[str, str, str]:
        """
        Returns (subject, html_body, plain_text_body)
        Applies html.escape() to all dynamic variables and handles None/empty defaults gracefully.
        """
        import html

        first_name = (attendee.get("first_name") or "").strip() or "there"
        last_name = (attendee.get("last_name") or "").strip()
        org = (attendee.get("organization") or "").strip()
        title = (attendee.get("title") or "").strip()
        gallery_url = attendee.get("zenfolio_gallery_url") or "https://www.tannereli.com/headshots2026"
        event_name = config.event_name or "Conference Headshots"
        sender_name = config.gmail_config.get("sender_name", "Tanner Scholten Photography")

        template_str = custom_template or self.get_template_content()
        jinja_tpl = Template(template_str)
        
        ctx = {
            "first_name": html.escape(first_name),
            "last_name": html.escape(last_name),
            "full_name": html.escape(f"{first_name} {last_name}".strip()),
            "organization": html.escape(org),
            "title": html.escape(title),
            "gallery_url": gallery_url, # URL preserved for href
            "event_name": html.escape(event_name),
            "sender_name": html.escape(sender_name)
        }
        
        html_body = jinja_tpl.render(ctx)

        # Dynamic subject line: extract from <title> tag in template, or fallback to default
        import re
        title_match = re.search(r'<title>(.*?)</title>', template_str, re.IGNORECASE | re.DOTALL)
        if title_match and title_match.group(1).strip():
            raw_subj = title_match.group(1).strip()
            subject = Template(raw_subj).render(ctx)
        else:
            subject = f"Your Professional Headshots from {event_name}"

        # Clean plain-text fallback
        plain_text = f"""Hi {first_name},

Thank you for stopping by the headshot booth at {event_name}!

Your professional portraits have been calibrated and uploaded to your private online gallery.

View and download your headshots here:
{gallery_url}

Thesis Research:
https://new.express.adobe.com/webpage/Rgl6JSa7FZVnw/

My Photography:
https://www.tannereli.com/landscapes

Instagram:
https://www.instagram.com/TannerScholten

If you were pleased with my work, it would be very helpful to me as a small business if you could leave a quick review on my Google Maps listing:
https://maps.app.goo.gl/34xqcCANceTbRJHA6?g_st=ac

Best regards,
{sender_name}
www.tannereli.com
"""
        return subject, html_body, plain_text

    def send_delivery_email(self, attendee: Dict[str, Any], custom_template: Optional[str] = None) -> Tuple[bool, str]:
        gmail_cfg = config.gmail_config
        sender_email = gmail_cfg.get("sender_email")
        sender_name = gmail_cfg.get("sender_name", "Tanner Scholten Photography")
        app_password = gmail_cfg.get("app_password", "").replace(" ", "")
        recipient_email = (attendee.get("email") or "").strip()

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

        subject, html_content, plain_text = self.render_email(attendee, custom_template)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = recipient_email
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

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
        except smtplib.SMTPAuthenticationError:
            return False, "Gmail authentication failed. Verify your App Password in config.json."
        except smtplib.SMTPRecipientsRefused:
            return False, f"Recipient address rejected by Gmail: {recipient_email}"
        except (smtplib.SMTPException, OSError) as e:
            return False, f"SMTP Error sending to {recipient_email}: {str(e)}"

    def send_batch_emails(self, attendees: list, custom_template: Optional[str] = None) -> Tuple[int, list]:
        """
        Sends emails in a batch using a single persistent SMTP connection to avoid TLS renegotiation.
        """
        gmail_cfg = config.gmail_config
        sender_email = gmail_cfg.get("sender_email")
        sender_name = gmail_cfg.get("sender_name", "Tanner Scholten Photography")
        app_password = gmail_cfg.get("app_password", "").replace(" ", "")

        if not attendees:
            return 0, []

        sent_count = 0
        failures = []

        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP(gmail_cfg.get("smtp_server", "smtp.gmail.com"), int(gmail_cfg.get("smtp_port", 587)), timeout=20)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, app_password)

            for att in attendees:
                recipient_email = (att.get("email") or "").strip()
                if not recipient_email or "@" not in recipient_email:
                    failures.append((att.get("id"), f"Invalid email: '{recipient_email}'"))
                    continue

                # Rate limit spacing
                now = time.time()
                elapsed = now - self._last_send_time
                required_delay = config.email_rate_limit_seconds
                if elapsed < required_delay:
                    time.sleep(required_delay - elapsed)

                try:
                    subject, html_content, plain_text = self.render_email(att, custom_template)
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = subject
                    msg["From"] = f"{sender_name} <{sender_email}>"
                    msg["To"] = recipient_email
                    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
                    msg.attach(MIMEText(html_content, "html", "utf-8"))

                    server.sendmail(sender_email, recipient_email, msg.as_string())
                    self._last_send_time = time.time()
                    sent_count += 1
                except Exception as ex:
                    failures.append((att.get("id"), str(ex)))

            server.quit()
        except Exception as e:
            failures.append((None, f"Connection failure: {str(e)}"))

        return sent_count, failures

# Global instance
email_service = EmailService()
