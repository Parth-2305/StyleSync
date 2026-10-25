"""Notifications: the in-app bell and real browser push (Web Push).
create() is the one function other files call: it stores the message AND pushes it to the user's browsers."""
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request
from pywebpush import WebPushException, webpush

import db
from auth import current_user_id, login_required
from extensions import limiter

bp = Blueprint("notify", __name__, url_prefix="/api")
log = logging.getLogger(__name__)

# Only these push services may be contacted. Without this list, a user could register ANY web address as their
# "browser" and make our server send requests to it (SSRF). Chrome, Edge, Firefox and Safari use these hosts.
PUSH_HOSTS = ("fcm.googleapis.com", ".notify.windows.com", "updates.push.services.mozilla.com", ".push.services.mozilla.com",
              "web.push.apple.com", ".push.apple.com")
MAX_SUBSCRIPTIONS = 10   # browsers per user
NUDGE_DAYS = 60          # "you haven't worn this in 60 days" reminder
NUDGE_EVERY_DAYS = 7     # but at most one reminder a week
SEND_IN_BACKGROUND = True  # tests switch this off so they can check the result straight away


def push_enabled():
    return bool(os.getenv("VAPID_PUBLIC_KEY") and os.getenv("VAPID_PRIVATE_KEY"))


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def host_allowed(url):
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == h.lstrip(".") or (h.startswith(".") and host.endswith(h)) for h in PUSH_HOSTS)


# ---------------------------------------------------------------- sending
def _push_to_user(user_id, payload):
    """Sends one push to every browser the user allowed. A dead subscription (browser uninstalled) is deleted."""
    table = db.data_client().table("push_subscriptions")
    for sub in table.select("id,endpoint,p256dh,auth").eq("user_id", user_id).execute().data:
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=json.dumps(payload),
                vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],  # proves to the push service that WE sent it
                vapid_claims={"sub": os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")},  # fresh dict: the library edits it
                ttl=3600,      # if the browser is offline, drop the message after an hour
                timeout=8,
            )
        except WebPushException as error:
            if error.response is not None and error.response.status_code in (404, 410):  # "this subscription no longer exists"
                table.delete().eq("id", sub["id"]).execute()
            else:
                log.warning("push failed: %s", error.response.status_code if error.response is not None else "no response")
        except Exception:
            log.exception("push error")


def run_later(task, *args):
    """Run slow work (database writes the caller does not need the result of) in the background, so the ESP32 gets its answer sooner.
    Tests switch SEND_IN_BACKGROUND off, so they still see the result straight away."""
    def safe():
        try:
            task(*args)
        except Exception:
            log.exception("background task failed")
    if SEND_IN_BACKGROUND:
        threading.Thread(target=safe, daemon=True).start()
    else:
        safe()


def create(user_id, message, kind="info", link=None, push=True, title="StyleSync", later=False):
    """Store a notification, and push it to the user's browsers if push is set up. `title` is the bold first line of the pop-up.
    later=True (used by hanger scans) stores it in the background so the reader is not kept waiting."""
    message = message[:300]

    def save_and_push():
        db.data_client().table("notifications").insert({"user_id": user_id, "message": message, "kind": kind, "link": link}).execute()
        if push and push_enabled():
            _push_to_user(user_id, {"title": title[:60], "body": message, "url": link or "/dashboard"})

    if later:
        run_later(save_and_push)  # a slow database or push service must never slow down the ESP32's request
    else:
        save_and_push()


# ---------------------------------------------------------------- reminders
def _maybe_nudge(user_id):
    """At most one reminder a week: 'You haven't worn X in 60 days'. Created lazily, when the bell is polled."""
    now = datetime.now(timezone.utc)
    table = db.data_client().table("notifications")
    since = (now - timedelta(days=NUDGE_EVERY_DAYS)).isoformat()
    if table.select("id").eq("user_id", user_id).eq("kind", "nudge").gte("created_at", since).limit(1).execute().data:
        return
    pieces = db.data_client().table("clothing_items").select("id,name,last_worn_at,created_at").eq("user_id", user_id).execute().data
    cutoff = now - timedelta(days=NUDGE_DAYS)
    stale = [(_parse(p["last_worn_at"] or p["created_at"]), p) for p in pieces if _parse(p["last_worn_at"] or p["created_at"]) < cutoff]
    if stale:
        oldest = min(stale, key=lambda pair: pair[0])[1]
        create(user_id, f"You haven't worn {oldest['name']} in over {NUDGE_DAYS} days. Give it a turn?", kind="nudge", link="/matcher")


