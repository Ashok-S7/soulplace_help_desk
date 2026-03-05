# Create Vercel — Get your live link

Follow these steps to create your Vercel deployment and get your link. **No coding required.**

---

## Step 1: Put your project on GitHub

1. Go to **[github.com](https://github.com)** and sign in.
2. Click **+** → **New repository**.
3. Name it (e.g. `soulplace-help-desk`). Leave other options default. Click **Create repository**.
4. On your PC, open **Command Prompt** or **PowerShell** and run (replace `YOUR_USERNAME` and `YOUR_REPO` with your GitHub username and repo name):

```bash
cd "c:\mini project\soulplace_help_desk"
git init
git add .
git commit -m "Soulplace Help Desk"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

If you don’t have **git**, install it from [git-scm.com](https://git-scm.com), or use GitHub Desktop to create the repo and upload the `soulplace_help_desk` folder.

---

## Step 2: Create the project on Vercel

1. Go to **[vercel.com/new](https://vercel.com/new)** (or run **CREATE_VERCEL.bat** in this folder to open it).
2. Sign in with **GitHub**.
3. Under **Import Git Repository**, find your repo (e.g. `soulplace-help-desk`) and click **Import**.
4. **Root Directory:** click **Edit** and set it to **`.`** (or leave empty if the repo contains only the app).
   - If your repo has a parent folder and `soulplace_help_desk` is inside it, set Root Directory to **`soulplace_help_desk`**.
5. **Environment Variables** (optional but recommended):
   - Add **Name:** `SOULPLACE_SECRET_KEY` → **Value:** any long random text.
   - Add **Name:** `SOULPLACE_API_TOKEN` → **Value:** any secret (or leave blank; the app will generate one).
6. Click **Deploy**.

---

## Step 3: Get your link

- When the deployment finishes, Vercel shows: **“Congratulations! Your project has been deployed.”**
- Your link is there, e.g. **`https://soulplace-help-desk-xxxxx.vercel.app`**
- Use it like this:
  - **Login:** `https://YOUR-LINK/soulplace/login`
  - **Tables (QR):** `https://YOUR-LINK/soulplace/tables`

That link is your **Vercel app link**. You can use it on your phone, PC, or anywhere.
