"""
Unlimited free notifications: Gmail + Telegram + SMS + WhatsApp.
Import your details via: (1) notifications.json or (2) Vercel Environment Variables.
"""
import json
import os
import smtplib
import urllib.parse
import urllib.request
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

_NOTIFY_CONFIG = None


def _get_config():
    """Load notifications.json once (env vars override)."""
    global _NOTIFY_CONFIG
    if _NOTIFY_CONFIG is not None:
        return _NOTIFY_CONFIG
    try:
        path = Path(__file__).resolve().parent / "notifications.json"
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                _NOTIFY_CONFIG = json.load(f) or {}
        else:
            _NOTIFY_CONFIG = {}
    except Exception:
        _NOTIFY_CONFIG = {}
    return _NOTIFY_CONFIG


def _env(key, default=""):
    return os.environ.get(key, default).strip()


def _cfg(section, key, default=""):
    c = _get_config()
    val = (c.get(section) or {}).get(key)
    if val is None:
        return default
    return str(val).strip()


def _message_body(table, note=None):
    text = "Soulplace: Table %s requested help." % table
    if note:
        text += " Note: %s" % (note[:200] if len(note) > 200 else note)
    return text


# ----- 1. Gmail / Email -----
def send_email(body, to_emails=None):
    to_list = to_emails or [e.strip() for e in (_env("SOULPLACE_EMAIL_TO") or _cfg("email", "email_to", "")).split(",") if e.strip()]
    if not to_list:
        return False
    host = _env("SOULPLACE_SMTP_HOST") or _cfg("email", "smtp_host")
    user = _env("SOULPLACE_SMTP_USER") or _cfg("email", "smtp_user")
    password = _env("SOULPLACE_SMTP_PASSWORD") or _cfg("email", "smtp_password")
    from_addr = _env("SOULPLACE_EMAIL_FROM") or _cfg("email", "email_from") or user
    if not host or not user or not password:
        return False
    try:
        port = int(_env("SOULPLACE_SMTP_PORT") or _cfg("email", "smtp_port") or "587")
    except ValueError:
        port = 587
    use_tls = (_env("SOULPLACE_SMTP_TLS") or str(_cfg("email", "smtp_tls", "1"))).lower() in ("1", "true", "yes")
    msg = MIMEMultipart()
    msg["Subject"] = "Soulplace – Table help request"
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            if use_tls:
                s.starttls()
            s.login(user, password)
            s.sendmail(from_addr, to_list, msg.as_string())
        return True
    except Exception:
        return False


# ----- 2. SMS free (TextBelt) -----
def send_sms_free(body):
    to = _env("SOULPLACE_SMS_TO") or _cfg("sms", "to")
    if not to:
        return False
    to = "".join(c for c in to if c.isdigit() or c == "+")
    if len(to) < 10:
        return False
    try:
        data = urllib.parse.urlencode({"phone": to, "message": body, "key": "textbelt"}).encode()
        req = urllib.request.Request("https://textbelt.com/text", data=data, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200:
                return True
    except Exception:
        pass
    return False


# ----- 3a. WhatsApp free (CallMeBot) -----
def send_whatsapp_free(body):
    phone = _env("CALLMEBOT_WHATSAPP_PHONE") or _cfg("whatsapp", "phone")
    apikey = _env("CALLMEBOT_WHATSAPP_APIKEY") or _cfg("whatsapp", "apikey")
    if not phone or not apikey:
        return False
    phone = "".join(c for c in phone if c.isdigit() or c == "+")
    if len(phone) < 10:
        return False
    try:
        text_enc = urllib.parse.quote(body)
        url = "https://api.callmebot.com/whatsapp.php?phone=%s&text=%s&apikey=%s" % (phone, text_enc, urllib.parse.quote(apikey))
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200:
                return True
    except Exception:
        pass
    return False


# ----- 3b. WhatsApp free (WA Bridge – alternative when CallMeBot doesn't work) -----
def send_whatsapp_wabridge(body):
    """Send via wabridge.cloud – free, no business account. Register at https://wabridge.cloud"""
    api_key = _env("WABRIDGE_API_KEY") or _cfg("whatsapp", "wabridge_api_key")
    phone = _env("SOULPLACE_WHATSAPP_TO") or _cfg("whatsapp", "to") or _env("SOULPLACE_SMS_TO") or _cfg("sms", "to")
    if not api_key or not phone:
        return False
    phone = "".join(c for c in phone if c.isdigit())
    if len(phone) < 10:
        return False
    try:
        data = json.dumps({"phone": phone, "message": body}).encode("utf-8")
        req = urllib.request.Request(
            "https://wabridge.cloud/api/send/message",
            data=data,
            method="POST",
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200:
                out = r.read().decode("utf-8", errors="ignore")
                if "success" in out.lower() or "true" in out:
                    return True
    except Exception:
        pass
    return False


# ----- 3c. WhatsApp (Green API – free Developer plan, 3 chats) -----
def send_whatsapp_greenapi(body):
    """Send via Green API – free Developer plan at https://console.green-api.com"""
    id_instance = _env("GREEN_API_ID_INSTANCE") or _cfg("whatsapp", "green_api_id_instance")
    token = _env("GREEN_API_TOKEN") or _cfg("whatsapp", "green_api_token")
    phone = _env("SOULPLACE_WHATSAPP_TO") or _cfg("whatsapp", "to") or _env("SOULPLACE_SMS_TO") or _cfg("sms", "to")
    if not id_instance or not token or not phone:
        return False
    phone = "".join(c for c in phone if c.isdigit())
    if len(phone) < 10:
        return False
    chat_id = phone + "@c.us"
    base = (_env("GREEN_API_URL") or _cfg("whatsapp", "green_api_url") or "https://api.green-api.com").rstrip("/")
    try:
        url = "%s/waInstance%s/sendMessage/%s" % (base, id_instance, token)
        data = json.dumps({"chatId": chat_id, "message": body}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200:
                out = r.read().decode("utf-8", errors="ignore")
                if "idMessage" in out or "id" in out.lower():
                    return True
    except Exception:
        pass
    return False


# ----- 4. Telegram (unlimited free) -----
def send_telegram(body):
    token = _env("TELEGRAM_BOT_TOKEN") or _cfg("telegram", "bot_token")
    chat_id = _env("TELEGRAM_CHAT_ID") or _cfg("telegram", "chat_id")
    if not token or not chat_id:
        return False
    try:
        url = "https://api.telegram.org/bot%s/sendMessage" % token
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": body}).encode()
        req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                return True
    except Exception:
        pass
    return False


def notify_new_help_request(table, note=None):
    """Sends to all configured channels. Details from notifications.json or env vars."""
    body = _message_body(table, note)
    email_ok = send_email(body)
    telegram_ok = send_telegram(body)
    sms_ok = send_sms_free(body)
    wa_callme = send_whatsapp_free(body)
    wa_wabridge = send_whatsapp_wabridge(body)
    wa_green = send_whatsapp_greenapi(body)
    wa_ok = wa_callme or wa_wabridge or wa_green
    return email_ok or telegram_ok or sms_ok or wa_ok
