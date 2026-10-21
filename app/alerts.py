"""Send alerts by email (optional).

Configure with GitHub repository secrets:
  SMTP_HOST, SMTP_PORT, SMTP_USER,
  SMTP_PASS, ALERT_EMAIL_TO        -> email (e.g. Gmail with an app password)
  DASHBOARD_URL (optional)         -> link included in each alert
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send(title: str, body: str) -> list[str]:
    sent = []
    url = os.environ.get("DASHBOARD_URL", "")
    if url:
        body = f"{body}\n\nDashboard: {url}"

    host, to = os.environ.get("SMTP_HOST", "").strip(), os.environ.get("ALERT_EMAIL_TO", "").strip()
    if host and to:
        try:
            msg = EmailMessage()
            msg["Subject"] = title
            msg["From"] = os.environ.get("SMTP_USER", "")
            msg["To"] = to
            msg.set_content(body)
            with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=20) as s:
                s.starttls()
                s.login(os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASS", ""))
                s.send_message(msg)
            sent.append("email")
        except Exception as e:
            print(f"email failed: {e}")

    if not sent:
        print(f"[alert not sent — email not configured]\n{title}\n{body}")
    return sent
