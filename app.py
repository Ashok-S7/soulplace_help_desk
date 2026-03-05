"""
Soulplace Boardgames Help Desk
Flask backend: login (admins + staff), dashboard, help requests, QR codes, API token.
"""
import io
import json
import os
import re
import secrets
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path

import qrcode
from flask import Flask, Blueprint, Response, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SOULPLACE_SECRET_KEY", "soulplace-help-desk-secret-key-change-in-production")

# URL prefix so you get links like https://your-app.vercel.app/soulplace (same style as .../game-guru)
URL_PREFIX = os.environ.get("SOULPLACE_URL_PREFIX", "/soulplace").rstrip("/") or ""
bp = Blueprint("main", __name__, url_prefix=URL_PREFIX)

# Storage: Vercel uses /tmp; local uses project dir so it works when you run it.
DATA_FILE = (
    Path("/tmp/soulplace_data.json")
    if os.environ.get("VERCEL")
    else Path(__file__).parent / "data.json"
)

# Admins: (display_name, password)
ADMINS = [
    ("ASHOK", "SoulOfBlue#7"),
    ("BOO", "SoulOfblack#7"),
]

# Staff: (display_name, password)
STAFF = [
    ("BALA MURUGAN", "DarkSoul@7"),
    ("RAJESH", "BlueSoul!92"),
    ("RITHISH", "SilentSoul#66"),
    ("LOKESH", "CyberSoul@501"),
    ("DILLI BABU", "SoulWave#309"),
]

# Login key (lowercase, stripped) -> {password, display_name, role}
USER_DB = {}
for name, pwd in ADMINS:
    USER_DB[name.strip().lower()] = {"password": pwd, "display_name": name.strip(), "role": "admin"}
for name, pwd in STAFF:
    USER_DB[name.strip().lower()] = {"password": pwd, "display_name": name.strip(), "role": "staff"}

NUM_TABLES = 10

# In-memory state
help_requests = []
accepted_requests = []
api_token = None


def load_data():
    global help_requests, accepted_requests, api_token
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                help_requests[:] = data.get("help_requests", [])
                accepted_requests[:] = data.get("accepted_requests", [])
                api_token = data.get("api_token") or os.environ.get("SOULPLACE_API_TOKEN")
        except (json.JSONDecodeError, IOError):
            pass
    if api_token is None:
        api_token = os.environ.get("SOULPLACE_API_TOKEN") or secrets.token_urlsafe(32)
        save_data()


def save_data():
    if not os.environ.get("VERCEL"):
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "help_requests": help_requests,
        "accepted_requests": accepted_requests,
    }
    if api_token is not None and not os.environ.get("SOULPLACE_API_TOKEN"):
        payload["api_token"] = api_token
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


# Chennai (IST) = UTC+5:30
CHENNAI_TZ = timezone(timedelta(hours=5, minutes=30))


