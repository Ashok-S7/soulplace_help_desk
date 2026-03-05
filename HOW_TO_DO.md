# How to do — Get Soulplace on Vercel (step by step)

---

## What you need

- A **GitHub** account (free): [github.com](https://github.com)
- A **Vercel** account (free): sign up at [vercel.com](https://vercel.com) with GitHub

---

## Step 1: Put your project on GitHub

1. Go to **[github.com](https://github.com)** and sign in.
2. Click the **+** at the top right → **New repository**.
3. **Repository name:** type `soulplace-help-desk` (or any name).
4. Leave everything else as default. Click **Create repository**.
5. You’ll see a page with “quick setup” and a URL like  
   `https://github.com/YOUR_USERNAME/soulplace-help-desk.git`.

**Upload the folder:**

- **Option A — Drag and drop**  
  On the new repo page, scroll to “uploading an existing file”.  
  Open `c:\mini project\soulplace_help_desk` on your PC, select **all files and folders** inside it (app.py, templates, static, etc.), drag them into the browser and drop.  
  Add a commit message like “Initial commit” and click **Commit**.

- **Option B — GitHub Desktop**  
  1. Install [GitHub Desktop](https://desktop.github.com).  
  2. File → Add local repository → choose `c:\mini project\soulplace_help_desk`.  
  3. If it says “not a Git repository”, choose “create a repository” there.  
  4. Publish to GitHub and choose the account and repo name you created.

When you’re done, your code should be visible on the repo page (e.g. you see `app.py`, `templates/`, etc.).

---

## Step 2: Deploy on Vercel

1. Go to **[vercel.com/new](https://vercel.com/new)**.
2. Click **Sign in** and choose **Continue with GitHub**.
3. The first time, Vercel may ask to access your GitHub repos. Click **Authorize**.
4. Under **Import Git Repository**, you should see your repo (e.g. `soulplace-help-desk`).  
   Click **Import** next to it.
5. **Configure Project:**
   - **Root Directory:**  
     - If you uploaded *only* the contents of `soulplace_help_desk` (app.py, templates, static, etc.) into the repo, leave this **empty** or as **.**  
     - If the repo has a parent folder and the app is inside a folder, click **Edit** and set Root Directory to that folder name.
   - **Environment Variables (optional):**  
     Click **Add** and add:
     - Name: `SOULPLACE_SECRET_KEY`  
       Value: any long random text (e.g. `mySecretKey12345`)
6. Click **Deploy**.
7. Wait 1–2 minutes. When it’s done you’ll see **“Congratulations!”** and a link like  
   `https://soulplace-help-desk-xxxxx.vercel.app`.

That link is your **Vercel link**.

---

## Step 3: Use your link

- **Login (staff):**  
  `https://YOUR-LINK/soulplace/login`  
  Example: `https://soulplace-help-desk-abc123.vercel.app/soulplace/login`

- **Tables (QR codes):**  
  `https://YOUR-LINK/soulplace/tables`

- **Request help (e.g. table 5):**  
  `https://YOUR-LINK/soulplace/table?table=5`

Open these on your phone or PC. Log in with your staff account (e.g. ASHOK / SoulOfBlue#7).

---

## Summary

| Step | What to do |
|------|------------|
| 1 | Create a repo on GitHub and upload the contents of `soulplace_help_desk`. |
| 2 | Go to vercel.com/new → Sign in with GitHub → Import your repo → Deploy. |
| 3 | Copy the link Vercel gives you and use it with `/soulplace/login` and `/soulplace/tables`. |

If something fails (e.g. “Build error” on Vercel), copy the error message and we can fix it step by step.
