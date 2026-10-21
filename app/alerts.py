"""Send alerts by phone push (ntfy.sh) and/or email. Both are optional.

Configure with GitHub repository secrets:
  NTFY_TOPIC                       -> free push notifications via the ntfy app
  SMTP_HOST, SMTP_PORT, SMTP_USER,
  SMTP_PASS, ALERT_EMAIL_TO        -> email (e.g. Gmail with an app password)
  DASHBOARD_URL (optional)         -> link included in each alert
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send(title: str, body: str, priority: str = "default") -> list[str]:
    sent = []
    url = os.environ.get("DASHBOARD_URL", "")
    if url:
        body = f"{body}\n\nDashboard: {url}"

    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if topic:
        try:
            import requests
            headers = {"Title": title.encode("ascii", "ignore").decode(), "Priority": priority, "Tags": "rocket"}
            if url:
                headers["Click"] = url
            r = requests.post(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), headers=headers, timeout=15)
            r.raise_for_status()
            sent.append("push")
        except Exception as e:
            print(f"push failed: {e}")

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
        print(f"[alert not sent — no channels configured]\n{title}\n{body}")
    return sent
