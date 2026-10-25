"""Test helper: pretend a piece was last worn N days ago, so you can see the one-week repeat warning without waiting a day.

    python tools/pretend_worn.py --email you@example.com --piece "Black T-Shirt" --days 1
    python tools/pretend_worn.py --email you@example.com --piece "Black T-Shirt" --days 0     (0 = forget that it was ever worn)

It changes ONE thing: the "last worn" time of that one piece. Nothing else in your data is touched.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import db  # noqa: E402

parser = argparse.ArgumentParser(description="Pretend a piece was last worn N days ago.")
parser.add_argument("--email", required=True, help="the email of your StyleSync account")
parser.add_argument("--piece", required=True, help="part of the piece's name, for example 'T-Shirt'")
parser.add_argument("--days", type=int, required=True, help="how many days ago (1 = yesterday, 0 = forget)")
args = parser.parse_args()
if not 0 <= args.days <= 60:
    sys.exit("--days must be between 0 and 60")

client = db.data_client()
users = [u for u in client.auth.admin.list_users(page=1, per_page=100) if (u.email or "").lower() == args.email.lower()]
if not users:
    sys.exit("No account with that email.")
items = client.table("clothing_items").select("id,name,category").eq("user_id", users[0].id).execute().data
matches = [i for i in items if args.piece.lower() in i["name"].lower()]
if len(matches) != 1:
    sys.exit("Found %d pieces matching '%s'%s" % (len(matches), args.piece, ": " + ", ".join(i["name"] for i in matches) if matches else "."))

piece = matches[0]
when = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat() if args.days else None
client.table("clothing_items").update({"last_worn_at": when}).eq("id", piece["id"]).eq("user_id", users[0].id).execute()
print(f"OK: '{piece['name']}' now counts as last worn {args.days} day(s) ago." if args.days else f"OK: '{piece['name']}' now counts as never worn.")
