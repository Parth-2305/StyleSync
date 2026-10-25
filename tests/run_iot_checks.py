"""StyleSync automated checks. Uses an in-memory fake database (tests/fakedb.py), so it needs no Supabase tables and changes no real data.
Run from the project folder:   venv\Scripts\python.exe tests\run_iot_checks.py
Covers: scan logic, isolation between users, one-week rule, matcher, same-day and midnight, per-account tags,
beep data, live feed, notifications, push (SSRF), and login + CSRF + rate limits on every route."""
import base64, json, os, re, sys, threading, uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder, wherever it is
os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fakedb import FakeDB
import db
fake = FakeDB(); db.data_client = lambda: fake  # all data goes to memory
import app as A, notify, tags, iot, outfits, items

notify.SEND_IN_BACKGROUND = False
passed, failed = 0, []
def check(label, cond, extra=""):
    global passed
    if cond: passed += 1; print(f"  ok   {label}")
    else: failed.append(label); print(f"  FAIL {label} {extra}")

UA, UB = str(uuid.uuid4()), str(uuid.uuid4())
now = datetime.now(timezone.utc)
def piece(owner, name, **kw):
    row = {"user_id": owner, "name": name, "category": "top", "color": "Navy", "season": ["All-season"], "occasion": "Casual", **kw}
    return fake.table("clothing_items").insert(row).execute().data[0]
p1, p2, p3 = piece(UA, "Navy Blazer"), piece(UA, "White Shirt"), piece(UA, "Brown Loafers", category="footwear")
pB = piece(UB, "Bob's Jacket")

def session_for(uid):
    c = A.app.test_client()
    html = c.get("/").get_data(as_text=True)  # gives us the session + CSRF token
    token = re.search(r'csrf-token" content="([^"]+)', html).group(1)
    with c.session_transaction() as s:
        s.update(user_id=uid, email="x@y.z", full_name="Test User")
    return c, {"X-CSRFToken": token}

ca, ha = session_for(UA); cb, hb = session_for(UB)
post = lambda c, h, url, body=None: c.post(url, json=body or {}, headers=h)

print("== 1. readers (devices)")
r = post(ca, ha, "/api/devices", {"name": "Bedroom wardrobe"}); key = r.get_json().get("key", "")
check("pair a reader returns a 256-bit key once", r.status_code == 201 and len(key) >= 40)
stored = json.dumps(fake.tables["devices"])
check("only a hash is stored, never the key", key not in stored and "key_hash" in stored)
check("bad reader name rejected", post(ca, ha, "/api/devices", {"name": "<script>"}).status_code == 400)
for i in range(4): post(ca, ha, "/api/devices", {"name": f"R{i}"})
check("reader cap (5)", post(ca, ha, "/api/devices", {"name": "one too many"}).status_code == 400)
kb = post(cb, hb, "/api/devices", {"name": "Bob reader"}).get_json()["key"]
dev_a = [d for d in fake.tables["devices"] if d["name"] == "R3"][0]["id"]
check("another user cannot remove my reader", (cb.delete(f"/api/devices/{dev_a}", headers=hb), len([d for d in fake.tables['devices'] if d['id'] == dev_a]))[1] == 1)
check("I can remove my reader", ca.delete(f"/api/devices/{dev_a}", headers=ha).status_code == 200 and not [d for d in fake.tables["devices"] if d["id"] == dev_a])
check("junk device id is not found", ca.delete("/api/devices/not-a-uuid", headers=ha).status_code == 404)

print("== 2. the scan route (what the ESP32 calls)")
reader = A.app.test_client()
scan = lambda k, tag, c=reader: c.post("/api/iot/scan", json={"tag_uid": tag}, headers={"X-Device-Key": k} if k is not None else {})
check("no key -> 401", scan(None, "04A1B2C3").status_code == 401)
check("short key -> 401", scan("abc", "04A1B2C3").status_code == 401)
check("wrong key -> 401 (same message)", scan("x" * 43, "04A1B2C3").get_json() == {"error": "Not authorised."})
check("valid key but bad tag -> 400", scan(key, "ZZZ").status_code == 400)
check("no CSRF token needed for the reader (exempt) but the key is", scan(key, "04A1B2C3").status_code == 200)
tag1 = tag2 = tag3 = None
print("== 3. unknown tag, debounce, notifications")
tag1, tag2, tag3, tagB = "04A1B2C3", "04D4E5F6A7B8C9", "AABBCCDD", "11223344"
tg = lambda t: [x for x in fake.tables["hanger_tags"] if x["tag_uid"] == t][0]
check("first scan of a new tag is 'unknown' (done above), stored unlinked", tg(tag1)["item_id"] is None and tg(tag1)["user_id"] == UA)
check("an 'unknown_tag' notification was created", any(n["kind"] == "unknown_tag" for n in fake.tables["notifications"]))
n_before = len(fake.tables["notifications"])
check("repeat scan within 5 s is ignored", scan(key, tag1).get_json()["status"] == "ignored" and len(fake.tables["notifications"]) == n_before)
tg(tag1)["last_scanned_at"] = (now - timedelta(seconds=30)).isoformat()
scan(key, tag1)
check("30 s later: a read of the same waiting tag notifies again, and is still stored only once", len(fake.tables["notifications"]) == n_before + 1 and len([x for x in fake.tables["hanger_tags"] if x["tag_uid"] == tag1]) == 1)
tg(tag1)["last_scanned_at"] = (now - timedelta(seconds=90)).isoformat()
scan(key, tag1)
check("and again after a longer pause (every read notifies)", len(fake.tables["notifications"]) == n_before + 2 and "not linked" in fake.tables["notifications"][-1]["message"])
check("lower-case / separators in a tag id are cleaned", tags.clean_tag("04:a1-b2 c3") == "04A1B2C3")

