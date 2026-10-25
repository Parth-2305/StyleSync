"""Hanger tags. process_scan() is the heart: it is called by the ESP32 route (iot.py) and by the website's
"Simulate scan" button, so real hardware and the demo behave exactly the same.
As everywhere, every query filters by the user's id."""
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

import db
import items as items_mod
import notify
import options
from auth import current_user_id, login_required
from extensions import limiter

bp = Blueprint("tags", __name__, url_prefix="/api/tags")
log = logging.getLogger(__name__)
TAG_RE = re.compile(r"[0-9A-F]{8,20}")  # the hex id printed by the RFID reader (4 to 10 bytes)
DEBOUNCE_SECONDS = 5          # a reader often reports one swipe two or three times: ignore repeats within 5 s
LOOK_WINDOW_HOURS = 2         # pieces taken off the rail within 2 hours count as ONE outfit
MAX_TAGS = 300


def _table(name):
    return db.data_client().table(name)


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def tagged_item_ids(user_id):
    """Ids of this user's pieces that have a hanger tag (the Wardrobe shows a green dot for them)."""
    try:
        rows = _table("hanger_tags").select("item_id").eq("user_id", user_id).execute().data
    except Exception:
        log.exception("could not read hanger tags")  # the Wardrobe must still open if this fails
        return set()
    return {r["item_id"] for r in rows if r["item_id"]}


def clean_tag(value):
    """'04:a1-b2 c3' -> '04A1B2C3'. Returns None when it is not a plausible tag id."""
    tag = re.sub(r"[\s:\-]", "", str(value or "")).upper()
    return tag if TAG_RE.fullmatch(tag) else None


def _valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- the scan itself
def _count_wear(user_id, piece, now):
    """A piece counts as worn once per day, however many times its tag is scanned that day."""
    already_today = piece["last_worn_at"] and _parse(piece["last_worn_at"]).astimezone().date() == now.astimezone().date()
    update = {"last_worn_at": now.isoformat()}  # also tells the matcher to skip this piece for a few days
    if not already_today:
        update["wear_count"] = piece["wear_count"] + 1
    notify.run_later(lambda: _table("clothing_items").update(update).eq("id", piece["id"]).eq("user_id", user_id).execute())  # the reader need not wait for this


def _local_midnight_utc(now):
    """The start of today on the server's clock (your laptop), as a UTC time. 'Today' and 'yesterday' flip at YOUR midnight."""
    return datetime.combine(now.astimezone().date(), datetime.min.time()).astimezone().astimezone(timezone.utc)


def _same_day_note(user_id, piece, earlier, now):
    """Tapping a piece that is already recorded as worn TODAY: say what is recorded, instead of the usual 'taken off the rail'."""
    if not earlier or _parse(earlier).astimezone().date() != now.astimezone().date():
        return None
    today = _table("outfit_logs").select("item_ids,source").eq("user_id", user_id).neq("source", "saved").gte("created_at", _local_midnight_utc(now).isoformat()).execute().data
    if any(piece["id"] in look["item_ids"] and look["source"] == "worn" for look in today):  # added with "Wear this today"
        return f"{piece['name']} is already in the outfit you added to Worn today, so nothing new was logged."
    return f"{piece['name']} was already logged as worn today."


def _when(days):
    return "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"


def _alternatives(user_id, piece, now):
    """Up to two pieces of the same kind that were NOT worn this week, best first: same occasion, then the longest unworn."""
    since = (now - timedelta(days=options.REPEAT_WINDOW_DAYS)).isoformat()
    rows = _table("clothing_items").select("id,name,occasion,wear_count,last_worn_at").eq("user_id", user_id).eq("category", piece["category"]).execute().data
    fresh = [r for r in rows if r["id"] != piece["id"] and (not r["last_worn_at"] or r["last_worn_at"] < since)]
    fresh.sort(key=lambda r: (r["occasion"] != piece["occasion"], r["last_worn_at"] or "", r["wear_count"]))  # never worn sorts first
    return [r["name"] for r in fresh[:2]]


