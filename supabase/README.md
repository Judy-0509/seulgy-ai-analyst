# Seulgy — 이메일 OTP 로그인 (Supabase) 설정

Supabase Auth + 이메일 OTP(비밀번호 없는 6자리 코드). 사용자는 이메일 주소를 입력하면
6자리 코드를 받아 로그인한다. Google OAuth·비밀번호 없음.

```
/login → 이메일 입력 → signInWithOtp({email}) → 메일함에서 6자리 코드 확인
       → 코드 입력 → verifyOtp({email, token, type:'email'}) → 로그인 완료
세션      ─ supabase-js 가 localStorage 에 보관·자동 갱신 (PKCE, detectSessionInUrl)
멤버 라우트 ─ AuthContext.isAuthenticated → App.jsx MemberRoute
관리자 라우트 ─ AuthContext.isAdmin (ADMIN_EMAILS 일치 여부) → App.jsx AdminRoute
프로필    ─ public.profiles (트리거가 최초 로그인 시 이메일로 자동 생성)
```

## 1. 환경변수 (.env)

루트 `.env`에 추가 (`.env.example` 참고):

```
# Supabase 프로젝트 자격증명
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon public key>

# 관리자 이메일 (콤마 구분, 소문자로 비교)
ADMIN_EMAILS=owner@example.com
```

> Supabase 대시보드 → Project Settings → API 에서 복사. `anon` 키만 사용(브라우저 노출 안전).
> `ADMIN_EMAILS` 는 백엔드(`src/auth.py`)에서만 읽힌다. 브라우저에 노출되지 않는다.

## 2. 스키마 적용

Supabase 대시보드 → **SQL Editor** → [`schema.sql`](./schema.sql) 전체 붙여넣고 **Run**.

→ `public.profiles` 테이블 + RLS(본인 프로필만 조회) + 최초 로그인 시 프로필 자동 생성 트리거.
멱등(idempotent): 여러 번 실행해도 안전하다.

## 3. Supabase — Email provider 활성화

대시보드 → **Authentication → Providers → Email**:
- **Enable Email provider**: ON
- **Confirm email**: OFF (OTP 흐름에서 별도 확인 링크 불필요)
- **Secure email change**: 선택 (기본값 유지 가능)

## 4. Supabase — Redirect URL 허용

대시보드 → **Authentication → URL Configuration**:
- **Site URL**: 운영 URL (예: `https://seulgy.com`; 로컬만 쓰면 `http://localhost:5173`)
- **Redirect URLs** 에 추가:
  - `http://localhost:5173/**`
  - `https://seulgy.com/**`

## 5. 실행 / 테스트

```bash
# 백엔드
ADMIN_EMAILS=your@email.com uvicorn src.server:app --host 127.0.0.1 --port 8000

# 프론트엔드
cd frontend && npm install && npm run dev
```

1. `/login` → 이메일 입력 → **코드 받기**
2. 이메일 받은 6자리 코드 입력 → **확인**
3. `/archive` 로 자동 이동 (멤버 이상)
4. `ADMIN_EMAILS`에 등록된 이메일이면 `/app`, `/db`, `/keywords`, `/usage` 접근 가능

Supabase 대시보드 **Authentication → Users**, **Table Editor → profiles** 에서 생성 확인.

## 6. 접근 티어

| 티어 | 접근 가능 |
|------|----------|
| **Public** (비로그인) | `/` 랜딩, `/news`, `/archive` 목록, `/login` |
| **Member** (로그인) | + 보고서 상세 `/archive/:slug`, 보고서 파일 `/reports/*` |
| **Admin** (`ADMIN_EMAILS` 일치) | + `/app`, `/db`, `/keywords`, `/usage`, 아카이브 빌드, 키워드 수정, 보고서 생성·삭제 |

## 참고 · 한계

- 이메일 OTP만 지원 (Google OAuth·비밀번호 없음). 다른 provider 추가는 `src/auth.py`
  `verify_token` 이 Supabase JWT를 검증하므로 provider 무관하게 동작한다.
- OTP 코드 유효시간: Supabase 기본 60분 (대시보드에서 변경 가능).
- 관리자 권한은 `ADMIN_EMAILS` 환경변수 기준. Supabase 역할(role)과는 별개다.
