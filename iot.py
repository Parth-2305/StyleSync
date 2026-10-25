"""The ESP32 side: pairing a reader (device key) and receiving its scans.
A reader is NOT a person, so it cannot log in or hold a CSRF token. It proves itself with a secret device key instead,
and that key can do exactly one thing: report scans for its owner."""
import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

import db
import notify
from auth import current_user_id, login_required
from extensions import csrf, limiter
from tags import clean_tag, process_scan
from validators import _strip_hidden

bp = Blueprint("iot", __name__, url_prefix="/api")
log = logging.getLogger(__name__)
MAX_DEVICES = 5


def _hash(key):
    """Only this SHA-256 hash is stored. A 256-bit random key cannot be guessed, so a fast hash is enough."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _key_bucket():
    """Rate-limit bucket per device key, so one noisy reader can't use up another reader's allowance."""
    return _hash(request.headers.get("X-Device-Key", ""))[:16]


# ---------------------------------------------------------------- the scan route (called by the ESP32)
@bp.post("/iot/scan")
@csrf.exempt  # not a browser: it has no cookie or CSRF token. The device key is its proof of identity instead
@limiter.limit("120 per minute")
@limiter.limit("30 per minute", key_func=_key_bucket)
def scan():
    key = request.headers.get("X-Device-Key", "")
    if not 32 <= len(key) <= 100:
        return jsonify(error="Not authorised."), 401  # the same answer for a missing, short, wrong or revoked key
    devices = db.data_client().table("devices")
    found = devices.select("id,user_id").eq("key_hash", _hash(key)).execute().data
    if not found:
        return jsonify(error="Not authorised."), 401
    tag = clean_tag((request.get_json(silent=True) or {}).get("tag_uid"))
    if not tag:
        return jsonify(error="Bad request."), 400
    device = found[0]
    try:
        stamp = datetime.now(timezone.utc).isoformat()
        notify.run_later(lambda: devices.update({"last_seen_at": stamp}).eq("id", device["id"]).execute())  # not needed for the answer
        result = process_scan(device["user_id"], tag)  # the device never says WHICH user: the key decides
    except Exception:
        log.exception("scan failed")
        return jsonify(error="Server error."), 500
    return jsonify(status=result["status"], repeat=result.get("repeat", False))  # tiny answer: all the reader needs for LED and beep


# ---------------------------------------------------------------- pairing from the Hangers page
@bp.post("/devices")
@login_required
@limiter.limit("10 per minute")
def add_device():
    name = " ".join(_strip_hidden((request.get_json(silent=True) or {}).get("name")).split())
    if not re.fullmatch(r"[A-Za-z0-9 '\-]{1,40}", name):
        return jsonify(error="Give the reader a short name (letters, numbers, spaces)."), 400
    user_id, devices = current_user_id(), db.data_client().table("devices")
    if devices.select("id", count="exact").eq("user_id", user_id).limit(1).execute().count >= MAX_DEVICES:
        return jsonify(error=f"You can pair up to {MAX_DEVICES} readers. Remove one first."), 400
    key = secrets.token_urlsafe(32)  # 256 random bits. Shown ONCE below and never stored in readable form
    devices.insert({"user_id": user_id, "name": name, "key_hash": _hash(key)}).execute()
    return jsonify(ok=True, key=key, name=name), 201


@bp.delete("/devices/<device_id>")
@login_required
@limiter.limit("30 per minute")
def remove_device(device_id):
    try:
        device_id = str(uuid.UUID(device_id))
    except ValueError:
        return jsonify(error="Not found."), 404
    db.data_client().table("devices").delete().eq("id", device_id).eq("user_id", current_user_id()).execute()  # key stops working at once
    return jsonify(ok=True)
