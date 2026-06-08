# Email OTP Login + 3-Tier Access — Design Spec

Date: 2026-06-09
Branch: `feat/email-login` (off `main`)
Status: approved (approach 🅰)

## Goal

Add passwordless **Supabase email OTP** login (no Google, no password) to the
recruiter-facing app, and gate access in three tiers. Built on a new branch off
`main`; merged to `main` only after the owner configures Supabase and verifies
the OTP flow end-to-end. Translation/i18n/responsive work stays on
`feat/supabase-auth` and is intentionally NOT included.

## Access tiers

| Tier | Can access |
| --- | --- |
| **Public** (no login) | `/` landing, `/news`, report **list** `/archive`, `/login` |
| **Member** (logged in) | + report **detail** `/archive/:slug`, served report files |
| **Admin** (email in `ADMIN_EMAILS`) | + `/db`, `/keywords`, generation `/app`, `/usage`, dashboard, archive build, keyword writes |

Note: this flips today's `main` behavior (list is currently gated, detail is public).

## Backend (FastAPI)

- Add `src/auth.py` ported from `feat/supabase-auth` (provider-agnostic — verifies
  any Supabase session JWT, so it works for OTP unchanged):
  - `verify_token(token)` → `GET {SUPABASE_URL}/auth/v1/user` with 60s cache
  - `require_member`, `require_admin`, `require_admin_query`, `is_admin`
- Gate endpoints in `src/server.py`:
  - **Public:** `GET /api/reports` (list), topics/news data
  - **Member:** `GET /api/reports/{slug}`, `GET /reports/{filename}` → `Depends(require_member)`
  - **Admin:** `POST /api/archives/refresh`, `PUT /api/keywords`, `POST /api/report/*`
    (generation), `DELETE /api/reports/{slug}`, DB endpoints → `Depends(require_admin)`
- Env: `SUPABASE_URL`/`VITE_SUPABASE_URL`, `SUPABASE_ANON_KEY`/`VITE_SUPABASE_ANON_KEY`,
  `ADMIN_EMAILS` (comma-separated).

## Frontend (React)

- Add `src/lib/supabase.js` — Supabase client (PKCE, persist + auto-refresh session).
- Replace PIN auth:
  - `AuthContext` — holds Supabase session/user; exposes `isAuthenticated`, `isAdmin`,
    `accessToken`, `signOut`; subscribes to `onAuthStateChange`.
  - `LoginPage` — email field → `signInWithOtp({ email, options: { shouldCreateUser: true } })`
    → 6-digit code field → `verifyOtp({ email, token, type: 'email' })` → redirect to
    the intended route (default `/archive`).
- Routing (`App.jsx`) — replace the single `ProtectedRoute` with `MemberRoute` + `AdminRoute`:
  - Public: `/`, `/login`, `/news`, `/archive`
  - Member: `/archive/:slug`
  - Admin: `/app`, `/db`, `/keywords`, `/usage`
  - Unauthenticated → redirect `/login`; authenticated non-admin on an admin route → redirect `/`.
- Nav/tabs — hide admin-only tabs for non-admins; hide member-only actions for anon.
- API client — attach `Authorization: Bearer <access_token>` on gated calls
  (report detail + admin actions).

## Owner's external setup (Supabase dashboard — required before live use)

1. Create a Supabase project; run `supabase/schema.sql` (profiles + RLS + first-login trigger).
2. Authentication → Providers → enable **Email** (OTP); set Site URL + Redirect URLs (`/**`).
3. `.env`: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `ADMIN_EMAILS=<owner email>`.

## Testing

- Backend pytest: mock `verify_token` — detail endpoint returns 401 without token / 200 for
  a member; admin endpoints 403 for non-admin. Existing suite stays green.
- Frontend: lint + build green. (Live OTP E2E needs the owner's Supabase config.)
- CI (`main`) is untouched; this branch must be green before merge.

## Out of scope (YAGNI)

Google OAuth, password login, `team` role, feedback, report translation / public-page i18n /
mobile responsive — those remain on `feat/supabase-auth`.

## Rollout

All work on `feat/email-login` (off `main`). NOT merged to `main` until the owner configures
Supabase and verifies the OTP flow. `main` stays stable and CI-green in the meantime.
