# StyleSync: hand-off for the report writer

Read this first. The full technical description of the whole project (front end, back end, IoT, database, security, tests) is the PDF `docs/StyleSync_Complete_Project_Documentation.pdf`. Then `PROJECT_LOG.md` (every feature, how it works, which file). This page tells you WHAT to put in the report,
WHERE to find each thing, and what is honestly finished or not.

---

## 1. Project in 5 lines (for the abstract)

- **StyleSync** is a smart wardrobe website with an explainable outfit recommender and an IoT hanger-tag system.
- Users upload clothes; the **rule-based matcher** builds outfits (occasion, season, colour palette, style, rotation) and says WHY in plain sentences.
- RFID tags on hangers + an **ESP32 with an RC522 reader** log what you wear automatically when you take a garment off the rail.
- The site applies a **one-week no-repeat rule**, sends **in-app and browser push notifications**, and the reader answers with **beep patterns**.
- Security was built in from the start: server-side validation, rate limiting, hashed passwords, generic errors, CSRF, CSP, row-level security, device keys stored only as hashes.

Tech: Python 3 + Flask 3.1, Supabase (Postgres, Auth, Storage), HTML/CSS/JavaScript + Bootstrap, Pillow, ESP32 (Arduino C++), RC522, Web Push (pywebpush, VAPID, service worker).

---

## 2. Suggested report chapters and where the material is

| Chapter | Material | Where |
|---|---|---|
| 1 Introduction, problem, objectives | Wardrobe clutter, repeated outfits, no link between physical and digital wardrobe | `PRD.md`, `PROJECT_LOG.md` section 1 |
| 2 Literature / existing apps | Write from the web (Stylebook, Cladwell, Acloset). Not in the repo | (to write) |
| 3 Requirements | Functional and non-functional | `PRD.md`, `TASKS.md` |
| 4 System design | Architecture, folder structure, database, request flow | `ARCHITECTURE.md`, `PROJECT_MAP.md`, `database/schema.sql`, `database/iot.sql`, `database/tags_per_user.sql` |
| 5 Outfit algorithm | Scoring, occasion-first tiers, season filter, repeat penalty, near-best random pick, reasons | `outfit_engine.py` (read the top docstring), `options.py` |
| 6 IoT design | Hardware list, wiring, sketch, device key, scan flow, beeps | `firmware/README.md`, `firmware/rfid_scanner/rfid_scanner.ino`, `iot.py`, `tags.py`, `PROJECT_LOG.md` section 3 |
| 7 Security | Threat to control table | `SECURITY.md`, `HOW_IT_WORKS.md` |
| 8 UI / UX | Theme, screens | `DESIGN.md`, `THEME_PROMPT.md`, screenshots below |
| 9 Testing | 126 automated checks + browser checks + real hardware tests | `tests/run_iot_checks.py`, `PROJECT_LOG.md` section 5 |
| 10 Problems and solutions | Real bugs met and fixed | `PROJECT_LOG.md` section 6 |
| 11 Limitations and future work | See sections 5 and 6 below | this file |
| 12 Conclusion | Write from the above | (to write) |

---

## 3. Screenshots already captured (`docs/report_assets/`)

- `screens/` 01-14: landing/login, sign-up, dashboard, wardrobe, add-item popup, matcher (choices, sparkles, result, shuffled), history (worn, saved), profile, mobile dashboard and matcher.
- `iot/`: Hangers page (`hangers_page`, `hangers_live`, `hangers_key_reveal`, `hangers_mobile`), notification bell (`bell_panel`, `bell_mobile`), `history_hanger_look`, `toast_with_close`, `wardrobe_tag_status`, `wardrobe_wear_line`, `matcher_tag_status`.
- `samples/`: ten sample clothing images.
- Missing and worth taking by hand: a photo of the **real hardware** (ESP32 + RC522 + buzzer wired up), the **Serial Monitor** output of a scan, and the **real browser push pop-up** (Chrome notification).