print("== 4. linking tags to pieces")
check("link tag to my piece", post(ca, ha, "/api/tags/link", {"tag_uid": tag1, "item_id": p1["id"]}).status_code == 200 and tg(tag1)["item_id"] == p1["id"])
check("link a tag by typing its id (never scanned)", post(ca, ha, "/api/tags/link", {"tag_uid": tag2, "item_id": p2["id"]}).status_code == 200)
check("someone else's piece -> 404", post(ca, ha, "/api/tags/link", {"tag_uid": tag3, "item_id": pB["id"]}).status_code == 404)
check("invalid piece id -> 400", post(ca, ha, "/api/tags/link", {"tag_uid": tag3, "item_id": "nope"}).status_code == 400)
check("invalid tag id -> 400", post(ca, ha, "/api/tags/link", {"tag_uid": "xyz", "item_id": p3["id"]}).status_code == 400)
post(cb, hb, "/api/tags/link", {"tag_uid": tagB, "item_id": pB["id"]})
check("the SAME physical card can be linked by another account too, independently", post(ca, ha, "/api/tags/link", {"tag_uid": tagB, "item_id": p3["id"]}).status_code == 200
      and {(x["user_id"], x["item_id"]) for x in fake.tables["hanger_tags"] if x["tag_uid"] == tagB} == {(UA, p3["id"]), (UB, pB["id"])})
post(ca, ha, "/api/tags/link", {"tag_uid": tag3, "item_id": p3["id"]})
post(ca, ha, "/api/tags/link", {"tag_uid": "FFEEDDCC", "item_id": p3["id"]})
check("re-tagging a piece replaces its old tag (one tag per piece)", not [x for x in fake.tables["hanger_tags"] if x["tag_uid"] == tag3] and tg("FFEEDDCC")["item_id"] == p3["id"])
tag3 = "FFEEDDCC"

print("== 5. scanning linked tags = wearing")
fake.tables["hanger_tags"][0]["last_scanned_at"] = None
for t in (tag1, tag2, tag3): tg(t)["last_scanned_at"] = None
r = scan(key, tag1)
piece_row = lambda pid: [x for x in fake.tables["clothing_items"] if x["id"] == pid][0]
check("linked tag -> logged", r.get_json()["status"] == "logged")
check("wear_count +1 and last_worn_at set", piece_row(p1["id"])["wear_count"] == 1 and piece_row(p1["id"])["last_worn_at"])
check("a 'scan' notification was created", any(n["kind"] == "scan" and "Navy Blazer" in n["message"] for n in fake.tables["notifications"]))
tg(tag1)["last_scanned_at"] = (now - timedelta(minutes=5)).isoformat()
scan(key, tag1)
check("scanned again the same day: counted ONCE per day", piece_row(p1["id"])["wear_count"] == 1)
check("only one piece so far: no outfit yet", not fake.tables.get("outfit_logs"))
scan(key, tag2)
logs = fake.tables["outfit_logs"]
check("second piece within 2 h -> one 'hanger look' of 2 pieces", len(logs) == 1 and logs[0]["source"] == "hanger_scan" and set(logs[0]["item_ids"]) == {p1["id"], p2["id"]})
scan(key, tag3)
check("third piece joins the SAME look", len(fake.tables["outfit_logs"]) == 1 and len(fake.tables["outfit_logs"][0]["item_ids"]) == 3)
check("the matcher avoids everything worn this week, shoes included", {p1["id"], p2["id"], p3["id"]} <= outfits._recently_worn_ids(UA))
check("history page shows a 'Hanger look'", "Hanger look" in ca.get("/history").get_data(as_text=True))

