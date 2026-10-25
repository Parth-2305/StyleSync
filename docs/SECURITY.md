# Security: StyleSync (as built)

This describes what the code actually does today. Each line points at the file to open.

## Threat model

Protected against: guessing passwords, stealing or forging login cookies, one user reading or changing another user's data, malicious uploads, script injection (XSS), forged requests (CSRF), flooding, and leaked keys. Out of scope for a capstone: DDoS protection and penetration-test-grade hardening.

## 1. Secrets

| Secret | Where it lives | Reaches the browser? |
|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` (full database power) | `.env` only | Never |
| `SUPABASE_ANON_KEY` | `.env` only (used only on the server) | Never |
| `FLASK_SECRET_KEY` (signs login cookies) | `.env` only | Never |

- `.env` is in `.gitignore`. `.env.example` has placeholders only.
- `config.py` refuses to start the app if a secret is missing, a placeholder, too short, or the two Supabase keys are swapped.
- The browser never talks to Supabase. Only the Flask server does.

## 2. Authentication (`auth.py`)

- Passwords are handled by Supabase Auth (bcrypt hash). We never store, log or return a password.
- Server-side password rules: 8+ characters, a letter and a number, at most 72 bytes (`validators.py`).
- Every login failure gives the same message ("Incorrect email or password"), so attackers can't learn which emails exist.
- Login cookie: signed, `HttpOnly`, `SameSite=Lax`, `Secure` + `__Host-` prefix in production, expires after 2 hours. `session.clear()` runs before login (stops session fixation) and on logout.
- Every page and every `/api/*` route needs a login (`@login_required`).
- No admin pages exist, so there is nothing to protect there. The service key never leaves the server.

## 3. Authorisation (users see only their own data)

- Every database query filters by the logged-in user's id (`items.py`, `outfits.py`).
- Someone else's item or look returns "not found", never "forbidden", so existence isn't revealed.
- Looks can only contain pieces the user owns. Only saved looks can be removed.
- Supabase Row Level Security is ON for every table with no policies, and `database/hardening.sql` revokes all access for `anon` and `authenticated`. The public key cannot read or write anything (tested).

## 4. Input handling

- All checks are repeated on the server (`validators.py`). The browser checks are only for convenience.
- Dropdown values must be on fixed lists. "Other" values: letters/numbers/spaces/hyphens only, 30 characters max.
- Invisible control characters (null bytes, right-to-left overrides) are stripped.
- Output is escaped: Jinja auto-escape on the server, `escapeHtml()` in JavaScript. A script tag saved as an item name is shown as plain text (tested).
- Photos (`images.py`): opened with Pillow (so renamed non-images fail), converted to a fresh JPEG (removes hidden metadata and GPS), shrunk, stored under a random name.

## 5. Abuse limits (`extensions.py`, each route)

| Limit | Value |
|---|---|
| Login | 5 / minute and 30 / hour per IP; 10 / hour per email |
| Signup | 3 / minute and 10 / hour per IP |
| Add item / save look / suggest / delete | 20 / 30 / 60 / 60 per minute |
| Everything else | 300 / hour per IP |
| Pieces per account | 300 |
| History rows per account | 2000 |
| Request size | 6 MB, and 512 KB / 40 parts for text forms |

## 6. Forged requests and browser protections (`app.py`)

- CSRF token required on every POST/DELETE (all 17 routes verified).
- Headers on every response: Content-Security-Policy (with a per-request nonce), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`. HSTS in production.
- Bootstrap and the icon font are pinned to exact versions with integrity hashes.
- Debug mode is off unless `FLASK_DEBUG=1`, and never in production. Errors show friendly generic messages, never stack traces.

## 7. Dependencies

Exact versions are pinned in `requirements.txt`. `pip-audit` reports no known vulnerabilities. Re-run it before every demo: `pip install pip-audit` then `pip-audit`.

## 8. IoT readers, push and notifications

| Risk | Defence | File |
|---|---|---|
| Someone calls the scan route without being a reader | Secret device key (256 random bits), shown once, stored only as a SHA-256 hash; any wrong, missing or revoked key gets the same 401 | `iot.py` |
| A reader acting for another user | The key decides the owner; the reader never names a user. Tags belong to the account whose reader scanned them, so the same card in two accounts never interferes | `iot.py`, `tags.py` |
| A stolen key | It can only report scans for its owner. Removing the reader on the Hangers page kills it at once | `iot.py` |
| Flooding by a noisy or hostile reader | 30 scans per minute per key, 120 per IP, 5-second debounce per tag, caps of 5 readers and 300 tags per user | `iot.py`, `tags.py` |
| CSRF on the scan route | It is the one route exempt from CSRF (a device has no cookie); the device key replaces it. Every other new route still needs a token | `iot.py` |
| Server-side request forgery through push | A push endpoint must be https and on a short list of real push services (Chrome, Edge, Firefox, Safari); anything else is refused | `notify.py` |
| Forged push messages | Every push is signed with the server's private VAPID key | `notify.py` |
| A notification link opening another website | The service worker only opens pages on our own address | `static/js/sw.js` |
| Reminder spam | Double reads within 5 seconds are ignored, one 60-day reminder per week | `tags.py`, `notify.py` |
| Database | `database/iot.sql`: RLS on, no access for public roles, format and length rules on tags and notifications | `database/iot.sql` |

Known limits of the IoT part: tag ids are not secret (they can be read by anyone holding a phone near a tag), so a scan is a logging convenience and not proof of identity. The scan request travels over plain HTTP on a home network in development; a real deployment must use HTTPS. A captured scan request could be replayed on a hostile network (signed timestamps would stop that).

## 9. Known limits and what to do before going public

| Limit | Fix before launch |
|---|---|
| Rate-limit counters are in memory (reset on restart) | Use Redis storage for Flask-Limiter |
| Behind a proxy all visitors look like one IP | Set `PROXY_HOPS=1` in `.env` |
| Logging out clears the cookie, but a stolen cookie works until it expires (2 h) | Server-side sessions, or a shorter lifetime |
| "Confirm email" is off in Supabase (demo setting) | Turn it on and connect real SMTP (Major Project) |
| Photos are public by URL (unguessable random names) | Private bucket + signed URLs if privacy matters |
| Google Fonts and jsDelivr are third-party hosts | Self-host the files |

## 10. Manual checklist (dashboard settings no code can change)

1. Supabase, SQL Editor: run `database/hardening.sql` once.
2. Supabase, Authentication, Attack Protection: enable CAPTCHA and leaked-password protection if available.
3. Supabase, Authentication, URL Configuration: Site URL and Redirect URLs must list only your real address.
4. Turn on two-factor sign-in for your Supabase, GitHub and Google accounts.
5. Production: set `FLASK_ENV=production`, serve over HTTPS, keep `FLASK_DEBUG` unset.
6. Before the first `git init`: confirm `.env` shows as ignored (`git status` must not list it). If a key ever reaches Git or a chat, rotate it in Supabase, Project Settings, API Keys.
