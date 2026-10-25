-- StyleSync: hanger tags belong to an ACCOUNT, not to the physical card.
-- Run ONCE in Supabase: SQL Editor -> New query -> paste -> Run. Safe to run again. It does not delete any data.
--
-- Before: a tag id could exist only once in the whole database, so a card used by one account was "taken" for everyone.
-- After:  the same card can be used by several accounts, each with its own meaning (e.g. my card = Nike shoes, yours = a blue shirt).

do $$
declare pk text;
begin
  select conname into pk from pg_constraint where conrelid = 'public.hanger_tags'::regclass and contype = 'p';
  if pk is not null then
    execute format('alter table public.hanger_tags drop constraint %I', pk);   -- remove the old "tag id is unique everywhere" key
  end if;
end $$;

alter table hanger_tags add primary key (user_id, tag_uid);                    -- new rule: unique per account