print("== 6. isolation between users")
before = json.dumps(fake.tables["clothing_items"], sort_keys=True)
tg(tag1)["last_scanned_at"] = None
check("Bob's reader scanning a card that is MY tag: it is simply new for Bob", scan(kb, tag1).get_json()["status"] == "unknown" and any(x["user_id"] == UB and x["tag_uid"] == tag1 and x["item_id"] is None for x in fake.tables["hanger_tags"]))
check("and changed nothing of mine", json.dumps(fake.tables["clothing_items"], sort_keys=True) == before)
sim = post(ca, ha, "/api/tags/simulate", {"tag_uid": "99887766"}); check("simulate (website button) works like a reader", sim.status_code == 200 and sim.get_json()["status"] == "unknown")
check("simulate with a bad id -> 400", post(ca, ha, "/api/tags/simulate", {"tag_uid": "?"}).status_code == 400)
check("forgetting a tag removes it", ca.delete("/api/tags/99887766", headers=ha).status_code == 200 and not [x for x in fake.tables["hanger_tags"] if x["tag_uid"] == "99887766"])
check("cannot forget someone else's tag", (cb.delete(f"/api/tags/{tag2}", headers=hb), len([x for x in fake.tables['hanger_tags'] if x['tag_uid'] == tag2]))[1] == 1)

print("== 7. notifications API and reminders")
lst = ca.get("/api/notifications").get_json()
check("bell lists notifications with an unread count", lst["unread"] >= 3 and len(lst["items"]) >= 3)
check("push flag is reported", lst["push"] is True)
nid = lst["items"][0]["id"]
post(ca, ha, "/api/notifications/read", {"id": nid})
check("mark one as read", ca.get("/api/notifications").get_json()["unread"] == lst["unread"] - 1)
check("mark all as read", (post(ca, ha, "/api/notifications/read"), ca.get("/api/notifications").get_json()["unread"])[1] == 0)
check("bad id -> 404", post(ca, ha, "/api/notifications/read", {"id": "x"}).status_code == 404)
check("Bob sees none of mine", all(n["user_id"] == UB for n in fake.tables["notifications"] if n["id"] in [i["id"] for i in cb.get("/api/notifications").get_json()["items"]]))
old = piece(UA, "Forgotten Scarf", created_at=(now - timedelta(days=100)).isoformat())
ca.get("/api/notifications"); ca.get("/api/notifications")
nudges = [n for n in fake.tables["notifications"] if n["kind"] == "nudge"]
check("a 60-day reminder is created, once", len(nudges) == 1 and "Forgotten Scarf" in nudges[0]["message"])

print("== 8. push subscriptions (SSRF protection)")
sub = lambda ep: post(ca, ha, "/api/push/subscribe", {"endpoint": ep, "keys": {"p256dh": "BP" + "A" * 80, "auth": "A" * 22}})
check("http:// endpoint refused", sub("http://fcm.googleapis.com/fcm/send/abc").status_code == 400)
check("internal address refused (SSRF)", sub("https://127.0.0.1/steal").status_code == 400)
check("look-alike host refused", sub("https://fcm.googleapis.com.evil.com/x").status_code == 400)
check("random website refused", sub("https://example.com/push").status_code == 400)
check("Chrome (FCM) endpoint accepted", sub("https://fcm.googleapis.com/fcm/send/abc123").status_code == 200)
check("Firefox endpoint accepted", sub("https://updates.push.services.mozilla.com/wpush/v2/xyz").status_code == 200)
check("Edge endpoint accepted", sub("https://wns2-par02p.notify.windows.com/w/?token=abc").status_code == 200)
check("push public key is served", ca.get("/api/push/key").get_json()["public_key"] != "")
check("unsubscribe removes it", (post(ca, ha, "/api/push/unsubscribe", {"endpoint": "https://fcm.googleapis.com/fcm/send/abc123"}), not [s for s in fake.tables["push_subscriptions"] if s["endpoint"].endswith("abc123")])[1])

print("== 9. real Web Push delivery to a fake push service (payload decrypted)")
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import http_ece
received = {}
class Sink(BaseHTTPRequestHandler):
    def do_POST(self):
        received["headers"] = {k.lower(): v for k, v in self.headers.items()}
        received["body"] = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(201); self.end_headers()
    def log_message(self, *a): pass
srv = HTTPServer(("127.0.0.1", 0), Sink); threading.Thread(target=srv.serve_forever, daemon=True).start()
browser_key = ec.generate_private_key(ec.SECP256R1()); auth_secret = os.urandom(16)
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
fake.tables["push_subscriptions"] = [{"id": str(uuid.uuid4()), "user_id": UA, "endpoint": f"http://127.0.0.1:{srv.server_port}/push/abc",
    "p256dh": b64(browser_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)), "auth": b64(auth_secret)}]
notify.create(UA, "Navy Blazer was taken off the rail and logged as worn today.", kind="scan", link="/history")
check("push service received a request", "body" in received)
auth_header = received.get("headers", {}).get("authorization", "")
check("it carries our VAPID signature", auth_header.lower().startswith("vapid ") and "k=" in auth_header)
check("payload is encrypted (aes128gcm)", received.get("headers", {}).get("content-encoding") == "aes128gcm" and b"Navy Blazer" not in received.get("body", b""))
plain = json.loads(http_ece.decrypt(received["body"], private_key=browser_key, auth_secret=auth_secret))
check("the browser could decrypt it: title/body/url correct", plain == {"title": "StyleSync", "body": "Navy Blazer was taken off the rail and logged as worn today.", "url": "/history"}, str(plain))
srv.shutdown()