def _repeat_advice(user_id, piece, earlier, now):
    """The 7-day memory for ONE piece. `earlier` = when it was last worn, read BEFORE this scan overwrites it.
    A second tap on the same day is not a repeat. (Categories listed in options.REPEAT_EXEMPT, none right now, are skipped.)"""
    if piece["category"] in options.REPEAT_EXEMPT or not earlier:
        return None
    days = (now.astimezone().date() - _parse(earlier).astimezone().date()).days
    if not 1 <= days <= options.REPEAT_WINDOW_DAYS:
        return None
    alternatives = _alternatives(user_id, piece, now)
    ending = f"Repeat it, or try {' or '.join(alternatives)} instead?" if alternatives else "Repeat it, or pick something you have not worn this week."
    return f"{piece['name']} detected. You wore it {_when(days)}. {ending}"


def _repeat_outfit_note(user_id, ids, now, just_scanned):
    """The 7-day memory for the WHOLE outfit: does what is out today include every piece of a look worn on an earlier day
    this week? Looks from today are ignored (they are today's own).
    It speaks only at the scan that COMPLETES the repeat, not again for every extra piece taken out afterwards."""
    pieces = {p["id"]: p for p in items_mod.get_items(user_id)}
    today_set = {i for i in ids if i in pieces and pieces[i]["category"] not in options.REPEAT_EXEMPT}
    before = today_set - {just_scanned}  # what was already out before this scan
    if len(today_set) < 2:
        return None
    local_today = now.astimezone().date()
    midnight = _local_midnight_utc(now)
    since = (now - timedelta(days=options.REPEAT_WINDOW_DAYS)).isoformat()
    past = _table("outfit_logs").select("item_ids,created_at").eq("user_id", user_id).neq("source", "saved").gte("created_at", since).execute().data
    for look in sorted(past, key=lambda l: l["created_at"], reverse=True):
        when = _parse(look["created_at"])
        if when >= midnight:
            continue
        earlier = {i for i in look["item_ids"] if i in pieces and pieces[i]["category"] not in options.REPEAT_EXEMPT}
        if len(earlier) >= 2 and earlier <= today_set and not earlier <= before:
            scanned = pieces[just_scanned]["name"]  # lead with the piece the user just touched, then name the rest of the outfit
            others = " + ".join(sorted(pieces[i]["name"] for i in earlier if i != just_scanned))
            return (f"{scanned} detected. With {others} (also taken out today) it repeats the outfit you wore "
                    f"{_when((local_today - when.astimezone().date()).days)}. Try swapping one piece to keep your week fresh.")
    return None


def _group_into_look(user_id, piece, now):
    """Pieces scanned within 2 hours of each other form one 'hanger look' in History (2 to 6 pieces).
    Returns a warning if a clothing piece just completed an outfit that repeats one from this week, else None."""
    since = (now - timedelta(hours=LOOK_WINDOW_HOURS)).isoformat()
    rows = _table("hanger_tags").select("item_id").eq("user_id", user_id).gte("last_scanned_at", since).execute().data
    ids = list(dict.fromkeys(r["item_id"] for r in rows if r["item_id"]))[:6]
    if len(ids) < 2:
        return None
    logs = _table("outfit_logs")
    open_look = logs.select("id").eq("user_id", user_id).eq("source", "hanger_scan").gte("created_at", since).order("created_at", desc=True).limit(1).execute().data
    if open_look:
        logs.update({"item_ids": ids}).eq("id", open_look[0]["id"]).eq("user_id", user_id).execute()
    else:
        logs.insert({"user_id": user_id, "item_ids": ids, "source": "hanger_scan"}).execute()
    return None if piece["category"] in options.REPEAT_EXEMPT else _repeat_outfit_note(user_id, ids, now, piece["id"])


