"""Wardrobe items: list, add (with photo), delete.
The server key bypasses database locks, so EVERY query below filters by the logged-in user's id."""
import logging
import uuid

from flask import Blueprint, jsonify, request

import db
import images
from auth import current_user_id, login_required
from extensions import limiter
from validators import clean_item

bp = Blueprint("items", __name__, url_prefix="/api/items")
log = logging.getLogger(__name__)
COLUMNS = "id,name,category,color,season,occasion,style,notes,image_url,wear_count,last_worn_at"
MAX_ITEMS = 300  # per user: stops one account filling the database and photo storage


def get_items(user_id):
    """All of one user's clothes, newest first. Also used by the pages in app.py."""
    query = db.data_client().table("clothing_items").select(COLUMNS)
    return query.eq("user_id", user_id).order("created_at", desc=True).execute().data


@bp.post("")
@login_required
@limiter.limit("20 per minute")
def add_item():
    item, error = clean_item(request.form)
    if error:
        return jsonify(error=error), 400

    user_id, photo = current_user_id(), request.files.get("image")
    try:
        owned = db.data_client().table("clothing_items").select("id", count="exact").eq("user_id", user_id).limit(1).execute().count
        if owned >= MAX_ITEMS:
            return jsonify(error=f"Your closet is full ({MAX_ITEMS} pieces). Remove something first."), 400
        if photo and photo.filename:
            item["image_url"] = images.save_photo(photo, user_id)
        row = db.data_client().table("clothing_items").insert({**item, "user_id": user_id}).execute().data[0]
    except images.BadImage:
        return jsonify(error="That file isn't a valid JPG, PNG or WebP image."), 400
    except Exception:  # details go to our log; the user only sees a generic message
        log.exception("add item failed")
        return jsonify(error="We couldn't save that piece. Please try again."), 500
    return jsonify(ok=True, item={key: row[key] for key in COLUMNS.split(",")}), 201


@bp.delete("/<item_id>")
@login_required
@limiter.limit("60 per minute")
def delete_item(item_id):
    try:
        uuid.UUID(item_id)  # anything that isn't a real id is just "not found"
    except ValueError:
        return jsonify(error="That piece wasn't found."), 404

    table, user_id = db.data_client().table("clothing_items"), current_user_id()
    found = table.select("image_url").eq("id", item_id).eq("user_id", user_id).execute().data
    if not found:  # also what you get for someone else's item: no hint that it exists
        return jsonify(error="That piece wasn't found."), 404
    table.delete().eq("id", item_id).eq("user_id", user_id).execute()
    if found[0]["image_url"]:
        images.delete_photo(found[0]["image_url"])
    return jsonify(ok=True)