# ---------------------------------------------------------------- the bell
@bp.get("/notifications")
@login_required
@limiter.limit("120 per minute")  # the page asks every 15 seconds
def list_notifications():
    user_id = current_user_id()
    table = db.data_client().table("notifications")
    try:
        try:
            _maybe_nudge(user_id)
        except Exception:
            log.exception("nudge failed")  # a reminder problem must never break the bell
        rows = table.select("id,message,kind,link,is_read,created_at").eq("user_id", user_id).order("created_at", desc=True).limit(15).execute().data
        unread = table.select("id", count="exact").eq("user_id", user_id).eq("is_read", False).limit(1).execute().count
    except Exception:
        log.warning("notifications unavailable: has database/iot.sql been run in Supabase?")  # quiet empty bell instead of an error on every page
        return jsonify(items=[], unread=0, push=False)
    return jsonify(items=rows, unread=unread, push=push_enabled())


@bp.post("/notifications/read")
@login_required
@limiter.limit("60 per minute")
def mark_read():
    """Marks one notification (or all, when no id is sent) as read."""
    note_id = (request.get_json(silent=True) or {}).get("id")
    query = db.data_client().table("notifications").update({"is_read": True}).eq("user_id", current_user_id())
    if note_id:
        try:
            query = query.eq("id", str(uuid.UUID(str(note_id))))
        except ValueError:
            return jsonify(error="Not found."), 404
    query.execute()
    return jsonify(ok=True)


# ---------------------------------------------------------------- browser push subscription
@bp.get("/push/key")
@login_required
@limiter.limit("30 per minute")
def push_key():
    return jsonify(enabled=push_enabled(), public_key=os.getenv("VAPID_PUBLIC_KEY", ""))


@bp.post("/push/subscribe")
@login_required
@limiter.limit("10 per minute")
def subscribe():
    data = request.get_json(silent=True) or {}
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    endpoint, p256dh, auth = data.get("endpoint"), keys.get("p256dh"), keys.get("auth")
    if not (isinstance(endpoint, str) and isinstance(p256dh, str) and isinstance(auth, str)) \
            or len(endpoint) > 600 or len(p256dh) > 200 or len(auth) > 100 or not host_allowed(endpoint):
        return jsonify(error="That browser can't receive notifications."), 400
    user_id, table = current_user_id(), db.data_client().table("push_subscriptions")
    existing = table.select("id").eq("endpoint", endpoint).execute().data
    if existing:  # same browser, maybe a different account now: it belongs to whoever is logged in
        table.update({"user_id": user_id, "p256dh": p256dh, "auth": auth}).eq("id", existing[0]["id"]).execute()
    else:
        if table.select("id", count="exact").eq("user_id", user_id).limit(1).execute().count >= MAX_SUBSCRIPTIONS:
            return jsonify(error="Too many browsers are registered. Turn some off first."), 400
        table.insert({"user_id": user_id, "endpoint": endpoint, "p256dh": p256dh, "auth": auth}).execute()
    create(user_id, "Browser notifications are on. You'll be told when a hanger is scanned.", kind="info", link="/hangers")
    return jsonify(ok=True)


@bp.post("/push/unsubscribe")
@login_required
@limiter.limit("10 per minute")
def unsubscribe():
    endpoint = (request.get_json(silent=True) or {}).get("endpoint")
    if isinstance(endpoint, str):
        db.data_client().table("push_subscriptions").delete().eq("user_id", current_user_id()).eq("endpoint", endpoint).execute()
    return jsonify(ok=True)
