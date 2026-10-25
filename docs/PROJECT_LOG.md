# StyleSync: complete project log (for the college report and for revising)

Everything that was built, in the order it happened, with HOW it works and WHERE the code is.
Read top to bottom once and you can explain the whole project. Last updated after the "beeps, live feed, wear line" step.

---

(Folder layout: see the diagram near the top of `README.md`. Documents are in `docs/`, SQL in `database/`.)

## 1. What StyleSync is (one paragraph)

A smart wardrobe website. You photograph your clothes, and the site suggests outfits **and explains why**
(rule-based, no black-box AI). A second part, **IoT hanger tags**, connects the physical wardrobe to the website:
an RFID tag on each hanger, an ESP32 reader, and the website logs what you wear, warns you about repeats, and notifies you.

Stack: Python Flask, Supabase (Postgres + login + photo storage), HTML/CSS/JS + Bootstrap, Pillow, ESP32 (Arduino C++) + RC522 reader, Web Push.

---

## 2. Features, with where the code lives

### Core website
| Feature | How it works | Files |
|---|---|---|
| Sign up / log in | Supabase Auth (passwords hashed with bcrypt, we never see them). Flask keeps a session cookie. | `auth.py` |
| Wardrobe | Add a piece with photo, category, colour (or "Other"), season, occasion, style. Photos are re-encoded with Pillow (strips hidden data). | `items.py`, `images.py`, `wardrobe-gallery.html` |
| Outfit Matcher | Scores every combination of top + bottom + shoes (+ layer, accessory): occasion, season, colour palette, style unity, rarely-worn bonus. Picks randomly among the near-best so Shuffle gives variety. Shows reasons as plain sentences. | `outfit_engine.py`, `outfits.py` |
| Occasion first | For each slot only the pieces closest to the chosen occasion are used (exact, else the nearest related one). Freshness never beats occasion. Fixed the "Party shows Casual" bug. | `outfit_engine.py` (`_closeness`) |
| One-week rule | A piece or whole outfit worn in the last 7 days is penalised (`REPEAT_PENALTY`). Nothing is exempt (shoes and accessories too, as you chose). | `options.py` (`REPEAT_WINDOW_DAYS`, `REPEAT_EXEMPT`) |
| History | Worn / Saved looks, remove from saved, hanger looks. | `outfits.py`, `history.html` |
| Dashboard cards link to pages | Stats cards are clickable. | `dashboard.html` |

### Security (all done and documented in `SECURITY.md` / `HOW_IT_WORKS.md`)
Server-side validation, rate limiting (Flask-Limiter), password hashing, generic error messages, CSRF tokens,
Content-Security-Policy with nonce + SRI, Supabase row-level security with the service key used only on the server,
startup environment checks, SSRF allow-list for push endpoints, device keys stored only as SHA-256 hashes.

### IoT part (hanger tags)
| Feature | How it works | Files |
|---|---|---|
| Pair a reader | Hangers page creates a random 256-bit key, shown ONCE. The server stores only its hash. Max 5 readers per account. | `iot.py`, `hangers.html` |
| ESP32 reads a tag | RC522 reads the card id, ESP32 sends `POST /api/iot/scan` with header `X-Device-Key`. The **key decides which account** the scan belongs to; the reader never names a user. | `firmware/rfid_scanner/rfid_scanner.ino`, `iot.py` |
| Link tag to piece | Unknown tag appears on the Hangers page, you pick a piece. One tag per piece. | `tags.py` |
| What a scan does | Debounce 5 s; linked tag: counts as worn (once per day), checks the 7-day rule (piece and whole outfit), groups pieces scanned within 2 h into one "Hanger look" in History, notifies. Unknown tag: notifies every time, stored once. | `tags.py` (`process_scan`) |
| Same-day tap | Tapping a piece already worn today says so, no double count. "Today" flips at the laptop's local midnight. | `tags.py` (`_same_day_note`) |
| Notifications | Bell in the header (polls every 15 s) plus real browser push (Web Push, VAPID, service worker `sw.js`). Pop-up titles: "Hanger scan", "New hanger tag", "Worn this week", "Outfit repeat", "Already worn today". 60-day "you haven't worn this" nudge. | `notify.py`, `notifications.js`, `sw.js` |
| Simulate scan | Same code as the real reader, for demos without hardware. | `tags.py` (`/api/tags/simulate`) |
| Tags per account | A tag belongs to the ACCOUNT, not the card. The same physical card can mean Nike shoes in one account and a watch in another. Database key is `(user_id, tag_uid)`. | `tags.py`, `database/tags_per_user.sql` |

