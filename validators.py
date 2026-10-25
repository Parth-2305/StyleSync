"""Server-side input checks. The browser also checks, but only THIS is trusted:
anyone can bypass the browser (curl, dev tools) and send anything."""
import re
import unicodedata

import options

EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,255}\.[^\s@]{2,}$")


def clean_email(value):
    email = str(value or "").strip().lower()
    return email if len(email) <= 254 and EMAIL_RE.match(email) else None


def _strip_hidden(text, keep_newlines=False):
    """Removes invisible control characters (null bytes, right-to-left overrides, zero-width tricks) that can
    disguise text or break logs. Normal letters, emoji and spaces are kept."""
    return "".join(ch for ch in str(text or "") if (keep_newlines and ch == "\n") or unicodedata.category(ch) not in ("Cc", "Cf"))


def password_problem(password):
    """Returns a message if the password is too weak, else None."""
    # bcrypt only reads the first 72 BYTES, so the limit is in bytes (an emoji is 4 bytes, not 1 character)
    if not isinstance(password, str) or len(password) < 8 or len(password.encode("utf-8")) > 72:
        return "Password must be at least 8 characters and at most 72 bytes (about 72 characters)."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Password needs at least one letter and one number."
    return None


def clean_name(value):
    name = " ".join(_strip_hidden(value).split())  # drop hidden characters, collapse stray whitespace
    return name if 1 <= len(name) <= 60 else None


OTHER_CHOICE = "__other"  # value of the "Other…" option in the dropdowns
CUSTOM_FIELDS = ("color", "occasion", "style")  # fields where the user may type their own value
# Category and season stay fixed: the outfit matcher's rules (top + bottom + shoes, season fit) depend on them.


def clean_custom(text):
    """A typed-in value: 1-30 letters/numbers/spaces/hyphens/apostrophes, tidied to 'Mustard Yellow' style."""
    text = " ".join(str(text or "").split())
    return text.title() if re.fullmatch(r"[A-Za-z0-9 '\-]{1,30}", text) else None


def _pick(form, field, allowed):
    """The chosen dropdown value if it is on our list, or the typed value for 'Other…'. Else None."""
    value = form.get(field)
    if value == OTHER_CHOICE and field in CUSTOM_FIELDS:
        return clean_custom(form.get(field + "_other"))
    return value if value in allowed else None


def clean_item(form):
    """Checks the Add Item form. Returns (clean_dict, None) or (None, error_message).
    Dropdown values must be on our fixed lists (or a tidy typed 'Other'), so nobody can inject anything else."""
    name = clean_name(form.get("name"))
    notes = _strip_hidden(form.get("notes"), keep_newlines=True).strip()
    if not name:
        return None, "Give this piece a name (up to 60 characters)."
    if len(notes) > 280:
        return None, "Notes can be up to 280 characters."

    fields = {
        "category": options.CATEGORY_LABELS,
        "color": [c["name"] for c in options.COLORS],
        "season": options.SEASONS,
        "occasion": options.OCCASIONS,
        "style": options.STYLES + [""],  # style is optional
    }
    item = {"name": name, "notes": notes}
    for field, allowed in fields.items():
        item[field] = _pick(form, field, allowed)
        if item[field] is None:
            hint = " (letters or numbers, up to 30 characters)" if field in CUSTOM_FIELDS else ""
            return None, f"Please choose a valid {field}{hint}."
    item["season"] = [item["season"]]  # the database column holds a list of seasons
    return item, None