---

## 4. How to run and demo it (the team member can follow this)

1. Python 3.11+ and a Supabase project. Copy `.env.example` to `.env` and fill it (ask Parth for the values; **never share or upload `.env`**).
2. `python -m venv venv`, then `venv\Scripts\pip install -r requirements.txt`.
3. In Supabase SQL Editor run, once and in this order: `database/schema.sql`, `database/hardening.sql`, `database/iot.sql`, `database/tags_per_user.sql`.
4. Start: `$env:HOST="0.0.0.0"; venv\Scripts\python.exe app.py`, open http://127.0.0.1:5000
5. Demo without hardware: Hangers page -> **Simulate scan**. Demo with hardware: `firmware/README.md`.
6. Tests: `venv\Scripts\python.exe tests\run_iot_checks.py` (should print `126 checks passed, 0 failed`).

Demo script (3 minutes): sign up -> add 4-5 pieces -> Matcher (Party / All-season) and show the reasons -> Hangers: pair reader, scan an unknown card (2 beeps, appears live), link to a piece -> scan again (1 beep, notification, pop-up) -> scan twice on another day or use `tools/pretend_worn.py` to show the repeat warning (long beep) -> History shows the "Hanger look".

---

## 5. Honest status: what is done, what was not verified

**Done and tested:** everything listed in `PROJECT_LOG.md` section 2. 126 automated checks pass; browser checks pass; the hardware path (ESP32 -> website -> notification) was tested live by Parth.

**Not verified (say this honestly in the report or fix before the viva):**
1. The final sketch with the **three beep patterns** was never compiled by Claude (no Arduino compiler on the PC). Parth must upload it and listen once.
2. `database/tags_per_user.sql` must have been run in the real Supabase (Parth believes he did; the website cannot confirm this).
3. Browser push depends on the three `VAPID_*` values in `.env` and on Chrome permission being allowed.
4. Tested on Windows + Chrome + one ESP32 DevKit only.

## 6. Known limitations (good "Limitations" chapter)

- One reader belongs to **one account** (its key). Switching accounts means pairing a new reader and changing the key with the Serial command `key ...`.
- The ESP32 and the laptop must be on the **same Wi-Fi**; the ESP32 needs **2.4 GHz** (no 5 GHz). Hotspot demo works; the laptop IP changes per network.
- The site runs on the laptop (Flask development server). Not deployed. For production: a real WSGI server, HTTPS, a shared rate-limit store (Redis), and `FLASK_DEBUG` off.
- Rate limiting uses in-memory storage (resets on restart; fine for one process).
- RFID card ids can be cloned by someone who reads them. Acceptable for a wardrobe, not for payments.
- The matcher is rule-based by design (explainable), not machine learning; it does not know weather or body type.
- No email verification at sign-up (the team chose to postpone it to the major project).

## 7. Future work (not built)

Laundry / "in the wardrobe" status (second scan = returned), reader online/offline heartbeat, "you never wear these" nudges,
cost per wear, several labelled readers, wear statistics page, weather-based morning suggestion, email verification, deployment.

---

## 8. Viva questions to prepare (with the answer file)

| Question | Answer in |
|---|---|
| How does the matcher decide, and why not ML? | `outfit_engine.py` docstring, `PROJECT_LOG.md` |
| How does a card tap become a notification? | `PROJECT_LOG.md` section 3 |
| How do you stop one user reading another's data? | `SECURITY.md` (every query filters by user id; RLS; service key server-only) |
| How is the reader authenticated? | 256-bit key shown once, only its SHA-256 stored, rate limited per key |
| What if someone floods the scan route? | 120/min per IP, 30/min per key |
| Why can the same card work in two accounts? | Tag key is `(user_id, tag_uid)` |
| What is CSRF and where is it off? | Flask-WTF on all forms; only the device scan route is exempt, protected by the key instead |
