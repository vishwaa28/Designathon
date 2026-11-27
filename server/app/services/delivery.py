"""Outbound traveler notifications: e-mail through Twilio SendGrid or SMTP, and SMS through Twilio or Fast2SMS.

Only passengers flagged as contacts (real address and number) are sent anything; every other
notification in the simulation is recorded but not transmitted.
"""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor, wait
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx

from app.config import settings
from app.core.utils import iso, now
from app.data import db

log = logging.getLogger("arro.delivery")
executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="delivery")
_record_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="delivery-record")
TIMEOUT_S = 20
HELP_DESK = "1800 200 4040"


def _sms_provider() -> str | None:
    p = settings.sms_provider
    if p in ("twilio", "fast2sms"):
        return p
    if settings.twilio_account_sid and settings.twilio_auth_token and (settings.twilio_from or settings.twilio_messaging_service_sid):
        return "twilio"
    if settings.fast2sms_api_key:
        return "fast2sms"
    return None


def _email_provider() -> str | None:
    p = settings.email_provider
    if p in ("sendgrid", "smtp"):
        return p
    if settings.sendgrid_api_key and settings.sendgrid_from:
        return "sendgrid"
    if settings.smtp_host and settings.smtp_from:
        return "smtp"
    return None


def email_configured() -> bool:
    p = _email_provider()
    if p == "sendgrid":
        return bool(settings.sendgrid_api_key and settings.sendgrid_from)
    return p == "smtp" and bool(settings.smtp_host and settings.smtp_from)


def sms_configured() -> bool:
    p = _sms_provider()
    if p == "twilio":
        return bool(settings.twilio_account_sid and settings.twilio_auth_token
                    and (settings.twilio_from or settings.twilio_messaging_service_sid))
    return p == "fast2sms" and bool(settings.fast2sms_api_key)


def status() -> dict:
    return {
        "email": {"configured": email_configured(),
                  "provider": "SendGrid" if _email_provider() == "sendgrid" else "SMTP",
                  "sender": settings.sendgrid_from if _email_provider() == "sendgrid" else settings.smtp_from},
        "sms": {"configured": sms_configured(), "provider": (_sms_provider() or "none").title()},
    }


def mask_email(addr: str) -> str:
    user, _, domain = addr.partition("@")
    return f"{user[:3]}{'*' * max(1, len(user) - 3)}@{domain}"


def mask_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    return f"+91 {digits[:2]}xxxxx{digits[-3:]}" if len(digits) == 10 else phone


def _result(channel: str, to: str, status_: str, detail: str = "", provider: str | None = None) -> dict:
    return {"channel": channel, "to": to, "status": status_, "detail": detail[:240], "provider": provider,
            "at": iso(now())}


def _email_html(subject: str, message: str, details: list[tuple[str, str]], link: str | None,
                english: str | None) -> str:
    rows = "".join(
        f'<tr><td style="padding:6px 0;color:#64748b;font-size:13px;width:130px">{html.escape(k)}</td>'
        f'<td style="padding:6px 0;color:#0f172a;font-size:13px;font-weight:600">{html.escape(v)}</td></tr>'
        for k, v in details if v)
    button = (f'<a href="{html.escape(link)}" style="display:inline-block;background:#1d4ed8;color:#ffffff;'
              f'text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:600;font-size:14px">'
              f'Manage my trip</a>') if link else ""
    extra = (f'<p style="margin:16px 0 0;color:#475569;font-size:13px;line-height:1.6">'
             f'<strong>English:</strong> {html.escape(english)}</p>') if english else ""
    return f"""<!doctype html>
<html><body style="margin:0;background:#f1f5f9;font-family:Segoe UI,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:14px;overflow:hidden">
<tr><td style="background:#0b1f3a;padding:20px 24px;color:#ffffff">
<div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#93c5fd">Meridian Airways</div>
<div style="font-size:20px;font-weight:700;margin-top:4px">{html.escape(subject)}</div>
</td></tr>
<tr><td style="padding:24px">
<p style="margin:0;color:#0f172a;font-size:15px;line-height:1.65">{html.escape(message)}</p>
{extra}
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:20px 0;width:100%;border-top:1px solid #e2e8f0;padding-top:8px">{rows}</table>
{button}
</td></tr>
<tr><td style="padding:16px 24px;background:#f8fafc;color:#64748b;font-size:12px;line-height:1.5">
Need help? Call our help desk on {HELP_DESK} (24x7). This message was sent by the Chennai operations control centre.
</td></tr>
</table></td></tr></table></body></html>"""


def _send_smtp(to: str, subject: str, text: str, html_body: str) -> str:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.smtp_from_name, settings.smtp_from))
    msg["To"] = to
    msg["Message-ID"] = make_msgid(domain=settings.smtp_from.partition("@")[2] or None)
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_S, context=context)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_S)
        server.starttls(context=context)
    with server:
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    return f"via {settings.smtp_host}"


