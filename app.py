"""
Soulplace Boardgames Help Desk
Flask backend: login (admins + staff), dashboard, help requests, QR codes, API token.
"""
import csv
import hashlib
import io
import json
import logging
import os

# Load .env so Gmail, Telegram, SMS, WhatsApp vars work when running locally
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass
import re
import secrets
import socket
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import qrcode
from flask import Flask, Blueprint, Response, render_template, request, redirect, url_for, session, jsonify, make_response, g

try:
    import pyotp
except ImportError:
    pyotp = None

try:
    import soulplace_enhancements as spx
except ImportError:
    spx = None
try:
    import soulplace_features_catalog as sfc
except ImportError:
    sfc = None
try:
    import soulplace_100_registry as sreg
except ImportError:
    sreg = None

app = Flask(__name__)
app.secret_key = os.environ.get("SOULPLACE_SECRET_KEY", "soulplace-help-desk-secret-key-change-in-production")

# Log errors to console (PowerShell/terminal) when running locally
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
app.logger.setLevel(logging.INFO)
# Session cookie: work on Vercel so /soulplace/dashboard stays logged in
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
if os.environ.get("VERCEL"):
    app.config["SESSION_COOKIE_SECURE"] = True

# URL prefix so you get links like https://your-app.vercel.app/soulplace (same style as .../game-guru)
URL_PREFIX = os.environ.get("SOULPLACE_URL_PREFIX", "/soulplace").rstrip("/") or ""
bp = Blueprint("main", __name__, url_prefix=URL_PREFIX)

# Storage: Vercel uses /tmp; local uses project dir so it works when you run it.
DATA_FILE = (
    Path("/tmp/soulplace_data.json")
    if os.environ.get("VERCEL")
    else Path(__file__).parent / "data.json"
)

# Config file for tables and users – edit config.json and redeploy to change
CONFIG_FILE = Path(__file__).parent / "config.json"
# Default public URL when deployed on Vercel (QR codes & links use this).
# Replace with YOUR Vercel project URL (e.g. https://your-project.vercel.app) – see MY_LINKS.txt
# Use your actual Vercel URL so /links and QR codes work. If you use soulplace-help-desk (no kappa), redeploy from Vercel.
DEFAULT_PUBLIC_URL = "https://soulplace-help-desk-kappa.vercel.app"

# Default config if file missing (same as original hardcoded values)
DEFAULT_CONFIG = {
    "num_tables": 10,
    "admins": [
        {"name": "ASHOK", "password": "Ashok123"},
        {"name": "BOO", "password": "SoulOfBlack#7"},
    ],
    "staff": [
        {"name": "BALA MURUGAN", "password": "DarkSoul@7"},
        {"name": "RAJESH", "password": "BlueSoul!92"},
        {"name": "RITHISH", "password": "SilentSoul#66"},
        {"name": "LOKESH", "password": "CyberSoul@501"},
        {"name": "DILLI BABU", "password": "SoulWave#309"},
    ],
}

# Dynamic: loaded from config (see load_config())
USER_DB = {}
NUM_TABLES = 10
APP_CONFIG = {}  # guest_wifi_hint, table_images, table_zones, default_location_id, billing_url (from config.json)

# In-memory state (loaded/saved from data.json as usual)
help_requests = []
accepted_requests = []
api_token = None
request_history = []  # For analytics: never cleared by "clear all"
requests_paused = False  # Quiet hours: when True, new requests are rejected
password_overrides = {}  # Runtime password overrides (username -> new password), saved in data.json
push_subscriptions = []  # Web Push subscriptions (for notifications when screen is off); saved in data.json
last_push_debug = {}  # last push send diagnostics for quick troubleshooting in dashboard
customer_feedback = []  # {at, table, rating, comment, request_id}
staff_presence = {}  # username -> {mode: online|break|offline, updated_at}
activity_log = []  # {at, by, display, action, table, request_id} staff audit trail
incident_log = []  # {at, by, message, severity} ops notes; last N in data.json
cafe_menu_groups = None  # list of {label, options: [{value, text}]}; persisted in data.json
_rate_limit_store = {}  # "ip:table" -> last unix time (best-effort per server instance)
_idempotency_create = {}  # idempotency key -> (expires_unix, response_dict)
shift_handoff_note = ""  # One line for next shift; persisted in data.json
admin_totp_secrets = {}  # username (lower) -> base32 secret; persisted in data.json
totp_enroll_pending = {}  # username (lower) -> base32 secret until user confirms with app code
_login_burst_times = {}  # ip -> [unix times] for POST /login rate limit
LOGIN_BURST_WINDOW_SEC = int(os.environ.get("SOULPLACE_LOGIN_BURST_WINDOW_SEC", "120"))
LOGIN_BURST_MAX = int(os.environ.get("SOULPLACE_LOGIN_BURST_MAX", "30"))

# Rate limit for POST /api/request/create (seconds between requests per IP+table)
RATE_LIMIT_SECONDS = int(os.environ.get("SOULPLACE_RATE_LIMIT_SECONDS", "45"))
ACTIVITY_LOG_MAX = 500
INCIDENT_LOG_MAX = 80


def load_config():
    """Load num_tables, admins, staff from env, data.json, config.json, or defaults. Updates USER_DB and NUM_TABLES."""
    global USER_DB, NUM_TABLES, APP_CONFIG
    config = None
    # 1) Env override (JSON string) for Vercel / serverless
    env_json = os.environ.get("SOULPLACE_CONFIG_JSON", "").strip()
    if env_json:
        try:
            config = json.loads(env_json)
        except json.JSONDecodeError:
            pass
    # 2) config.json file (source of truth – edit this file and redeploy to change users/tables)
    if config is None and CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    if not config or not isinstance(config, dict):
        config = DEFAULT_CONFIG.copy()
    num_tables = config.get("num_tables")
    if isinstance(num_tables, int) and 1 <= num_tables <= 999:
        NUM_TABLES = num_tables
    else:
        NUM_TABLES = DEFAULT_CONFIG["num_tables"]
    admins = config.get("admins") or []
    staff = config.get("staff") or []
    if not isinstance(admins, list):
        admins = []
    if not isinstance(staff, list):
        staff = []
    USER_DB = {}
    for u in admins:
        if isinstance(u, dict) and u.get("name") and u.get("password"):
            key = str(u["name"]).strip().lower()
            pwd = str(u["password"]).strip()
            r = str(u.get("role") or "admin").strip().lower()
            if r not in ("admin", "manager"):
                r = "admin"
            USER_DB[key] = {
                "password": pwd,
                "display_name": str(u["name"]).strip(),
                "role": r,
            }
    for u in staff:
        if isinstance(u, dict) and u.get("name") and u.get("password"):
            key = str(u["name"]).strip().lower()
            if key not in USER_DB:
                pwd = str(u["password"]).strip()
                r = str(u.get("role") or "staff").strip().lower()
                if r not in ("staff", "manager"):
                    r = "staff"
                USER_DB[key] = {
                    "password": pwd,
                    "display_name": str(u["name"]).strip(),
                    "role": r,
                }
    # If no users loaded (e.g. broken config), ensure admins + staff from defaults
    if not USER_DB:
        for u in DEFAULT_CONFIG.get("admins") or []:
            if isinstance(u, dict) and u.get("name") and u.get("password"):
                key = str(u["name"]).strip().lower()
                pwd = str(u["password"]).strip()
                r = str(u.get("role") or "admin").strip().lower()
                if r not in ("admin", "manager"):
                    r = "admin"
                USER_DB[key] = {
                    "password": pwd,
                    "display_name": str(u["name"]).strip(),
                    "role": r,
                }
        for u in DEFAULT_CONFIG.get("staff") or []:
            if isinstance(u, dict) and u.get("name") and u.get("password"):
                key = str(u["name"]).strip().lower()
                if key not in USER_DB:
                    pwd = str(u["password"]).strip()
                    r = str(u.get("role") or "staff").strip().lower()
                    if r not in ("staff", "manager"):
                        r = "staff"
                    USER_DB[key] = {
                        "password": pwd,
                        "display_name": str(u["name"]).strip(),
                        "role": r,
                    }
    qr_cfg = config.get("qr_promo") if isinstance(config.get("qr_promo"), dict) else {}
    img_rel = str(qr_cfg.get("image") or "images/promo/qr-promo.png").strip().lstrip("/")
    img_path = Path(__file__).resolve().parent / "static" / img_rel.replace("/", os.sep)
    ext_url = str(qr_cfg.get("url") or "").strip()
    promo_wanted = bool(qr_cfg.get("enabled", True))
    if ext_url:
        promo_show = promo_wanted
    else:
        promo_show = promo_wanted and img_path.is_file()
    env_bill = os.environ.get("SOULPLACE_BILLING_URL", "").strip()
    cfg_bill = str(config.get("billing_url") or "").strip()
    raw_bill = env_bill or cfg_bill
    billing_portal = ""
    if raw_bill:
        billing_portal = raw_bill if raw_bill.startswith(("http://", "https://")) else "https://" + raw_bill.lstrip("/")

    sp_cfg = config.get("slot_pricing") if isinstance(config.get("slot_pricing"), dict) else {}
    slot_weekday = str(sp_cfg.get("weekday") or "₹99 per head/hour at weekdays").strip()[:240]
    slot_weekend = str(sp_cfg.get("weekend") or "₹129 per head/hour at weekend").strip()[:240]

    pm = config.get("payment_methods") if isinstance(config.get("payment_methods"), dict) else {}
    upi = pm.get("upi") if isinstance(pm.get("upi"), dict) else {}
    cash = pm.get("cash") if isinstance(pm.get("cash"), dict) else {}
    card = pm.get("card") if isinstance(pm.get("card"), dict) else {}
    payment_methods = {
        "intro": str(pm.get("intro") or "You can pay using UPI, cash, or card at Soulplace.").strip()[:500],
        "upi": {
            "enabled": upi.get("enabled", True) is not False,
            "id": str(upi.get("id") or "").strip()[:120],
            "note": str(upi.get("note") or "Use GPay, PhonePe, Paytm, or any UPI app. Ask staff for the exact amount.").strip()[:500],
        },
        "cash": {
            "enabled": cash.get("enabled", True) is not False,
            "note": str(cash.get("note") or "Cash is accepted at the counter before or after your slot.").strip()[:500],
        },
        "card": {
            "enabled": card.get("enabled", True) is not False,
            "note": str(card.get("note") or "Debit and credit cards accepted at the counter (RuPay, Visa, Mastercard).").strip()[:500],
        },
    }

    APP_CONFIG = {
        "guest_wifi_hint": str(config.get("guest_wifi_hint") or "").strip()[:500],
        "table_images": config.get("table_images") if isinstance(config.get("table_images"), dict) else {},
        "table_zones": config.get("table_zones") if isinstance(config.get("table_zones"), dict) else {},
        "default_location_id": str(config.get("default_location_id") or "default")[:64],
        "billing_url": billing_portal,
        "slot_pricing": {"weekday": slot_weekday, "weekend": slot_weekend},
        "payment_methods": payment_methods,
        "qr_promo": {
            "show": promo_show,
            "image_static": img_rel if promo_show and not ext_url else None,
            "image_url": ext_url if promo_show and ext_url else None,
            "once_per_session": bool(qr_cfg.get("once_per_session", True)),
        },
    }


def _default_cafe_menu_from_file():
    """Load default café menu JSON (groups + options for table page)."""
    path = Path(__file__).parent / "static" / "cafe_menu_default.json"
    try:
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                g = data.get("groups")
                if isinstance(g, list) and g:
                    return g
    except (json.JSONDecodeError, IOError, TypeError):
        pass
    return [{"label": "Other help", "options": [{"value": "Need explanation of rules", "text": "Need explanation of rules"}]}]


