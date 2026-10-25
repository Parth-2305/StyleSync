# Architecture — Style Sync

## 1. Overview

Style Sync is a server-rendered Flask app (Jinja templates + Bootstrap 5 + vanilla JS) backed by Supabase (Postgres + Auth + Storage). There is no separate SPA build step — HTML pages are served by Flask, and page-specific JS files progressively enhance them (form handling, gallery filtering, toasts, nav state).

```
Browser  ─┬─> Flask routes (HTML pages)          ─> Jinja templates (templates/*.html)
          └─> Flask REST endpoints (JSON, /api/*) ─> Supabase (Postgres via supabase-py)
                                                    ─> Supabase Storage (garment images)
                                                    ─> Supabase Auth (JWT-based sessions)

ESP32 + RC522 (Phase 2) ─> Wi-Fi ─> Flask webhook endpoint (/api/rfid/scan) ─> Postgres
```

Flask never talks to Postgres with raw SQL for user-facing CRUD — it uses the `supabase-py` client so Supabase's Row Level Security (RLS) policies are enforced consistently whether the request comes from the browser or a script. See `SECURITY.md` for RLS details.

## 2. Directory Structure

Current + planned layout (existing files marked `[existing]`, everything else is what Phase 1 work still needs to add):

```
StyleSync_Prototype/
├── app.py                        # Flask app factory / entrypoint
├── config.py                     # Loads env vars, builds Supabase client config
├── requirements.txt              # Flask, supabase-py, Pillow, python-dotenv, etc.
├── .env                          # Local secrets (NEVER committed — see SECURITY.md)
├── .env.example                  # Documents required env vars with placeholder values
├── .gitignore
│
├── routes/                       # Flask Blueprints
│   ├── __init__.py
│   ├── pages.py                  # Renders HTML pages (landing, dashboard, gallery, add-item)
│   ├── auth.py                   # /api/auth/* — signup, login, logout, session check
│   ├── wardrobe.py                # /api/items/* — CRUD for clothing items
│   ├── outfits.py                 # /api/outfits/* — suggestion engine, mark-as-worn
│   └── rfid.py                    # /api/rfid/* — Phase 2 ESP32 webhook + tag binding
│
├── services/                      # Business logic, kept out of route handlers
│   ├── __init__.py
│   ├── supabase_client.py         # Singleton Supabase client (server-side, service role for trusted ops)
│   ├── image_service.py           # Pillow resize/compress + Supabase Storage upload
│   ├── outfit_engine.py           # Rule-based (Phase 1) / weighted scoring (Phase 2) suggestion logic
│   └── auth_service.py            # Session/token helpers, login-required decorator
│
├── templates/                     # [existing] Jinja HTML templates
│   ├── landing.html               # [existing] public marketing/login page
│   ├── dashboard.html             # [existing] post-login home (today's outfit, stats)
│   ├── wardrobe-gallery.html      # [existing] filterable item gallery
│   ├── add-clothing-item.html     # [existing] add/edit item form
│   └── partials/                  # shared nav/sidebar/toast includes (extract from existing pages)
│
├── static/
│   ├── css/
│   │   └── style.css              # [existing] shared design system (needs re-theme — see DESIGN.md)
│   ├── js/
│   │   ├── landing.js             # [existing]
│   │   ├── public-nav.js          # [existing]
│   │   ├── app-nav.js             # [existing] sidebar/topbar behavior for logged-in shell
│   │   ├── dashboard.js           # [existing] fetches dashboard data, renders stats + suggestion
│   │   ├── wardrobe-gallery.js    # [existing] fetch + filter + render item cards
│   │   ├── add-clothing-item.js   # [existing] form validation + image preview + submit
│   │   ├── toast.js               # [existing] shared toast/notification helper
│   │   └── api.js                 # thin fetch() wrapper: base URL, auth header, error handling
│   └── images/
│       └── logo.svg               # [existing]
│
├── firmware/                      # Phase 2 — ESP32 Arduino/PlatformIO project
│   └── rfid_scanner/
│       └── rfid_scanner.ino
│
├── tests/
│   ├── test_wardrobe_api.py
│   └── test_outfit_engine.py
│
├── PRD.md / ARCHITECTURE.md / DESIGN.md / RULES.md / SECURITY.md / TASKS.md / README.md
```

