# Style Sync: project map for beginners

Read this first. No coding knowledge needed. To find anything in VS Code, press **Ctrl+Shift+F** and search the keyword given in the tables below.

## 1. The idea: Style Sync is a restaurant

| In the restaurant | In our project | Files |
|---|---|---|
| The **dining room** (what customers see) | The **frontend**: pages, colours, buttons | `templates/*.html`, `static/css/style.css` |
| The **waiter** (reacts to clicks) | **JavaScript** in the browser | `static/js/*.js` |
| The **kitchen** (does the real work, follows the rules) | The **backend**: Python + Flask | `app.py`, `auth.py`, `validators.py` |
| The **storeroom** (keeps everything safe) | The **database**: Supabase | `database/schema.sql` (the storeroom's blueprint) |
| The **security guard** | Login, rate limit, CSRF | `auth.py`, `extensions.py` |
| The **secret keys** to the storeroom | Passwords for Supabase | `.env` (never share it) |

**Rule:** the customer never walks into the kitchen or storeroom. The browser only talks to Flask, and only Flask talks to Supabase.

## 2. What happens when you click "Log in"

1. **You** type an email and password and click Log in.
2. **`landing.js`** (waiter) checks nothing is empty, then sends the details to the kitchen. Search: `handleAuthSubmit`.
3. **`app.py`** receives the request and checks the CSRF token ("is this request really from our own page?"). Search: `csrf`.
4. **`extensions.py`** (guard) counts your attempts. More than 5 per minute means "Too many attempts". Search: `limiter`.
5. **`validators.py`** checks the email and password are properly shaped. Search: `clean_email`.
6. **`auth.py`** sends them to Supabase, which compares against the stored hash. Search: `def login`.
7. **`auth.py`** either creates a login cookie ("wristband") or answers with the same vague error for every failure.
8. **`landing.js`** either moves you to the dashboard or shows a red message.

Every feature we add later follows this same path: click, JavaScript, Flask, check, Supabase, answer.

## 3. Folder tour: what to open and what to ignore

(The IoT files, new features and the full build history are listed in `PROJECT_LOG.md`.)

```
StyleSync_Prototype/
├── app.py            MAIN FILE. Starts the website, lists the pages (routes), sets security rules
├── auth.py           Signup / login / logout
├── validators.py     Rules for what input is allowed
├── extensions.py     Security tools: CSRF + rate limiter
├── db.py             Connection to Supabase
├── items.py          Wardrobe: list / add (with photo) / delete clothes
├── images.py         Photo safety + shrinking + upload to Supabase Storage
├── options.py        The fixed dropdown choices (categories, colours, seasons...)
├── outfit_engine.py  THE MATCHER'S BRAIN: scores pieces and whole outfits, avoids repeats
├── outfits.py        Suggestion API, save/wear a look, remove a saved look, history
├── tags.py           Hanger tags: the scan logic (process_scan), link a tag to a piece, simulate a scan
├── iot.py            The ESP32 side: pair a reader (device key) and receive its scans
├── notify.py         Notifications: the bell, reminders, and real browser push (Web Push)
├── database/iot.sql           Database additions for readers, push subscriptions, notifications
├── firmware/         ESP32 sketch (rfid_scanner.ino) and wiring guide
├── tools/            fake_reader.py: a pretend ESP32 for testing without hardware
├── database/schema.sql        Database tables. Pasted into Supabase once
├── .env              Your secret keys (you create this from .env.example)
├── templates/        The HTML pages
│   ├── base.html         The frame every page shares (fonts, styles, scripts)
│   ├── landing.html      Login / signup page
│   ├── dashboard.html, wardrobe-gallery.html, outfit-matcher.html, history.html, profile.html
│   └── includes/         Reusable pieces: top menu (nav.html), "Add item" popup
├── static/           Files the browser downloads directly
│   ├── css/style.css     ALL the colours and layout (the coral theme)
│   ├── js/               The waiters: one small file per page + app.js (shared helpers)
│   └── images/logo.svg
├── PROJECT_MAP.md    This file
├── HOW_IT_WORKS.md   The security explained
│
├── venv/             IGNORE. Python's toolbox (thousands of files, not ours)
├── __pycache__/      IGNORE. Python's automatic cache
└── _legacy_unused/   Old files we no longer use. Safe to delete
```

**Only about 10 files are really ours.** The rest is tools.

## 4. "Where do I find...?" cheat sheet

| I want to change or show... | Open | Search for |
|---|---|---|
| Colours, fonts, button look | `static/css/style.css` | `Tokens` (all colours at the top) |
| Top menu | `templates/includes/nav.html` | `nav_links` |
| A page's text | `templates/<page>.html` | the visible words |
| What a button does | `static/js/<page>.js` | the button's `id` |
| The list of pages/URLs | `app.py` | `@app.route` |
| Login rules | `auth.py` | `def login` |
| Password rules | `validators.py` | `password_problem` |
| Rate limits | `auth.py` | `@limiter.limit` |
| Error messages users see | `app.py` and `auth.py` | `_error`, `LOGIN_FAILED` |
| Database tables | `database/schema.sql` | `create table` |
| Adding / deleting clothes | `items.py` | `def add_item`, `def delete_item` |
| What photos are allowed / how they're shrunk | `images.py` | `_to_clean_jpeg` |
| Add Item popup behaviour | `static/js/add-item-modal.js` | `handleSubmit` |
| Dropdown choices | `options.py` | `COLORS`, `OCCASIONS` |
| Hanger scan rules (debounce, once-a-day wear, hanger looks) | `tags.py` | `process_scan` |
| ESP32 scan route and device keys | `iot.py` | `def scan`, `_hash` |
| Notifications and push | `notify.py` | `create`, `_push_to_user`, `host_allowed` |
| Outfit-matching logic (the rules and points) | `outfit_engine.py` | `_piece_points`, `_palette`, `suggest` |
| Matcher page behaviour + sparkles | `static/js/outfit-matcher.js`, `static/js/sparkles.js` | `handleMatch`, `sparkleBurst` |
| Worn / Saved history | `outfits.py`, `templates/history.html` | `get_history`, `remove_saved` |

## 5. Vocabulary in one line each

- **Route:** a URL and the Python function that answers it (`@app.route("/dashboard")`).
- **Template:** an HTML page with blanks Python fills in (`{{ user_first_name }}`).
- **Session / cookie:** a signed wristband the browser shows on every request so we know who you are.
- **Hash:** a scrambled version of a password that can't be turned back. We only ever store this.
- **CSRF token:** a secret code in each form, proving the request came from our page.
- **Rate limit:** a cap on how often someone can try something.
- **API endpoint:** a URL that returns data instead of a page (for example `/auth/login`).
- **RLS:** Supabase's built-in lock on database tables.

## 6. How we'll build the rest, in small steps

Each step ends with something you can click and see working.

| Step | You will see | New files |
|---|---|---|
| 1. Login works with real accounts | Sign up, log in, log out, wrong password blocked | DONE |
| 2. Real wardrobe | Add a garment with a photo, it stays after refresh, delete it | DONE: `items.py`, `images.py` |
| 3. Outfit matcher in Python | Smarter matcher, rules live on the server | DONE: `outfit_engine.py` |
| 4. Wear history + dashboard numbers | Worn / Saved tabs, remove saved, clickable stats | DONE: `outfits.py` |
| 5. Hanger tags | Pair a reader, link tags, scan = worn, hanger looks in History | DONE: `tags.py`, `iot.py`, firmware |
| 6. Notifications | Bell with unread badge, reminders, real browser push | DONE: `notify.py`, `sw.js` |

After each step I will tell you in plain words: what changed, which file, and why. You test it, then we move on. If anything looks wrong, tell me what you see and I'll trace it.

## 7. How you can help right now

1. Make a free account at supabase.com and create a project.
2. Tell me when it's created. **Don't paste any keys in chat.**
3. I'll walk you through the 4 clicks to connect it (turn off email confirmation, run `database/schema.sql`, fill `.env`).
