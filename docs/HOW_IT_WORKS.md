# How Style Sync's security works (learning guide)

Read this top to bottom once. Each section says **what** we did, **which tool**, **where in the code**, and **why it helps**. This is also your viva answer sheet.

## The big picture

```
Browser  --(JSON + CSRF token)-->  Flask (app.py, auth.py)  --(secret keys)-->  Supabase
   ^                                    |
   +------ signed login cookie <--------+
```

The browser never talks to Supabase. Only Flask does, and only Flask holds the secret keys. So all security checks live in one place: our Python code.

## 1. Server-side validation: `validators.py`

- **What:** Python re-checks every field (name length, email shape, password strength) on the server.
- **Why:** JavaScript checks in `landing.js` only give instant feedback. Anyone can skip them with dev tools or `curl`. Only the server check is trusted.
- **Rule of thumb:** client-side validation is for users, server-side validation is for security.

## 2. Login rate limiting: `extensions.py` and `@limiter.limit` in `auth.py`

- **Tool:** Flask-Limiter.
- **What:**
  - Login: 5 per minute and 30 per hour per IP address.
  - Login, per target email: 10 per hour, so many IPs can't all hammer one account.
  - Signup: 3 per minute and 10 per hour.
  - Everything else: 300 per hour.
- **Why:** Guessing passwords needs thousands of tries. A limit makes that impractical. The server answers `429 Too many attempts`.

## 3. Passwords: never stored, never readable

- **Tool:** Supabase Auth, which uses bcrypt (a slow, salted, one-way hash).
- **What:** We forward the password once to Supabase and never save it or log it. Supabase keeps only the hash. Even we cannot read anyone's password.
- **Why:** If the database leaks, the attacker gets hashes that can't be reversed cheaply. Writing our own password code is a common beginner mistake, so we don't.
- **Also:** passwords must be 8 to 72 characters with a letter and a number. 72 is bcrypt's limit.

## 4. Generic errors: `auth.py` and error handlers in `app.py`

- **What:**
  - Every login failure says `Incorrect email or password.` Wrong email and wrong password look identical.
  - Failed signup says `We couldn't create that account...` without revealing "email already registered".
  - Crashes show `Something went wrong on our side.` The real error goes to our log only (`log.exception`).
- **Why:** Detailed errors help attackers. "No such user" tells them which emails have accounts (called user enumeration). Stack traces reveal our code.

## 5. Proper authentication and sessions

| Protection | Tool / setting | What it stops |
|---|---|---|
| Signed login cookie | Flask `session` + `SECRET_KEY` | Forging a login. Changing the cookie breaks its signature. |
| `HttpOnly` cookie | `SESSION_COOKIE_HTTPONLY` | JavaScript (XSS) stealing the cookie. |
| `SameSite=Lax` | `SESSION_COOKIE_SAMESITE` | Cookie being sent from other websites' forms. |
| `Secure` cookie | `SESSION_COOKIE_SECURE` (on in production) | Cookie travelling over plain HTTP. |
| 2-hour lifetime | `PERMANENT_SESSION_LIFETIME` | A forgotten logged-in browser staying open forever. |
| `session.clear()` before login | `_start_session` in `auth.py` | Session fixation (reusing an old cookie). |
| CSRF token on every POST | Flask-WTF `CSRFProtect` | Another site tricking your browser into submitting actions. |
| `@login_required` on all pages | `auth.py` | Reaching `/dashboard` without logging in. |
| Security headers | `add_security_headers` in `app.py` | Clickjacking (`X-Frame-Options`), content-type tricks (`nosniff`). |
| Upload size cap | `MAX_CONTENT_LENGTH` | Huge files eating memory. |
| Secrets in `.env` | python-dotenv, `.gitignore` | Keys leaking into code or GitHub. |
| Row Level Security ON | `database/schema.sql` | Anyone using the public key reading the tables. |

## 6. One trade-off to know for your viva

Flask uses Supabase's **service-role key**, which bypasses row-level security. So every wardrobe query must include `.eq("user_id", current_user_id())`. We route all queries through one helper so it can't be forgotten. The alternative (per-user tokens and RLS policies) is safer by design but more complex and slower to build.

## 7. Files added

| File | Job |
|---|---|
| `auth.py` | signup, login, logout routes, `login_required` |
| `validators.py` | server-side input checks |
| `extensions.py` | CSRF and rate limiter objects |
| `db.py` | Supabase connections |
| `database/schema.sql` | database tables and RLS |
| `.env.example` | which secrets you need |

## 8. Try it yourself

1. In the Supabase dashboard, go to Authentication, then Providers, then Email, and turn off "Confirm email" (for the demo).
2. Run `database/schema.sql` in the SQL editor.
3. Copy `.env.example` to `.env` and fill it in.
4. Run `venv\Scripts\python.exe app.py` and sign up.
5. Try 6 wrong passwords in a row and watch the rate limit kick in.
