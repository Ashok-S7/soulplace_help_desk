# Soulplace Help Desk – Mini Project Documentation

**Project:** Soulplace Boardgames Help Desk  
**Type:** Mini Project (College)  
**Domain:** Web Application – Restaurant/Café Table Service Management

---

## 1. Introduction

**Soulplace Help Desk** is a web-based help-request system for **Soulplace Boardgames** (a board-game café). It lets **customers at tables** request staff help (e.g. orders, queries) from their phone or tablet, and **staff/admin** see all requests on a dashboard, accept them, and get sound/notification when new requests arrive.

### 1.1 Problem Statement

- Customers had no quick way to call staff without leaving their table.
- Staff had no central view of which tables needed help.
- Manual tracking of “who asked for what” was error-prone.

### 1.2 Solution

A single web app where:

- **Customers** open a link (or scan a QR code on their table), enter table number and optional note, and submit a “Request help.”
- **Staff/Admin** log in, see pending help requests with table numbers and notes, and mark “I’m attending.” They get browser sound and notification when a new request is raised.

---

## 2. Features

| Feature | Description |
|--------|-------------|
| **Customer – Request help** | Form: table number (1–N), optional “What you need” note. Works from any device. |
| **QR codes per table** | One QR per table; scan opens the request-help page with that table pre-filled. |
| **Staff/Admin login** | Role-based login (admin / staff) with credentials from `config.json`. |
| **Dashboard** | Lists pending help requests (table, time in IST, note). Only last 2 hours shown to avoid clutter. |
| **Accept request** | Staff click “I’m attending” to move a request to “Accepted” and track who is handling it. |
| **Sound & notifications** | Optional browser notification and sound when a new request arrives (after first load). |
| **Clear all pending** | Button to clear all pending and accepted requests (e.g. for testing or end of day). |
| **Links page** | Central page with login, dashboard, table links, and table links with API token for sharing. |
| **API token** | Optional token for server-to-server or external calls to create help requests. |
| **IST (Chennai) time** | All displayed times in Indian Standard Time (UTC+5:30). |

---

## 3. Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3, Flask (WSGI) |
| **Frontend** | HTML5, CSS3, JavaScript (vanilla) |
| **Templates** | Jinja2 (Flask) |
| **Storage** | JSON files (`data.json`, `config.json`) – no database |
| **QR codes** | `qrcode` (Python) + Pillow |
| **Deployment** | Vercel (serverless); local run via Flask dev server |
| **Version control** | Git; repo can be connected to GitHub for Vercel deploy |

---

## 4. System Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    SOULPLACE HELP DESK                   │
                    └─────────────────────────────────────────────────────────┘
                                              │
         ┌───────────────────────────────────┼───────────────────────────────────┐
         │                                   │                                   │
         ▼                                   ▼                                   ▼
  ┌──────────────┐                   ┌──────────────┐                   ┌──────────────┐
  │   CUSTOMER   │                   │    STAFF     │                   │    ADMIN     │
  │  (Table/QR)  │                   │  (Dashboard) │                   │ (Dashboard +  │
  │              │                   │              │                   │  API token)   │
  └──────┬───────┘                   └──────┬───────┘                   └──────┬───────┘
         │                                  │                                   │
         │  POST /api/request/create        │  GET /api/requests                 │
         │  (table, note)                   │  POST /api/requests/accept        │
         │                                  │  GET /api/requests/accepted        │
         └──────────────────────────────────┼───────────────────────────────────┘
                                            │
                                            ▼
                                    ┌───────────────┐
                                    │  Flask App    │
                                    │  (app.py)     │
                                    │  - Sessions   │
                                    │  - JSON data │
                                    └───────┬───────┘
                                            │
                                            ▼
                                    ┌───────────────┐
                                    │ data.json     │  ← help_requests, accepted_requests, api_token
                                    │ config.json   │  ← num_tables, admins, staff
                                    └───────────────┘
