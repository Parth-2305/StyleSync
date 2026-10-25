"""The Outfit Matcher's brain. Plain rules and points, no AI, so every choice can be explained.

How it thinks:
  1. Keep only pieces that suit the chosen season, and give each piece points (occasion, style, colour, rarely worn...).
  1b. OCCASION COMES FIRST: for each slot, use only the pieces closest to the chosen occasion (exact matches, else the nearest
      related occasion, and so on). Freshness and the one-week rule then choose WITHIN that group, never across it.
  2. Take the best few pieces per slot (top / bottom / shoes) and build EVERY combination, plus optional layer and accessory.
  3. Score each combination as a whole: do the colours go together, is it one style, is the dress code right?
  4. Pick one of the near-best combinations that hasn't been shown yet, so Shuffle always shows something new."""
import itertools
import random

import options

REQUIRED = ("top", "bottom", "footwear")
# Occasions that dress alike still earn partial credit (a Work shirt can appear in a Formal look).
RELATED_OCCASIONS = {"Work": ("Formal",), "Formal": ("Work",), "Casual": ("Party",), "Party": ("Casual", "Formal"), "Ethnic": ("Party",)}
NEUTRAL_FAMILIES = {"Monochrome", "Neutrals"}  # colours that go with almost anything
SPORTY_STYLES = {"Streetwear", "Athleisure"}   # these clash with a Formal / Work dress code
FAMILY = {c["name"]: c["family"] for c in options.COLORS}
NEUTRAL_COLORS = {name for name, family in FAMILY.items() if family in NEUTRAL_FAMILIES} | {"Brown"}  # brown shoes/belts are a basic
BEST_PER_SLOT = 6   # only the best few pieces per slot are combined: keeps the number of combinations small and fast
NEAR_BEST = 2.5     # a look may be picked if it scores within this many points of the best unseen look
LAYER_WEIGHT, ACCESSORY_WEIGHT = 0.7, 0.5  # a jacket or accessory counts for less than the main three pieces
REPEAT_PENALTY = 10  # wearing the same clothes as a look from this week: only chosen when nothing else is possible


def _closeness(item, occasion):
    """How close a piece's occasion is to the chosen one: 0 = exact, 1 = the nearest related occasion, 2 = the next one, 9 = unrelated."""
    if item["occasion"] == occasion:
        return 0
    related = RELATED_OCCASIONS.get(occasion, ())
    return 1 + related.index(item["occasion"]) if item["occasion"] in related else 9


def _fits_season(item, season):
    return season == "All-season" or season in item["season"] or "All-season" in item["season"]


def _piece_points(item, choices, prefs, recent_ids):
    """How good is this ONE piece for what the user asked for?"""
    points = 0
    if item["occasion"] == choices["occasion"]:
        points += 3
    elif item["occasion"] in RELATED_OCCASIONS.get(choices["occasion"], ()):
        points += 1
    if choices["style"] and item["style"] == choices["style"]:
        points += 2
    if choices["color"] and FAMILY.get(item["color"]) == choices["color"]:
        points += 2
    if item["style"] in prefs["styles"]:
        points += 1  # the user's own favourites (Profile page)
    if item["color"] in prefs["colors"]:
        points += 1
    if choices["season"] != "All-season" and choices["season"] in item["season"]:
        points += 1  # made for this season, not just "good any time"
    if item["wear_count"] < 5:
        points += 0.5  # gently favour pieces that rarely get worn, so the closet rotates
    if item["id"] in recent_ids:
        points -= 3    # worn in the last few days: avoid repeating
    return points


def _best_possible_piece(choices, prefs):
    """The most points one piece could earn for these choices (used to turn points into a % match)."""
    return (3 + 2 * bool(choices["style"]) + 2 * bool(choices["color"]) + bool(prefs["styles"]) + bool(prefs["colors"])
            + (choices["season"] != "All-season") + 0.5)


def _palette(pieces):
    """Do the colours go together? Returns (points, sentence). One statement colour on neutrals is the classic recipe."""
    accents = {p["color"] for p in pieces if p["color"] not in NEUTRAL_COLORS}
    if not accents:
        return 2, "A calm neutral palette that goes with everything."
    if len(accents) == 1:
        return 3, f"{next(iter(accents))} is the one statement colour; the rest stays neutral."
    if len({FAMILY.get(c, c) for c in accents}) == 1:
        return 1, "The bold colours come from the same family, so they sit well together."
    return (-2 if len(accents) == 2 else -4), None  # several competing colours: a clash, so no flattering sentence


def _style_unity(pieces):
    styles = {p["style"] for p in pieces if p["style"]}
    if len(styles) == 1:
        return 2, f"Every piece shares a {next(iter(styles)).lower()} style."
    return (1 if len(styles) == 2 else 0), None


def _build(choices, prefs, picks, recent_sets=()):
    """Scores one whole outfit. `picks` = [(slot, points, item, weight), ...].
    `recent_sets` = the clothes (ids) of looks worn this week; shoes and accessories are not part of them."""
    pieces = [item for _, _, item, _ in picks]
    clothes = [p for slot, _, p, _ in picks if slot != "accessory"]
    score = sum(points * weight for _, points, _, weight in picks)
    score += _palette(clothes)[0] + _style_unity(clothes)[0]
    if choices["occasion"] in ("Formal", "Work"):
        score -= 2 * sum(1 for p in clothes if p["style"] in SPORTY_STYLES)  # dress code
    clothing_ids = {p["id"] for slot, _, p, _ in picks if slot not in options.REPEAT_EXEMPT}
    repeated = any(len(old) >= 2 and old <= clothing_ids for old in recent_sets)
    if repeated:
        score -= REPEAT_PENALTY  # the one-week rule: do not repeat an outfit
    ideal = sum(_best_possible_piece(choices, prefs) * weight for _, _, _, weight in picks) + 5
    return {"score": score, "ideal": ideal, "slots": [slot for slot, *_ in picks], "pieces": pieces, "repeated": repeated,
            "key": ",".join(sorted(p["id"] for p in pieces))}


