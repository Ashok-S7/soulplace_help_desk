# Get your URL & API token (Vercel + Chrome)

---

## Use on your phone (when running on PC)

**`127.0.0.1` only works on the same computer.** To open the app on your phone:

1. **Same Wi‑Fi:** Phone and PC must be on the same Wi‑Fi.
2. **Start the app:** Run `run.bat` or `python app.py` in `soulplace_help_desk`.
3. **Use the URL shown in the terminal:** It will look like `http://192.168.x.x:5000/soulplace/login`. Type that exact URL in your phone’s browser (Chrome, etc.).

If you deploy to Vercel, use your Vercel URL on the phone — that works from anywhere.

---

## 1. Get your URL link (Vercel)

You get the URL **only after you deploy** to Vercel. Follow these steps:

1. **Push code to GitHub**
   - Create a repo at [github.com/new](https://github.com/new).
   - In terminal:
     ```bash
     cd "c:\mini project"
     git init
     git add soulplace_help_desk
     git commit -m "Soulplace Help Desk"
     git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
     git push -u origin main
     ```

2. **Deploy on Vercel**
   - Go to **[vercel.com/new](https://vercel.com/new)** and sign in with GitHub.
   - Click **Import** on your repo.
   - Set **Root Directory** to: `soulplace_help_desk`.
   - Click **Deploy**.

3. **Copy your URL**
   - After deploy, Vercel shows: **“Your project has been deployed.”**
   - Your link is there, e.g.: `https://soulplace-help-desk-abc123.vercel.app`
   - **Login link (use from anywhere):** `https://YOUR-URL/soulplace/login`
   - **Copy your links:** Open `https://YOUR-URL/soulplace/links` — that page shows the login link and all table links to copy and share (e.g. with staff who are far away).
   - Other URLs:
     - Tables (QR): `https://YOUR-URL/soulplace/tables`
     - Request help: `https://YOUR-URL/soulplace/table?table=5`

---

## 2. API token for Vercel

You need an **API token** so the app (and optional external callers) can use `POST /api/request/create`.

### Option A – Set your own token in Vercel (recommended)

1. In the Vercel project: **Settings → Environment Variables**.
2. Add:
   - **Name:** `SOULPLACE_API_TOKEN`
   - **Value:** any long secret string, e.g. `SoulPlace2024SecureToken#XYZ`
3. Redeploy the project (Deployments → ⋮ → Redeploy).

Use this token in requests:

- **Header:** `X-API-Token: YOUR_TOKEN`
- Or: `Authorization: Bearer YOUR_TOKEN`

### Option B – Let the app generate a token

1. Do **not** set `SOULPLACE_API_TOKEN` in Vercel.
2. Deploy, then open your URL in Chrome and log in as **ASHOK** or **BOO**.
3. On the dashboard, open **“API Token (for Vercel / external API)”**.
4. Click **Show token** and **Copy**.
5. Use that value as the API token (e.g. in Vercel env or in API calls).

---

## 3. Required env var for sessions

In Vercel **Environment Variables**, also add:

- **Name:** `SOULPLACE_SECRET_KEY`
- **Value:** any long random string (e.g. `MySecretKey-12345-ChangeThis`)

Then redeploy. This is used for login sessions.

---

## 4. QR codes working from long distance

QR codes are generated with the **current site URL**. When the app runs on Vercel, they already point to your Vercel URL, so scans work from anywhere.

- **Optional:** In Vercel **Environment Variables**, set **`SOULPLACE_PUBLIC_URL`** to your full app URL (e.g. `https://your-app.vercel.app`). Then QR codes and the **/soulplace/links** page always use that URL even if request headers differ.
- Open **https://YOUR-URL/soulplace/tables** to view or print the 10 table QR codes. Each QR encodes the request-help URL for that table (e.g. `https://YOUR-URL/soulplace/table?table=3`).

---

## Summary

| What you need | Where to get it |
|---------------|-----------------|
| **URL link** | After deploy: Vercel project page → your `.vercel.app` URL |
| **API token** | Set `SOULPLACE_API_TOKEN` in Vercel env, or show/copy from dashboard (admin login) |
| **Secret key** | Set `SOULPLACE_SECRET_KEY` in Vercel env (any long random string) |

Use the URL only in **Chrome** (or any browser). No local server.