def load_data():
    """Load help_requests, accepted_requests, api_token, request_history, requests_paused, password_overrides, push_subscriptions from data.json."""
    global help_requests, accepted_requests, api_token, request_history, requests_paused, password_overrides, push_subscriptions
    global activity_log, incident_log, cafe_menu_groups, customer_feedback, staff_presence
    global shift_handoff_note, admin_totp_secrets, totp_enroll_pending
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                help_requests[:] = data.get("help_requests", [])
                accepted_requests[:] = data.get("accepted_requests", [])
                api_token = data.get("api_token") or os.environ.get("SOULPLACE_API_TOKEN")
                request_history[:] = data.get("request_history", [])
                keep_hist = int(os.environ.get("SOULPLACE_HISTORY_KEEP_DAYS", "0") or "0")
                if spx and keep_hist > 0:
                    request_history[:] = spx.truncate_old_history_rows(request_history, keep_hist)
                requests_paused = bool(data.get("requests_paused", False))
                password_overrides.clear()
                password_overrides.update(data.get("password_overrides") or {})
                push_subscriptions[:] = data.get("push_subscriptions", [])
                activity_log[:] = (data.get("activity_log") or [])[-ACTIVITY_LOG_MAX:]
                incident_log[:] = (data.get("incident_log") or [])[-INCIDENT_LOG_MAX:]
                customer_feedback[:] = (data.get("customer_feedback") or [])[-1000:]
                staff_presence.clear()
                raw_presence = data.get("staff_presence") or {}
                if isinstance(raw_presence, dict):
                    for k, v in raw_presence.items():
                        if isinstance(k, str) and isinstance(v, dict):
                            staff_presence[k] = {
                                "mode": str(v.get("mode") or "offline"),
                                "updated_at": str(v.get("updated_at") or _utc_iso_now()),
                            }
                raw_menu = data.get("cafe_menu_groups")
                if isinstance(raw_menu, list) and len(raw_menu) > 0:
                    cafe_menu_groups = raw_menu
                else:
                    cafe_menu_groups = None
                shift_handoff_note = str(data.get("shift_handoff_note") or "")[-4000:]
                admin_totp_secrets.clear()
                raw_totp = data.get("admin_totp_secrets")
                if isinstance(raw_totp, dict):
                    for k, v in raw_totp.items():
                        if isinstance(k, str) and isinstance(v, str) and v.strip():
                            admin_totp_secrets[k.strip().lower()] = v.strip()
                totp_enroll_pending.clear()
                raw_pend = data.get("totp_enroll_pending")
                if isinstance(raw_pend, dict):
                    for k, v in raw_pend.items():
                        if isinstance(k, str) and isinstance(v, str) and v.strip():
                            totp_enroll_pending[k.strip().lower()] = v.strip()
        except (json.JSONDecodeError, IOError):
            pass
    if api_token is None:
        api_token = os.environ.get("SOULPLACE_API_TOKEN") or secrets.token_urlsafe(32)
        save_data()
    if cafe_menu_groups is None:
        cafe_menu_groups = _default_cafe_menu_from_file()
    # Apply password overrides to USER_DB (load_config already ran in before_request)
    for uname, pwd in (password_overrides or {}).items():
        if uname and pwd and isinstance(uname, str) and isinstance(pwd, str):
            key = uname.strip().lower()
            if key in USER_DB:
                USER_DB[key]["password"] = pwd.strip()


def save_data():
    """Save help_requests, accepted_requests, api_token, request_history, requests_paused, password_overrides to data.json."""
    try:
        if not os.environ.get("VERCEL"):
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "help_requests": help_requests,
            "accepted_requests": accepted_requests,
            "request_history": request_history,
            "requests_paused": requests_paused,
            "password_overrides": password_overrides,
            "push_subscriptions": push_subscriptions,
            "activity_log": activity_log[-ACTIVITY_LOG_MAX:],
            "incident_log": incident_log[-INCIDENT_LOG_MAX:],
            "customer_feedback": customer_feedback[-1000:],
            "staff_presence": staff_presence,
            "cafe_menu_groups": cafe_menu_groups,
            "shift_handoff_note": shift_handoff_note,
            "admin_totp_secrets": admin_totp_secrets,
            "totp_enroll_pending": totp_enroll_pending,
        }
        if api_token is not None and not os.environ.get("SOULPLACE_API_TOKEN"):
            payload["api_token"] = api_token
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass  # Don't crash on Vercel if /tmp write fails


# Chennai (IST) = UTC+5:30
CHENNAI_TZ = timezone(timedelta(hours=5, minutes=30))


