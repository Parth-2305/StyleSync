# Style Sync

Smart Wardrobe Management & Personalized Outfit Recommendation System — B.Tech IT Capstone (Phase 1) / Major Project (Phase 2).

Style Sync lets you digitize your wardrobe (photos + tags), get outfit suggestions built entirely from clothes you already own, and track what you've worn over time. Phase 2 adds ESP32 + RC522 RFID hardware so scanning a physical garment can automatically log it as worn.

See `docs/PRD.md` for full scope, `docs/ARCHITECTURE.md` for system design, `docs/DESIGN.md` for the visual design system, `docs/SECURITY.md` for the security model, and `docs/TASKS.md` for the build checklist.

## Folder layout (what is where)

```
StyleSync_Prototype/
├── README.md              This file: how to set up and run
├── .env / .env.example    Secrets (never share .env) / the template without secrets
├── requirements.txt       Python packages to install
│
├── app.py                 Starts the site, lists the pages, sets security headers
├── auth.py  validators.py  extensions.py  config.py  db.py      Login, input rules, security tools, settings, Supabase link
├── items.py  images.py    Wardrobe pieces and photo handling
├── outfit_engine.py  outfits.py  options.py                      The outfit matcher, history, and its lists/constants
├── tags.py  iot.py  notify.py                                    Hanger tags, ESP32 scan route, notifications and push
│   (the .py files stay together at the top because they import each other by name)
│
├── templates/             HTML pages (Jinja)
├── static/                CSS, JavaScript, images, service worker
├── database/              SQL to run in Supabase: schema, hardening, iot, tags_per_user
├── firmware/              ESP32 sketch + wiring guide
├── tools/                 Helper scripts: fake_reader, make_vapid_keys, pretend_worn
├── tests/                 126 automated checks (run_iot_checks.py + fake database)
└── docs/                  ALL documents: PROJECT_LOG, HANDOFF_FOR_REPORT, SECURITY, ARCHITECTURE, PRD, ... the PDFs and report_assets (screenshots)
```

## Tech Stack

- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5
- **Backend:** Python (Flask)
- **Database & Auth:** Supabase (PostgreSQL + Auth)
- **Image handling:** Pillow + Supabase Storage
- **Hardware (Phase 2):** ESP32 + RC522 RFID reader over Wi-Fi

## Prerequisites

- Python 3.10+
- A free [Supabase](https://supabase.com) account/project
- Git

## 1. Clone & Set Up a Virtual Environment

```bash
git clone <this-repo-url>
cd StyleSync_Prototype

python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

## 2. Configure Environment Variables

Copy the example file and fill in real values from your Supabase project (**Project Settings → API**):

```bash
cp .env.example .env
```

`.env`:

```env
# Supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here   # server-side only, never expose to the frontend

# Flask
FLASK_SECRET_KEY=generate-a-long-random-string-here
FLASK_ENV=development

# Phase 2 — RFID device auth (only needed once ESP32 integration starts)
RFID_DEVICE_API_KEY=generate-a-separate-random-string-here
```

**Never commit `.env`.** It's already in `.gitignore`. See `docs/SECURITY.md` §6 for what each key is used for and why the service role key is especially sensitive.

## 3. Set Up the Supabase Database

In the Supabase SQL editor, run the schema from `docs/ARCHITECTURE.md` §3 (tables: `profiles`, `clothing_items`, `outfit_logs`, `rfid_tags`), then apply the Row Level Security policies from `docs/SECURITY.md` §2.

Create a Storage bucket named `garment-images` and apply the Storage policies from `docs/SECURITY.md` §3.

## 4. Run the App Locally

```bash
python app.py
```

By default the app runs at **http://localhost:5000**. Open it in a browser — you should see the landing page.

> **Security note:** the app refuses to start unless `.env` is complete and valid (`config.py`). Debug mode is off by default; for development only, run `set FLASK_DEBUG=1` first (Windows). See `docs/SECURITY.md`.

| URL | Page |
|---|---|
| `/` | Landing — log in / sign up |
| `/dashboard` | Greeting, "What should I wear?", stats, latest pieces |
| `/wardrobe` | Filterable gallery + "Add New Piece" modal (`/wardrobe/add` opens the modal directly) |
| `/matcher` | Outfit Matcher |
| `/history` | Worn / saved outfits |
| `/profile` | Style + colour preferences |

## 5. Project Structure

See `docs/ARCHITECTURE.md` §2 for the full annotated directory layout (routes, services, templates, static assets, and the Phase 2 `firmware/` folder).

## 6. Running Tests

```bash
venv\Scripts\python.exe tests\run_iot_checks.py
```

This runs 126 automated checks against an in-memory fake database (`tests/fakedb.py`): nothing in Supabase is touched. It should end with `126 checks passed, 0 failed`.

## 7. Phase 2 — Hardware Setup (ESP32 + RC522)

Firmware lives in `firmware/rfid_scanner/`. High-level steps (details in `docs/ARCHITECTURE.md` §7 and `docs/TASKS.md` Milestone 2.2):

1. Wire the RC522 to the ESP32 over SPI.
2. Flash `firmware/rfid_scanner/rfid_scanner.ino` with your Wi-Fi credentials, the Flask server's reachable URL, and `RFID_DEVICE_API_KEY` set to match your `.env`.
3. Ensure the ESP32 and the machine running Flask are reachable from each other (same LAN, or a deployed/tunneled Flask instance for off-network testing).

## 8. Contributing / Working on This Repo

Read `docs/RULES.md` before making changes — it covers error handling expectations, commenting style, and how to avoid breaking shared files (`style.css`, `api.js`, base templates) that every page depends on.

## 9. Hanger tags (ESP32) and notifications

1. In Supabase, open the SQL Editor and run `database/iot.sql` once (it adds the tables for readers and push subscriptions).
2. Also run `database/tags_per_user.sql` once (it lets the same RFID card be used by several accounts independently). Then restart the site. A new **Hangers** page and a notification bell appear.
3. Hangers page: pair a reader (you get a secret key once), then link tags to your clothes. No hardware yet? Use **Simulate scan**.
4. ESP32: follow `firmware/README.md` (wiring, flashing, Wi-Fi, device key).
5. Browser notifications: click the bell, then **Turn on browser notifications** (needs the three `VAPID_*` values in `.env`).
6. Test without hardware from the command line: `venv\Scripts\python.exe tools\fake_reader.py --key YOUR_KEY --tag 04A1B2C3`
7. The reader's buzzer: 1 short beep = logged, 2 short = new/unlinked tag, 1 long = worn this week, 3 quick = error. The Hangers page is **Live**: it refreshes itself within about 3 seconds of a scan.
8. A reader belongs to ONE account (its key decides). For another account, pair a new reader there and change the ESP32's key with `key NEWKEY` in the Serial Monitor.

Full history of everything built, how it works and what to run: see `docs/PROJECT_LOG.md`.

**Starting everything for a demo (step by step): `docs/DEMO_STARTUP_GUIDE.md`.**