def process_scan(user_id, tag_uid):
    """Returns {"status": "logged" | "unknown" | "ignored", "item": name}.
    logged  = a linked tag: the piece is counted as worn and the user is notified
    unknown = a new or unlinked tag: remembered so the user can link it on the Hangers page
    ignored = a repeat within a few seconds, or too many tags"""
    now = datetime.now(timezone.utc)
    tags = _table("hanger_tags")
    # A tag belongs to the ACCOUNT, not to the physical card: two accounts can use the same card, each with its own meaning.
    found = tags.select("tag_uid,user_id,item_id,last_scanned_at").eq("tag_uid", tag_uid).eq("user_id", user_id).execute().data
    row = found[0] if found else None
    previous = _parse(row["last_scanned_at"]) if row and row["last_scanned_at"] else None
    if previous and 0 <= (now - previous).total_seconds() < DEBOUNCE_SECONDS:  # 0 <= : a stamp from the FUTURE (the laptop clock was wrong once) must not block scans
        return {"status": "ignored"}

    if row is None:
        if tags.select("tag_uid", count="exact").eq("user_id", user_id).limit(1).execute().count >= MAX_TAGS:
            return {"status": "ignored"}
        tags.insert({"tag_uid": tag_uid, "user_id": user_id, "item_id": None, "last_scanned_at": now.isoformat()}).execute()
    else:
        tags.update({"last_scanned_at": now.isoformat()}).eq("tag_uid", tag_uid).eq("user_id", user_id).execute()

    piece = None
    if row and row["item_id"]:
        found_piece = _table("clothing_items").select("id,name,category,occasion,wear_count,last_worn_at").eq("id", row["item_id"]).eq("user_id", user_id).execute().data
        piece = found_piece[0] if found_piece else None

    if piece is None:  # brand-new tag, or one that is not linked yet
        # Every real read notifies (the 5-second debounce above already dropped double reads). The tag itself is stored only
        # once, so the Hangers page never lists the same tag twice.
        if row is None:
            message = f"A new hanger tag ({tag_uid}) was scanned. Link it to a piece of clothing."
        else:
            message = f"Tag {tag_uid} was scanned but is not linked to a piece yet. Link it on the Hangers page."
        notify.create(user_id, message, kind="unknown_tag", link="/hangers", title="New hanger tag", later=True)
        return {"status": "unknown"}

    earlier = piece["last_worn_at"]  # read BEFORE _count_wear overwrites it
    advice = _repeat_advice(user_id, piece, earlier, now)
    same_day = _same_day_note(user_id, piece, earlier, now)
    _count_wear(user_id, piece, now)
    outfit_note = _group_into_look(user_id, piece, now)
    note = outfit_note or advice  # a repeated whole outfit matters more than one repeated piece; this is what the user is warned about
    if outfit_note:
        title = "Outfit repeat"
    elif advice:
        title = "Worn this week"
    elif same_day:
        title = "Already worn today"
    else:
        title = "Hanger scan"
    message = note or same_day or f"{piece['name']} was taken off the rail and logged as worn today."
    notify.create(user_id, message, kind="scan", link="/matcher" if note else "/history", title=title, later=True)
    return {"status": "logged", "item": piece["name"], "repeat": bool(note), "note": note or same_day}


# ---------------------------------------------------------------- the Hangers page
def _state(tag_rows):
    """A short fingerprint of the tag list. It changes whenever a tag is scanned, added or linked: the page compares it to see 'something new happened'."""
    return "|".join(f"{t['tag_uid']}:{t['item_id']}:{t['last_scanned_at']}" for t in tag_rows)