def _utc_iso_now():
    """Current time in UTC as ISO string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_raised_at(iso_or_legacy):
    """Parse raised_at to UTC datetime. Returns None if unparseable."""
    if not iso_or_legacy:
        return None
    s = str(iso_or_legacy).strip()
    if "T" in s:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return None


# Only show pending requests from the last N minutes (so refresh doesn't show very old ones)
PENDING_REQUEST_MAX_AGE_MINUTES = int(os.environ.get("SOULPLACE_PENDING_MAX_AGE_MINUTES", "120"))


def _client_ip():
    """Best-effort client IP (Vercel forwards X-Forwarded-For)."""
    xff = request.headers.get("X-Forwarded-For") or ""
    if xff:
        return xff.split(",")[0].strip()
    return (request.remote_addr or "").strip() or "0.0.0.0"


def _session_role():
    return (session.get("role") or "").strip().lower()


def _admin_or_manager():
    return _session_role() in ("admin", "manager")


def _effective_requests_paused():
    """Manual pause OR scheduled quiet hours (when enabled)."""
    if requests_paused:
        return True
    if spx and spx.feature_enabled("quiet_hours") and spx.quiet_hours_should_block():
        return True
    return False


def _path_is_allowlist_exempt(path: str) -> bool:
    """Guest/health/public API paths — not blocked by SOULPLACE_IP_ALLOWLIST."""
    p = ((path or "").rstrip("/") or "/")
    up = (URL_PREFIX or "").rstrip("/")
    if p == "/health":
        return True
    if not up:
        return p in ("/", "/health")
    root_redirects = (
        "/login",
        "/menu",
        "/table",
        "/tables",
        "/links",
        "/dashboard",
        "/notification-setup",
        "/notification-status",
        "/notification-test",
        "/admin/menu",
        "/admin/system",
    )
    if p in root_redirects:
        return True
    if "/static/" in p:
        return True
    if not p.startswith(up + "/"):
        return False
    rel = p[len(up) :]
    if rel in ("", "/"):
        return True
    if rel.startswith("/api/public"):
        return True
    if rel in ("/api/status", "/health", "/api/request/create"):
        return True
    if rel.startswith("/table"):
        return True
    if rel.startswith("/tables") or rel.startswith("/links") or rel.startswith("/menu"):
        return True
    if rel.startswith("/login") or rel.startswith("/notification"):
        return True
    if rel.startswith("/test-notify"):
        return True
    if rel.startswith("/static/"):
        return True
    return False


def _idempotency_take_create(key: str, ttl_sec: int = 120):
    """Return cached JSON body if key still valid; else None."""
    if not key:
        return None
    now = time.time()
    row = _idempotency_create.get(key)
    if not row:
        return None
    exp, payload = row[0], row[1]
    if now > exp:
        _idempotency_create.pop(key, None)
        return None
    return payload


def _idempotency_store_create(key: str, payload: dict, ttl_sec: int = 120):
    if not key:
        return
    now = time.time()
    _idempotency_create[key] = (now + ttl_sec, payload)
    if len(_idempotency_create) > 600:
        for k, v in list(_idempotency_create.items())[:100]:
            if now > v[0]:
                _idempotency_create.pop(k, None)


def _login_burst_allow(ip):
    """Limit POST /login frequency per IP (best-effort per server instance)."""
    now = time.time()
    arr = _login_burst_times.setdefault(ip, [])
    arr[:] = [t for t in arr if now - t < LOGIN_BURST_WINDOW_SEC]
    if len(arr) >= LOGIN_BURST_MAX:
        return False, max(1, int(LOGIN_BURST_WINDOW_SEC - (now - arr[0])))
    arr.append(now)
    return True, None


def _rate_limit_allow(table_int):
    """Return (True, None) or (False, retry_after_seconds). In-memory per instance only."""
    key = "%s:%s" % (_client_ip(), table_int)
    now = time.time()
    last = _rate_limit_store.get(key, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False, int(RATE_LIMIT_SECONDS - (now - last)) + 1
    _rate_limit_store[key] = now
    return True, None


def _append_activity(action, table, request_id):
    """Record staff action for audit trail."""
    global activity_log
    entry = {
        "at": _utc_iso_now(),
        "by": session.get("username") or "",
        "display": session.get("display_name") or session.get("username") or "",
        "action": action,
        "table": table,
        "request_id": str(request_id) if request_id is not None else "",
    }
    activity_log.append(entry)
    activity_log[:] = activity_log[-ACTIVITY_LOG_MAX:]


def _public_table_status(table_num):
    """Guest-facing status: none | pending | on_the_way | at_table | done (active work on table)."""
    if table_num < 1 or table_num > NUM_TABLES:
        return {"ok": False, "error": "invalid table"}
    # Active accepted (not done), newest first
    active = [r for r in accepted_requests if r.get("table") == table_num and (r.get("status") or "on_the_way") != "done"]
    if active:
        active.sort(key=lambda x: str(x.get("accepted_at") or ""), reverse=True)
        st = active[0].get("status") or "on_the_way"
        msg = {"on_the_way": "Staff is on the way.", "at_table": "Staff is at your table."}.get(st, "In progress.")
        return {"ok": True, "status": st, "message": msg}
    accepted_ids = {r["request_id"] for r in accepted_requests}
    for r in help_requests:
        if r.get("table") == table_num and r.get("id") not in accepted_ids:
            return {"ok": True, "status": "pending", "message": "Your request was received. A Soul will be with you soon."}
    done_rows = [r for r in accepted_requests if r.get("table") == table_num and (r.get("status") or "") == "done"]
    if done_rows:
        done_rows.sort(key=lambda x: str(x.get("accepted_at") or ""), reverse=True)
        return {"ok": True, "status": "done", "message": "Service completed. Please rate your experience."}
    return {"ok": True, "status": "none", "message": ""}


def _public_queue_info(table_num):
    if table_num < 1 or table_num > NUM_TABLES:
        return {"ok": False, "error": "invalid table"}
    accepted_ids = {r["request_id"] for r in accepted_requests}
    pending = []
    for r in help_requests:
        if r.get("id") in accepted_ids:
            continue
        pending.append(r)
    position = 0
    for idx, r in enumerate(pending, start=1):
        if int(r.get("table") or 0) == table_num:
            position = idx
            break
    avg_minutes = 3
    eta = position * avg_minutes if position else 0
    out = {
        "ok": True,
        "table": table_num,
        "pending_count": len(pending),
        "position": position,
        "eta_minutes": eta,
        "avg_minutes_per_request": avg_minutes,
    }
    if spx and spx.feature_enabled("queue_eta_bands"):
        low, high = spx.eta_band_minutes(position, len(pending), float(avg_minutes))
        out["eta_minutes_low"] = low
        out["eta_minutes_high"] = high
    return out


def _webhook(event: str, payload: dict):
    if spx and spx.feature_enabled("webhooks"):
        try:
            spx.outbound_webhooks(event, payload)
        except Exception:
            pass


def _wait_minutes_raised(req_row) -> int:
    if spx:
        return spx.wait_minutes_since_raised((req_row or {}).get("raised_at"))
    dt = _parse_raised_at((req_row or {}).get("raised_at"))
    if dt is None:
        return 0
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 60))


def _sla_tier_for_wait(wait_minutes: int) -> str:
    if spx:
        return spx.sla_tier(wait_minutes)
    return "ok"


def _pending_request_priority(req):
    """Higher score = higher priority for staff suggestion."""
    score = 0
    if req.get("urgent"):
        score += 100
    raised = _parse_raised_at(req.get("raised_at"))
    if raised is not None:
        age_min = max(0, int((datetime.now(timezone.utc) - raised).total_seconds() // 60))
        score += min(age_min, 240)
    if req.get("category") and str(req.get("category")).strip().lower() == "order":
        score += 5
    if req.get("quiet_preferred"):
        score += 15
    return score


def _active_load_by_user():
    """Current active accepted load by username (not done)."""
    loads = {}
    for r in accepted_requests:
        st = str(r.get("status") or "").strip().lower()
        if st == "done":
            continue
        u = str(r.get("accepted_by") or "").strip().lower()
        if not u:
            continue
        loads[u] = int(loads.get(u, 0)) + 1
    return loads


def _eligible_staff_users():
    """Eligible assignees based on role + presence mode."""
    users = []
    for uname, info in USER_DB.items():
        role = str((info or {}).get("role") or "").strip().lower()
        if role not in ("staff", "admin", "manager"):
            continue
        mode = str((staff_presence.get(uname) or {}).get("mode") or "online").strip().lower()
        if mode == "offline":
            continue
        users.append({"username": uname, "role": role, "mode": mode})
    return users


def _best_assignee_username():
    """Pick assignee with lightest load; prefer online over break."""
    users = _eligible_staff_users()
    if not users:
        return None
    loads = _active_load_by_user()
    users.sort(key=lambda x: (0 if x["mode"] == "online" else 1, int(loads.get(x["username"], 0)), x["username"]))
    return users[0]["username"]


def _to_chennai_time(iso_or_legacy):
    """Convert to Chennai (IST) display. Handles ISO UTC and legacy 'HH:MM:SS AM/PM' (was server UTC)."""
    if not iso_or_legacy:
        return ""
    s = str(iso_or_legacy).strip()
    out = None
    # ISO from backend (UTC)
    if "T" in s:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            ist = dt.astimezone(CHENNAI_TZ)
            out = ist.strftime("%I:%M:%S %p")
        except (ValueError, TypeError):
            pass
    # Legacy format "08:49:20 PM" was stored as server (UTC) time – convert to Chennai
    if out is None:
        m = re.match(r"^\s*(\d{1,2}):(\d{2}):(\d{2})\s*(AM|PM)\s*$", s, re.IGNORECASE)
        if m:
            try:
                h, mi, sec, ampm = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4).upper()
                if ampm == "PM" and h != 12:
                    h += 12
                elif ampm == "AM" and h == 12:
                    h = 0
                now_utc = datetime.now(timezone.utc)
                dt_utc = now_utc.replace(hour=h, minute=mi, second=sec, microsecond=0)
                ist = dt_utc.astimezone(CHENNAI_TZ)
                out = ist.strftime("%I:%M:%S %p")
            except (ValueError, TypeError):
                pass
    if out is not None:
        return out + " IST"
    return iso_or_legacy


def seed_demo_requests():
    """Add demo requests only when running locally (not on Vercel). On production, never re-add so «Clear all pending» stays cleared."""
    if os.environ.get("VERCEL"):
        return
    if not help_requests:
        now = _utc_iso_now()
        demos = [
            {"id": "1", "table": 2, "raised_at": now},
            {"id": "2", "table": 5, "raised_at": now},
        ]
        help_requests.extend(demos)
        save_data()


@app.before_request
def before_request():
    g.soulplace_rid = secrets.token_hex(4)
    g.soulplace_t0 = time.time()
    try:
        load_config()
        load_data()
        seed_demo_requests()
    except Exception:
        pass  # Don't crash live; use in-memory defaults
    if spx and spx.feature_enabled("staff_ip_allowlist"):
        raw = (os.environ.get("SOULPLACE_IP_ALLOWLIST") or "").strip()
        if raw and not spx.ip_allowed(_client_ip()):
            if not _path_is_allowlist_exempt(request.path):
                return Response(
                    "Access denied (IP not allowlisted for staff routes).",
                    status=403,
                    mimetype="text/plain",
                )
    idle_sec = int(spx.session_idle_seconds() or 0) if spx else 0
    if idle_sec > 0 and "username" in session:
        now = time.time()
        last = session.get("_sp_last")
        if last is not None and now - float(last) > idle_sec:
            session.clear()
            up = URL_PREFIX.rstrip("/") or ""
            p = request.path or ""
            if p.startswith(up + "/api/") or (up and "/api/" in p):
                return jsonify({"ok": False, "error": "Session expired due to inactivity."}), 401
            return _redirect_to_login()
        session["_sp_last"] = now


@app.after_request
def soulplace_after_request(resp):
    try:
        ms = (time.time() - getattr(g, "soulplace_t0", time.time())) * 1000
        app.logger.info(
            "rid=%s %s %s status=%s %.0fms",
            getattr(g, "soulplace_rid", "-"),
            request.method,
            request.path,
            resp.status_code,
            ms,
        )
    except Exception:
        pass
    return resp


@app.context_processor
def inject_base_url():
    """Give every template a full base URL so links work on live (Vercel)."""
    try:
        base = get_public_base_url()
    except Exception:
        base = DEFAULT_PUBLIC_URL
    base = (base or DEFAULT_PUBLIC_URL).rstrip("/")
    up = URL_PREFIX.rstrip("/") or "/soulplace"
    return {
        "base_url": base,
        "url_prefix": up,
        "default_public_origin": DEFAULT_PUBLIC_URL.rstrip("/"),
        "app_config": APP_CONFIG or {},
    }


def _redirect_to_login():
    """Redirect to login; use full URL on live so browser stays on same origin."""
    try:
        base = get_public_base_url().rstrip("/")
        if base and base.startswith("http"):
            return redirect(base + url_for("main.login"))
    except Exception:
        pass
    return redirect(url_for("main.login"))


def login_required(f):
    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            return _redirect_to_login()
        return f(*args, **kwargs)

    return wrapped


@bp.route("/")
def index():
    if "username" in session:
        return redirect(url_for("main.role_home"))
    return redirect(url_for("main.login"))


@bp.route("/home")
@login_required
def role_home():
    """Role-based landing entrypoint (extensible for future role-specific home pages)."""
    role = (session.get("role") or "").strip().lower()
    if role in ("admin", "staff", "manager"):
        return redirect(url_for("main.dashboard"))
    return _redirect_to_login()


def _deployment_meta():
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA") or os.environ.get("GIT_COMMIT") or ""
    return {
        "git_sha": (sha or "")[:40],
        "deployment_id": os.environ.get("VERCEL_DEPLOYMENT_ID") or os.environ.get("SOULPLACE_BUILD_ID") or "",
    }


@bp.route("/health")
def health():
    """Health check for Vercel/live; returns 200 so you can verify the app is running."""
    meta = _deployment_meta()
    return jsonify(
        {
            "ok": True,
            "status": "live",
            "app": "soulplace-help-desk",
            "prefix": URL_PREFIX or "/soulplace",
            "vercel": bool(os.environ.get("VERCEL")),
            **meta,
        }
    ), 200


@bp.route("/api/status")
def api_status():
    """Public machine-readable status (deploy smoke tests, monitoring)."""
    meta = _deployment_meta()
    return jsonify(
        {
            "ok": True,
            "status": "live",
            "app": "soulplace-help-desk",
            "prefix": URL_PREFIX or "/soulplace",
            "vercel": bool(os.environ.get("VERCEL")),
            "requests_paused": _effective_requests_paused(),
            "manual_requests_paused": requests_paused,
            "num_tables": NUM_TABLES,
            "pending_requests_count": len([r for r in help_requests if r.get("id") not in {a["request_id"] for a in accepted_requests}]),
            "push_subscriptions_count": len(push_subscriptions),
            **meta,
        }
    ), 200


@bp.route("/api/public/paused", methods=["GET"])
def public_paused():
    """Whether quiet hours are on (for table page banner)."""
    return jsonify(
        {
            "paused": _effective_requests_paused(),
            "manual_paused": requests_paused,
            "quiet_hours_active": bool(spx and spx.feature_enabled("quiet_hours") and spx.quiet_hours_should_block()),
        }
    )


@bp.route("/api/public/config", methods=["GET"])
def public_config():
    """Safe public settings for table apps / kiosks (no secrets)."""
    cfg = APP_CONFIG or {}
    return jsonify(
        {
            "ok": True,
            "num_tables": NUM_TABLES,
            "guest_wifi_hint": cfg.get("guest_wifi_hint") or "",
            "default_location_id": cfg.get("default_location_id") or "default",
            "rate_limit_seconds": RATE_LIMIT_SECONDS,
            "url_prefix": URL_PREFIX.rstrip("/") or "/soulplace",
        }
    )


@bp.route("/api/public/table-status", methods=["GET"])
def public_table_status():
    """Guest: ?table=N → pending | on_the_way | at_table | none."""
    t = request.args.get("table", type=int)
    if t is None:
        return jsonify({"ok": False, "error": "table required"}), 400
    return jsonify(_public_table_status(t))


@bp.route("/api/public/queue-info", methods=["GET"])
def public_queue_info():
    """Guest queue information: position and ETA for ?table=N."""
    t = request.args.get("table", type=int)
    if t is None:
        return jsonify({"ok": False, "error": "table required"}), 400
    return jsonify(_public_queue_info(t))


@bp.route("/api/public/feedback", methods=["POST"])
def public_feedback():
    """Guest feedback after service completion."""
    data = request.get_json() or request.form or {}
    try:
        table = int(data.get("table"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "table must be a number"}), 400
    if table < 1 or table > NUM_TABLES:
        return jsonify({"ok": False, "error": f"table must be 1–{NUM_TABLES}"}), 400
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "rating must be 1-5"}), 400
    if rating < 1 or rating > 5:
        return jsonify({"ok": False, "error": "rating must be 1-5"}), 400
    comment = (data.get("comment") or "").strip()[:300]
    request_id = str(data.get("request_id") or "").strip()[:30] or None
    customer_feedback.append(
        {
            "at": _utc_iso_now(),
            "table": table,
            "rating": rating,
            "comment": comment,
            "request_id": request_id,
        }
    )
    customer_feedback[:] = customer_feedback[-1000:]
    save_data()
    return jsonify({"ok": True, "message": "Thanks for your feedback."})


@bp.route("/api/table/<int:table_num>/history", methods=["GET"])
@login_required
def table_request_history(table_num):
    """Last N request_history rows for this table (staff)."""
    if table_num < 1 or table_num > NUM_TABLES:
        return jsonify({"ok": False, "error": "invalid table"}), 400
    limit = min(50, max(1, request.args.get("limit", type=int) or 15))
    rows = []
    for h in reversed(request_history):
        if len(rows) >= limit:
            break
        if int(h.get("table") or 0) == table_num:
            rows.append(
                {
                    "id": h.get("id"),
                    "raised_at": h.get("raised_at"),
                    "note": h.get("note") or "",
                    "category": h.get("category") or "",
                    "urgent": bool(h.get("urgent")),
                }
            )
    return jsonify({"ok": True, "table": table_num, "items": rows})


@bp.route("/api/admin/activity", methods=["GET"])
@login_required
def admin_activity():
    if not _admin_or_manager():
        return jsonify({"ok": False, "error": "Admin or manager only"}), 403
    limit = min(200, max(1, request.args.get("limit", type=int) or 80))
    return jsonify({"ok": True, "items": list(reversed(activity_log[-limit:]))})


@bp.route("/api/admin/export/requests", methods=["GET"])
@login_required
def admin_export_requests():
    """CSV of request_history in date range (admin). ?from=YYYY-MM-DD&to=YYYY-MM-DD"""
    if not _admin_or_manager():
        return jsonify({"error": "Admin or manager only"}), 403
    from_s = (request.args.get("from") or "").strip()
    to_s = (request.args.get("to") or "").strip()
    try:
        d_from = datetime.strptime(from_s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if from_s else None
        d_to = datetime.strptime(to_s, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1) if to_s else None
    except ValueError:
        return jsonify({"error": "Invalid from/to; use YYYY-MM-DD"}), 400
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "table", "raised_at_utc", "note", "category", "urgent"])
    for h in request_history:
        raised = _parse_raised_at(h.get("raised_at"))
        if raised is None:
            continue
        if d_from and raised < d_from:
            continue
        if d_to and raised >= d_to:
            continue
        w.writerow(
            [
                h.get("id", ""),
                h.get("table", ""),
                h.get("raised_at", ""),
                h.get("note") or "",
                h.get("category") or "",
                "1" if h.get("urgent") else "0",
            ]
        )
    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=soulplace_requests_export.csv"
    return resp


@bp.route("/api/admin/menu", methods=["GET", "POST"])
@login_required
def admin_menu_api():
    global cafe_menu_groups
    if session.get("role") != "admin":
        return jsonify({"ok": False, "error": "Admin only"}), 403
    if request.method == "GET":
        return jsonify({"ok": True, "groups": cafe_menu_groups or []})
    data = request.get_json() or {}
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        return jsonify({"ok": False, "error": "groups must be a non-empty array"}), 400
    cafe_menu_groups = groups
    save_data()
    return jsonify({"ok": True, "message": "Menu saved."})


@bp.route("/admin/menu", methods=["GET", "POST"])
@login_required
def admin_menu_page():
    global cafe_menu_groups
    if session.get("role") != "admin":
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        raw = (request.form.get("menu_json") or "").strip()
        try:
            parsed = json.loads(raw)
            groups = parsed.get("groups") if isinstance(parsed, dict) else None
            if not isinstance(groups, list) or not groups:
                raise ValueError("Need JSON object with key groups (array)")
            cafe_menu_groups = groups
            save_data()
            return render_template("admin_menu.html", ok=True, message="Saved.", menu_json=json.dumps({"groups": groups}, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return render_template("admin_menu.html", ok=False, message=str(e), menu_json=raw)
    payload = {"groups": cafe_menu_groups or []}
    return render_template("admin_menu.html", ok=None, message="", menu_json=json.dumps(payload, indent=2, ensure_ascii=False))


def _redirect_role_home():
    try:
        base = get_public_base_url().rstrip("/")
        if base and base.startswith("http"):
            return redirect(base + url_for("main.role_home"))
    except Exception:
        pass
    return redirect(url_for("main.role_home"))


def _complete_session_login(uname):
    session["username"] = uname
    session["display_name"] = USER_DB[uname]["display_name"]
    session["role"] = USER_DB[uname]["role"]
    session.pop("pending_2fa_user", None)
    session["_sp_last"] = time.time()


@bp.route("/login", methods=["GET", "POST"])
def login():
    def _render(**extra):
        ctx = {"num_tables": NUM_TABLES, "cache_bust": "v17", "error": None, "totp_step": False, "pending_user": ""}
        ctx.update(extra)
        return make_response(render_template("login.html", **ctx))

    if request.method == "GET":
        if request.args.get("cancel_2fa"):
            session.pop("pending_2fa_user", None)
        pending_u = (session.get("pending_2fa_user") or "").strip().lower()
        if pending_u and (not pyotp or not admin_totp_secrets.get(pending_u)):
            session.pop("pending_2fa_user", None)
            pending_u = ""
        totp_step = bool(pending_u)
        r = _render(error=None, totp_step=totp_step, pending_user=pending_u)
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return r

    ip = _client_ip()
    ok_b, retry_b = _login_burst_allow(ip)
    if not ok_b:
        r = _render(error="Too many login attempts. Please wait %s seconds." % retry_b, totp_step=False, pending_user="")
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return r

    totp_code = (request.form.get("totp") or "").strip().replace(" ", "")
    pending_user = (session.get("pending_2fa_user") or "").strip().lower()

    if pending_user and totp_code:
        if pending_user not in USER_DB:
            session.pop("pending_2fa_user", None)
            r = _render(error="Session expired. Sign in again.", totp_step=False, pending_user="")
            r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return r
        secret = admin_totp_secrets.get(pending_user)
        valid_totp = False
        if secret and pyotp:
            try:
                valid_totp = bool(pyotp.TOTP(secret).verify(totp_code, valid_window=1))
            except Exception:
                valid_totp = False
        if valid_totp:
            _complete_session_login(pending_user)
            resp = _redirect_role_home()
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return resp
        r = _render(error="Invalid authenticator code.", totp_step=True, pending_user=pending_user)
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return r

    username = (request.form.get("username") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    if not username:
        r = _render(error="Invalid username or password.", totp_step=False, pending_user="")
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return r

    if username not in USER_DB or USER_DB[username]["password"].lower() != password.lower():
        r = _render(error="Invalid username or password.", totp_step=False, pending_user="")
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return r

    if USER_DB[username]["role"] == "admin" and admin_totp_secrets.get(username) and pyotp:
        session["pending_2fa_user"] = username
        r = _render(error=None, totp_step=True, pending_user=username)
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return r

    _complete_session_login(username)
    resp = _redirect_role_home()
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@bp.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("display_name", None)
    session.pop("role", None)
    session.pop("pending_2fa_user", None)
    try:
        base = get_public_base_url().rstrip("/")
        if base and base.startswith("http"):
            return redirect(base + url_for("main.login", forget=1))
    except Exception:
        pass
    return redirect(url_for("main.login", forget=1))


@bp.route("/dashboard")
@login_required
def dashboard():
    display = session.get("display_name") or session.get("username", "").capitalize()
    role = _session_role()
    is_admin = role == "admin"
    is_manager = role == "manager"
    resp = make_response(render_template(
        "dashboard.html",
        username=display,
        is_admin=is_admin,
        is_manager=is_manager,
        num_tables=NUM_TABLES,
    ))
    # Avoid showing old dashboard (e.g. missing "Clear all pending") from cache
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@bp.route("/payments")
def payments_page():
    """Payments & billing: rates, UPI, cash, card; optional portal URL in config."""
    portal = (APP_CONFIG or {}).get("billing_url") or ""
    resp = make_response(render_template("billing.html", billing_portal_url=portal))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@bp.route("/billing")
def billing_page():
    """Same as /payments (redirect for old bookmarks)."""
    r = redirect(url_for("main.payments_page"))
    r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return r


@bp.route("/api/requests", methods=["GET"])
@login_required
def list_requests():
    """Return pending help requests (not yet accepted). Urgent first. Only recent ones (last N minutes). Times in Chennai (IST)."""
    accepted_ids = {r["request_id"] for r in accepted_requests}
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=PENDING_REQUEST_MAX_AGE_MINUTES)
    pending = []
    current_user = str(session.get("username") or "").strip().lower()
    suggested_user = _best_assignee_username()
    for r in help_requests:
        if r["id"] in accepted_ids:
            continue
        raised_dt = _parse_raised_at(r.get("raised_at"))
        if raised_dt is None or raised_dt < cutoff:
            continue
        out = {"id": r["id"], "table": r["table"], "raised_at": _to_chennai_time(r["raised_at"])}
        if r.get("note"):
            out["note"] = r["note"]
        if r.get("category"):
            out["category"] = r["category"]
        if r.get("urgent"):
            out["urgent"] = True
        if r.get("quiet_preferred"):
            out["quiet_preferred"] = True
        if r.get("allergens"):
            out["allergens"] = r["allergens"]
        if r.get("location_id"):
            out["location_id"] = r["location_id"]
        wm = _wait_minutes_raised(r)
        out["wait_minutes"] = wm
        out["sla"] = _sla_tier_for_wait(wm)
        if suggested_user:
            out["recommended_to"] = suggested_user
            out["recommended_for_me"] = bool(current_user and suggested_user == current_user)
        if r.get("extras") and isinstance(r.get("extras"), dict):
            out["extras"] = r["extras"]
        pending.append(out)
    pending.sort(key=lambda x: (0 if x.get("urgent") else 1, -int(x.get("wait_minutes") or 0)))
    return jsonify({"requests": pending})


@bp.route("/api/requests/next-suggestion", methods=["GET"])
@login_required
def next_request_suggestion():
    """Suggest next request to attend using urgency + waiting-time score."""
    accepted_ids = {r["request_id"] for r in accepted_requests}
    current_user = str(session.get("username") or "").strip().lower()
    suggested_user = _best_assignee_username()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=PENDING_REQUEST_MAX_AGE_MINUTES)
    candidates = []
    for r in help_requests:
        if r.get("id") in accepted_ids:
            continue
        raised_dt = _parse_raised_at(r.get("raised_at"))
        if raised_dt is None or raised_dt < cutoff:
            continue
        score = _pending_request_priority(r)
        out = {"id": r.get("id"), "table": r.get("table"), "urgent": bool(r.get("urgent")), "score": score}
        if r.get("note"):
            out["note"] = r["note"]
        if r.get("category"):
            out["category"] = r["category"]
        out["raised_at"] = _to_chennai_time(r.get("raised_at"))
        wm = _wait_minutes_raised(r)
        out["wait_minutes"] = wm
        out["sla"] = _sla_tier_for_wait(wm)
        if r.get("allergens"):
            out["allergens"] = r["allergens"]
        if r.get("quiet_preferred"):
            out["quiet_preferred"] = True
        if r.get("extras") and isinstance(r.get("extras"), dict):
            out["extras"] = r["extras"]
        candidates.append(out)
    if not candidates:
        return jsonify({"ok": True, "suggested": None, "reason": "No pending requests"})
    candidates.sort(key=lambda x: (-int(x.get("score") or 0), int(x.get("table") or 9999)))
    return jsonify({
        "ok": True,
        "suggested": candidates[0],
        "pending_count": len(candidates),
        "recommended_staff": suggested_user,
        "recommended_for_me": bool(current_user and suggested_user == current_user),
    })


@bp.route("/api/staff/presence", methods=["GET", "POST"])
@login_required
def staff_presence_api():
    """Get/update staff availability mode."""
    username = session.get("username", "").strip().lower()
    if request.method == "POST":
        data = request.get_json() or {}
        mode = str(data.get("mode") or "").strip().lower()
        if mode not in ("online", "break", "offline"):
            return jsonify({"ok": False, "error": "mode must be online|break|offline"}), 400
        staff_presence[username] = {"mode": mode, "updated_at": _utc_iso_now()}
        save_data()
        return jsonify({"ok": True, "username": username, "mode": mode})
    mine = staff_presence.get(username) or {"mode": "online", "updated_at": _utc_iso_now()}
    out = {"ok": True, "me": {"username": username, "mode": mine.get("mode", "online"), "updated_at": mine.get("updated_at")}}
    if _session_role() in ("admin", "manager"):
        out["all"] = [
            {"username": u, "mode": v.get("mode", "offline"), "updated_at": v.get("updated_at", "")}
            for u, v in sorted(staff_presence.items())
            if isinstance(v, dict)
        ]
    return jsonify(out)


@bp.route("/api/requests/clear", methods=["POST"])
@login_required
def clear_all_requests():
    """Clear all help requests and accepted records (for testing). Staff only. request_history is kept for analytics."""
    global help_requests, accepted_requests
    help_requests.clear()
    accepted_requests.clear()
    save_data()
    return jsonify({"ok": True, "message": "All requests cleared."})


@bp.route("/api/requests/accept", methods=["POST"])
@login_required
def accept_request():
    """Mark a request as accepted by current user."""
    data = request.get_json() or {}
    request_id = data.get("request_id")
    if not request_id:
        return jsonify({"ok": False, "error": "request_id required"}), 400
    req = next((r for r in help_requests if r["id"] == request_id), None)
    if not req:
        return jsonify({"ok": False, "error": "Request not found"}), 404
    accepted_ids = {r["request_id"] for r in accepted_requests}
    if request_id in accepted_ids:
        return jsonify({"ok": False, "error": "Already accepted"}), 400
    accepted_at = _utc_iso_now()
    acc = {
        "request_id": request_id,
        "table": req["table"],
        "raised_at": req["raised_at"],
        "accepted_at": accepted_at,
        "accepted_by": session["username"],
        "status": "on_the_way",
    }
    if req.get("note"):
        acc["note"] = req["note"]
    if req.get("category"):
        acc["category"] = req["category"]
    if req.get("urgent"):
        acc["urgent"] = True
    if req.get("quiet_preferred"):
        acc["quiet_preferred"] = True
    if req.get("allergens"):
        acc["allergens"] = req["allergens"]
    if req.get("location_id"):
        acc["location_id"] = req["location_id"]
    if req.get("extras") and isinstance(req.get("extras"), dict):
        acc["extras"] = req["extras"]
    accepted_requests.append(acc)
    try:
        _append_activity("accept", req["table"], request_id)
    except Exception:
        pass
    save_data()
    wh_acc = {
        "request_id": request_id,
        "table": req["table"],
        "accepted_by": session["username"],
        "urgent": bool(req.get("urgent")),
        "allergens": req.get("allergens"),
    }
    if req.get("extras"):
        wh_acc["extras"] = req["extras"]
    _webhook("request.accepted", wh_acc)
    return jsonify({"ok": True, "accepted_at": _to_chennai_time(accepted_at)})


@bp.route("/api/requests/bulk-accept", methods=["POST"])
@login_required
def bulk_accept_requests():
    """Accept multiple pending request ids (same rules as single accept). Max 25 per call."""
    data = request.get_json() or {}
    ids = data.get("request_ids") or data.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"ok": False, "error": "request_ids array required"}), 400
    ids = [str(x).strip() for x in ids[:25] if str(x).strip()]
    accepted_ids = {r["request_id"] for r in accepted_requests}
    uname = session["username"]
    ok_n = 0
    errors = []
    for request_id in ids:
        if request_id in accepted_ids:
            errors.append({"id": request_id, "error": "Already accepted"})
            continue
        req = next((r for r in help_requests if r["id"] == request_id), None)
        if not req:
            errors.append({"id": request_id, "error": "Not found"})
            continue
        accepted_at = _utc_iso_now()
        acc = {
            "request_id": request_id,
            "table": req["table"],
            "raised_at": req["raised_at"],
            "accepted_at": accepted_at,
            "accepted_by": uname,
            "status": "on_the_way",
        }
        if req.get("note"):
            acc["note"] = req["note"]
        if req.get("category"):
            acc["category"] = req["category"]
        if req.get("urgent"):
            acc["urgent"] = True
        if req.get("quiet_preferred"):
            acc["quiet_preferred"] = True
        if req.get("allergens"):
            acc["allergens"] = req["allergens"]
        if req.get("location_id"):
            acc["location_id"] = req["location_id"]
        if req.get("extras") and isinstance(req.get("extras"), dict):
            acc["extras"] = req["extras"]
        accepted_requests.append(acc)
        accepted_ids.add(request_id)
        try:
            _append_activity("accept", req["table"], request_id)
        except Exception:
            pass
        wh_b = {
            "request_id": request_id,
            "table": req["table"],
            "accepted_by": uname,
            "urgent": bool(req.get("urgent")),
            "allergens": req.get("allergens"),
            "bulk": True,
        }
        if req.get("extras"):
            wh_b["extras"] = req["extras"]
        _webhook("request.accepted", wh_b)
        ok_n += 1
    if ok_n:
        save_data()
    return jsonify({"ok": True, "accepted_count": ok_n, "errors": errors})


@bp.route("/api/settings/token", methods=["GET"])
@login_required
def get_token():
    """Return API token for admins (for use in Vercel env or external API)."""
    if session.get("role") != "admin":
        return jsonify({"error": "Admin only"}), 403
    return jsonify({"api_token": get_api_token()})


@bp.route("/api/analytics", methods=["GET"])
@login_required
def analytics():
    """Request history: counts per day and per table (last 30 days). Optional ?format=csv to export."""
    from collections import defaultdict
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    by_day = defaultdict(int)
    by_table = defaultdict(int)
    for h in request_history:
        raised = _parse_raised_at(h.get("raised_at"))
        if raised is None or raised < cutoff:
            continue
        day = raised.strftime("%Y-%m-%d")
        by_day[day] += 1
        t = h.get("table")
        if t is not None:
            by_table[int(t)] += 1
    ratings = [int(x.get("rating")) for x in customer_feedback if isinstance(x, dict) and str(x.get("rating", "")).isdigit()]
    out = {
        "by_day": dict(by_day),
        "by_table": {str(k): v for k, v in sorted(by_table.items())},
        "total": sum(by_day.values()),
        "feedback_count": len(ratings),
        "feedback_avg": (round(sum(ratings) / len(ratings), 2) if ratings else 0),
    }
    if request.args.get("format") == "csv":
        lines = ["date,count"]
        for d in sorted(by_day.keys()):
            lines.append(f"{d},{by_day[d]}")
        lines.append("")
        lines.append("table,count")
        for t in sorted(by_table.keys(), key=int):
            lines.append(f"{t},{by_table[t]}")
        resp = make_response("\n".join(lines))
        resp.headers["Content-Type"] = "text/csv"
        resp.headers["Content-Disposition"] = "attachment; filename=soulplace_analytics.csv"
        return resp
    if spx and spx.feature_enabled("analytics_extras"):
        out["heatmap_ist"] = spx.analytics_heatmap_buckets(request_history)
        out["cost_estimate"] = spx.cost_estimate_minutes(accepted_requests, request_history)
    return jsonify(out)


@bp.route("/api/public/features-100", methods=["GET"])
def public_features_100():
    """All 100 roadmap features with wiring notes (read-only)."""
    if not sreg:
        return jsonify({"ok": False, "error": "registry unavailable"}), 500
    items = sreg.public_features_payload()
    return jsonify({"ok": True, "count": len(items), "items": items})


@bp.route("/api/analytics/funnel", methods=["GET"])
@login_required
def analytics_funnel():
    acc_ids = {r["request_id"] for r in accepted_requests}
    pending_n = len([r for r in help_requests if r.get("id") not in acc_ids])
    active_n = len([a for a in accepted_requests if (a.get("status") or "") != "done"])
    done_n = len([a for a in accepted_requests if (a.get("status") or "") == "done"])
    return jsonify({"ok": True, "pending": pending_n, "active_attending": active_n, "completed": done_n})


@bp.route("/api/analytics/word-cloud", methods=["GET"])
@login_required
def analytics_word_cloud():
    from collections import Counter

    words = Counter()
    for f in customer_feedback:
        if not isinstance(f, dict):
            continue
        c = (f.get("comment") or "").lower()
        for w in re.findall(r"[a-zA-Z\u0080-\uFFFF]{4,}", c):
            words[w.lower()] += 1
    return jsonify({"ok": True, "top": words.most_common(50)})


@bp.route("/api/analytics/week-compare", methods=["GET"])
@login_required
def analytics_week_compare():
    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d14 = now - timedelta(days=14)
    c_recent = 0
    c_prev = 0
    for h in request_history:
        ra = _parse_raised_at(h.get("raised_at"))
        if ra is None:
            continue
        if ra >= d7:
            c_recent += 1
        elif d14 <= ra < d7:
            c_prev += 1
    return jsonify({"ok": True, "last_7_days": c_recent, "previous_7_days": c_prev})


@bp.route("/api/analytics/anomalies", methods=["GET"])
@login_required
def analytics_anomalies():
    from collections import defaultdict

    by_day = defaultdict(int)
    for h in request_history:
        ra = _parse_raised_at(h.get("raised_at"))
        if ra is None:
            continue
        by_day[ra.strftime("%Y-%m-%d")] += 1
    vals = list(by_day.values())
    med = sorted(vals)[len(vals) // 2] if vals else 0
    flags = [d for d, n in by_day.items() if med and n > max(10, med * 3)]
    return jsonify({"ok": True, "median_per_day": med, "spike_days": flags})


@bp.route("/api/analytics/cohorts", methods=["GET"])
@login_required
def analytics_cohorts():
    """Rough: tables with repeat requests in history."""
    from collections import defaultdict

    per_table = defaultdict(int)
    for h in request_history:
        t = h.get("table")
        if t is not None:
            per_table[int(t)] += 1
    repeat = sum(1 for _t, n in per_table.items() if n >= 2)
    return jsonify({"ok": True, "tables_with_repeat_requests": repeat, "tables_tracked": len(per_table)})


@bp.route("/api/analytics/table-pain", methods=["GET"])
@login_required
def analytics_table_pain():
    """Simple score: pending + urgent count per table."""
    acc_ids = {r["request_id"] for r in accepted_requests}
    scores = {}
    for r in help_requests:
        if r.get("id") in acc_ids:
            continue
        t = int(r.get("table") or 0)
        scores[t] = scores.get(t, 0) + 2 + (3 if r.get("urgent") else 0)
    top = sorted(scores.items(), key=lambda x: -x[1])[:15]
    return jsonify({"ok": True, "top_tables": [{"table": a, "pain": b} for a, b in top]})


@bp.route("/api/analytics/leaderboard", methods=["GET"])
@login_required
def analytics_leaderboard():
    from collections import defaultdict

    counts = defaultdict(int)
    for row in activity_log:
        u = (row.get("by") or "").strip().lower()
        if u:
            counts[u] += 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:20]
    return jsonify({"ok": True, "activity_actions": [{"user": a, "count": b} for a, b in top]})


@bp.route("/api/staff/next-route-hint", methods=["GET"])
@login_required
def staff_next_route_hint():
    accepted_ids = {r["request_id"] for r in accepted_requests}
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=PENDING_REQUEST_MAX_AGE_MINUTES)
    tables = []
    for r in help_requests:
        if r.get("id") in accepted_ids:
            continue
        raised_dt = _parse_raised_at(r.get("raised_at"))
        if raised_dt is None or raised_dt < cutoff:
            continue
        tables.append(int(r.get("table") or 0))
    tables = sorted(set(t for t in tables if t > 0))
    return jsonify({"ok": True, "suggested_visit_order": tables})


@bp.route("/api/requests/<request_id>/whisper", methods=["POST"])
@login_required
def request_whisper_note(request_id):
    """Staff-only note on a pending request (stored under extras.whisper_notes)."""
    data = request.get_json() or {}
    note = (data.get("note") or "").strip()[:800]
    if not note:
        return jsonify({"ok": False, "error": "note required"}), 400
    for r in help_requests:
        if str(r.get("id")) != str(request_id):
            continue
        ex = r.get("extras")
        if not isinstance(ex, dict):
            ex = {}
        ex["whisper_notes"] = note
        r["extras"] = ex
        save_data()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "pending request not found"}), 404


@bp.route("/api/requests/bulk-done-mine", methods=["POST"])
@bp.route("/api/requests/bulk-status", methods=["POST"])
@login_required
def bulk_done_mine():
    """Mark all accepted (non-done) requests owned by current user as done."""
    u = session.get("username")
    n = 0
    for a in accepted_requests:
        if a.get("accepted_by") != u:
            continue
        if (a.get("status") or "") == "done":
            continue
        a["status"] = "done"
        a["completed_at"] = _utc_iso_now()
        n += 1
    if n:
        save_data()
    return jsonify({"ok": True, "marked_done": n})


@bp.route("/api/admin/gdpr-export", methods=["GET"])
@login_required
def admin_gdpr_export():
    if session.get("role") != "admin":
        return jsonify({"ok": False, "error": "Admin only"}), 403
    return jsonify(
        {
            "ok": True,
            "exported_at": _utc_iso_now(),
            "customer_feedback": customer_feedback[-500:],
            "request_history_tail": request_history[-500:],
        }
    )


@bp.route("/api/admin/shift-log-sign", methods=["GET"])
@login_required
def admin_shift_log_sign():
    if not _admin_or_manager():
        return jsonify({"ok": False, "error": "Admin or manager only"}), 403
    blob = json.dumps(activity_log[-ACTIVITY_LOG_MAX:], sort_keys=True, ensure_ascii=False).encode("utf-8")
    h = hashlib.sha256(blob).hexdigest()
    return jsonify({"ok": True, "sha256": h, "activity_rows": len(activity_log)})


@bp.route("/api/settings/pause", methods=["GET", "POST"])
@login_required
def pause_requests():
    """GET: return { paused: bool }. POST: toggle (admin only)."""
    global requests_paused
    if request.method == "POST":
        if session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Admin only"}), 403
        requests_paused = not requests_paused
        save_data()
        return jsonify({"ok": True, "paused": requests_paused, "effective_paused": _effective_requests_paused()})
    return jsonify(
        {
            "paused": requests_paused,
            "effective_paused": _effective_requests_paused(),
            "quiet_hours_active": bool(spx and spx.feature_enabled("quiet_hours") and spx.quiet_hours_should_block()),
        }
    )


@bp.route("/api/settings/change-password", methods=["POST"])
@login_required
def change_password():
    """Change current user's password. Body: current, new (and optionally new_confirm)."""
    data = request.get_json() or request.form or {}
    current = (data.get("current") or "").strip()
    new_pwd = (data.get("new") or data.get("new_password") or "").strip()
    if not current or not new_pwd:
        return jsonify({"ok": False, "error": "current and new password required"}), 400
    username = session.get("username", "").strip().lower()
    if username not in USER_DB or USER_DB[username]["password"].lower() != current.lower():
        return jsonify({"ok": False, "error": "Current password is wrong"}), 400
    if spx:
        ok_pol, err_pol = spx.password_policy_check(new_pwd)
        if not ok_pol:
            return jsonify({"ok": False, "error": err_pol}), 400
    password_overrides[username] = new_pwd
    if username in USER_DB:
        USER_DB[username]["password"] = new_pwd
    save_data()
    return jsonify({"ok": True, "message": "Password updated."})


