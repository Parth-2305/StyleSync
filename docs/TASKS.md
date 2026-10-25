# Tasks — Style Sync

Checklist form, grouped by phase and milestone. Work top to bottom within a phase — later tasks assume earlier ones are done (see `RULES.md` §5). Check items off as completed.

## Phase 0 — Project Setup

- [ ] Initialize git repo (`git init`), add `.gitignore` (Python, Flask, `.env`, `__pycache__`, `venv/`, `.DS_Store`, node/build artifacts if any)
- [ ] Create Python virtual environment, add `requirements.txt` (`flask`, `supabase`, `python-dotenv`, `pillow`, `flask-cors` if needed)
- [ ] Create `.env.example` documenting all required variables (see `SECURITY.md` §6)
- [ ] Create Supabase project; note project URL, anon key, service role key (store locally in `.env`, never commit)
- [ ] Run schema SQL for `profiles`, `clothing_items`, `outfit_logs`, `rfid_tags` (see `ARCHITECTURE.md` §3)
- [ ] Enable RLS and apply all policies from `SECURITY.md` §2
- [ ] Create `garment-images` Storage bucket, apply Storage policies from `SECURITY.md` §3
- [ ] Scaffold `app.py` (Flask app factory), `config.py`, `routes/`, `services/` per `ARCHITECTURE.md` §2
- [ ] Wire up base Jinja layout (`templates/base.html`) with shared `<head>` (Google Fonts, Bootstrap 5 CDN, `style.css`, Bootstrap Icons CDN)
- [ ] Confirm `python app.py` runs and serves the existing `landing.html` without errors

## Phase 1 — Capstone MVP

### Milestone 1.1 — Design System Migration
- [ ] Add the token block from `DESIGN.md` §3 to the top of `static/css/style.css`
- [ ] Re-theme existing components (navbar, buttons, sidebar, cards) from the old forest/terracotta palette to the new Deep Ocean Blue / Coral / Sky Blue palette
- [ ] Swap fonts to Poppins (display) + Inter (body) per `DESIGN.md` §2
- [ ] Add `.glass-panel` styles and apply to navbar + dashboard hero panel per `DESIGN.md` §4
- [ ] Visually re-check all four existing pages (landing, dashboard, gallery, add-item) against the new palette — fix any low-contrast text

### Milestone 1.2 — Auth
- [ ] Build `services/auth_service.py`: Supabase client init, `login_required` decorator, session/token helpers
- [ ] Build `routes/auth.py`: signup, login, logout, session-check endpoints
- [ ] Wire `landing.html` login/signup forms to the auth API (replace any placeholder JS)
- [ ] Add a `profiles` row automatically on signup (DB trigger or app-side insert right after signup)
- [ ] Protect `/dashboard`, `/wardrobe`, `/wardrobe/add` routes — redirect unauthenticated requests to `/`
- [ ] Manually test: sign up, log out, log back in, refresh page while logged in (session persists)

### Milestone 1.3 — Wardrobe CRUD + Image Upload
- [ ] Build `services/image_service.py`: validate, strip EXIF, resize/re-encode, upload to Storage (see `SECURITY.md` §4)
- [ ] Build `routes/wardrobe.py`: `GET/POST /api/items`, `GET/PUT/DELETE /api/items/<id>`
- [ ] Wire `add-clothing-item.js` to `POST /api/items` (create) and `PUT /api/items/<id>` (edit mode)
- [ ] Wire `wardrobe-gallery.js` to `GET /api/items` with filter query params
- [ ] Implement delete with a confirmation step (no raw `confirm()` — use a styled modal/toast per `RULES.md`)
- [ ] Manually test: add an item with a photo, see it appear in the gallery, edit it, delete it

### Milestone 1.4 — Dashboard + Stats
- [ ] Build `GET /api/dashboard/stats` (total items, most/least worn, recent activity) in `routes/outfits.py`
- [ ] Wire `dashboard.js` to render real stats instead of placeholder/skeleton data
- [ ] Add empty-state handling: brand-new account with 0 items shows a clear "add your first item" prompt, not a broken/empty dashboard