print("== 10. pages and static pieces")
page = ca.get("/hangers"); html = page.get_data(as_text=True)
check("/hangers renders", page.status_code == 200 and "Your wardrobe, connected." in html and 'id="add-device-form"' in html)
check("it lists my tagged pieces and readers", "Navy Blazer" in html and "Bedroom wardrobe" in html)
check("it never shows a device key or hash", key not in html and "key_hash" not in html)
check("bell is in the nav on app pages", 'id="bell-btn"' in ca.get("/dashboard").get_data(as_text=True))
sw = ca.get("/sw.js")
check("/sw.js is served with root scope", sw.status_code == 200 and sw.headers.get("Service-Worker-Allowed") == "/" and "javascript" in sw.mimetype)
csp = ca.get("/dashboard").headers["Content-Security-Policy"]
check("CSP allows our worker only", "worker-src 'self'" in csp)
check("anonymous cannot open /hangers", A.app.test_client().get("/hangers").status_code == 302)

print("== 12. the one-week rule (repeat warnings, nothing exempt)")
T = lambda days: (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
UC = str(uuid.uuid4()); cc, hc = session_for(UC)
key_c = post(cc, hc, "/api/devices", {"name": "Week test"}).get_json()["key"]
blue = piece(UC, "Blue Shirt", category="top", occasion="Work", last_worn_at=T(1), wear_count=4)
grey = piece(UC, "Grey Shirt", category="top", occasion="Work")
party = piece(UC, "Party Shirt", category="top", occasion="Party")
green = piece(UC, "Green Shirt", category="top", occasion="Work", last_worn_at=T(2))
oldie = piece(UC, "Old Shirt", category="top", occasion="Work", last_worn_at=T(10))
shoes = piece(UC, "Sneakers", category="footwear", last_worn_at=T(1))
black = piece(UC, "Black Trousers", category="bottom", last_worn_at=T(2))
beige = piece(UC, "Beige Chinos", category="bottom")
tag_of = {}
for i, pc in enumerate([blue, oldie, shoes, green, black, beige]):
    tag_of[pc["name"]] = f"A000000{i}"
    post(cc, hc, "/api/tags/link", {"tag_uid": tag_of[pc["name"]], "item_id": pc["id"]})
mine = lambda: [n for n in fake.tables["notifications"] if n["user_id"] == UC]
tagrow = lambda name: [x for x in fake.tables["hanger_tags"] if x["tag_uid"] == tag_of[name]][0]
r = scan(key_c, tag_of["Blue Shirt"])
msg = mine()[-1]["message"]
check("worn yesterday: 'detected' + 'you wore it yesterday' + a question", "Blue Shirt detected" in msg and "You wore it yesterday" in msg and "Repeat it, or try" in msg, msg)
check("it suggests unworn pieces of the same kind (same occasion first)", "Grey Shirt" in msg and "Old Shirt" in msg, msg)
check("it never suggests a shirt already worn this week, nor one for another occasion first", "Green Shirt" not in msg and "Party Shirt" not in msg, msg)
check("the reader is told it was a repeat", r.get_json().get("repeat") is True)
watch = piece(UC, "Gold Watch", category="accessory", last_worn_at=T(3))
post(cc, hc, "/api/tags/link", {"tag_uid": "A00000FF", "item_id": watch["id"]})
scan(key_c, "A00000FF")
check("an accessory worn 3 days ago is warned too", "Gold Watch detected" in mine()[-1]["message"] and "3 days ago" in mine()[-1]["message"], mine()[-1]["message"])
check("the warning links to the matcher", mine()[-1]["link"] == "/matcher")
scan(key_c, tag_of["Sneakers"])
check("shoes worn yesterday: warned like everything else (nothing is exempt)", "Sneakers detected" in mine()[-1]["message"] and "You wore it yesterday" in mine()[-1]["message"], mine()[-1]["message"])
scan(key_c, tag_of["Old Shirt"])
check("worn 10 days ago: no warning (outside the week)", "taken off the rail" in mine()[-1]["message"], mine()[-1]["message"])
tagrow("Blue Shirt")["last_scanned_at"] = (now - timedelta(minutes=5)).isoformat()
scan(key_c, tag_of["Blue Shirt"])
check("tapped again the same day: says it is already logged (not a repeat warning, not 'taken off the rail')", "Blue Shirt was already logged as worn today" in mine()[-1]["message"] and "detected" not in mine()[-1]["message"], mine()[-1]["message"])
seed_id = str(uuid.uuid4())
fake.tables["outfit_logs"].append({"id": seed_id, "user_id": UC, "item_ids": [green["id"], black["id"], shoes["id"]], "source": "worn", "created_at": T(2), "occasion": "Work", "season": "All-season"})
scan(key_c, tag_of["Green Shirt"])
scan(key_c, tag_of["Black Trousers"])
msg = mine()[-1]["message"]
check("the SAME shirt + trousers as 2 days ago: warns about the whole outfit", "it repeats the outfit you wore 2 days ago" in msg and msg.startswith("Black Trousers detected. With Green Shirt") and "also taken out today" in msg, msg)
scan(key_c, tag_of["Beige Chinos"])
check("a different combination is not flagged as a repeated outfit", "repeat the outfit" not in mine()[-1]["message"], mine()[-1]["message"])
ancient = piece(UC, "Ancient Shirt", category="top", last_worn_at=T(10))  # worn 10 days ago and never scanned today
recent = outfits._recently_worn_ids(UC)
check("matcher week memory: clothes yes, shoes yes, 10-day-old no", {green["id"], black["id"], shoes["id"]} <= recent and ancient["id"] not in recent)
kept = [l for l in fake.tables["outfit_logs"] if l["id"] == seed_id]
check("the main history is untouched: the 2-day-old look is still stored, unchanged", len(kept) == 1 and kept[0]["item_ids"] == [green["id"], black["id"], shoes["id"]])

print("== 13. the matcher and the one-week rule")
UD = str(uuid.uuid4()); cd, hd = session_for(UD)
mk = lambda name, cat: piece(UD, name, category=cat, occasion="Casual")
t1, t2, b1, b2, s1, s2 = mk("Top 1", "top"), mk("Top 2", "top"), mk("Bottom 1", "bottom"), mk("Bottom 2", "bottom"), mk("Shoes 1", "footwear"), mk("Shoes 2", "footwear")
fake.tables["outfit_logs"].append({"id": str(uuid.uuid4()), "user_id": UD, "item_ids": [t1["id"], b1["id"], s1["id"]], "source": "worn", "created_at": T(1), "occasion": "Casual", "season": "All-season"})
seen, shown = [], []
for _ in range(6):
    out = post(cd, hd, "/api/outfits/suggest", {"occasion": "Casual", "season": "All-season", "seen": seen}).get_json()["outfit"]
    seen.append(out["key"]); shown.append({x["item"]["name"] for x in out["items"]})
check("worn yesterday: the exact same Top 1 + Bottom 1 + Shoes 1 is not suggested again (first 6 looks)", not any({"Top 1", "Bottom 1", "Shoes 1"} <= look for look in shown), str(shown))
check("changing even one piece makes it a different outfit, so those are offered", any({"Top 1", "Bottom 1", "Shoes 2"} <= look for look in shown) or any("Top 2" in look for look in shown), str(shown))
check("other combinations are offered (e.g. Top 2 + Bottom 1)", any({"Top 2", "Bottom 1"} <= look for look in shown) or any({"Top 1", "Bottom 2"} <= look for look in shown), str(shown))
UE = str(uuid.uuid4()); ce, he = session_for(UE)
o1, o2, o3 = (piece(UE, n, category=c, occasion="Casual") for n, c in (("Only Top", "top"), ("Only Bottom", "bottom"), ("Only Shoes", "footwear")))
fake.tables["outfit_logs"].append({"id": str(uuid.uuid4()), "user_id": UE, "item_ids": [o1["id"], o2["id"], o3["id"]], "source": "worn", "created_at": T(1), "occasion": "Casual", "season": "All-season"})
r = post(ce, he, "/api/outfits/suggest", {"occasion": "Casual", "season": "All-season", "seen": []})
check("a closet with nothing else still gets an answer (the rule yields when it must)", r.status_code == 200 and len(r.get_json()["outfit"]["items"]) == 3)
fake.tables["outfit_logs"][-1]["created_at"] = T(9)
out = post(ce, he, "/api/outfits/suggest", {"occasion": "Casual", "season": "All-season", "seen": []}).get_json()["outfit"]
check("the same look aged 9 days (outside the week) is no longer held back: healthy match %", out["match_percent"] >= 60, str(out["match_percent"]))

print("== 14. occasion comes first")
UF = str(uuid.uuid4()); cf, hf = session_for(UF)
def mk2(name, cat, occ, worn=None):
    return piece(UF, name, category=cat, occasion=occ, **({"last_worn_at": T(worn)} if worn else {}))
for n in ("Party Shoes A", "Party Shoes B"): mk2(n, "footwear", "Party", worn=1)      # the only party shoes, both worn yesterday
for n in ("Casual Shoes 1", "Casual Shoes 2", "Casual Shoes 3"): mk2(n, "footwear", "Casual")  # unworn
mk2("Formal Shoes", "footwear", "Formal")
mk2("Party Top", "top", "Party"); mk2("Casual Top", "top", "Casual")
jeans = mk2("Jeans", "bottom", "Casual"); mk2("Formal Pants 1", "bottom", "Formal"); mk2("Formal Pants 2", "bottom", "Formal")
def ask(occasion, runs=40):
    A.limiter.reset()  # this test asks far more than 60 times a minute, which the real limiter (rightly) blocks
    seen, got = [], []
    for _ in range(runs):
        r = post(cf, hf, "/api/outfits/suggest", {"occasion": occasion, "season": "All-season", "seen": seen}).get_json()
        out = r["outfit"]; seen.append(out["key"]); got.append(out)
        if r["exhausted"]: seen = []
    return got
party = ask("Party")
names = lambda got, slot: {x["item"]["name"] for o in got for x in o["items"] if x["slot"] == slot}
check("Party: shoes are ONLY the party shoes, even though both were worn recently", names(party, "footwear") <= {"Party Shoes A", "Party Shoes B"} and names(party, "footwear"), str(names(party, "footwear")))
check("Party: both party shoes take turns", names(party, "footwear") == {"Party Shoes A", "Party Shoes B"})
check("Party: the top is the party top", names(party, "top") == {"Party Top"}, str(names(party, "top")))
check("Party: no party bottom exists, so the NEAREST occasion (casual jeans) is used, never formal pants", names(party, "bottom") == {"Jeans"}, str(names(party, "bottom")))
check("the reasons say a related piece was used", any("no party bottom" in t and "casual one was used" in t for t in party[0]["reasons"]), str(party[0]["reasons"]))
casual = ask("Casual")
check("Casual: casual pieces only (no party or formal shoes)", names(casual, "footwear") <= {"Casual Shoes 1", "Casual Shoes 2", "Casual Shoes 3"} and names(casual, "top") == {"Casual Top"}, str((names(casual, "footwear"), names(casual, "top"))))
fake.tables["clothing_items"] = [x for x in fake.tables["clothing_items"] if not (x["user_id"] == UF and x["name"] == "Jeans")]
party2 = ask("Party", runs=12)
check("with no casual bottom either, the next nearest (formal pants) is used instead of failing", names(party2, "bottom") <= {"Formal Pants 1", "Formal Pants 2"} and names(party2, "bottom"), str(names(party2, "bottom")))

print("== 15. same-day taps, titles, and the midnight boundary")
captured = []
real_push = notify._push_to_user
notify._push_to_user = lambda uid, payload: captured.append((uid, payload))   # record the pop-ups instead of sending them
UG = str(uuid.uuid4()); cg, hg = session_for(UG)
key_g = post(cg, hg, "/api/devices", {"name": "Midnight test"}).get_json()["key"]
midnight = tags._local_midnight_utc(datetime.now(timezone.utc))
mine_g = lambda: [n for n in fake.tables["notifications"] if n["user_id"] == UG]
def prep(name, cat, last_worn, tag, wear=4):
    pc = piece(UG, name, category=cat, occasion="Party", wear_count=wear, **({"last_worn_at": last_worn} if last_worn else {}))
    post(cg, hg, "/api/tags/link", {"tag_uid": tag, "item_id": pc["id"]}); return pc
row_of = lambda pc: [x for x in fake.tables["clothing_items"] if x["id"] == pc["id"]][0]
# a) already in today's outfit, added on the website with "Wear this today"
renew = prep("Renew Elevate", "footwear", now.isoformat(), "B0000001")
fake.tables["outfit_logs"].append({"id": str(uuid.uuid4()), "user_id": UG, "item_ids": [renew["id"], "x1", "x2"], "source": "worn", "created_at": now.isoformat(), "occasion": "Party", "season": "All-season"})
captured.clear(); scan(key_g, "B0000001")
check("tap a piece already in today's WORN outfit: says so", "already in the outfit you added to Worn today" in mine_g()[-1]["message"] and "taken off the rail" not in mine_g()[-1]["message"], mine_g()[-1]["message"])
check("... and does not count it twice (wear count unchanged)", row_of(renew)["wear_count"] == 4)
check("... pop-up title is 'Already worn today'", captured and captured[-1][1]["title"] == "Already worn today", str(captured))
# b) midnight boundary: worn at 23:50 last night, tapped just after midnight = YESTERDAY
late = prep("Late Shoes", "footwear", (midnight - timedelta(minutes=10)).isoformat(), "B0000002")
other = piece(UG, "Other Shoes", category="footwear", occasion="Party")
captured.clear(); scan(key_g, "B0000002")
check("worn 10 minutes before midnight counts as YESTERDAY after midnight", "Late Shoes detected. You wore it yesterday" in mine_g()[-1]["message"], mine_g()[-1]["message"])
check("... and suggests another pair (Other Shoes)", "Other Shoes" in mine_g()[-1]["message"], mine_g()[-1]["message"])
check("... pop-up title is 'Worn this week'", captured and captured[-1][1]["title"] == "Worn this week", str(captured))
# c) worn 10 minutes AFTER midnight is still today
soon = prep("Soon Shoes", "footwear", (midnight + timedelta(minutes=10)).isoformat(), "B0000003")
scan(key_g, "B0000003")
check("worn 10 minutes after midnight (today): same-day wording, not 'yesterday'", "already logged as worn today" in mine_g()[-1]["message"], mine_g()[-1]["message"])
# d) ordinary scan and unknown tag titles
fresh = prep("Fresh Shoes", "footwear", None, "B0000004", wear=0)
captured.clear(); scan(key_g, "B0000004")
check("a normal first tap: 'taken off the rail', title 'Hanger scan'", "taken off the rail" in mine_g()[-1]["message"] and captured[-1][1]["title"] == "Hanger scan", str(captured))
captured.clear(); scan(key_g, "B0000099")
check("a brand-new tag: title 'New hanger tag'", captured and captured[-1][1]["title"] == "New hanger tag", str(captured))
notify._push_to_user = real_push

print("== 16. the same physical card in two accounts")
UH, UJ = str(uuid.uuid4()), str(uuid.uuid4())
ch, hh = session_for(UH); cj, hj = session_for(UJ)
kh = post(ch, hh, "/api/devices", {"name": "Reader H"}).get_json()["key"]; kj = post(cj, hj, "/api/devices", {"name": "Reader J"}).get_json()["key"]
shoes_h = piece(UH, "Vedant's Shoes", category="footwear", wear_count=1); shirt_j = piece(UJ, "Aditya's Shirt", category="top", wear_count=7)
CARD = "C0FFEE01"
post(ch, hh, "/api/tags/link", {"tag_uid": CARD, "item_id": shoes_h["id"]})
check("account J sees the card as NEW (not taken by H)", scan(kj, CARD).get_json()["status"] == "unknown")
check("... J can link it to its own piece", post(cj, hj, "/api/tags/link", {"tag_uid": CARD, "item_id": shirt_j["id"]}).status_code == 200)
for x in fake.tables["hanger_tags"]:
    if x["tag_uid"] == CARD: x["last_scanned_at"] = None
check("H's reader + the card: logs H's shoes", scan(kh, CARD).get_json()["status"] == "logged" and row_of(shoes_h)["wear_count"] == 2)
check("... and J's shirt was NOT touched", row_of(shirt_j)["wear_count"] == 7)
check("J's reader + the same card: logs J's shirt", scan(kj, CARD).get_json()["status"] == "logged" and row_of(shirt_j)["wear_count"] == 8)
check("... and H's shoes were NOT touched", row_of(shoes_h)["wear_count"] == 2)
check("each account's notifications mention only its own piece", all("Shoes" in n["message"] for n in fake.tables["notifications"] if n["user_id"] == UH and n["kind"] == "scan") and all("Shirt" in n["message"] for n in fake.tables["notifications"] if n["user_id"] == UJ and n["kind"] == "scan"))
check("H unlinking the card leaves J's link in place", (ch.delete(f"/api/tags/{CARD}", headers=hh).status_code == 200) and any(x["user_id"] == UJ and x["tag_uid"] == CARD and x["item_id"] == shirt_j["id"] for x in fake.tables["hanger_tags"]))
html = cj.get("/wardrobe").get_data(as_text=True)
check("J's wardrobe page marks its shirt as tagged", "Hanger tag assigned" in html and "No hanger tag" not in html, "")
html_h = ch.get("/wardrobe").get_data(as_text=True)
check("H's wardrobe page (card unlinked) shows 'No hanger tag'", "No hanger tag" in html_h and "Hanger tag assigned" not in html_h)

print("== 17. beep answers, matcher tags, wardrobe wear line, live feed")
UK = str(uuid.uuid4()); ck, hk = session_for(UK)
kk = post(ck, hk, "/api/devices", {"name": "Reader K"}).get_json()["key"]
tagged_k = piece(UK, "Tagged Tee", category="top", occasion="Casual", wear_count=3, last_worn_at=(now - timedelta(days=2)).isoformat())
plain_k = piece(UK, "Plain Jeans", category="bottom", occasion="Casual")
post(ck, hk, "/api/tags/link", {"tag_uid": "D0000001", "item_id": tagged_k["id"]})
a = scan(kk, "D0000099").get_json()
check("beep data: a new tag answers status unknown (reader: 2 short beeps)", a["status"] == "unknown" and a["repeat"] is False, str(a))
fake.tables["clothing_items"][[x["id"] for x in fake.tables["clothing_items"]].index(tagged_k["id"])]["last_worn_at"] = None
a = scan(kk, "D0000001").get_json()
check("beep data: a normal scan answers logged, repeat false (reader: 1 short beep)", a["status"] == "logged" and a["repeat"] is False, str(a))
for x in fake.tables["hanger_tags"]:
    if x["tag_uid"] == "D0000001" and x["user_id"] == UK: x["last_scanned_at"] = None
fake.tables["clothing_items"][[x["id"] for x in fake.tables["clothing_items"]].index(tagged_k["id"])]["last_worn_at"] = (now - timedelta(days=2)).isoformat()
a = scan(kk, "D0000001").get_json()
check("beep data: worn 2 days ago answers repeat true (reader: 1 long beep)", a["status"] == "logged" and a["repeat"] is True, str(a))
raw = A.app.test_client().post("/api/iot/scan", json={"tag_uid": "D0000001"}, headers={"X-Device-Key": kk}).get_data(as_text=True).replace(" ", "")
check("the exact text the sketch looks for is in the reply (no-space JSON)", '"status":"' in raw and '"repeat":' in raw, raw)
html = ck.get("/wardrobe").get_data(as_text=True)
expected = f"Worn {row_of(tagged_k)['wear_count']} times"
check("wardrobe shows the real wear count and last-worn time", expected in html and "last just now" in html, expected)
check("wardrobe shows 'Never worn yet' for a new piece", "Never worn yet" in html)
hp = ck.get("/hangers").get_data(as_text=True)
check("the Hangers page carries the live-state fingerprint and Live badge", 'data-state="D0000' in hp and 'class="live-pill"' in hp)
f1 = ck.get("/api/tags/feed").get_json()
check("feed: returns a fingerprint and the newest hanger message", f1["state"] and "Tagged Tee" in f1["latest"], str(f1))
for x in fake.tables["hanger_tags"]:
    if x["tag_uid"] == "D0000001" and x["user_id"] == UK: x["last_scanned_at"] = None
scan(kk, "D0000001")
check("feed: the fingerprint CHANGES after a scan (the page then reloads)", ck.get("/api/tags/feed").get_json()["state"] != f1["state"])
check("feed: another account sees none of it", cj.get("/api/tags/feed").get_json()["state"] != ck.get("/api/tags/feed").get_json()["state"] and "Tagged Tee" not in cj.get("/api/tags/feed").get_json()["latest"])
check("feed: needs login", A.app.test_client().get("/api/tags/feed").status_code in (302, 401))
for name, cat, occ in (("M Shoes", "footwear", "Casual"),):
    piece(UK, name, category=cat, occasion=occ)
r = post(ck, hk, "/api/outfits/suggest", {"occasion": "Casual", "season": "All-season"})
got = r.get_json()["outfit"]["items"]
flags = {e["item"]["name"]: e["item"]["tagged"] for e in got}
check("matcher: every suggested piece says whether it has a tag", all(isinstance(v, bool) for v in flags.values()) and flags.get("Tagged Tee") is True and flags.get("Plain Jeans") is False, str(flags))
js = open("static/js/app.js", encoding="utf8").read()
check("matcher card draws the tag line only when 'tagged' is sent", "item.tagged === undefined" in js and "Hanger tag assigned" in js)

print("== 18. a wrong laptop clock must not block scans")
UL = str(uuid.uuid4()); cl, hl = session_for(UL)
kl = post(cl, hl, "/api/devices", {"name": "Clock test"}).get_json()["key"]
pl = piece(UL, "Clock Shoes", category="footwear")
post(cl, hl, "/api/tags/link", {"tag_uid": "E0000001", "item_id": pl["id"]})
for x in fake.tables["hanger_tags"]:
    if x["tag_uid"] == "E0000001" and x["user_id"] == UL: x["last_scanned_at"] = (datetime.now(timezone.utc) + timedelta(hours=11)).isoformat()  # stamped 11 h in the FUTURE
check("a tag stamped in the future is NOT ignored (status logged, not ignored)", scan(kl, "E0000001").get_json()["status"] == "logged")
check("a real double read right after is still ignored (debounce still works)", scan(kl, "E0000001").get_json()["status"] == "ignored")

print("== 11. every new route: login + CSRF + rate limit")
problems = []
for rule in A.app.url_map.iter_rules():
    if not (rule.rule.startswith(("/api/tags", "/api/devices", "/api/notifications", "/api/push", "/api/iot")) or rule.rule == "/hangers"): continue
    for m in rule.methods - {"HEAD", "OPTIONS"}:
        url = re.sub(r"<[^>]+>", "04A1B2C3" if "tags" in rule.rule else str(uuid.uuid4()), rule.rule)
        anon = A.app.test_client()
        r = anon.open(url, method=m)
        if rule.rule == "/api/iot/scan":
            if r.status_code != 401: problems.append(f"scan without key gave {r.status_code}")
        elif m == "GET" and r.status_code not in (302, 401): problems.append(f"GET {rule.rule} open: {r.status_code}")
        elif m != "GET" and r.status_code != 400: problems.append(f"{m} {rule.rule} no-CSRF gave {r.status_code}")
        if m != "GET" and rule.rule != "/api/iot/scan":
            c, h = session_for(UA);
            r2 = c.open(url, method=m, json={})   # logged in but no CSRF token
            if r2.status_code != 400: problems.append(f"{m} {rule.rule} logged-in without CSRF gave {r2.status_code}")
check("all routes protected as designed", not problems, str(problems))
A.limiter.reset()
codes = [scan(kb, "ABCDEF12").status_code for _ in range(35)]
check("a noisy reader is rate limited (30 per minute)", 429 in codes and codes.index(429) <= 31, str(codes[28:34]))

print(f"\n{passed} checks passed, {len(failed)} failed")
for f in failed: print("   FAILED:", f)