@bp.route("/api/shift-handoff", methods=["GET", "POST"])
@login_required
def shift_handoff_api():
    global shift_handoff_note
    if request.method == "GET":
        return jsonify({"ok": True, "note": shift_handoff_note})
    data = request.get_json() or request.form or {}
    shift_handoff_note = str(data.get("note") or "")[:4000]
    save_data()
    return jsonify({"ok": True, "note": shift_handoff_note})


@bp.route("/api/admin/incidents", methods=["GET", "POST"])
@login_required
def incidents_api():
    """Short ops incident / handoff log (admin or manager)."""
    global incident_log
    if not _admin_or_manager():
        return jsonify({"ok": False, "error": "Admin or manager only"}), 403
    if request.method == "GET":
        return jsonify({"ok": True, "items": list(reversed(incident_log[-50:]))})
    data = request.get_json() or {}
    msg = str(data.get("message") or data.get("text") or "").strip()[:2000]
    if not msg:
        return jsonify({"ok": False, "error": "message required"}), 400
    sev = str(data.get("severity") or "info").strip().lower()
    if sev not in ("info", "warn", "critical"):
        sev = "info"
    u = session.get("username", "").strip()
    disp = session.get("display_name") or u
    incident_log.append(
        {
            "at": _utc_iso_now(),
            "by": u,
            "display": disp,
            "message": msg,
            "severity": sev,
        }
    )
    incident_log[:] = incident_log[-INCIDENT_LOG_MAX:]
    save_data()
    return jsonify({"ok": True})


