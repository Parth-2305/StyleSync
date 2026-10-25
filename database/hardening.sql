-- StyleSync database hardening. Run ONCE in Supabase: SQL Editor -> New query -> paste -> Run.
-- Safe to run again. It does not delete or change any of your data.

-- 1. The public roles (anon = anyone with the public key, authenticated = any logged-in user talking to Supabase
--    directly) get NOTHING. Row Level Security already blocks them; this is a second, independent lock.
--    Only our Flask server (service_role) may touch the tables.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke execute on all functions in schema public from public, anon, authenticated;

-- 2. Tables and functions created in the FUTURE start locked too, so a new table can't be exposed by accident.
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;

-- 3. The database itself refuses nonsense, even if a bug in the app ever let it through.
alter table clothing_items drop constraint if exists items_field_limits;
alter table clothing_items add constraint items_field_limits check (
  char_length(color) <= 30 and char_length(occasion) <= 30 and char_length(coalesce(style, '')) <= 30
  and cardinality(season) between 1 and 4 and wear_count >= 0);

alter table outfit_logs drop constraint if exists logs_field_limits;
alter table outfit_logs add constraint logs_field_limits check (
  char_length(coalesce(occasion, '')) <= 30 and char_length(coalesce(season, '')) <= 30
  and cardinality(item_ids) between 2 and 6);

alter table notifications drop constraint if exists notifications_limits;
alter table notifications add constraint notifications_limits check (char_length(message) <= 300);

-- 4. Make sure Row Level Security is on for every table (it should already be; this repeats it harmlessly).
alter table profiles enable row level security;
alter table clothing_items enable row level security;
alter table outfit_logs enable row level security;
alter table hanger_tags enable row level security;
alter table notifications enable row level security;

-- 5. Keep the server's access (the revokes above never touch service_role).
grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