def _reasons(outfit, choices):
    """A few plain-English reasons, so the user (and the examiner) can see WHY this look was chosen."""
    pieces, slots = outfit["pieces"], outfit["slots"]
    clothes = [p for s, p in zip(slots, pieces) if s != "accessory"]
    occasion = choices["occasion"]
    labels = {"top": "top", "bottom": "bottom", "footwear": "shoes", "outerwear": "jacket", "accessory": "accessory"}
    first = []  # the things worth knowing first: a repeated week, or a slot that had to use a related occasion
    if outfit.get("repeated"):
        first.append(f"Heads up: this repeats a look from this week. You have no other {occasion.lower()} combination yet.")
    for slot, p in zip(slots, pieces):
        if slot in REQUIRED and p["occasion"] != occasion:
            first.append(f"You have no {occasion.lower()} {labels[slot]} for this season, so a {p['occasion'].lower()} one was used.")
    fits = sum(1 for p in pieces if p["occasion"] == occasion)
    reasons = first + ([f"{fits} of {len(pieces)} pieces are tagged for {occasion.lower()}."] if fits else [])
    reasons += [note for note in (_palette(clothes)[1], _style_unity(clothes)[1]) if note]
    if "outerwear" in slots:
        layer = pieces[slots.index("outerwear")]["name"]
        why = f"for the {choices['season'].lower()} weather" if choices["season"] in ("Winter", "Monsoon") else             "to dress it up" if choices["occasion"] == "Formal" else "as an extra layer"
        reasons.append(f"{layer} adds a layer {why}.")
    rare = min(pieces, key=lambda p: p["wear_count"])
    if rare["wear_count"] < 5:
        worn = "you haven't worn it yet" if rare["wear_count"] == 0 else f"you've worn it only {rare['wear_count']} time{'s' * (rare['wear_count'] != 1)}"
        reasons.append(f"{rare['name']} is due a turn: {worn}.")
    return reasons[:5]


def suggest(items, choices, prefs, recent_ids, seen, recent_sets=()):
    """Returns {"missing": [...]} if a core slot is empty, else {"outfit", "total", "exhausted"}.
    `seen` = keys of looks already shown for these choices; they're skipped until every look has been shown."""
    random.shuffle(items)  # so pieces with equal points take turns instead of always the same one winning
    slots = {}
    for item in items:
        if _fits_season(item, choices["season"]):
            slots.setdefault(item["category"], []).append((_piece_points(item, choices, prefs, recent_ids), item))
    for slot, found in slots.items():  # occasion first: keep only the pieces closest to the chosen occasion in each slot
        nearest = min(_closeness(item, choices["occasion"]) for _, item in found)
        slots[slot] = [pair for pair in found if _closeness(pair[1], choices["occasion"]) == nearest]
    for found in slots.values():
        found.sort(key=lambda pair: pair[0], reverse=True)

    missing = [slot for slot in REQUIRED if not slots.get(slot)]
    if missing:
        return {"missing": missing}

    # A layer is needed in cold/wet weather or for Formal; in "All-season" it's optional (so we get variety).
    layers = slots.get("outerwear", [])[:BEST_PER_SLOT]
    if not (choices["season"] in ("Winter", "Monsoon") or choices["occasion"] == "Formal") or not layers:
        layers = [None] + (layers[:2] if choices["season"] == "All-season" else [])
    # An accessory only if it genuinely fits (3+ points ~ matches the occasion), never as filler.
    accessories = [None] + [a for a in slots.get("accessory", []) if a[0] >= 3][:3]

    outfits = []
    for top, bottom, shoes, layer, accessory in itertools.product(
            slots["top"][:BEST_PER_SLOT], slots["bottom"][:BEST_PER_SLOT], slots["footwear"][:BEST_PER_SLOT], layers, accessories):
        picks = [("top", *top, 1), ("bottom", *bottom, 1), ("footwear", *shoes, 1)]
        if layer:
            picks.append(("outerwear", *layer, LAYER_WEIGHT))
        if accessory:
            picks.append(("accessory", *accessory, ACCESSORY_WEIGHT))
        outfits.append(_build(choices, prefs, picks, recent_sets))

    outfits.sort(key=lambda o: o["score"], reverse=True)
    fresh = [o for o in outfits if o["key"] not in seen]
    pool = fresh or outfits  # every look has been shown: start over
    near_best = [o for o in pool if o["score"] >= pool[0]["score"] - NEAR_BEST][:15]
    chosen = random.choice(near_best)  # nosec B311: only picks which outfit to show, nothing security-related

    return {
        "outfit": {
            "key": chosen["key"],
            "items": [{"slot": s, "item": p} for s, p in zip(chosen["slots"], chosen["pieces"])],
            "match_percent": max(45, min(99, round(100 * chosen["score"] / chosen["ideal"]))),
            "reasons": _reasons(chosen, choices),
        },
        "total": len(outfits),
        "exhausted": not fresh,
    }
