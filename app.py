"""StyleSync: Flask entrypoint. Settings and security headers live here; login is in auth.py,
wardrobe in items.py, outfits and history in outfits.py."""
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask_limiter.errors import RateLimitExceeded
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()  # reads the .env file into environment variables

import auth
import iot
import items
import notify
import options
import outfits
import tags
from auth import current_user_id, login_required
from config import IS_PRODUCTION, check_environment
from extensions import csrf, limiter

check_environment()  # stops the app right here if a secret is missing, a placeholder, or the keys are swapped

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["FLASK_SECRET_KEY"],  # signs the login cookie; no random fallback, check_environment insists it exists
    SESSION_COOKIE_NAME="__Host-session" if IS_PRODUCTION else "session",  # __Host- = HTTPS-only, can't be set by a sub-domain
    SESSION_COOKIE_HTTPONLY=True,   # JavaScript can't read the cookie (blocks XSS theft)
    SESSION_COOKIE_SAMESITE="Lax",  # not sent on cross-site POSTs (CSRF defence in depth)
    SESSION_COOKIE_SECURE=IS_PRODUCTION,  # HTTPS-only once deployed
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),  # auto logout
    WTF_CSRF_TIME_LIMIT=7200,       # a form's CSRF token lasts as long as the login session (default 1 h surprised users)
    MAX_CONTENT_LENGTH=6 * 1024 * 1024,  # reject any request over 6 MB before reading it
    MAX_FORM_MEMORY_SIZE=512 * 1024,     # text fields in a form: 512 KB at most
    MAX_FORM_PARTS=40,                   # and at most 40 fields/files per form
)
if os.getenv("PROXY_HOPS"):  # only behind a trusted reverse proxy (e.g. 1): makes the rate limiter see the real visitor IP
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=int(os.environ["PROXY_HOPS"]), x_proto=int(os.environ["PROXY_HOPS"]))
csrf.init_app(app)
limiter.init_app(app)
app.register_blueprint(auth.bp)
app.register_blueprint(items.bp)
app.register_blueprint(outfits.bp)
app.register_blueprint(tags.bp)
app.register_blueprint(iot.bp)
app.register_blueprint(notify.bp)

SUPABASE_HOST = urlparse(os.environ["SUPABASE_URL"]).netloc  # garment photos are served from here


@app.before_request
def make_csp_nonce():
    g.csp_nonce = secrets.token_urlsafe(16)  # one-time code that lets OUR inline script run and nothing injected


@app.context_processor
def inject_csp_nonce():
    return {"csp_nonce": g.get("csp_nonce", "")}


@app.after_request
def add_security_headers(response):
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"        # browser must trust our content types
    h["X-Frame-Options"] = "DENY"                  # nobody can embed us (clickjacking)
    h["Referrer-Policy"] = "same-origin"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"  # features we never use stay off
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    # Content-Security-Policy: the browser only runs scripts/loads files from places we list. Even if someone
    # managed to inject HTML, their script would be blocked.
    h["Content-Security-Policy"] = "; ".join([
        "default-src 'self'",
        f"script-src 'self' 'nonce-{g.get('csp_nonce', '')}' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com",
        f"img-src 'self' data: blob: https://{SUPABASE_HOST}",
        "connect-src 'self'",
        "worker-src 'self'",  # the push-notification service worker (static/js/sw.js)
        "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
    ] + (["upgrade-insecure-requests"] if IS_PRODUCTION else []))
    if IS_PRODUCTION:
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"  # browsers refuse plain HTTP for a year
    if request.endpoint != "static":  # CSS/JS/images keep Flask's default caching, so edits show on refresh
        h["Cache-Control"] = "no-store" if "user_id" in session else "no-cache"
    return response


# Generic errors: the user sees a short friendly message, never a stack trace or internals.
def _error(message, status):
    if request.path.startswith("/auth/") or request.path.startswith("/api/"):
        return jsonify(error=message), status
    return render_template("error.html", message=message, status=status), status


@app.errorhandler(RateLimitExceeded)
def too_many(_e):
    return _error("Too many attempts. Please wait a minute and try again.", 429)


@app.errorhandler(CSRFError)
def bad_csrf(_e):
    return _error("Your session expired. Please refresh the page and try again.", 400)


