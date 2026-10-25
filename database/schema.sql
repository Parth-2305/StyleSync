-- Run this ONCE in Supabase: Dashboard -> SQL Editor -> New query -> paste -> Run.

-- One row per user, filled automatically when someone signs up (auth.users is Supabase's own table).
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  styles text[] default '{}',
  colors text[] default '{}',
  city text,
  created_at timestamptz default now()
);

create table clothing_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) <= 60),
  category text not null check (category in ('top','bottom','outerwear','footwear','accessory')),
  color text not null,
  season text[] not null,
  occasion text not null,
  style text,
  notes text check (char_length(notes) <= 500),
  image_url text,
  wear_count int not null default 0,
  last_worn_at timestamptz,
  created_at timestamptz default now()
);
create index on clothing_items(user_id);

create table outfit_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  item_ids uuid[] not null,
  occasion text,
  season text,
  source text not null check (source in ('saved','worn','hanger_scan')),
  created_at timestamptz default now()
);
create index on outfit_logs(user_id, created_at desc);

-- Hanger tag = RFID tag on a hanger. The ESP32 reader sends the tag's UID; we look up which garment it is.
create table hanger_tags (
  tag_uid text primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  item_id uuid references clothing_items(id) on delete set null,
  last_scanned_at timestamptz
);

create table notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  message text not null,
  is_read boolean not null default false,
  created_at timestamptz default now()
);
create index on notifications(user_id, is_read);

-- Row Level Security: ON with NO policies means "nobody using the public anon key can read or write".
-- Only our Flask server (service-role key) touches these tables, and it always filters by the logged-in user.
alter table profiles enable row level security;
alter table clothing_items enable row level security;
alter table outfit_logs enable row level security;
alter table hanger_tags enable row level security;
alter table notifications enable row level security;

-- Auto-create the profile row on signup.
create function handle_new_user() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, full_name) values (new.id, new.raw_user_meta_data->>'full_name');
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function handle_new_user();

-- Only our Flask server (the service_role key) may use these tables. Needed because we turned off
-- "Automatically expose new tables" when creating the project. anon/authenticated get nothing.
grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
