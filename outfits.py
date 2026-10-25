"""Outfits: ask for a suggestion, save/wear a look, remove a saved look, and read the history.
As in items.py, every query filters by the logged-in user's id."""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

import db
import items
import options
import outfit_engine
import tags
from auth import current_user_id, login_required
from extensions import limiter

bp = Blueprint("outfits", __name__, url_prefix="/api/outfits")
log = logging.getLogger(__name__)
RECENT_DAYS = options.REPEAT_WINDOW_DAYS  # pieces worn in the last week are avoided: the whole point is rotation
MAX_LOGS = 2000  # per user: history rows (worn + saved) cannot grow without limit


def _table():
    return db.data_client().table("outfit_logs")


def _short_list(value, allowed):
    """A list from the browser, trimmed to known option names (never trust what the browser sends)."""
    return [v for v in (value if isinstance(value, list) else [])[:20] if v in allowed]


def _recently_worn_ids(user_id):
    """Pieces worn in the last week, via "Wear this today" or a hanger-tag scan: both set last_worn_at."""
    since = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)).isoformat()
    rows = db.data_client().table("clothing_items").select("id,category").eq("user_id", user_id).gte("last_worn_at", since).execute().data
    return {row["id"] for row in rows if row["category"] not in options.REPEAT_EXEMPT}


def _recent_clothing_sets(user_id, pieces):
    """The pieces of every look worn in the last week, one set per look. This 7-day memory is only a window over the history;
    the history itself is kept for good."""
    since = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)).isoformat()
    category = {p["id"]: p["category"] for p in pieces}
    rows = _table().select("item_ids").eq("user_id", user_id).neq("source", "saved").gte("created_at", since).execute().data
    sets = [{i for i in row["item_ids"] if i in category and category[i] not in options.REPEAT_EXEMPT} for row in rows]
    return [s for s in sets if len(s) >= 2]


@bp.post("/suggest")
@login_required
@limiter.limit("60 per minute")
def suggest():
    data = request.get_json(silent=True) or {}
    choices = {"occasion": data.get("occasion"), "season": data.get("season"),
               "style": data.get("style") or "", "color": data.get("color") or ""}
    if choices["occasion"] not in options.OCCASIONS or choices["season"] not in options.SEASONS \
            or choices["style"] not in options.STYLES + [""] or choices["color"] not in options.COLOR_MOODS + [""]:
        return jsonify(error="Pick an occasion and a season first."), 400

    prefs_in = data.get("prefs") if isinstance(data.get("prefs"), dict) else {}
    prefs = {"styles": _short_list(prefs_in.get("styles"), options.STYLES),
             "colors": _short_list(prefs_in.get("colors"), [c["name"] for c in options.COLORS])}
    seen = {s for s in (data.get("seen") if isinstance(data.get("seen"), list) else [])[:500] if isinstance(s, str)}

    user_id = current_user_id()
    try:
        pieces = items.get_items(user_id)
        result = outfit_engine.suggest(pieces, choices, prefs, _recently_worn_ids(user_id), seen, _recent_clothing_sets(user_id, pieces))
    except Exception:
        log.exception("suggest failed")
        return jsonify(error="We couldn't build a look just now. Please try again."), 500
    if result.get("outfit"):  # the matcher card shows which suggested pieces have a hanger tag
        tagged = tags.tagged_item_ids(user_id)
        for entry in result["outfit"]["items"]:
            entry["item"] = {**entry["item"], "tagged": entry["item"]["id"] in tagged}
    return jsonify(result)


@bp.post("")
@login_required
@limiter.limit("30 per minute")
def save_look():
    """Logs a look as 'worn' (updates wear counts) or 'saved' (just bookmarks it)."""
    data = request.get_json(silent=True) or {}
    ids, source = data.get("item_ids"), data.get("source")
    if source not in ("worn", "saved") or not isinstance(ids, list) or not 2 <= len(set(ids)) <= 6 \
            or data.get("occasion") not in options.OCCASIONS or data.get("season") not in options.SEASONS:
        return jsonify(error="That look couldn't be saved."), 400
    try:
        ids = [str(uuid.UUID(i)) for i in set(ids)]
    except (ValueError, AttributeError, TypeError):
        return jsonify(error="That look couldn't be saved."), 400

    user_id, table = current_user_id(), db.data_client().table("clothing_items")
    try:
        if _table().select("id", count="exact").eq("user_id", user_id).limit(1).execute().count >= MAX_LOGS:
            return jsonify(error="Your history is full. Remove some saved looks first."), 400
        mine = table.select("id,wear_count").eq("user_id", user_id).in_("id", ids).execute().data
        if len(mine) != len(ids):  # someone else's (or deleted) piece
            return jsonify(error="That look couldn't be saved."), 400

        if source == "saved":
            same = [r for r in _table().select("item_ids").eq("user_id", user_id).eq("source", "saved").execute().data
                    if set(r["item_ids"]) == set(ids)]
            if same:
                return jsonify(ok=True, message="That look is already in your Saved list.")
        else:  # worn: count it, and remember when, so the matcher skips these pieces for a few days
            now = datetime.now(timezone.utc).isoformat()
            for row in mine:
                table.update({"wear_count": row["wear_count"] + 1, "last_worn_at": now}).eq("id", row["id"]).eq("user_id", user_id).execute()

        _table().insert({"user_id": user_id, "item_ids": ids, "occasion": data["occasion"],
                         "season": data["season"], "source": source}).execute()
    except Exception:
        log.exception("save look failed")
        return jsonify(error="We couldn't save that look. Please try again."), 500
    return jsonify(ok=True, message="Logged as today's outfit. See it in History." if source == "worn" else "Look saved to your History.")


@bp.delete("/<log_id>")
@login_required
@limiter.limit("60 per minute")
def remove_saved(log_id):
    """Only SAVED looks can be removed; the 'worn' record is a true history and also fed the wear counts."""
    try:
        uuid.UUID(log_id)
    except ValueError:
        return jsonify(error="That look wasn't found."), 404
    user_id = current_user_id()
    found = _table().select("id").eq("id", log_id).eq("user_id", user_id).eq("source", "saved").execute().data
    if not found:
        return jsonify(error="That look wasn't found."), 404
    _table().delete().eq("id", log_id).eq("user_id", user_id).execute()
    return jsonify(ok=True)


def get_history(user_id):
    """Newest first. Each entry carries its full piece details; pieces deleted since are simply left out."""
    rows = _table().select("id,item_ids,occasion,season,source,created_at").eq("user_id", user_id) \
        .order("created_at", desc=True).limit(200).execute().data
    by_id = {item["id"]: item for item in items.get_items(user_id)}
    entries = []
    for row in rows:
        pieces = [by_id[i] for i in row["item_ids"] if i in by_id]
        if not pieces:
            continue
        when = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).astimezone()
        entries.append({**row, "items": pieces, "day": when.strftime("%d"), "weekday": when.strftime("%a"),
                        "label": when.strftime("%a, %d %b")})
    return entries


def count_saved(user_id):
    return len(_table().select("id").eq("user_id", user_id).eq("source", "saved").execute().data)