@app.errorhandler(404)
def not_found(_e):
    return _error("We couldn't find that page.", 404)


@app.errorhandler(413)
def too_large(_e):
    return _error("That file is too large.", 413)


@app.errorhandler(500)
def server_error(_e):
    return _error("Something went wrong on our side. Please try again.", 500)


def get_greeting():
    """Time-of-day greeting for the dashboard ("Good morning")."""
    hour = datetime.now().hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"


COLOR_HEX = {color["name"]: color["hex"] for color in options.COLORS}


@app.template_filter("ago")
def ago(timestamp):
    """'2026-10-08T10:15:00+00:00' -> '5 min ago' (used on the Hangers page)."""
    if not timestamp:
        return "never"
    seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp.replace("Z", "+00:00"))).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    days = int(seconds // 86400)
    return f"{days} day{'s' * (days != 1)} ago"


@app.context_processor
def inject_shared_template_data():
    """Values every page can use in its template: who's logged in, and the dropdown choices."""
    full_name = session.get("full_name", "")
    return {
        "user": {"full_name": full_name, "email": session.get("email", "")},
        "user_first_name": full_name.split()[0] if full_name else "",
        "user_initial": full_name[:1].upper(),
        "color_hex": lambda name: COLOR_HEX.get(name, "#D1D5DB"),  # grey if unknown
        "category_labels": options.CATEGORY_LABELS,
        "occasions": options.OCCASIONS,
        "seasons": options.SEASONS,
        "styles": options.STYLES,
        "colors": options.COLORS,
    }


@app.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="images/favicon.ico"))


@app.route("/")
def landing():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/dashboard")
@login_required
def dashboard():
    my_items = items.get_items(current_user_id())
    # Day-of-year rotation so the note changes daily without needing a database.
    style_note = options.STYLE_NOTES[date.today().timetuple().tm_yday % len(options.STYLE_NOTES)]
    return render_template(
        "dashboard.html",
        greeting=get_greeting(),
        stats={
            "pieces": len(my_items),
            "categories_covered": len({item["category"] for item in my_items}),
            "categories_total": len(options.CATEGORY_LABELS),
            "saved_looks": outfits.count_saved(current_user_id()),
        },
        latest_items=my_items[:4],
        style_note=style_note,
    )


@app.route("/wardrobe")
@login_required
def wardrobe():
    user_id = current_user_id()
    return render_template("wardrobe-gallery.html", items=items.get_items(user_id), tagged_ids=tags.tagged_item_ids(user_id))


@app.route("/wardrobe/add")
@login_required
def add_item():
    # Old URL kept alive: open the gallery with the Add Item popup already showing.
    return redirect(url_for("wardrobe", add=1))


@app.route("/matcher")
@login_required
def matcher():
    return render_template("outfit-matcher.html", color_moods=options.COLOR_MOODS)


@app.route("/history")
@login_required
def history():
    entries = outfits.get_history(current_user_id())
    return render_template(
        "history.html",
        worn=[e for e in entries if e["source"] != "saved"],  # "worn" plus later hanger-scan entries
        saved=[e for e in entries if e["source"] == "saved"],
        tab="saved" if request.args.get("tab") == "saved" else "worn",
    )


@app.route("/hangers")
@login_required
def hangers():
    return render_template("hangers.html", **tags.page_data(current_user_id()), push_enabled=notify.push_enabled())


@app.route("/sw.js")
def service_worker():
    """The service worker must be served from the site root so it can show notifications for every page.
    It is public on purpose: it contains no secrets, only the code that displays a notification."""
    response = send_from_directory(app.static_folder + "/js", "sw.js", mimetype="text/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")


if __name__ == "__main__":
    # Debug mode lets anyone who can reach the page run code on your computer, so it is OFF unless you ask:
    #   set FLASK_DEBUG=1   (only on your own laptop, only for development)
    # HOST=0.0.0.0 lets the ESP32 reach this computer over your home Wi-Fi. Only do that on a network you trust:
    # this built-in server is for development. For real use, run behind a proper server with HTTPS.
    app.run(host=os.getenv("HOST", "127.0.0.1"), debug=os.getenv("FLASK_DEBUG") == "1" and not IS_PRODUCTION)