def page_data(user_id):
    pieces = items_mod.get_items(user_id)
    by_id = {p["id"]: p for p in pieces}
    tags = _table("hanger_tags").select("tag_uid,item_id,last_scanned_at").eq("user_id", user_id).order("last_scanned_at", desc=True).execute().data
    linked = [{**t, "item": by_id[t["item_id"]]} for t in tags if t["item_id"] in by_id]
    tagged = {t["item_id"] for t in linked}
    activity = _table("notifications").select("message,kind,created_at").eq("user_id", user_id).in_("kind", ["scan", "unknown_tag"]) \
        .order("created_at", desc=True).limit(8).execute().data
    return {
        "state": _state(tags),
        "linked": linked,
        "pending": [t for t in tags if not t["item_id"]],
        "free_pieces": [p for p in pieces if p["id"] not in tagged],  # pieces that still need a tag
        "devices": _table("devices").select("id,name,last_seen_at,created_at").eq("user_id", user_id).order("created_at").execute().data,
        "activity": activity,
    }


# ---------------------------------------------------------------- API used by the Hangers page
@bp.get("/feed")
@login_required
@limiter.limit("60 per minute")
def feed():
    """Polled every 3 seconds by the Hangers page: the fingerprint of my tags and my newest hanger message."""
    user_id = current_user_id()
    rows = _table("hanger_tags").select("tag_uid,item_id,last_scanned_at").eq("user_id", user_id).order("last_scanned_at", desc=True).execute().data
    latest = _table("notifications").select("message").eq("user_id", user_id).in_("kind", ["scan", "unknown_tag"]).order("created_at", desc=True).limit(1).execute().data
    return jsonify(state=_state(rows), latest=latest[0]["message"] if latest else "")


@bp.post("/link")
@login_required
@limiter.limit("30 per minute")
def link_tag():
    data = request.get_json(silent=True) or {}
    tag, item_id = clean_tag(data.get("tag_uid")), data.get("item_id")
    if not tag or not _valid_uuid(item_id):
        return jsonify(error="Enter a valid tag id and choose a piece."), 400
    user_id, tags = current_user_id(), _table("hanger_tags")
    if not _table("clothing_items").select("id").eq("id", item_id).eq("user_id", user_id).execute().data:
        return jsonify(error="That piece wasn't found."), 404
    found = tags.select("tag_uid").eq("tag_uid", tag).eq("user_id", user_id).execute().data  # only MY tags: the same card may exist in other accounts
    if not found and tags.select("tag_uid", count="exact").eq("user_id", user_id).limit(1).execute().count >= MAX_TAGS:
        return jsonify(error=f"You have reached the limit of {MAX_TAGS} tags."), 400
    tags.delete().eq("user_id", user_id).eq("item_id", item_id).neq("tag_uid", tag).execute()  # one tag per piece: re-tagging replaces the old one
    if found:
        tags.update({"item_id": item_id}).eq("tag_uid", tag).eq("user_id", user_id).execute()
    else:
        tags.insert({"tag_uid": tag, "user_id": user_id, "item_id": item_id, "last_scanned_at": None}).execute()
    return jsonify(ok=True)


@bp.delete("/<tag_uid>")
@login_required
@limiter.limit("30 per minute")
def forget_tag(tag_uid):
    tag = clean_tag(tag_uid)
    if not tag:
        return jsonify(error="Not found."), 404
    _table("hanger_tags").delete().eq("tag_uid", tag).eq("user_id", current_user_id()).execute()
    return jsonify(ok=True)


@bp.post("/simulate")
@login_required
@limiter.limit("30 per minute")
def simulate_scan():
    """Same code as the real reader, for demos before the hardware is ready."""
    tag = clean_tag((request.get_json(silent=True) or {}).get("tag_uid"))
    if not tag:
        return jsonify(error="Enter a valid tag id (8 to 20 letters and digits from 0-9 and A-F)."), 400
    try:
        result = process_scan(current_user_id(), tag)
    except Exception:
        log.exception("simulated scan failed")
        return jsonify(error="We couldn't process that scan. Please try again."), 500
    messages = {"logged": result.get("note") or f"{result.get('item', 'The piece')} was logged as worn today.",
                "unknown": "New tag recorded. Link it to a piece below.",
                "ignored": "Scan ignored: the same tag was scanned a moment ago."}
    return jsonify(ok=True, status=result["status"], message=messages[result["status"]])