@bp.route("/api/admin/features-catalog", methods=["GET"])
@login_required
def admin_features_catalog():
    """100-feature roadmap: titles, categories, status (done|partial|planned). Admin only."""
    if session.get("role") != "admin":
        return jsonify({"ok": False, "error": "Admin only"}), 403
    if not sfc:
        return jsonify({"ok": False, "error": "Catalog module missing"}), 500
    cat = request.args.get("category", "").strip().lower()
    items = list(sfc.FEATURES_CATALOG)
    if cat:
        items = [x for x in items if (x.get("category") or "").lower() == cat]
    return jsonify({"ok": True, "summary": sfc.catalog_summary(), "items": items})


@bp.route("/api/admin/system-info", methods=["GET"])
@login_required
def admin_system_info():
    if session.get("role") != "admin":
        return jsonify({"ok": False, "error": "Admin only"}), 403
    n_adm = sum(1 for _u, i in USER_DB.items() if (i or {}).get("role") == "admin")
    n_staff = sum(1 for _u, i in USER_DB.items() if (i or {}).get("role") == "staff")
    u = session.get("username", "").strip().lower()
    return jsonify(
        {
            "ok": True,
            "num_tables": NUM_TABLES,
            "admin_count": n_adm,
            "staff_count": n_staff,
            "user_count": len(USER_DB),
            "config_from_env_json": bool(os.environ.get("SOULPLACE_CONFIG_JSON", "").strip()),
            "config_file_exists": CONFIG_FILE.is_file(),
            "vercel": bool(os.environ.get("VERCEL")),
            "data_file_path": str(DATA_FILE),
            "requests_paused": requests_paused,
            "totp_enabled_for_me": bool(admin_totp_secrets.get(u)) if u else False,
            "pyotp_available": bool(pyotp),
            **_deployment_meta(),
        }
    )


