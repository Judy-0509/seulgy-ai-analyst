-- Seulgy — Supabase 스키마 (Google OAuth 로그인)
-- 사용법: Supabase 대시보드 → SQL Editor 에 전체 붙여넣고 Run.
-- 멱등(idempotent): 여러 번 실행해도 안전하며, 예전 username 스키마에서도 안전하게 업그레이드된다.

-- ─────────────────────────────────────────────────────────────
-- 1) 프로필 테이블 : auth.users 와 1:1, Google 프로필(이름/이메일/아바타) 보관
-- ─────────────────────────────────────────────────────────────
create table if not exists public.profiles (
  id         uuid primary key references auth.users (id) on delete cascade,
  email      text,
  full_name  text,
  avatar_url text,
  created_at timestamptz not null default now()
);

-- 예전(아이디/비번) 스키마 호환: 누락 컬럼 추가, 레거시 username은 nullable 로.
alter table public.profiles add column if not exists email      text;
alter table public.profiles add column if not exists full_name  text;
alter table public.profiles add column if not exists avatar_url text;

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'profiles' and column_name = 'username'
  ) then
    alter table public.profiles alter column username drop not null;
  end if;
end $$;

comment on table public.profiles is 'Seulgy 회원 프로필 (auth.users 1:1, Google 프로필)';

-- ─────────────────────────────────────────────────────────────
-- 2) Row Level Security
--    - 본인 프로필만 조회 (다른 사용자 프로필 비공개)
--    - 클라이언트 직접 수정 차단 (프로필은 트리거가 Google 메타로 관리)
--    - INSERT/UPSERT 는 아래 트리거(security definer)가 담당
-- ─────────────────────────────────────────────────────────────
alter table public.profiles enable row level security;

-- 본인 프로필만 조회. (이전의 전체 공개 정책 profiles_select_authenticated 제거)
drop policy if exists "profiles_select_authenticated" on public.profiles;
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
  on public.profiles for select
  to authenticated
  using (auth.uid() = id);

-- 클라이언트 직접 UPDATE 차단(이메일/이름 변조 방지). 프로필은 트리거가 관리.
-- 편집 기능이 필요해지면 컬럼 제한 정책 또는 RPC로 별도 추가할 것.
drop policy if exists "profiles_update_own" on public.profiles;

-- ─────────────────────────────────────────────────────────────
-- 3) 최초 로그인(가입) 시 프로필 자동 생성
--    auth.users insert 시 1회 실행하여 Google 메타데이터(full_name/name,
--    avatar_url/picture)를 프로필에 기록한다. (재로그인 시에는 갱신되지 않음 —
--    on conflict do update 는 트리거가 중복 실행될 때를 위한 idempotency 안전장치)
-- ─────────────────────────────────────────────────────────────
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'),
    coalesce(new.raw_user_meta_data ->> 'avatar_url', new.raw_user_meta_data ->> 'picture')
  )
  on conflict (id) do update set
    email      = excluded.email,
    full_name  = excluded.full_name,
    avatar_url = excluded.avatar_url;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
