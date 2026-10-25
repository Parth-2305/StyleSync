"""A tiny in-memory stand-in for the supabase-py query builder (only the calls StyleSync uses), for testing without the new tables."""
import copy
import uuid
from datetime import datetime, timezone


class Result:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


UNIQUE = {"hanger_tags": [("user_id", "tag_uid")], "devices": ["key_hash"], "push_subscriptions": ["endpoint"]}
DEFAULTS = {
    "clothing_items": {"wear_count": 0, "last_worn_at": None, "style": "", "notes": "", "image_url": None},
    "notifications": {"is_read": False, "kind": "info", "link": None},
    "hanger_tags": {"item_id": None, "last_scanned_at": None},
    "devices": {"last_seen_at": None},
    "outfit_logs": {"occasion": None, "season": None},
}


class Query:
    def __init__(self, db, name):
        self.db, self.name = db, name
        self.op, self.filters, self.payload, self.order_by, self.lim, self.count_mode = "select", [], None, None, None, None

    def select(self, cols="*", count=None): self.op, self.count_mode = "select", count; return self
    def insert(self, row): self.op, self.payload = "insert", row; return self
    def update(self, data): self.op, self.payload = "update", data; return self
    def delete(self): self.op = "delete"; return self
    def eq(self, c, v): self.filters.append(lambda r: r.get(c) == v); return self
    def neq(self, c, v): self.filters.append(lambda r: r.get(c) != v); return self
    def gte(self, c, v): self.filters.append(lambda r: r.get(c) is not None and r.get(c) >= v); return self
    def in_(self, c, vals): self.filters.append(lambda r: r.get(c) in vals); return self
    def order(self, c, desc=False): self.order_by = (c, desc); return self
    def limit(self, n): self.lim = n; return self

    def execute(self):
        rows = self.db.tables.setdefault(self.name, [])
        if self.op == "insert":
            row = {**DEFAULTS.get(self.name, {}), **copy.deepcopy(self.payload)}
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            for col in UNIQUE.get(self.name, []):
                cols = col if isinstance(col, tuple) else (col,)   # a tuple = unique as a COMBINATION (like the database's new key)
                if any(all(r.get(c) == row.get(c) for c in cols) for r in rows):
                    raise Exception(f"duplicate key value violates unique constraint ({cols})")
            rows.append(row)
            return Result([copy.deepcopy(row)])
        matched = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "update":
            for r in matched: r.update(copy.deepcopy(self.payload))
            return Result([copy.deepcopy(r) for r in matched])
        if self.op == "delete":
            for r in matched: rows.remove(r)
            return Result([copy.deepcopy(r) for r in matched])
        if self.order_by:
            c, desc = self.order_by
            matched = sorted(matched, key=lambda r: (r.get(c) is None, r.get(c) or ""), reverse=desc)
            if desc:  # keep None last when descending
                matched = [r for r in matched if r.get(c) is not None] + [r for r in matched if r.get(c) is None]
        total = len(matched)
        if self.lim is not None: matched = matched[: self.lim]
        return Result([copy.deepcopy(r) for r in matched], count=total if self.count_mode else None)


class Table:
    """Like the real library: every select/insert/update/delete starts a BRAND NEW query, so a table object can be reused."""
    def __init__(self, db, name): self.db, self.name = db, name
    def select(self, *a, **k): return Query(self.db, self.name).select(*a, **k)
    def insert(self, row): return Query(self.db, self.name).insert(row)
    def update(self, data): return Query(self.db, self.name).update(data)
    def delete(self): return Query(self.db, self.name).delete()


class FakeDB:
    def __init__(self): self.tables = {}
    def table(self, name): return Table(self, name)