@bp.route("/admin/system", methods=["GET"])
@login_required
def admin_system_page():
    if session.get("role") != "admin":
        return redirect(url_for("main.dashboard"))
    return render_template("admin_system.html", num_tables=NUM_TABLES)


@bp.route("/api/admin/totp/start", methods=["POST"])
@login_required
def admin_totp_start():
    if session.get("role") != "admin" or not pyotp:
        return jsonify({"ok": False, "error": "Authenticator app support is not available on the server."}), 400
    u = session.get("username", "").strip().lower()
    if admin_totp_secrets.get(u):
        return jsonify({"ok": False, "error": "2FA is already enabled. Disable it first."}), 400
    secret = pyotp.random_base32()
    totp_enroll_pending[u] = secret
    save_data()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=u + "@soulplace", issuer_name="Soulplace Help Desk")
    return jsonify({"ok": True, "secret": secret, "provisioning_uri": uri})


@bp.route("/api/admin/totp/confirm", methods=["POST"])
@login_required
def admin_totp_confirm():
    global admin_totp_secrets
    if not pyotp:
        return jsonify({"ok": False, "error": "pyotp not installed"}), 400
    u = session.get("username", "").strip().lower()
    secret = totp_enroll_pending.get(u)
    if not secret:
        return jsonify({"ok": False, "error": "Start enrollment first (generate QR / secret)."}), 400
    data = request.get_json() or request.form or {}
    code = str(data.get("code") or data.get("totp") or "").strip().replace(" ", "")
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return jsonify({"ok": False, "error": "Invalid code."}), 400
    admin_totp_secrets[u] = secret
    totp_enroll_pending.pop(u, None)
    save_data()
    return jsonify({"ok": True, "message": "Two-factor authentication is enabled for your admin account."})


@bp.route("/api/admin/totp/disable", methods=["POST"])
@login_required
def admin_totp_disable():
    if session.get("role") != "admin":
        return jsonify({"ok": False, "error": "Admin only"}), 403
    u = session.get("username", "").strip().lower()
    admin_totp_secrets.pop(u, None)
    totp_enroll_pending.pop(u, None)
    save_data()
    return jsonify({"ok": True, "message": "2FA disabled."})


@bp.route("/api/requests/accepted", methods=["GET"])
@login_required
def list_accepted():
    """Return requests accepted by current user, with status. Times in Chennai (IST)."""
    username = session["username"]
    mine = []
    for r in accepted_requests:
        if r["accepted_by"] == username:
            row = {"request_id": r["request_id"], "table": r["table"], "raised_at": _to_chennai_time(r["raised_at"]), "accepted_at": _to_chennai_time(r["accepted_at"]), "status": r.get("status") or "on_the_way"}
            if r.get("note"):
                row["note"] = r["note"]
            if r.get("category"):
                row["category"] = r["category"]
            if r.get("allergens"):
                row["allergens"] = r["allergens"]
            if r.get("quiet_preferred"):
                row["quiet_preferred"] = True
            if r.get("completed_at"):
                row["completed_at"] = r["completed_at"]
            if r.get("extras") and isinstance(r.get("extras"), dict):
                row["extras"] = r["extras"]
            mine.append(row)
    return jsonify({"accepted": mine})


@bp.route("/api/admin/staff-options", methods=["GET"])
@login_required
def admin_staff_options():
    """Admin: list assignable staff/admin users with mode and active load."""
    if not _admin_or_manager():
        return jsonify({"ok": False, "error": "Admin or manager only"}), 403
    loads = _active_load_by_user()
    items = []
    for uname, info in sorted(USER_DB.items()):
        role = str((info or {}).get("role") or "").strip().lower()
        if role not in ("staff", "admin", "manager"):
            continue
        mode = str((staff_presence.get(uname) or {}).get("mode") or "online").strip().lower()
        items.append(
            {
                "username": uname,
                "display_name": str((info or {}).get("display_name") or uname),
                "role": role,
                "mode": mode,
                "active_load": int(loads.get(uname, 0)),
            }
        )
    return jsonify({"ok": True, "items": items})


@bp.route("/api/admin/requests/reassign", methods=["POST"])
@login_required
def admin_reassign_request():
    """Admin: reassign a pending request to a selected staff user."""
    if not _admin_or_manager():
        return jsonify({"ok": False, "error": "Admin or manager only"}), 403
    data = request.get_json() or {}
    request_id = str(data.get("request_id") or "").strip()
    assignee = str(data.get("assignee") or "").strip().lower()
    if not request_id or not assignee:
        return jsonify({"ok": False, "error": "request_id and assignee are required"}), 400
    info = USER_DB.get(assignee) or {}
    role = str(info.get("role") or "").strip().lower()
    if role not in ("staff", "admin", "manager"):
        return jsonify({"ok": False, "error": "Invalid assignee"}), 400
    req = next((r for r in help_requests if r.get("id") == request_id), None)
    if not req:
        return jsonify({"ok": False, "error": "Request not found"}), 404
    accepted_ids = {r["request_id"] for r in accepted_requests}
    if request_id in accepted_ids:
        return jsonify({"ok": False, "error": "Request already accepted"}), 400
    accepted_at = _utc_iso_now()
    acc = {
        "request_id": request_id,
        "table": req["table"],
        "raised_at": req["raised_at"],
        "accepted_at": accepted_at,
        "accepted_by": assignee,
        "status": "on_the_way",
    }
    if req.get("note"):
        acc["note"] = req["note"]
    if req.get("category"):
        acc["category"] = req["category"]
    if req.get("urgent"):
        acc["urgent"] = True
    if req.get("quiet_preferred"):
        acc["quiet_preferred"] = True
    if req.get("allergens"):
        acc["allergens"] = req["allergens"]
    if req.get("location_id"):
        acc["location_id"] = req["location_id"]
    if req.get("extras") and isinstance(req.get("extras"), dict):
        acc["extras"] = req["extras"]
    accepted_requests.append(acc)
    try:
        _append_activity("admin_reassign_to_" + assignee, req["table"], request_id)
    except Exception:
        pass
    save_data()
    wh_r = {"request_id": request_id, "table": req["table"], "accepted_by": assignee, "reassigned": True}
    if req.get("extras"):
        wh_r["extras"] = req["extras"]
    _webhook("request.accepted", wh_r)
    return jsonify({"ok": True, "request_id": request_id, "assignee": assignee, "accepted_at": _to_chennai_time(accepted_at)})


