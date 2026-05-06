# Canopy Frontend Design System

이 문서는 Canopy 프론트엔드에 기능을 추가할 때 유지해야 하는 공통 디자인 규칙이다. 목표는 `LandingPage`, `/app`, `/archive`, `/db`, `/news`가 하나의 제품처럼 보이게 하는 것이다.

## 1. Product Tone

- 리서치/운영 도구처럼 조용하고 정보 밀도가 높은 UI를 우선한다.
- 마케팅 랜딩 페이지처럼 장식적인 카드나 과한 설명을 늘리지 않는다.
- 반복 사용 화면은 빠른 스캔, 명확한 상태, 안정적인 리스트 배치를 우선한다.
- 브랜드 마크는 `frontend/public/logo-mark.png`를 사용한다.

## 2. Typography

- 기본 폰트는 `index.css`의 iOS 계열 폰트 스택을 따른다.
- 본문/UI 기본 letter spacing은 `0`이다.
- 화면 제목은 `24px`, `700` 전후를 기본으로 한다.
- 카드/리스트 제목은 `12-16px`, `500-700` 범위에서 사용한다.
- 메타 정보와 timestamp는 `9-12px`, muted color를 사용한다.
- 좁은 패널에서는 hero-scale type을 쓰지 않는다.

## 3. Base UI Tokens

일반 앱/DB/News/Archive 화면은 `frontend/src/theme.js`의 `C` 토큰을 우선 사용한다.

| 역할 | 토큰 | 용도 |
| --- | --- | --- |
| Page background | `C.bg` | 앱 전체 배경 |
| Surface | `C.card` | 카드, 패널, 입력 영역 |
| Subtle surface | `C.subtle` | 보조 박스, chips |
| Text primary | `C.t1` | 제목, 핵심 값 |
| Text secondary | `C.t2`, `C.t3` | 본문, 설명 |
| Muted text | `C.t4` | meta, timestamp |
| Border | `C.border`, `C.borderM` | 카드/입력 경계 |

## 4. Domain Themes

`LandingPage`와 `/app` pipeline은 현재 선택된 domain에 따라 배경 이미지와 accent palette가 바뀐다. 구조는 복사하지 않고 동일 UI에 theme token만 바꾼다.

### Smartphone

- Background asset: `frontend/public/smartphone-bg.png`
- Accent: emerald green
- Main accent: `#10b981`
- Accent dark: `#059669`
- Soft background: `rgba(16,185,129,.04)` to `rgba(16,185,129,.09)`
- Use case: smartphone/mobile market research

### Humanoid

- Background asset: `frontend/public/humanoid-bg.png`
- Accent: burgundy/red
- Main accent: `#b73745`
- Accent dark: `#9f2f3b`
- Soft background: `rgba(183,55,69,.045)` to `rgba(183,55,69,.10)`
- Use case: humanoid/robotics market research

### Automotive

- Background asset: `frontend/public/automotive-bg.png`
- Accent: electric blue
- Main accent: `#2563eb`
- Accent dark: `#1d4ed8`
- Soft background: `rgba(37,99,235,.06)` to `rgba(37,99,235,.12)`
- Use case: automotive/EV market research (Build · Market · Shift 3축)

### SmartGlass

- Background asset: `frontend/public/smartglass-bg.png`
- Accent: teal/cyan
- Main accent: `#0891b2`
- Accent light: `#06b6d4`
- Accent lighter: `#67e8f9`
- Soft background: `rgba(8,145,178,.12)`
- bgPos: `100% 40%`
- Use case: smart glasses / AI glass market research (폼팩터·광학계·온디바이스 AI)

### Tablet

- Background asset: `frontend/public/tablet-bg.png`
- Accent: violet/purple
- Main accent: `#7c3aed`
- Accent light: `#8b5cf6`
- Accent lighter: `#c4b5fd`
- Soft background: `rgba(124,58,237,.12)`
- Use case: tablet market research (iPad·Android·폼팩터·엔터프라이즈)

### Macro

- Background asset: `frontend/public/macro-bg.png`
- Accent: amber/gold
- Main accent: `#d97706`
- Accent light: `#f59e0b`
- Accent lighter: `#fcd34d`
- Soft background: `rgba(217,119,6,.12)`
- Use case: macroeconomics research (금리·환율·무역·지정학 분석)

### Theme Rules

- Do not hardcode smartphone green inside shared pipeline components.
- Use `E.em`, `E.emD`, `E.emBg`, `E.emBr`, `E.emSoft`, `E.emSoft2`, `E.sidebarBg`, `E.aura1`, `E.aura2`.
- If adding a new domain, add a theme object and only swap tokens/assets.
- The `/app` flow should feel visually continuous after pressing `Start Research` from the selected domain.