### Latest additions (this step)
| Feature | How it works | Files |
|---|---|---|
| Longer pop-ups + close button | Toasts stay 7 s (9 s for problems), pause while the mouse is on them, have a cross button. Text is inserted as text, never HTML. | `static/js/toast.js`, `style.css` |
| Wardrobe tag status | Green dot + tag icon "Hanger tag assigned", or grey "No hanger tag" under each card. | `macros.html`, `tags.tagged_item_ids` |
| **1. Different beeps** | The server's JSON answer (`status`, `repeat`) is turned into sound by the sketch: **1 short = logged, 2 short = new/unlinked tag, 1 long = worn this week, 3 quick = error.** Needs ONE re-upload of the sketch. | `rfid_scanner.ino`, `firmware/README.md` |
| **2. Tag status in Matcher** | Matcher suggestions mark each piece `tagged: true/false`; the card shows the same green/grey line. | `outfits.py`, `static/js/app.js` (`tagStatus`) |
| **3. Wear line in Wardrobe** | "Worn 3 times · last 2 days ago" or "Never worn yet" from `wear_count` and `last_worn_at`. | `items.py` (COLUMNS), `macros.html` |
| **4. Live Hangers page** | Page asks `/api/tags/feed` every 3 s. The answer contains a fingerprint of the tag list; if it changed (a scan happened) the page shows the scan message and reloads itself. Never reloads while you type or while the one-time key is shown; pauses in a hidden tab. Green pulsing "Live" badge. | `tags.py` (`feed`, `_state`), `hangers.js`, `hangers.html` |

---

## 3. How a real scan travels (explain this in the viva)

1. You touch a hanger card to the RC522. The ESP32 reads the id (e.g. `F35891 04`).
2. ESP32 sends it over Wi-Fi: `POST http://<laptop-ip>:5000/api/iot/scan`, header `X-Device-Key`, body `{"tag_uid": "..."}`.
3. `iot.py` hashes the key, finds the device and so the OWNER account (rate limits: 120/min per IP, 30/min per key).
4. `tags.process_scan(owner, tag)` does the work (debounce, link lookup, wear count, repeat rules, look grouping, notification).
5. The server answers `{"status": "...", "repeat": true/false}`. The ESP32 beeps accordingly.
6. The notification appears in the bell, as a browser pop-up (push), and the open Hangers page refreshes itself.

Important rule to remember: **the reader belongs to ONE account (its key).** To use the same reader for another account,
pair a new reader on that account and change the ESP32 key with the Serial command `key NEWKEY`.

---

## 4. Files you must run / know

| Item | Notes |
|---|---|
| `database/schema.sql`, `database/hardening.sql`, `database/iot.sql` | Already run in Supabase. |
| `database/tags_per_user.sql` | Run once in Supabase SQL Editor so the same card works in several accounts. (Run it if you haven't.) |
| `.env` | Supabase keys, VAPID keys for push. Never share or commit. |
| Start the site | `$env:HOST="0.0.0.0"; venv\Scripts\python.exe app.py` (0.0.0.0 so the ESP32 can reach it) |
| ESP32 settings | Serial Monitor 115200, line ending "Newline": `ssid`, `pass`, `url`, `key`, `show`, `restart`. Saved inside the ESP32; the sketch's DEFAULT_* values are only a fallback. |
| College demo | Use your phone hotspot (2.4 GHz). Run `ipconfig`, set `ssid`, `pass`, `url http://<new-ip>:5000/api/iot/scan`, then `restart`. |
| Tools | `tools/fake_reader.py` (pretend ESP32), `tools/make_vapid_keys.py`, `tools/pretend_worn.py`. |

Other documents: `README.md` (setup), `SECURITY.md` (what is protected and where), `HOW_IT_WORKS.md` (security explained),
`PROJECT_MAP.md` (folder tour), `firmware/README.md` (wiring + beeps), `THEME_PROMPT.md` (UI theme).

---

## 5. How it was tested (honest summary)

The 126 checks are saved in `tests/run_iot_checks.py` (run it, it should print `126 checks passed, 0 failed`). For the report writer see `HANDOFF_FOR_REPORT.md`.

- 126 automated checks with an in-memory fake database (scan logic, isolation between users, one-week rule, matcher, same-day/midnight, per-account tags, beeps data, feed, rate limits, CSRF on every route).
- Headless-Chrome browser checks for toasts, Wardrobe, Matcher tags, live Hangers page (reload, no reload while typing).
- Live checks against the real Supabase earlier in the project, and real hardware tests by you (ESP32 + RC522 + buzzer, cards `F3 58 91 04` and `24 61 D6 05`).
- NOT verified by me: the newest sketch (beeps) was not compiled here, no Arduino compiler on this PC. Upload it and try the three beeps.

---

## 6. Problems met and how they were solved (good material for the report)

- Notification bell updated slowly: polling 30 s changed to 15 s, plus push message refreshes it at once.
- Unknown tag notified only once: removed the throttle; every read notifies, the tag is stored once.
- Party showed Casual outfits: freshness points beat the occasion; fixed with "occasion first" tiers.
- ESP32 setup: Wi-Fi name was a 5 GHz network, placeholder URL/key, empty Serial Monitor until reset; fixed with Serial commands that save settings in the ESP32.
- Same card in two accounts: the old database key made a tag unique worldwide; changed to unique per account.
- Scans going to the wrong account: the reader's key belongs to one account; explained and documented (section 3).
- Test-quality lessons: removed tests that always pass; fixed a fake-database bug that reused queries.

---

## 7. Ideas not built yet (future work for the report)

Laundry / "in the wardrobe" status (second scan = returned), reader online/offline heartbeat, unworn-piece nudges,
cost per wear, several readers with labels, wear statistics page, weather-based morning suggestion,
email verification at sign-up (planned for the major project).

---

## 8. The PDF

The complete, up-to-date PDF of the whole project is `StyleSync_Complete_Project_Documentation.pdf` (in this docs folder). The older study guide and report PDFs were removed because they did not include the IoT part.
