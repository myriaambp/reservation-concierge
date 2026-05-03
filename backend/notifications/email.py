"""Email notifications — multi-provider, fail-soft.

Tries providers in order:
  1. Resend (RESEND_API_KEY) — recommended; 30s signup at resend.com
  2. Gmail SMTP (GMAIL_USER + GMAIL_APP_PASSWORD) — works with your own gmail;
     requires 2FA + App Password from https://myaccount.google.com/apppasswords
  3. Console — logs to stdout; fine for dev when no provider is configured.

Never raises on send failure — emails are best-effort. The in-app notification
record always succeeds.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal

import httpx


@dataclass
class EmailResult:
    ok: bool
    provider: str
    detail: str = ""


def _send_resend(to: str, subject: str, html: str, text: str) -> EmailResult:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        return EmailResult(False, "resend", "RESEND_API_KEY not set")
    sender = os.getenv("RESEND_FROM", "Tableau <onboarding@resend.dev>")
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": sender,
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text,
            },
            timeout=15,
        )
        if r.status_code >= 400:
            return EmailResult(False, "resend", f"{r.status_code}: {r.text[:160]}")
        return EmailResult(True, "resend", r.json().get("id", ""))
    except Exception as e:
        return EmailResult(False, "resend", f"{type(e).__name__}: {e}")


def _send_gmail_smtp(to: str, subject: str, html: str, text: str) -> EmailResult:
    user = os.getenv("GMAIL_USER", "").strip()
    pwd = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if not (user and pwd):
        return EmailResult(False, "gmail", "GMAIL_USER or GMAIL_APP_PASSWORD not set")
    msg = EmailMessage()
    msg["From"] = f"Tableau Concierge <{user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=15) as s:
            s.login(user, pwd)
            s.send_message(msg)
        return EmailResult(True, "gmail", "")
    except Exception as e:
        return EmailResult(False, "gmail", f"{type(e).__name__}: {e}")


def _send_console(to: str, subject: str, html: str, text: str) -> EmailResult:
    print(f"\n--- EMAIL (console fallback) ---")
    print(f"To:      {to}")
    print(f"Subject: {subject}")
    print(f"Body:    {text}")
    print(f"--- /EMAIL ---\n")
    return EmailResult(True, "console", "logged-only")


def _wrap_html(subject: str, body: str, slot_url: str | None = None) -> str:
    cta_html = (
        f'<a href="{slot_url}" style="display:inline-block;background:#1a1a1a;color:#f5f1e8;padding:12px 22px;border-radius:6px;text-decoration:none;font-family:Inter,sans-serif;font-size:14px;font-weight:500;letter-spacing:0.02em;margin-top:18px">Open Tableau →</a>'
        if slot_url
        else ""
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;background:#f5f1e8;font-family:'Inter',-apple-system,sans-serif;color:#1a1a1a">
  <div style="max-width:560px;margin:24px auto;background:#fff;border:1px solid #e8e2d4;border-radius:10px;overflow:hidden">
    <div style="background:linear-gradient(135deg,#1a1a1a 0%,#2d1810 100%);color:#f5f1e8;padding:24px 28px">
      <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:28px;line-height:1;letter-spacing:-0.01em">Tableau</div>
      <div style="opacity:0.7;font-size:12px;margin-top:4px;letter-spacing:0.06em;text-transform:uppercase">Reservation Concierge</div>
    </div>
    <div style="padding:28px">
      <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:24px;line-height:1.2;margin-bottom:14px;color:#1a1a1a">{subject}</div>
      <div style="font-size:15px;line-height:1.55;color:#2d1810">{body}</div>
      {cta_html}
    </div>
    <div style="padding:16px 28px;background:#f5f1e8;border-top:1px solid #e8e2d4;font-size:11px;color:#6b6453">
      You set up a watch on Tableau. Manage notifications in Settings.
    </div>
  </div>
</body></html>"""


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    slot_url: str | None = None,
) -> EmailResult:
    """Send an email best-effort. Returns success state + provider used."""
    if not to or "@" not in to:
        return EmailResult(False, "skip", "no recipient email")

    html = _wrap_html(subject, body, slot_url=slot_url)

    for provider_fn in (_send_resend, _send_gmail_smtp):
        res = provider_fn(to, subject, html, body)
        if res.ok:
            return res
    # All providers failed or unconfigured — console fallback.
    return _send_console(to, subject, html, body)
