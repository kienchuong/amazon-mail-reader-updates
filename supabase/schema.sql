-- Run this once in Supabase: SQL Editor > New query > Run.
create table if not exists public.amr_mobile_snapshot (
  id boolean primary key default true check (id),
  payload jsonb not null,
  synced_at timestamptz not null default now()
);

alter table public.amr_mobile_snapshot enable row level security;

-- No browser policies are intentionally created. Only the Edge Function,
-- using the server-side service role, can read or replace the snapshot.
