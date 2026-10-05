-- Rota App — Supabase şeması (hesap/favoriler özelliği).
-- Supabase Dashboard → SQL Editor'de bir kerelik çalıştırılır.
-- Bu dosya, panelde zaten var olan kurulumun 2026-10-05'te `pg_policies` /
-- `information_schema.columns` / `pg_proc` üzerinden çıkarılmış birebir
-- karşılığıdır (bkz. ROADMAP.md Milestone 4 — Supabase RLS denetimi).

-- ============================================================
-- profiles: auth.users'a 1-1, kullanıcı adı.
-- ============================================================

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  username text not null,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists profiles_select_all on public.profiles;
create policy profiles_select_all
  on public.profiles for select
  using (true);

drop policy if exists profiles_insert_own on public.profiles;
create policy profiles_insert_own
  on public.profiles for insert
  with check (auth.uid() = id);

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own
  on public.profiles for update
  using (auth.uid() = id);
-- Not: WITH CHECK yazılmadı; Postgres, UPDATE policy'sinde WITH CHECK
-- verilmezse USING'i WITH CHECK için de kullanır — yani güncellenen satırın
-- id'si de auth.uid() ile eşleşmek zorunda kalır (bkz. CREATE POLICY dokümanı).

-- auth.users'a yeni kullanıcı eklenince profiles'a otomatik satır açar;
-- signUp'ın options.data.username metadata'sından okur. SECURITY DEFINER
-- olduğu için RLS'i (profiles_insert_own, auth.uid() henüz bu bağlamda farklı
-- davranabilir) atlar; search_path sabitlenmesi search_path hijack'ine karşı.
--
-- ÖNEMLİ: username NOT NULL ama frontend'in signUp çağrısı HER ZAMAN
-- options.data.username göndermek zorunda — göndermezse bu trigger NOT NULL
-- ihlaliyle patlar ve auth.users insert'i de (dolayısıyla kayıt) geri alınır.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $function$
begin
  insert into public.profiles (id, username) values (new.id, new.raw_user_meta_data ->> 'username');
  return new;
end;
$function$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================
-- saved_plans: kaydedilen/favorilenen rotalar, link ile paylaşım.
-- Gizlilik modeli: id (uuid) tahmin edilemez olduğu için select herkese
-- açık; sahiplik yalnızca insert/delete'te kontrol edilir. Bilerek UPDATE
-- policy'si yok — frontend hiçbir satırı güncellemiyor.
-- ============================================================

create table if not exists public.saved_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  theme text not null,
  title text not null,
  summary text not null,
  stops jsonb not null,
  legs jsonb not null,
  routes_available boolean not null default true,
  created_at timestamptz not null default now()
);

alter table public.saved_plans enable row level security;

drop policy if exists saved_plans_select_all on public.saved_plans;
create policy saved_plans_select_all
  on public.saved_plans for select
  using (true);

drop policy if exists saved_plans_insert_own on public.saved_plans;
create policy saved_plans_insert_own
  on public.saved_plans for insert
  with check (auth.uid() = user_id);

drop policy if exists saved_plans_delete_own on public.saved_plans;
create policy saved_plans_delete_own
  on public.saved_plans for delete
  using (auth.uid() = user_id);