def _send_sendgrid(to: str, subject: str, text: str, html_body: str) -> str:
    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.sendgrid_from, "name": settings.sendgrid_from_name},
        "subject": subject,
        "content": [{"type": "text/plain", "value": text}, {"type": "text/html", "value": html_body}],
    }
    resp = httpx.post("https://api.sendgrid.com/v3/mail/send", json=payload, timeout=TIMEOUT_S,
                      headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"})
    if resp.status_code in (200, 201, 202):
        return f"SendGrid accepted {resp.headers.get('x-message-id', '')}".strip()
    try:
        errors = resp.json().get("errors") or []
        detail = "; ".join(e.get("message", "") for e in errors) or resp.text[:160]
    except ValueError:
        detail = resp.text[:160]
    raise RuntimeError(f"SendGrid {resp.status_code}: {detail}")


def send_email(to: str, subject: str, text: str, html_body: str) -> dict:
    masked = mask_email(to)
    provider = _email_provider()
    if not email_configured():
        return _result("EMAIL", masked, "NOT_CONFIGURED",
                       "Set SENDGRID_API_KEY and SENDGRID_FROM (or the SMTP_* settings)")
    label = "SendGrid" if provider == "sendgrid" else "SMTP"
    try:
        detail = (_send_sendgrid if provider == "sendgrid" else _send_smtp)(to, subject, text, html_body)
        return _result("EMAIL", masked, "SENT", detail, label)
    except Exception as exc:  # noqa: BLE001
        log.warning("E-mail to %s failed: %s", masked, exc)
        return _result("EMAIL", masked, "FAILED", f"{type(exc).__name__}: {exc}", label)

def _send_twilio(phone: str, text: str) -> tuple[bool, str]:
    data = {"To": phone, "Body": text}
    if settings.twilio_messaging_service_sid:
        data["MessagingServiceSid"] = settings.twilio_messaging_service_sid
    else:
        data["From"] = settings.twilio_from
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    resp = httpx.post(url, data=data, auth=(settings.twilio_account_sid, settings.twilio_auth_token), timeout=TIMEOUT_S)
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code in (200, 201):
        return True, f"Twilio {body.get('sid', '')} {body.get('status', '')}".strip()
    return False, f"Twilio {resp.status_code}: {body.get('message') or resp.text[:160]}"


def _send_fast2sms(phone: str, text: str) -> tuple[bool, str]:
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    payload = {"route": "q", "message": text, "numbers": digits, "flash": "0",
               "language": "english" if text.isascii() else "unicode"}
    resp = httpx.post("https://www.fast2sms.com/dev/bulkV2", data=payload,
                      headers={"authorization": settings.fast2sms_api_key}, timeout=TIMEOUT_S)
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code == 200 and body.get("return"):
        return True, f"Fast2SMS {body.get('request_id', '')}".strip()
    msg = body.get("message")
    return False, f"Fast2SMS {resp.status_code}: {msg if isinstance(msg, str) else msg or resp.text[:160]}"


def send_sms(phone: str, text: str) -> dict:
    masked = mask_phone(phone)
    if not sms_configured():
        return _result("SMS", masked, "NOT_CONFIGURED",
                       "Set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM or FAST2SMS_API_KEY")
    try:
        ok, detail = (_send_twilio if _sms_provider() == "twilio" else _send_fast2sms)(phone, text)
    except Exception as exc:  # noqa: BLE001
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    if not ok:
        log.warning("SMS to %s failed: %s", masked, detail)
    return _result("SMS", masked, "SENT" if ok else "FAILED", detail, (_sms_provider() or "").title() or None)


def _sms_text(record: dict) -> str:
    text = record["message"]
    if record.get("self_service_url") and record["self_service_url"] not in text:
        text = f"{text} {record['self_service_url']}"
    return f"Meridian: {text}"


def deliver(record: dict, passenger: dict, english: str | None = None) -> list[dict]:
    """Send one notification record by e-mail and SMS. Blocks until both attempts finish."""
    details = [("Passenger", record["name"]), ("Booking ref", record["pnr"]),
               ("Original service", record.get("trip") or ""), ("New service", record.get("new_trip") or "")]
    html_body = _email_html(record["subject"], record["message"], details, record.get("self_service_url"), english)
    text = record["message"] + (f"\n\nEnglish: {english}" if english else "")
    if record.get("self_service_url"):
        text += f"\n\nManage your trip: {record['self_service_url']}"
    text += f"\n\nHelp desk: {HELP_DESK}"
    jobs = []
    if passenger.get("email"):
        jobs.append(executor.submit(send_email, passenger["email"], f"{record['subject']} - {record['pnr']}", text, html_body))
    if passenger.get("phone"):
        jobs.append(executor.submit(send_sms, passenger["phone"], _sms_text(record)))
    done, _ = wait(jobs, timeout=TIMEOUT_S + 5)
    results = [j.result() for j in jobs if j in done]
    record["deliveries"] = results
    record["status"] = _overall(results)
    db.log_delivery(record, results)
    return results


def dispatch(record: dict, passenger: dict, english: str | None = None) -> None:
    """Fire-and-forget delivery for long-lived contexts such as the voice session."""
    _record_pool.submit(deliver, record, dict(passenger), english)


def _overall(results: list[dict]) -> str:
    sent = sum(1 for r in results if r["status"] == "SENT")
    if sent and sent == len(results):
        return "SENT"
    if sent:
        return "PARTIAL"
    if results and all(r["status"] == "NOT_CONFIGURED" for r in results):
        return "NOT_CONFIGURED"
    return "FAILED"


def deliver_many(items: list[tuple[dict, dict, str | None]]) -> dict:
    """Deliver several records in parallel; returns channel counts for the run summary."""
    jobs = [_record_pool.submit(deliver, rec, pax, english) for rec, pax, english in items]
    wait(jobs, timeout=TIMEOUT_S * 2)
    counts = {"email_sent": 0, "sms_sent": 0, "failed": 0, "not_configured": 0, "recipients": len(items)}
    for rec, _, _ in items:
        for r in rec.get("deliveries", []):
            if r["status"] == "SENT":
                counts["email_sent" if r["channel"] == "EMAIL" else "sms_sent"] += 1
            elif r["status"] == "FAILED":
                counts["failed"] += 1
            else:
                counts["not_configured"] += 1
    return counts