## 5. Landing Page

- First viewport uses a full-bleed image background.
- Main headline and search bar sit in the center, so the background image should keep center visual noise low.
- Primary subjects in background assets should avoid the exact center search area where possible.
- Top right nav buttons remain compact: `Archive`, `News`, `DB`.
- Domain menu is a floating glass menu, not a layout column. It must not create a left gray zone.

## 6. Pipeline Screen

Pipeline views use `PipelineScreen.jsx` theme tokens.

- `gl()` helper is the default glass panel style.
- Step labels, progress, confirm buttons, active sidebar items use `E.em`.
- Sidebar active/done backgrounds use `E.emBg` or `E.emSoft`, not hardcoded green.
- Humanoid should render red/burgundy soft tones throughout the sidebar and progress cards.
- Header logo sits directly on the header background. Do not wrap it in a colored square, border, or glow.

## 7. Surfaces

General cards:

```jsx
{
  background: C.card,
  border: `1px solid ${C.border}`,
  borderRadius: 10,
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
}
```

Pipeline glass panels:

```jsx
gl({ padding: 28 })
```

Do not nest decorative cards inside other decorative cards.

## 8. Buttons

- General primary actions can use `C.ind`.
- Pipeline confirmation/actions use `E.em` and `E.emD`.
- Buttons should have clear command text or familiar icons.
- Dense tool surfaces should avoid oversized button text.

## 9. Lists And References

- Use stable keys: `id`, `url`, `title`, or a combined stable key.
- Article/reference rows should show source, title, date, and optional URL.
- Source badges should use `SOURCE_CONFIG` or `SRC_COLORS`, not one global color.
- Long titles should use ellipsis with `minWidth: 0` on flex/grid children.

## 10. States

Every API-driven area should distinguish:

- `loading`: compact loader or progress text
- `empty`: neutral empty message
- `error`: restrained red error state
- `ready`: actual data

Do not reuse one generic fallback message for all states.

## 11. Copy Rules

- Korean UI text should be short and task-oriented.
- Use concrete dates or generated timestamps where available.
- Avoid hardcoded “최근 30일” if the API provides `days`.
- Do not put lengthy feature explanations directly inside the app UI.

## 12. Auth & Protected Routes

- 인증은 PIN 기반 단일 키 (`VITE_PIN_KEY` — `.env` 루트에 설정).
- `AuthContext`가 localStorage에 세션을 저장하고, `App.jsx`의 `ProtectedRoute`가 미인증 시 `/login`으로 리디렉트.
- **공개**: `/`, `/news`, `/login`
- **보호**: `/app`, `/db`, `/archive`, `/archive/:slug`
- 로그인 화면은 `C` 토큰 기반 흰색/크림 톤 — 큰 로고 + PIN 입력창만. 아이디/비밀번호 없음.
- 새 보호 라우트 추가 시: `App.jsx`에서 `<ProtectedRoute>` 로 감쌀 것.

## 13. Source Color Map

기관별 고정 색상은 `theme.js`의 `SRC_COLOR_MAP`으로 관리한다. `DbPage`의 `normalizeArchive`가 `SRC_COLOR_MAP[a.name]`을 우선 참조하고, 미등록 소스는 `SRC_COLORS` 배열로 폴백.

- **스마트폰 기관** → 초록 계열 shade (Counterpoint #166534 → Morgan Stanley #dcfce7)
- **휴머노이드 기관** → 빨강 계열 shade (The Robot Report #7f1d1d → Unitree #fb7185)

새 소스 추가 시 `SRC_COLOR_MAP`에 항목을 추가한다. 전체 배열 순서에 의존하지 말 것.

## 14. Report Domain Theming

보고서 상세(`ReportPage`) 및 아카이브 목록(`ReportsArchivePage`)은 `domain` 필드로 색상을 자동 전환.

- `domain === "humanoid"` → 빨강 팔레트 (`#ef4444`, `#b91c1c` 계열)
- 그 외 → 초록 팔레트 (`#10b981`, `#047857` 계열)

`server.py`의 `_detect_domain(process_data)`가 `archive_sources`에서 도메인을 추론. 보고서 삭제는 `DELETE /api/reports/{slug}`로 `.md` + `.html` + `_process.json` 일괄 제거.

## 15. Integration Checklist

When adding a new feature:

1. Use `C` from `src/theme.js` for general surfaces.
2. Use domain theme tokens for landing/pipeline domain visuals.
3. Keep page padding around `24-32px` on desktop and `16-20px` on narrow screens.
4. Use 8-12px card radius unless there is an established local exception.
5. Add loading, empty, error, ready states.
6. Check text overflow on mobile and desktop.
7. Run targeted `eslint` and, when relevant, `npm run build`.