def _utc_iso_now():
    """Current time in UTC as ISO string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    """Add demo requests if none exist."""
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
    load_data()
    seed_demo_requests()


def login_required(f):
    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)

    return wrapped


@bp.route("/")
def index():
    return redirect(url_for("main.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        if username in USER_DB and USER_DB[username]["password"] == password:
            session["username"] = username
            session["display_name"] = USER_DB[username]["display_name"]
            session["role"] = USER_DB[username]["role"]
            return redirect(url_for("main.dashboard"))
        return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html", error=None)


@bp.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("display_name", None)
    session.pop("role", None)
    return redirect(url_for("main.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    display = session.get("display_name") or session.get("username", "").capitalize()
    is_admin = session.get("role") == "admin"
    return render_template(
        "dashboard.html",
        username=display,
        is_admin=is_admin,
    )


@bp.route("/api/requests", methods=["GET"])
@login_required
def list_requests():
    """Return pending help requests (not yet accepted). Times in Chennai (IST)."""
    accepted_ids = {r["request_id"] for r in accepted_requests}
    pending = [
        {"id": r["id"], "table": r["table"], "raised_at": _to_chennai_time(r["raised_at"])}
        for r in help_requests
        if r["id"] not in accepted_ids
    ]
    return jsonify({"requests": pending})


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
    accepted_requests.append(
        {
            "request_id": request_id,
            "table": req["table"],
            "raised_at": req["raised_at"],
            "accepted_at": accepted_at,
            "accepted_by": session["username"],
        }
    )
    save_data()
    return jsonify({"ok": True, "accepted_at": _to_chennai_time(accepted_at)})


@bp.route("/api/settings/token", methods=["GET"])
@login_required
def get_token():
    """Return API token for admins (for use in Vercel env or external API)."""
    if session.get("role") != "admin":
        return jsonify({"error": "Admin only"}), 403
    return jsonify({"api_token": get_api_token()})


@bp.route("/api/requests/accepted", methods=["GET"])
@login_required
def list_accepted():
    """Return requests accepted by current user. Times in Chennai (IST)."""
    username = session["username"]
    mine = [
        {
            "table": r["table"],
            "raised_at": _to_chennai_time(r["raised_at"]),
            "accepted_at": _to_chennai_time(r["accepted_at"]),
        }
        for r in accepted_requests
        if r["accepted_by"] == username
    ]
    return jsonify({"accepted": mine})


def get_api_token():
    """Return the API token (from env or stored). Call after load_data()."""
    return os.environ.get("SOULPLACE_API_TOKEN") or api_token


def require_api_token():
    """Return True if request is allowed. Phone/browser form requests work without token; external API can use token."""
    token = get_api_token()
    if not token:
        return True
    sent_auth = request.headers.get("Authorization", "")
    sent_api = request.headers.get("X-API-Token", "")
    sent_token = (sent_auth[7:].strip() if sent_auth.startswith("Bearer ") else "") or sent_api.strip()
    # No token sent → allow (browser/phone form; customers never need to enter API token)
    if not sent_token:
        return True
    # Token sent → must match
    return sent_token == token


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
    )


@bp.route("/tables")
def tables_page():
    """Page showing all 10 tables with QR codes for scanning."""
    return render_template("tables.html", num_tables=NUM_TABLES, base_url=get_public_base_url())


@bp.route("/links")
def links_page():
    """Page that shows login link and table links (with API token) for long-distance use (copy and share)."""
    base = get_public_base_url()
    token = get_api_token()
    login_link = base + url_for("main.login")
    tables_link = base + url_for("main.tables_page")
    # Build table links that already include the API token so they work when opened
    table_links = []
    for t in range(1, NUM_TABLES + 1):
        url = base + url_for("main.table_page", table=t)
        if token:
            url += "&token=" + token if "?" in url else "?token=" + token
        table_links.append({"table": t, "url": url})
    return render_template(
        "links.html",
        login_link=login_link,
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
    """Base URL for links and QR codes. Uses env SOULPLACE_PUBLIC_URL if set, else X-Forwarded-* / request host.
    When running locally (127.0.0.1), uses LAN IP so scanned QR codes work on phone on same WiFi."""
    explicit = os.environ.get("SOULPLACE_PUBLIC_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme) or "https"
    host = request.headers.get("X-Forwarded-Host", request.host) or request.host
    if "," in host:
        host = host.split(",")[0].strip()
    # When accessed via 127.0.0.1 or localhost, use LAN IP so QR scan on phone works (same WiFi)
    if not os.environ.get("VERCEL"):
        host_lower = host.lower()
        if "127.0.0.1" in host_lower or "localhost" in host_lower:
            port = ""
            if ":" in host:
                port = ":" + host.split(":")[-1]
            lan = _get_local_lan_ip()
            if lan:
                host = lan + port
    return f"{scheme}://{host}".rstrip("/")


@bp.route("/qr/<int:table_num>")
def qr_image(table_num):
    """Serve QR code image for the given table (1–10). Link includes API token so scan works."""
    if table_num < 1 or table_num > NUM_TABLES:
        return "Invalid table", 404
    base_url = get_public_base_url()
    path = url_for("main.table_page", table=table_num)
    help_url = base_url + path
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


@bp.route("/api/request/create", methods=["POST"])
def create_request():
    """Create a new help request (e.g. from a table terminal or QR scan). Requires API token when set."""
    if not require_api_token():
        return jsonify({"ok": False, "error": "Invalid or missing API token"}), 401
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
    new_id = str(max((int(r.get("id", 0)) for r in help_requests), default=0) + 1)
    raised_at = _utc_iso_now()
    help_requests.append({"id": new_id, "table": table, "raised_at": raised_at})
    save_data()
    return jsonify({"ok": True, "id": new_id, "raised_at": raised_at})


app.register_blueprint(bp)


@app.route("/")
def root():
    """Redirect root straight to login so the main link shows the login screen."""
    return redirect(url_for("main.login"))


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