## 3. Supabase Database Schema (Postgres)

All tables live in the `public` schema and use `auth.users.id` (UUID, supplied by Supabase Auth) as the owning-user foreign key. Every table has RLS enabled — see `SECURITY.md` §2 for the actual policies.

### 3.1 `profiles`
Extends Supabase's built-in `auth.users` with app-specific profile data.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid, PK | References `auth.users.id`, `ON DELETE CASCADE` |
| `full_name` | text | Nullable |
| `avatar_url` | text | Nullable, Supabase Storage public URL |
| `created_at` | timestamptz | `default now()` |

### 3.2 `clothing_items`
The core wardrobe catalog.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid, PK | `default gen_random_uuid()` |
| `user_id` | uuid, FK → `auth.users.id` | `ON DELETE CASCADE`, indexed |
| `name` | text | e.g. "Navy Oxford Shirt" |
| `category` | text | enum-like: `top`, `bottom`, `footwear`, `outerwear`, `accessory` |
| `subcategory` | text | e.g. "t-shirt", "jeans", "sneakers" — free text, filterable |
| `color` | text | primary color, used for pairing rules |
| `season` | text[] | e.g. `{summer, monsoon}` — array so an item can suit multiple seasons |
| `occasion_tags` | text[] | e.g. `{casual, formal, party}` |
| `image_url` | text | Supabase Storage public/signed URL |
| `notes` | text | Nullable, free text |
| `wear_count` | int | `default 0`, incremented by `outfit_logs` trigger or app logic |
| `last_worn_at` | timestamptz | Nullable, updated on wear |
| `rfid_tag_id` | text | Nullable (Phase 2), unique per user when set |
| `created_at` | timestamptz | `default now()` |
| `updated_at` | timestamptz | `default now()`, updated via trigger |

### 3.3 `outfit_logs`
History of suggested/worn outfits — powers stats, recency-avoidance, and Phase 2 analytics.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid, PK | `default gen_random_uuid()` |
| `user_id` | uuid, FK → `auth.users.id` | `ON DELETE CASCADE` |
| `item_ids` | uuid[] | the garments that made up this outfit |
| `worn_on` | date | defaults to today when logged |
| `source` | text | `manual` \| `suggested` \| `rfid_scan` (Phase 2) |
| `weather_snapshot` | jsonb | Nullable (Phase 2) — temp/condition at time of suggestion |
| `created_at` | timestamptz | `default now()` |

### 3.4 `rfid_tags` (Phase 2)
Tracks tag-to-item bindings separately so re-binding/unbinding is auditable.

| Column | Type | Notes |
|---|---|---|
| `tag_uid` | text, PK | Raw UID read from the RC522 |
| `user_id` | uuid, FK → `auth.users.id` | |
| `item_id` | uuid, FK → `clothing_items.id`, nullable | Null = scanned but not yet bound |
| `bound_at` | timestamptz | Nullable |
| `last_scanned_at` | timestamptz | Nullable |

### 3.5 Supabase Storage

- Bucket: `garment-images` (public read via signed/public URLs, write restricted to the owning authenticated user — see `SECURITY.md` §3).
- Path convention: `garment-images/{user_id}/{item_id}.jpg` so RLS-style storage policies can key off the path prefix.

## 4. Flask API Specification

Base path: `/api`. All authenticated routes require a valid Supabase session (JWT passed via `Authorization: Bearer <token>` or a secure session cookie set at login) and are protected by a `@login_required` decorator in `services/auth_service.py`.

### 4.1 Page routes (`routes/pages.py`, HTML)

| Method | Route | Auth | Renders |
|---|---|---|---|
| GET | `/` | Public | `landing.html` |
| GET | `/dashboard` | Required | `dashboard.html` |
| GET | `/wardrobe` | Required | `wardrobe-gallery.html` |
| GET | `/wardrobe/add` | Required | `add-clothing-item.html` (add mode) |
| GET | `/wardrobe/<item_id>/edit` | Required | `add-clothing-item.html` (edit mode) |

