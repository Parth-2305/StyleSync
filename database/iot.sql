-- StyleSync IoT and notifications setup. Run ONCE in Supabase: SQL Editor -> New query -> paste -> Run.
-- Safe to run again. It adds new tables and columns; it does not delete or change your existing data.

-- 1. Readers (ESP32 devices). The secret key is NEVER stored, only its SHA-256 hash, so even a database leak
--    cannot be used to impersonate a reader.
create table if not exists devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 40),
  key_hash text not null unique,
  last_seen_at timestamptz,
  created_at timestamptz default now()
);
create index if not exists devices_user_idx on devices(user_id);

-- 2. Browser push subscriptions (one row per browser the user allowed notifications in).
create table if not exists push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  endpoint text not null unique check (char_length(endpoint) <= 600),
  p256dh text not null check (char_length(p256dh) <= 200),
  auth text not null check (char_length(auth) <= 100),
  created_at timestamptz default now()
);
create index if not exists push_user_idx on push_subscriptions(user_id);

-- 3. Notifications get a type and an optional page to open when clicked.
alter table notifications add column if not exists kind text not null default 'info';
alter table notifications add column if not exists link text;
alter table notifications drop constraint if exists notifications_kind_link;
alter table notifications add constraint notifications_kind_link check (
  kind in ('info', 'scan', 'unknown_tag', 'nudge') and (link is null or (char_length(link) <= 200 and link like '/%')));

-- 4. A tag id is the hex id printed by the RFID reader (4 to 10 bytes = 8 to 20 hex characters).
alter table hanger_tags drop constraint if exists tag_uid_format;
alter table hanger_tags add constraint tag_uid_format check (tag_uid ~ '^[0-9A-F]{8,20}$');
create index if not exists hanger_tags_user_idx on hanger_tags(user_id);
create index if not exists hanger_tags_item_idx on hanger_tags(item_id);

-- 5. Same locks as every other table: RLS on, nothing for the public roles, full access only for our server.
alter table devices enable row level security;
alter table push_subscriptions enable row level security;
revoke all on devices, push_subscriptions from anon, authenticated;
grant all on devices, push_subscriptions to service_role;
grant all on hanger_tags, notifications to service_role;