```

- **Customer flow:** Open `/soulplace/table` (or table-specific URL/QR) → submit form → request stored in `data.json`.
- **Staff flow:** Login at `/soulplace/login` → Dashboard at `/soulplace/dashboard` → view pending requests, accept, hear sound on new request.
- **Admin:** Same as staff, plus API token visible on dashboard and optional use in env for serverless.

---

## 5. Project Structure

```
soulplace_help_desk/
├── app.py                 # Main Flask app: routes, API, config load, QR
├── api/
│   └── index.py           # Vercel serverless entry (imports app)
├── templates/
│   ├── login.html         # Staff/Admin login
│   ├── dashboard.html     # Help requests + accepted + (admin) API token
│   ├── table.html         # Customer “Request help” form
│   ├── tables.html        # All table QR codes
│   └── links.html         # All important links (login, dashboard, tables, table links)
├── static/
│   ├── css/style.css      # Global styles
│   ├── js/app.js          # Dashboard: fetch requests, accept, clear, notifications
│   ├── images/            # Logo, etc.
│   └── sounds/            # Notification sound (optional)
├── config.json            # num_tables, admins[], staff[] (passwords in plain text – change in production)
├── data.json              # help_requests, accepted_requests, api_token (created at run time)
├── requirements.txt       # flask, qrcode[pil], Pillow
├── vercel.json            # Build + rewrites to /api/index
└── DOCUMENTATION.md       # This file
```

---

## 6. How It Works

### 6.1 Customer (Request help)

1. Customer opens **Request help** link or scans **table QR** (e.g. Table 3).
2. Page shows table number (pre-filled if from QR) and optional “What you need.”
3. On submit, frontend sends `POST /soulplace/api/request/create` with `table` and `note`.
4. Backend appends a new help request to `data.json` and returns success.
5. Staff see the new request on the dashboard (and get sound/notification if enabled).

### 6.2 Staff / Admin (Dashboard)

1. Staff/Admin open **Login** link and enter credentials (from `config.json`).
2. After login, redirect to **Dashboard**.
3. Dashboard fetches **pending** requests (`GET /soulplace/api/requests`) every few seconds; only requests from the **last 2 hours** are shown.
4. For each request, staff can click **“I’m attending”** → `POST /soulplace/api/requests/accept` with `request_id` → request moves to “Accepted” and is stored in `data.json`.
5. **“Clear all pending”** clears all help and accepted records (for testing or reset).
6. **Links** page gives login, dashboard, tables, and per-table request links (with optional API token).

### 6.3 QR Codes

- **All tables:** `/soulplace/tables` shows a grid of QR codes, one per table. Each QR encodes the request-help URL for that table (and optional token).
- **Single table:** `/soulplace/qr/<table_num>` returns a PNG image of the QR for that table. Café can print and place one per table.

---

## 7. Setup and Installation

### 7.1 Prerequisites

- Python 3.8+
- pip

### 7.2 Local run

```bash
cd soulplace_help_desk
pip install -r requirements.txt
python app.py
```

- App runs at `http://127.0.0.1:5000/soulplace` (or with LAN IP printed in console for same-WiFi access).
- Open: `http://127.0.0.1:5000/soulplace/login` for staff, `http://127.0.0.1:5000/soulplace/table` for request help.

### 7.3 Configuration

- **config.json:** Set `num_tables`, and list of `admins` and `staff` with `name` and `password`. Edit and restart (or redeploy).
- **data.json:** Created automatically; holds help requests, accepted requests, and API token. On Vercel, data is stored under `/tmp` (ephemeral unless you switch to a DB).

---

## 8. Deployment (Vercel)

1. Push the project to a Git repository (e.g. GitHub).
2. In Vercel, create a new project and import that repository.
3. Set **Root Directory** to the folder that contains `app.py` (e.g. `soulplace_help_desk`).
4. (Optional) Add environment variable: `SOULPLACE_API_TOKEN` for API access; `SOULPLACE_SECRET_KEY` for session security; `SOULPLACE_PUBLIC_URL` if base URL differs.
5. Deploy. All routes are served via `vercel.json` rewrites to `api/index.py`, which imports the Flask `app`.

**Live base URL (example):**  
`https://soulplace-help-desk.vercel.app/soulplace`

---

## 9. API Summary

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/soulplace/api/request/create` | Optional token | Create help request (table, note). Used by customer form. |
| GET | `/soulplace/api/requests` | Login | List pending help requests (last 2 hours). |
| POST | `/soulplace/api/requests/accept` | Login | Accept a request by `request_id`. |
| GET | `/soulplace/api/requests/accepted` | Login | List requests accepted by current user. |
| POST | `/soulplace/api/requests/clear` | Login | Clear all help and accepted requests. |
| GET | `/soulplace/api/settings/token` | Admin | Get API token. |

---

## 10. Screenshots (For Presentation)

You can add screenshots here when presenting at college:

1. **Customer – Request help page** (table form + optional note).
2. **Tables page** (grid of QR codes).
3. **Staff login page.**
4. **Dashboard** (pending requests + “I’m attending” + accepted list).
5. **Links page** (all shareable links).

---

## 11. Future Enhancements

- Replace JSON storage with a database (e.g. SQLite/PostgreSQL) for persistence on Vercel.
- Add simple analytics (e.g. requests per day, average response time).
- Optional SMS or WhatsApp notification to staff on new request.
- Multi-branch support (different tables per branch).

---

## 12. References

- Flask: https://flask.palletsprojects.com/
- Vercel: https://vercel.com/docs
- QR Code (Python): https://pypi.org/project/qrcode/

---

## 13. Team / Author

*[Add your name, roll number, department, college name, and year here.]*

---

*This document is for the Soulplace Help Desk mini project submission at college.*