### 4.2 Auth API (`routes/auth.py`)

| Method | Route | Body | Response |
|---|---|---|---|
| POST | `/api/auth/signup` | `{email, password, full_name}` | `201 {user, session}` |
| POST | `/api/auth/login` | `{email, password}` | `200 {user, session}` |
| POST | `/api/auth/logout` | — | `204` |
| GET | `/api/auth/session` | — | `200 {user}` or `401` |

### 4.3 Wardrobe API (`routes/wardrobe.py`)

| Method | Route | Body / Query | Response |
|---|---|---|---|
| GET | `/api/items` | Query: `category, color, season, occasion, search` | `200 {items: [...]}` |
| GET | `/api/items/<id>` | — | `200 {item}` |
| POST | `/api/items` | multipart: fields + `image` file | `201 {item}` |
| PUT | `/api/items/<id>` | multipart or JSON | `200 {item}` |
| DELETE | `/api/items/<id>` | — | `204` |

### 4.4 Outfit API (`routes/outfits.py`)

| Method | Route | Body / Query | Response |
|---|---|---|---|
| GET | `/api/outfits/suggestion` | Query: `occasion?` | `200 {outfits: [{items: [...], reason}]}` |
| POST | `/api/outfits/log` | `{item_ids, worn_on?, source}` | `201 {log}` |
| GET | `/api/outfits/history` | Query: `from, to` | `200 {logs: [...]}` |
| GET | `/api/dashboard/stats` | — | `200 {total_items, most_worn, least_worn, recent_activity}` |

### 4.5 RFID API — Phase 2 (`routes/rfid.py`)

| Method | Route | Body | Response |
|---|---|---|---|
| POST | `/api/rfid/scan` | `{tag_uid, device_id}` (called by ESP32, API-key auth, not user JWT) | `200 {status: bound\|unbound\|logged}` |
| POST | `/api/rfid/bind` | `{tag_uid, item_id}` | `200 {tag}` |
| DELETE | `/api/rfid/bind/<tag_uid>` | — | `204` |

## 5. Frontend ↔ Backend Contract

- Every page-specific JS file (`dashboard.js`, `wardrobe-gallery.js`, `add-clothing-item.js`) talks to the API exclusively through `static/js/api.js`, which centralizes the base URL, auth header injection, and JSON error parsing so each page script doesn't duplicate `fetch` boilerplate.
- All API errors return a consistent shape: `{"error": {"code": "...", "message": "..."}}` so `toast.js` can render one generic error-toast handler.
- Image uploads always go through `FormData` (multipart), never base64-in-JSON, to keep payloads efficient.

## 6. Image Pipeline

1. Browser: user selects/drops a file in `add-clothing-item.html`'s dropzone → `add-clothing-item.js` shows a client-side preview and optionally downsamples via `<canvas>` before upload (keeps upload payload small on mobile).
2. Flask: `services/image_service.py` receives the file, re-validates it's a real image (Pillow `Image.open` + `.verify()`), strips EXIF, resizes to a max dimension (e.g. 1600px), re-encodes as JPEG/WebP, then uploads to the `garment-images` Supabase Storage bucket under `{user_id}/{item_id}.jpg`.
3. The resulting Storage URL is what's saved to `clothing_items.image_url`.

## 7. Phase 2 Hardware Integration Notes

- ESP32 firmware (`firmware/rfid_scanner/`) connects to Wi-Fi, reads UIDs from the RC522 over SPI, and POSTs `{tag_uid, device_id}` to `/api/rfid/scan` using a static device API key (not a user JWT — devices aren't users).
- `/api/rfid/scan` logic: if `tag_uid` is unbound → mark it "pending bind" for the UI to pick up next time the owning user opens the app; if bound → log a wear event in `outfit_logs` with `source = 'rfid_scan'` and update `clothing_items.last_worn_at` / `wear_count`.
- Keep the ESP32 → Flask contract dumb (raw UID + device id) — all business logic (bind vs. log-wear) stays server-side so firmware never needs redeploying when rules change.