### Milestone 1.5 — Rule-Based Outfit Suggestions
- [ ] Build `services/outfit_engine.py`: v1 rule-based logic — pick one `top`, one `bottom`, one `footwear` (+ optional `outerwear`), filtered by current season, excluding items worn in the last N days
- [ ] Build `GET /api/outfits/suggestion` endpoint
- [ ] Render the suggestion in the dashboard's glass hero panel
- [ ] Handle the "not enough items yet" case gracefully (e.g., fewer than 1 top+bottom+footwear combo exists)

### Milestone 1.6 — Mark as Worn + History
- [ ] Build `POST /api/outfits/log` — logs a worn outfit, updates `wear_count`/`last_worn_at` on each item
- [ ] Add a "Wear this today" action on the dashboard suggestion, wired to the log endpoint
- [ ] Confirm the suggestion engine actually avoids recently-logged items on the next load (test by logging 2–3 days of outfits in a row)

### Milestone 1.7 — Responsive Polish + QA
- [ ] Test all four pages at mobile width (≤480px), tablet (~768px), desktop (≥1200px)
- [ ] Run through every form's validation states (empty required field, invalid image type, oversized image)
- [ ] Cross-browser sanity check (Chrome + at least one more)
- [ ] Confirm no console errors on any page, no broken images, no dead links
- [ ] Update `README.md` with final setup steps if anything changed during build

**Phase 1 done when:** `PRD.md` §5.1 exit criteria are met — full signup → add items → get suggestion → mark worn → see updated stats loop works end to end with a real demo account.

## Phase 2 — Major Project (IoT + AI)

### Milestone 2.1 — RFID Binding Flow
- [ ] Add `rfid_tags` table + RLS policies (already specified in `ARCHITECTURE.md`/`SECURITY.md` — apply if not already run)
- [ ] Build `routes/rfid.py`: `POST /api/rfid/bind`, `DELETE /api/rfid/bind/<tag_uid>`
- [ ] Build a "Bind RFID tag" UI flow on the item detail/edit view (scan → shows unbound tag → user confirms which item it maps to)

### Milestone 2.2 — ESP32 + RC522 Firmware
- [ ] Wire RC522 to ESP32 (SPI), get raw UID reads working over serial first (bench test before Wi-Fi)
- [ ] Add Wi-Fi connectivity + HTTP POST to `/api/rfid/scan` with `{tag_uid, device_id}` + device API key header
- [ ] Build `POST /api/rfid/scan` endpoint (service-role write, resolves `tag_uid → user_id`, debounced per `SECURITY.md` §7)
- [ ] Bench test: scan a bound tag, confirm a wear log appears in the dashboard within a few seconds

### Milestone 2.3 — Weather + AI-Weighted Suggestions
- [ ] Pick and integrate a free weather API (decide provider — see `PRD.md` §9)
- [ ] Extend `outfit_engine.py` with a weighted scoring pass (weather fit, color pairing heuristic, wear recency) alongside the existing rule-based filter
- [ ] Store `weather_snapshot` on each `outfit_logs` row when a suggestion is generated
- [ ] A/B sanity check: confirm suggestions visibly change with different mock weather inputs

### Milestone 2.4 — Analytics & Notifications
- [ ] Build an outfit history view (calendar or list) reading from `outfit_logs`
- [ ] Add "not worn in 60+ days" detection and surface it as an in-app nudge (dashboard card or toast on load)
- [ ] (Optional stretch) email notification via a transactional email provider, gated behind a user setting

### Milestone 2.5 — Final Demo Prep
- [ ] End-to-end hardware demo rehearsal: physical tag scan → live dashboard update, timed
- [ ] Confirm all docs (`PRD.md`, `ARCHITECTURE.md`, `SECURITY.md`) reflect the final as-built system, not just the plan
- [ ] Prepare a short fallback path (recorded video/screenshots) in case live hardware demo fails during evaluation

**Phase 2 done when:** `PRD.md` §5.2 exit criteria are met.
