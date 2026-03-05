# Get your Vercel app link (takes ~2 minutes)

You get your own link only by deploying. Two ways:

---

## Option 1: Deploy from your PC (no GitHub)

1. **Install Vercel CLI** (one time):
   ```bash
   npm install -g vercel
   ```

2. **Open terminal** in the project folder:
   ```bash
   cd "c:\mini project\soulplace_help_desk"
   ```

3. **Deploy:**
   ```bash
   vercel
   ```
   - Log in with Google/GitHub/Email when asked.
   - Accept defaults (just press Enter).
   - At the end you’ll see something like:
     ```text
     Production: https://soulplace-help-desk-xxxxx.vercel.app
     ```
   **That URL is your Vercel app link.**

4. **Use it on phone/PC:**
   - Login: `https://YOUR-LINK/soulplace/login`
   - Or open `https://YOUR-LINK/` — it goes to login.

---

## Option 2: Deploy from GitHub

1. Push `soulplace_help_desk` to a repo on [github.com](https://github.com).
2. Go to [vercel.com/new](https://vercel.com/new) and sign in.
3. Click **Import** and select your repo.
4. Set **Root Directory** to `soulplace_help_desk`, then **Deploy**.
5. When it’s done, your link is on the project page (e.g. `https://your-repo-name.vercel.app`).

---

## After you have the link

- **Login (main link):** `https://YOUR-VERCEL-LINK/soulplace/login`
- **Tables (QR):** `https://YOUR-VERCEL-LINK/soulplace/tables`
- **Request help:** `https://YOUR-VERCEL-LINK/soulplace/table?table=5`

Set **Environment Variables** in the Vercel project:
- `SOULPLACE_SECRET_KEY` — any long random string
- `SOULPLACE_API_TOKEN` — (optional) your API token

Then redeploy once so the app uses them.
