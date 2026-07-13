# SafeSeedOps — Landing Page Integration Prompt
## Copy this entire prompt into Claude Code, Cursor, Copilot, or any AI coding tool.

---

## CONTEXT — what you are working with

You are working inside the **SafeSeedOps Lite** monorepo. The project structure is:

```
safeseedops-lite/
├── app/                  ← FastAPI backend (Python 3.11)
│   └── main.py           ← FastAPI app entry point
├── frontend/             ← React SPA (Vite + TypeScript)
│   ├── src/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   └── package.json
├── docs/
└── uv run seed dev       ← one-command startup
```

The existing frontend is a **React + Vite + TypeScript** app started with `npm run dev` on port **3000**.
The FastAPI backend runs on port **8000**.
The app is currently a single-page tool — there is no landing page or root marketing page.

---

## TASK — what you need to do

### Step 1 — Add the landing page file

Copy the file `safeseedops-landing.html` (provided separately, or already in your working directory) into the frontend project at:

```
frontend/public/index-landing.html
```

**Do not** replace `frontend/public/index.html` — that is the React app's HTML shell and must stay untouched.

---

### Step 2 — Set up routing so the landing page is the root

The goal is:
- `http://localhost:3000/` → shows the landing page
- `http://localhost:3000/app` → shows the React dashboard

**Option A — Vite dev server rewrite (recommended for development)**

Add this to `vite.config.ts`:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
    }
  },
  build: {
    rollupOptions: {
      input: {
        main:    'index.html',         // React SPA shell → served at /app
        landing: 'public/index-landing.html'  // landing page → served at /
      }
    }
  }
})
```

Then update `frontend/public/index-landing.html` — replace all three instances of `#DASHBOARD_URL_HERE` with:

```
/app
```

And replace:
```
https://github.com/your-repo-here
```
with the actual GitHub repository URL (or leave as a placeholder if not yet public).

**Option B — FastAPI serves the landing page (alternative if you want a single server)**

If you prefer the FastAPI backend to own the routing instead of Vite, add this to `app/main.py`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Mount the built frontend at /app
app.mount("/app", StaticFiles(directory="frontend/dist", html=True), name="frontend")

# Serve the landing page at root
@app.get("/", response_class=FileResponse)
async def landing():
    return FileResponse("frontend/public/index-landing.html")
```

Then set the dashboard URL in `index-landing.html` to `/app` (same as Option A).

---

### Step 3 — Wire up the "Launch Dashboard" buttons

In `frontend/public/index-landing.html`, find and replace every occurrence of:

```
href="#DASHBOARD_URL_HERE"
```

with:

```
href="/app"
```

There are **3 occurrences** — one in the nav bar, one in the hero section, and one in the CTA strip at the bottom. Replace all three.

---

### Step 4 — Add a "Back to home" link in the React app

In the React app, add a small link back to the landing page so users can navigate between them.

Find the main navigation or header component in `frontend/src/` (likely `App.tsx`, `Layout.tsx`, or a `Navbar` component) and add:

```tsx
<a href="/" style={{ fontSize: '0.8rem', color: '#64748B', textDecoration: 'none' }}>
  ← Home
</a>
```

Place it in the top-left of the app header, before the product name.

---

### Step 5 — Verify it works

Run the dev server:

```bash
uv run seed dev
```

Then check:

| URL | Expected result |
|-----|-----------------|
| `http://localhost:3000/` | Landing page loads, dark hero visible, grid animation running |
| `http://localhost:3000/app` | React dashboard loads normally |
| Clicking "Launch Dashboard →" on landing page | Navigates to `/app` |
| Clicking "← Home" in the app | Returns to landing page at `/` |
| Clicking any nav link on landing page (How it works, Architecture, For business) | Smooth scrolls to the correct section on the landing page |
| Architecture diagram boxes (click any layer) | Tooltip appears with layer description |

---

### Step 6 — Production build (before submission)

```bash
cd frontend
npm run build
```

The build output will be in `frontend/dist/`. The landing page should be served from `frontend/dist/index-landing.html` and the React app from `frontend/dist/index.html`.

If using FastAPI (Option B), make sure `app/main.py` points to `frontend/dist` not `frontend/public`.

---

## WHAT NOT TO CHANGE

- Do not modify `frontend/index.html` — it is the React SPA shell
- Do not change any FastAPI routes under `/api/` — the landing page is purely frontend
- Do not add any npm dependencies for the landing page — it is vanilla HTML/CSS/JS, zero dependencies
- Do not remove the `Space Grotesk` or `Inter` Google Fonts imports in the landing page `<head>` — the typography is load-bearing for the design
- Do not change the colour variables in `:root` — they are the design system

---

## QUICK REFERENCE — landing page anchor IDs

Use these if you want to deep-link to specific sections from the React app or any external page:

| Section | Anchor |
|---|---|
| Hero | `/#hero` |
| Problem | `/#problem` |
| How it works | `/#how-it-works` |
| Architecture | `/#architecture` |
| Comparison table | `/#compare` |
| Business outcomes | `/#outcomes` |
| Why consider this | `/#business` |
| Tech stack | `/#stack` |
| CTA / launch | `/#cta` |

---

## IF SOMETHING BREAKS

**Landing page shows blank:**
Check that `frontend/public/index-landing.html` exists and the path in `vite.config.ts` matches.

**Dashboard link goes to a 404:**
Make sure `/app` is a valid route in your Vite or FastAPI config. For Vite, ensure `index.html` is the input for the `main` entry and the SPA catches all `/app/*` routes.

**Fonts not loading:**
The landing page loads `Space Grotesk` and `Inter` from Google Fonts via CDN. In an offline or air-gapped environment, download both fonts and serve them locally, then update the `<link>` tags in `<head>`.

**Google Fonts blocked by CSP:**
Add `https://fonts.googleapis.com` and `https://fonts.gstatic.com` to your `Content-Security-Policy` font-src directive, or self-host the fonts as above.

**Architecture tooltip not working:**
The tooltip logic is in a `<script>` block at the bottom of `index-landing.html`. Make sure the file is not being processed by any HTML minifier that strips `<script>` tags from static files.