@bp.route("/api/requests/accepted/<request_id>/status", methods=["PATCH", "POST"])
@login_required
def update_accepted_status(request_id):
    """Update status of an accepted request: at_table | done. Only the user who accepted can update."""
    data = request.get_json() or {}
    status = (data.get("status") or "").strip().lower()
    if status not in ("at_table", "done"):
        return jsonify({"ok": False, "error": "status must be at_table or done"}), 400
    for r in accepted_requests:
        if r["request_id"] == request_id and r["accepted_by"] == session["username"]:
            r["status"] = status
            if status == "done":
                r["completed_at"] = _utc_iso_now()
            try:
                _append_activity("status_" + status, r.get("table"), request_id)
            except Exception:
                pass
            save_data()
            if status == "done":
                _webhook(
                    "request.completed",
                    {
                        "request_id": request_id,
                        "table": r.get("table"),
                        "completed_by": session["username"],
                        "category": r.get("category"),
                    },
                )
            return jsonify({"ok": True, "status": status})
    return jsonify({"ok": False, "error": "Request not found or not yours"}), 404


def get_api_token():
    """Return the API token (from env or data.json). Call after load_data()."""
    return os.environ.get("SOULPLACE_API_TOKEN") or api_token


def require_api_token():
    """Return True if request is allowed. Browser form never sends token, so always allowed; external API can send token to match."""
    token = get_api_token()
    if not token:
        return True
    sent_auth = request.headers.get("Authorization", "")
    sent_api = request.headers.get("X-API-Token", "")
    sent_token = (sent_auth[7:].strip() if sent_auth.startswith("Bearer ") else "") or sent_api.strip()
    # No token sent → allow (customer form; no token needed)
    if not sent_token or not sent_token.strip():
        return True
    # Token sent → must match (for external API calls)
    return sent_token.strip() == token


@bp.route("/table/<int:table_num>")
def table_page_by_num(table_num):
    """URL like /soulplace/table/6: show request-help page with that table pre-filled (same as ?table=6)."""
    if table_num < 1 or table_num > NUM_TABLES:
        return redirect(url_for("main.table_page"))
    api_token = request.args.get("token", "").strip() or get_api_token()
    return render_template(
        "table.html",
        table=table_num,
        num_tables=NUM_TABLES,
        api_token=api_token or None,
        menu_groups=cafe_menu_groups or _default_cafe_menu_from_file(),
    )


@bp.route("/table")
def table_page():
    """Page for a table to request help. ?table=N pre-fills table number. ?token=API_TOKEN embeds token in link."""
    table = request.args.get("table", type=int)
    if table is None or table < 1 or table > NUM_TABLES:
        table = None
    # Use token from URL if present so "link with token" works when shared or in QR
    api_token = request.args.get("token", "").strip() or get_api_token()
    return render_template(
        "table.html",
        table=table,
        num_tables=NUM_TABLES,
        api_token=api_token or None,
        menu_groups=cafe_menu_groups or _default_cafe_menu_from_file(),
    )


@bp.route("/tables")
def tables_page():
    """Page showing all 10 tables with QR codes for scanning."""
    return render_template("tables.html", num_tables=NUM_TABLES, base_url=get_public_base_url())


@bp.route("/menu")
def redirect_menu():
    """Redirect /soulplace/menu to request-help (menu feature removed)."""
    return redirect(url_for("main.table_page"))


@bp.route("/notification-setup")
def notification_setup_page():
    """Show where to import notification details (file or Vercel env vars)."""
    return render_template("notification_setup.html")


@bp.route("/notification-test")
def notification_test_page():
    """Simple page to test each channel one by one (no login required)."""
    return render_template("notification_test.html")


@bp.route("/test-notify")
def test_notify():
    """Try sending a test. ?channel=email|telegram|sms|whatsapp = one channel only; else all."""
    channel = request.args.get("channel", "").strip().lower()
    try:
        if channel in ("email", "telegram", "sms", "whatsapp"):
            from notify import test_one_channel
            ok, msg = test_one_channel(channel)
            return jsonify({"channel": channel, "ok": ok, "message": msg})
        from notify import test_all_channels
        result = test_all_channels()
        result["message"] = "Check your email, Telegram, SMS, WhatsApp for a test message."
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "ok": False, "message": str(e)}), 500


@bp.route("/notification-status")
def notification_status():
    """Show which notification channels are configured (no secrets). Helps debug 'not working'."""
    try:
        from notify import _env, _cfg, _get_config
        _get_config()
        email_ok = bool(_env("SOULPLACE_SMTP_USER") or _cfg("email", "smtp_user"))
        telegram_ok = bool(_env("TELEGRAM_BOT_TOKEN") or _cfg("telegram", "bot_token"))
        sms_ok = bool(_env("SOULPLACE_SMS_TO") or _cfg("sms", "to"))
        callme = (_env("CALLMEBOT_WHATSAPP_PHONE") or _cfg("whatsapp", "phone")) and (_env("CALLMEBOT_WHATSAPP_APIKEY") or _cfg("whatsapp", "apikey"))
        wabridge = (_env("WABRIDGE_API_KEY") or _cfg("whatsapp", "wabridge_api_key")) and (_env("SOULPLACE_WHATSAPP_TO") or _cfg("whatsapp", "to") or _env("SOULPLACE_SMS_TO") or _cfg("sms", "to"))
        green = (_env("GREEN_API_ID_INSTANCE") or _cfg("whatsapp", "green_api_id_instance")) and (_env("GREEN_API_TOKEN") or _cfg("whatsapp", "green_api_token")) and (_env("SOULPLACE_WHATSAPP_TO") or _cfg("whatsapp", "to") or _env("SOULPLACE_SMS_TO") or _cfg("sms", "to"))
        wa_ok = bool(callme or wabridge or green)
    except Exception:
        email_ok = telegram_ok = sms_ok = wa_ok = False
    return jsonify({
        "email": email_ok,
        "telegram": telegram_ok,
        "sms": sms_ok,
        "whatsapp": wa_ok,
        "hint": "Set env vars or notifications.json.",
    })


@bp.route("/links")
def links_page():
    """Page that shows login link and table links (with API token) for long-distance use (copy and share). Works in live (Vercel) with explicit paths."""
    try:
        base = get_public_base_url()
    except Exception:
        base = DEFAULT_PUBLIC_URL.rstrip("/")
    if not base or not base.startswith("http"):
        base = DEFAULT_PUBLIC_URL.rstrip("/")
    base = base.rstrip("/")
    prefix = (URL_PREFIX or "/soulplace").rstrip("/")
    login_link = base + prefix + "/login"
    dashboard_link = base + prefix + "/dashboard"
    payments_link = base + prefix + "/payments"
    tables_link = base + prefix + "/tables"
    token = get_api_token()
    table_links = []
    n = max(1, min(NUM_TABLES, 999))
    for t in range(1, n + 1):
        url = base + prefix + "/table?table=" + str(t)
        if token:
            url += "&token=" + token
        table_links.append({"table": t, "url": url})
    return render_template(
        "links.html",
        login_link=login_link,
        dashboard_link=dashboard_link,
        payments_link=payments_link,
        tables_link=tables_link,
        table_links=table_links,
    )


