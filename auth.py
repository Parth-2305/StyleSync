"""Sign up, log in, log out. Passwords are handled by Supabase Auth, which stores only a
bcrypt hash: we never store, log or even keep the password after forwarding it once."""
import logging
from functools import wraps

from flask import Blueprint, jsonify, redirect, request, session, url_for

import db
from extensions import limiter
from validators import clean_email, clean_name, password_problem

bp = Blueprint("auth", __name__, url_prefix="/auth")
log = logging.getLogger(__name__)

# One vague message for every login failure, so an attacker can't tell
# "no such email" from "wrong password" (that would reveal who has an account).
LOGIN_FAILED = "Incorrect email or password."
SIGNUP_FAILED = "We couldn't create that account. Check your details, or try logging in."
UNAVAILABLE = "Something went wrong on our side. Please try again."


def login_required(view):
    """Put on any page that needs a logged-in user; visitors go back to the landing page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return _fail("Please log in again.", 401)
            return redirect(url_for("landing"))
        return view(*args, **kwargs)
    return wrapper


def current_user_id():
    return session["user_id"]


def _fail(message, status):
    return jsonify(error=message), status


def _start_session(user, fallback_name=""):
    session.clear()  # drop any old cookie data so a stolen pre-login cookie can't be reused
    session.permanent = True  # lifetime is set in app.py
    session["user_id"] = user.id
    session["email"] = user.email
    session["full_name"] = (user.user_metadata or {}).get("full_name") or fallback_name or "Friend"


def _email_key():
    """Second rate-limit bucket: per target email, so many IPs can't hammer one account."""
    return ((request.get_json(silent=True) or {}).get("email") or "").strip().lower()[:254]


@bp.post("/signup")
@limiter.limit("3 per minute;10 per hour")
def signup():
    data = request.get_json(silent=True) or {}
    name, email, password = clean_name(data.get("full_name")), clean_email(data.get("email")), data.get("password")
    if not name:
        return _fail("Please enter your name (up to 60 characters).", 400)
    if not email:
        return _fail("Enter a valid email address.", 400)
    if password_problem(password):
        return _fail(password_problem(password), 400)
    if not db.is_configured():
        return _fail(UNAVAILABLE, 503)

    try:
        result = db.auth_client().auth.sign_up(
            {"email": email, "password": password, "options": {"data": {"full_name": name}}}
        )
    except Exception:  # supabase raises several error types; details go to OUR log, not the user
        log.exception("signup failed")
        return _fail(SIGNUP_FAILED, 400)

    if result.session and result.user:  # "Confirm email" is off in Supabase, so the account works at once
        _start_session(result.user, name)
        return jsonify(ok=True, redirect=url_for("dashboard"))
    return _fail(SIGNUP_FAILED, 400)  # no session = Supabase wants email confirmation, which we don't use yet


@bp.post("/login")
@limiter.limit("5 per minute;30 per hour")
@limiter.limit("10 per hour", key_func=_email_key)
def login():
    data = request.get_json(silent=True) or {}
    email, password = clean_email(data.get("email")), data.get("password")
    if not email or not isinstance(password, str) or not 1 <= len(password.encode("utf-8")) <= 72:
        return _fail(LOGIN_FAILED, 401)
    if not db.is_configured():
        return _fail(UNAVAILABLE, 503)

    try:
        result = db.auth_client().auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        log.warning("failed login attempt")  # never log the email or password
        return _fail(LOGIN_FAILED, 401)

    _start_session(result.user)
    return jsonify(ok=True, redirect=url_for("dashboard"))


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True, redirect=url_for("landing"))