def _get_local_lan_ip():
    """Get this machine's LAN IP so QR codes work when scanned from phone on same WiFi (not 127.0.0.1)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip if ip and ip != "127.0.0.1" else None
    except Exception:
        return None


def get_public_base_url():
    """Base URL for links and QR codes. Uses env SOULPLACE_PUBLIC_URL if set, else the host you're visiting, else DEFAULT_PUBLIC_URL.
    On Vercel we prefer X-Forwarded-Host so links always use the real live URL."""
    explicit = os.environ.get("SOULPLACE_PUBLIC_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme) or "https"
    host = request.headers.get("X-Forwarded-Host") or getattr(request, "host", None)
    if host and "," in host:
        host = host.split(",")[0].strip()
    # On Vercel, if we still don't have a proper host (e.g. serverless host), use default live URL
    if os.environ.get("VERCEL") and (not host or "vercel.app" not in host):
        return DEFAULT_PUBLIC_URL.rstrip("/")
    # When running locally via 127.0.0.1/localhost, use LAN IP so QR scan on phone works (same WiFi)
    if not os.environ.get("VERCEL") and host:
        host_lower = host.lower()
        if "127.0.0.1" in host_lower or "localhost" in host_lower:
            port = ""
            if ":" in host:
                port = ":" + host.split(":")[-1]
            lan = _get_local_lan_ip()
            if lan:
                host = lan + port
    base = f"{scheme}://{host}".rstrip("/") if host else ""
    if not base or not base.startswith("http"):
        base = DEFAULT_PUBLIC_URL.rstrip("/")
    return base


@bp.route("/qr")
def qr_image_general():
    """Serve QR code for the general request-help page (no table prefilled). Staff can scan to open request form."""
    base_url = get_public_base_url().rstrip("/")
    help_url = base_url + url_for("main.table_page")
    lang = (request.args.get("lang") or "").strip().lower()
    if lang in ("en", "ta", "te", "kn", "ml", "hi", "ur", "bn", "gu", "mr", "pa"):
        help_url += "&lang=" + lang if "?" in help_url else "?lang=" + lang
    token = get_api_token()
    if token:
        help_url += "&token=" + token if "?" in help_url else "?token=" + token
    qr = qrcode.QRCode(version=1, box_size=10, border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(help_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a1a", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.read(), mimetype="image/png")


@bp.route("/qr/<int:table_num>")
def qr_image(table_num):
    """Serve QR code image for the given table (1–10). Link includes API token so scan works."""
    if table_num < 1 or table_num > NUM_TABLES:
        return "Invalid table", 404
    base_url = get_public_base_url()
    path = url_for("main.table_page", table=table_num)
    help_url = base_url + path
    lang = (request.args.get("lang") or "").strip().lower()
    if lang in ("en", "ta", "te", "kn", "ml", "hi", "ur", "bn", "gu", "mr", "pa"):
        help_url += "&lang=" + lang if "?" in help_url else "?lang=" + lang
    token = get_api_token()
    if token:
        help_url += "&token=" + token if "?" in help_url else "?token=" + token
    qr = qrcode.QRCode(version=1, box_size=10, border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(help_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a1a", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.read(), mimetype="image/png")


def _send_web_push_to_all(table, request_id, note=None, urgent=False):
    """Send Web Push to all subscribed devices and return diagnostics."""
    global last_push_debug
    stats = {
        "ok": True,
        "attempted": 0,
        "sent": 0,
        "failed": 0,
        "removed_stale": 0,
        "error": "",
    }
    if not push_subscriptions:
        stats["ok"] = False
        stats["error"] = "No push subscriptions saved."
        last_push_debug = dict(stats)
        return stats
    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    if not vapid_private:
        stats["ok"] = False
        stats["error"] = "VAPID_PRIVATE_KEY is not set."
        last_push_debug = dict(stats)
        return stats
    try:
        import pywebpush

        title = "Soulplace – New help request"
        body = "Table " + str(table) + " needs a Soul."
        if note:
            body += " – " + (note[:80] + "…" if len(note) > 80 else note)
        if urgent:
            title = "Soulplace – Urgent: Table " + str(table)
        base = get_public_base_url().rstrip("/")
        sound_url = base + "/static/sounds/maroon_5_animals.mp3"
        payload = json.dumps({"title": title, "body": body, "sound": sound_url})
        vapid_claims = {"sub": os.environ.get("VAPID_SUB", "mailto:soulplace@localhost")}
        stale_endpoints = set()
        for sub in list(push_subscriptions):
            if not isinstance(sub, dict) or not sub.get("endpoint"):
                continue
            stats["attempted"] += 1
            try:
                pywebpush.webpush(
                    subscription_info=sub,
                    data=payload,
                    vapid_private_key=vapid_private,
                    vapid_claims=vapid_claims,
                )
                stats["sent"] += 1
            except Exception as e:
                stats["failed"] += 1
                msg = str(e)
                if not stats["error"]:
                    stats["error"] = msg
                if "410" in msg or "404" in msg:
                    stale_endpoints.add(sub.get("endpoint"))
        if stale_endpoints:
            push_subscriptions[:] = [
                s for s in push_subscriptions if not (isinstance(s, dict) and s.get("endpoint") in stale_endpoints)
            ]
            stats["removed_stale"] = len(stale_endpoints)
            save_data()
        if stats["sent"] == 0:
            stats["ok"] = False
            if not stats["error"]:
                stats["error"] = "Push send failed for all subscriptions."
        last_push_debug = dict(stats)
        return stats
    except Exception as e:
        stats["ok"] = False
        stats["error"] = str(e)
        last_push_debug = dict(stats)
        return stats


@bp.route("/sw.js")
def service_worker():
    """Serve service worker so it can be registered with scope /soulplace/ (for push when screen off)."""
    sw_path = Path(__file__).parent / "static" / "sw.js"
    if not sw_path.is_file():
        return "// no sw", 404, {"Content-Type": "application/javascript; charset=utf-8"}
    with open(sw_path, "r", encoding="utf-8") as f:
        body = f.read()
    resp = make_response(body)
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@bp.route("/api/push-vapid-public", methods=["GET"])
@login_required
def push_vapid_public():
    """Return the VAPID public key for the frontend to subscribe to push."""
    key = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    if not key:
        return jsonify({"publicKey": None, "message": "VAPID_PUBLIC_KEY not set"})
    return jsonify({"publicKey": key})


@bp.route("/api/push-subscribe", methods=["POST"])
@login_required
def push_subscribe():
    """Store a Web Push subscription so we can send notifications when screen is off."""
    global push_subscriptions
    data = request.get_json() or {}
    endpoint = data.get("endpoint")
    keys = data.get("keys")
    if not endpoint or not isinstance(keys, dict) or not keys.get("p256dh") or not keys.get("auth"):
        return jsonify({"ok": False, "error": "Invalid subscription"}), 400
    sub = {"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}}
    # Replace existing subscription with same endpoint
    push_subscriptions[:] = [s for s in push_subscriptions if isinstance(s, dict) and s.get("endpoint") != endpoint]
    push_subscriptions.append(sub)
    save_data()
    return jsonify({"ok": True, "message": "Subscribed. You'll get notifications even when screen is off."})


@bp.route("/api/push-status", methods=["GET"])
@login_required
def push_status():
    """Return Web Push debug info (count + whether VAPID keys are present)."""
    try:
        vapid_private_set = bool(os.environ.get("VAPID_PRIVATE_KEY", "").strip())
        vapid_public_set = bool(os.environ.get("VAPID_PUBLIC_KEY", "").strip())
        # Avoid returning huge payloads; endpoints are not secrets but can be long.
        subs = []
        for s in push_subscriptions[:5]:
            if isinstance(s, dict) and s.get("endpoint"):
                subs.append({"endpoint": s.get("endpoint")})
        return jsonify(
            {
                "ok": True,
                "push_subscriptions_count": len(push_subscriptions),
                "vapid_private_key_set": vapid_private_set,
                "vapid_public_key_set": vapid_public_set,
                "saved_endpoints_sample": subs,
                "last_push_debug": last_push_debug or {},
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/push-test", methods=["POST"])
@login_required
def push_test():
    """Send a test Web Push to all saved subscriptions (admin only)."""
    try:
        if session.get("role") != "admin":
            return jsonify({"ok": False, "error": "admin only"}), 403
        count = len(push_subscriptions)
        if count == 0:
            return jsonify({"ok": False, "error": "No subscriptions saved yet. Enable notifications on devices first."}), 400
        # Uses the same push pipeline as real requests.
        result = _send_web_push_to_all("Test", "test-" + str(int(datetime.now(timezone.utc).timestamp())), note="Test push", urgent=False)
        if result.get("ok"):
            return jsonify(
                {
                    "ok": True,
                    "message": "Test push sent.",
                    "subscriptions_count": count,
                    "attempted": result.get("attempted", 0),
                    "sent": result.get("sent", 0),
                    "failed": result.get("failed", 0),
                    "removed_stale": result.get("removed_stale", 0),
                }
            )
        return jsonify(
            {
                "ok": False,
                "error": result.get("error") or "Push test failed.",
                "subscriptions_count": count,
                "attempted": result.get("attempted", 0),
                "sent": result.get("sent", 0),
                "failed": result.get("failed", 0),
                "removed_stale": result.get("removed_stale", 0),
            }
        ), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/request/create", methods=["POST"])
def create_request():
    """Create a new help request (e.g. from a table terminal or QR scan). No API token required – form always works."""
    global requests_paused
    idem_key = (request.headers.get("Idempotency-Key") or "").strip()[:128]
    if _effective_requests_paused():
        return jsonify({"ok": False, "error": "Requests are currently paused (quiet hours)."}), 503
    if idem_key:
        cached = _idempotency_take_create(idem_key)
        if cached is not None:
            return jsonify(cached)
    data = request.get_json() or request.form or {}
    table = data.get("table")
    if table is None:
        return jsonify({"ok": False, "error": "table required"}), 400
    try:
        table = int(table)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "table must be a number"}), 400
    if table < 1 or table > NUM_TABLES:
        return jsonify({"ok": False, "error": f"table must be 1–{NUM_TABLES}"}), 400
    ok, retry_after = _rate_limit_allow(table)
    if not ok:
        resp = jsonify({"ok": False, "error": "Please wait before sending another request from this table.", "retry_after_seconds": retry_after})
        resp.headers["Retry-After"] = str(min(retry_after or RATE_LIMIT_SECONDS, 120))
        return resp, 429
    accepted_ids = {r["request_id"] for r in accepted_requests}
    for r in help_requests:
        if int(r.get("table") or 0) != table:
            continue
        rid = r.get("id")
        if rid in accepted_ids:
            continue
        return jsonify(
            {
                "ok": True,
                "id": str(rid),
                "raised_at": r.get("raised_at"),
                "duplicate": True,
                "message": "You already have a pending request for this table. We're on it.",
            }
        )
    note = (data.get("note") or "").strip()[:500]
    category = (data.get("category") or "").strip()[:100] or None
    urgent = bool(data.get("urgent") if isinstance(data.get("urgent"), bool) else str(data.get("urgent", "")).strip().lower() in ("1", "true", "yes"))
    quiet_preferred = bool(
        data.get("quiet_preferred")
        if isinstance(data.get("quiet_preferred"), bool)
        else str(data.get("quiet_preferred", "")).strip().lower() in ("1", "true", "yes")
    )
    loc = (data.get("location_id") or data.get("location") or (APP_CONFIG or {}).get("default_location_id") or "").strip()[:64] or None
    allergens_raw = data.get("allergens")
    allergens = None
    if isinstance(allergens_raw, list):
        allergens = [str(x).strip()[:80] for x in allergens_raw[:12] if str(x).strip()]
    elif isinstance(allergens_raw, str) and allergens_raw.strip():
        allergens = [allergens_raw.strip()[:200]]
    extras_payload: dict = {}
    extras_err = None
    if sreg:
        extras_payload, extras_err = sreg.parse_and_validate_extras(data, app_config=APP_CONFIG or {}, table=table)
    if extras_err:
        return jsonify({"ok": False, "error": extras_err}), 403
    new_id = str(max((int(r.get("id", 0)) for r in help_requests), default=0) + 1)
    raised_at = _utc_iso_now()
    req = {"id": new_id, "table": table, "raised_at": raised_at}
    if note:
        req["note"] = note
    if category:
        req["category"] = category
    if urgent:
        req["urgent"] = True
    if quiet_preferred:
        req["quiet_preferred"] = True
    if loc:
        req["location_id"] = loc
    if allergens:
        req["allergens"] = allergens
    if extras_payload:
        req["extras"] = extras_payload
    help_requests.append(req)
    hist_row = {"id": new_id, "table": table, "raised_at": raised_at, "note": note, "category": category, "urgent": urgent}
    if quiet_preferred:
        hist_row["quiet_preferred"] = True
    if loc:
        hist_row["location_id"] = loc
    if allergens:
        hist_row["allergens"] = allergens
    if extras_payload:
        hist_row["extras"] = extras_payload
    request_history.append(hist_row)
    save_data()
    _send_web_push_to_all(table, new_id, note, urgent)
    if os.environ.get("SOULPLACE_NOTIFY_MIRROR", "1") != "0":
        try:
            from notify import notify_new_help_request

            notify_new_help_request(table, note or None)
        except Exception:
            pass
    if spx and spx.feature_enabled("webhooks"):
        try:
            wh = {"table": table, "id": new_id, "urgent": urgent, "category": category, "location_id": loc}
            if extras_payload:
                wh["extras"] = extras_payload
            spx.outbound_webhooks("request.created", wh)
        except Exception:
            pass
    body = {"ok": True, "id": new_id, "raised_at": raised_at}
    if idem_key:
        _idempotency_store_create(idem_key, body)
    return jsonify(body)


app.register_blueprint(bp)


@app.route("/")
def root():
    """Redirect root straight to login so the main link shows the login screen."""
    return redirect(url_for("main.login"))


# Redirect typo URLs (e.g. /login without /soulplace) so users don't get 404
@app.route("/login")
def redirect_login():
    return redirect(url_for("main.login"))


@app.route("/menu")
def redirect_menu_root():
    return redirect(url_for("main.table_page"))


@app.route("/table")
def redirect_table():
    t = request.args.get("table", type=int)
    if t and 1 <= t <= NUM_TABLES:
        return redirect(url_for("main.table_page", table=t))
    return redirect(url_for("main.table_page"))

@app.route("/tables")
def redirect_tables():
    return redirect(url_for("main.tables_page"))

@app.route("/links")
def redirect_links():
    return redirect(url_for("main.links_page"))

@app.route("/dashboard")
def redirect_dashboard():
    return redirect(url_for("main.dashboard"))

@app.route("/notification-setup")
def redirect_notification_setup():
    return redirect(url_for("main.notification_setup_page"))

@app.route("/notification-status")
def redirect_notification_status():
    return redirect(url_for("main.notification_status"))

@app.route("/notification-test")
def redirect_notification_test():
    return redirect(url_for("main.notification_test_page"))


@app.route("/admin/menu")
def redirect_admin_menu():
    return redirect(url_for("main.admin_menu_page"))


@app.route("/admin/system")
def redirect_admin_system():
    return redirect(url_for("main.admin_system_page"))


def _local_ip():
    """Get this machine's local IP so phone/tablet on same Wi‑Fi can connect."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    load_data()
    seed_demo_requests()
    ip = _local_ip()
    base_pc = f"http://127.0.0.1:5000{URL_PREFIX}"
    base_phone = f"http://{ip}:5000{URL_PREFIX}"
    login_url = f"{base_pc}/login"
    print("\n" + "=" * 50)
    print("  SOULPLACE HELP DESK - SERVER RUNNING")
    print("=" * 50)
    print(f"\n  >>> OPEN THIS LINK IN BROWSER (PC):\n      {login_url}\n")
    print(f"  >>> ON PHONE (same Wi-Fi), open:\n      {base_phone}/login\n")
    print("  Keep this window open. Press Ctrl+C to stop.")
    print("=" * 50 + "\n")
    app.run(debug=True, port=5000, host="0.0.0.0")
