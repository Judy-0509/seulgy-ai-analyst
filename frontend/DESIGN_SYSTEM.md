# Seulgy Frontend Design System

이 문서는 Seulgy 프론트엔드에 기능을 추가할 때 유지해야 하는 공통 디자인 규칙이다. 목표는 `LandingPage`, `/app`, `/archive`, `/db`, `/news`, `/keywords`가 하나의 제품처럼 보이게 하는 것이다.

> 내부 코드네임은 한때 "Canopy"였다. 사용자에게 보이는 브랜드·문서 명칭은 모두 **Seulgy**로 통일한다. 단, `localStorage` 키(`canopy_auth`, `canopy_domain`)는 기존 세션·도메인 상태 호환을 위해 레거시 접두사를 의도적으로 유지한다.

## 1. Product Tone

- 리서치/운영 도구처럼 조용하고 정보 밀도가 높은 UI를 우선한다.
- 마케팅 랜딩 페이지처럼 장식적인 카드나 과한 설명을 늘리지 않는다.
- 반복 사용 화면은 빠른 스캔, 명확한 상태, 안정적인 리스트 배치를 우선한다.
- 보고서 상세(`ReportPage`)는 예외적으로 "프리미엄 에디토리얼" 톤 — 읽는 문서로서의 격(타이포 위계·여백·헤어라인)을 우선한다.

## 2. Brand & Logo

브랜드 마크는 더 이상 이미지(나무 캐노피)가 아니라 **워드마크**다.

### Wordmark
- 컴포넌트: `frontend/src/components/Wordmark.jsx`.
- 글자체: **Cabinet Grotesk** Extrabold(800), 자간 `-0.02em`, 텍스트 `"Seulgy"`.
- props: `size`(기본 22), `color`, `text`, `weight`, `style`.
- 헤더·로그인 등 기존 `<img src="/logo-mark.png">` 자리를 모두 이 컴포넌트로 대체했다. 새 화면에 로고가 필요하면 이미지가 아니라 `<Wordmark />`를 쓴다.

### Logo color policy (도메인색 연동)
- **도메인 맥락이 있는 화면**은 로고에 도메인 accent를 적용한다.
  - `ReportPage`: `color={R.emD}` → automotive 파랑 / humanoid 빨강 / smartphone 초록.
  - `PipelineScreen`: `color={E.emD}` → 파이프라인 도메인 테마색.
- **중립·교차 도메인 화면**(Login, News, DB, Archive)은 브랜드 forest green `#065f46`(`Wordmark` 기본값)을 유지한다.
- 한마디로: *도메인이 명확하면 도메인색, 아니면 브랜드 초록.*

### Favicon
- `frontend/public/favicon.svg` — **Cabinet Grotesk "S"**(실제 woff2를 SVG에 임베드, 폴백은 굵은 grotesk), 투명 배경 + 브랜드 초록 `#065f46`.
- `index.html`의 favicon은 이 SVG를 가리킨다. 과거의 나무 마크(`logo-mark.png`)는 브라우저 탭/헤더에서 제거했고, 레거시 에셋으로만 보관한다.

## 3. Typography

3개 패밀리로 역할을 분리한다. 본문/UI 기본 letter spacing은 `0`.

| 역할 | 폰트 | 사용처 |
| --- | --- | --- |
| **Brand / Label** | Cabinet Grotesk | Seulgy 워드마크, favicon S, 대문자 eyebrow·kicker·라벨, 랜딩 히어로 헤드라인(800), 랜딩·보고서 nav 영문 |
| **Editorial Serif (명조)** | Gowun Batang | 보고서 헤드라인·제목·핵심요약 리드·섹션 제목/deck·시사점 번호·참고 제목 |
| **Body / UI** | Pretendard | 기본 본문, 보고서 narrative, 모든 UI 컨트롤 |
| Latin fallback | Inter | 라틴 보조 |

- 폰트 로드는 `index.css` 상단 `@import` 규칙을 따른다.
  - Cabinet Grotesk: Fontshare (`cabinet-grotesk@700,800`).
  - Gowun Batang: Google Fonts (`Gowun+Batang:wght@400;700`).
  - Pretendard / Inter: 기존 CDN.
- 한글+라틴 혼용 헤드라인은 스택 `'Gowun Batang','Nanum Myeongjo',Georgia,serif`로 한글은 명조, 라틴은 동일 패밀리가 받는다.
- Gowun Batang은 400/700만 존재한다. 명조에 `font-weight:500`을 쓰면 400으로 자연 폴백되며, 이는 의도된 동작이다.
- 화면 제목(일반 UI)은 `24px`, `700` 전후. 카드/리스트 제목은 `12-16px`, `500-700`. 메타/timestamp는 `9-12px` muted.
- 좁은 패널에서는 hero-scale type을 쓰지 않는다.

## 4. Base UI Tokens

일반 앱/DB/News/Archive/Keywords 화면은 `frontend/src/theme.js`의 `C` 토큰을 우선 사용한다.

| 역할 | 토큰 | 용도 |
| --- | --- | --- |
| Page background | `C.bg` | 앱 전체 배경 |
| Surface | `C.card` | 카드, 패널, 입력 영역 |
| Subtle surface | `C.subtle` | 보조 박스, chips |
| Text primary | `C.t1` | 제목, 핵심 값 |
| Text secondary | `C.t2`, `C.t3` | 본문, 설명 |
| Muted text | `C.t4` | meta, timestamp |
| Border | `C.border`, `C.borderM` | 카드/입력 경계 |

## 5. Domain Themes

`LandingPage`와 `/app` pipeline은 현재 선택된 domain에 따라 배경 이미지와 accent palette가 바뀐다. 구조는 복사하지 않고 동일 UI에 theme token만 바꾼다.

### Smartphone
- Background asset: `frontend/public/smartphone-bg-v3-desktop.webp`
- Accent: emerald green / Main `#10b981` / Dark `#059669`
- Use case: smartphone/mobile market research

### Humanoid
- Background asset: `frontend/public/humanoid-bg-v2-desktop.webp`
- Accent: burgundy/red / Main `#b73745` / Dark `#9f2f3b`
- Use case: humanoid/robotics market research

### Automotive
- Background asset: `frontend/public/automotive-bg-v2-desktop.webp`
- Accent: electric blue / Main `#2563eb` / Dark `#1d4ed8`
- Use case: automotive/EV market research (Build · Market · Shift 3축)

### SmartGlass
- Background asset: `frontend/public/smartglass-bg.png`
- Accent: teal/cyan / Main `#0891b2` / Light `#06b6d4` / Lighter `#67e8f9`
- bgPos: `100% 40%` / Use case: smart glasses / AI glass

### Tablet
- Background asset: `frontend/public/tablet-bg.png`
- Accent: violet/purple / Main `#7c3aed` / Light `#8b5cf6` / Lighter `#c4b5fd`
- Use case: tablet market research

### Macro
- Background asset: `frontend/public/macro-bg.png`
- Accent: amber/gold / Main `#d97706` / Light `#f59e0b` / Lighter `#fcd34d`
- Use case: macroeconomics research

### Theme Rules
- Do not hardcode smartphone green inside shared pipeline components.
- Use `E.em`, `E.emD`, `E.emBg`, `E.emBr`, `E.emSoft`, `E.emSoft2`, `E.sidebarBg`, `E.aura1`, `E.aura2`.
- If adding a new domain, add a theme object and only swap tokens/assets.
- The `/app` flow should feel visually continuous after pressing `Start Research` from the selected domain.

## 6. Landing Page

- First viewport uses a full-bleed image background.
- 히어로 헤드라인(`Deep research. / {domain} insights.`)과 상단 nav 영문 라벨은 **Cabinet Grotesk**를 쓴다(브랜드 워드마크와 통일). 헤드라인은 800/자간 `-0.045em`.
- Main headline and search bar sit in the center, so the background image should keep center visual noise low.
- Top right nav buttons remain compact: `Archive`, `News`, `DB` 등.
- Domain menu is a floating glass menu, not a layout column. It must not create a left gray zone.

## 7. Pipeline Screen

Pipeline views use `PipelineScreen.jsx` theme tokens.

- `gl()` helper is the default glass panel style.
- Step labels, progress, confirm buttons, active sidebar items use `E.em`.
- Sidebar active/done backgrounds use `E.emBg` or `E.emSoft`, not hardcoded green.
- Humanoid should render red/burgundy soft tones throughout.
- Header logo는 워드마크(`<Wordmark color={E.emD} />`)를 헤더 배경 위에 직접 둔다. 색 박스/테두리/글로로 감싸지 않는다.

## 8. Report Editorial Layout (`ReportPage`)

보고서 상세는 프리미엄 에디토리얼 규칙을 따른다. 토큰은 파일 내부 `BASE_R`/`makeR(domain)`.

### Tokens
- 표면: `bg #f6f4ef`, `paper #fffefb`(본문 article), `border rgba(42,40,38,.10)`, `hair rgba(42,40,38,.13)`(에디토리얼 구분선).
- 텍스트: `t1 #211f1d`, `t2 #46433f`, `t3 #6f6c68`, `t4 #9a9793`.
- 도메인 accent: `em`/`emD`/`emBg`/`emBr` (automotive 파랑 / humanoid 빨강 / smartphone 초록).
- 글꼴 상수: `SERIF`(Gowun Batang 스택), `LABEL`(Cabinet Grotesk 스택).

### Layout
- 2단 그리드: 본문 `minmax(0,1fr)` + 사이드바 `332px`, gap `46`, maxWidth `1240`.
- 본문 article: `paper` 표면, padding `52px 60px 48px`, radius `18`.

### Composition (위→아래)
- **Masthead**: accent 짧은 룰 + Cabinet Grotesk eyebrow(`Executive Report · {Domain}`) → Gowun Batang 제목(38px/700) → 메타(run_ts · N개 섹션 · 참고 N건) + 헤어라인.
- **Executive summary**: 좌측 `2px` accent 세로룰 + `핵심 요약` kicker + Gowun Batang 18.5px 리드(스탠드퍼스트). 박스 채움이 아니라 룰형.
- **Section**: 상단 헤어라인 → `Section NN` kicker → Gowun Batang 25px 제목 → 명조 17px deck(headline) → Pretendard 본문(line-height 1.95, 측정폭 `68ch`) → `상세 수치` 접이식(불릿 마커 `—`).
- **Market Insights**: 헤어라인 구분 리스트, 큰 명조 번호 + 명조 소제목 + Pretendard 본문.
- **Sidebar(참고 수치)**: 헤어라인 행, Cabinet Grotesk 스몰캡 소스 라벨(소스 도메인별 색), 명조 제목, metric pill.

### Rules
- 모든 필드는 **조건부 가드**로 렌더한다(`executive_summary`, 섹션 `headline`/`narrative`/`bullets`, `insights`, `metrics`, `run_ts` 등은 모두 optional). sparse 보고서가 깨지지 않게 한다.
- 본문(narrative)은 Pretendard 고딕, 헤드라인류만 Gowun Batang 명조 — 명조/고딕 역할 분리를 유지한다.
- 인라인 style만으로 안 되는 효과(`:hover`, 가상요소)는 `LoginPage`처럼 주입 `<style>` 블록으로 처리한다(`.rpt-ref:hover`, `.rpt-navlink:hover`).
- **정적 HTML로 내보낼 때 주의**: `style="..."`(쌍따옴표) 속성 안 `font-family`의 폰트명은 **홑따옴표**로 적는다. 쌍따옴표를 중첩하면 속성이 끊겨 폰트가 통째로 무효화된다.

## 9. Surfaces

General cards:

```jsx
{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }
```

Pipeline glass panels: `gl({ padding: 28 })`. Do not nest decorative cards inside other decorative cards.

## 10. Buttons

- General primary actions can use `C.ind`.
- Pipeline confirmation/actions use `E.em` and `E.emD`.
- Buttons should have clear command text or familiar icons.
- Dense tool surfaces should avoid oversized button text.

## 11. Lists And References

- Use stable keys: `id`, `url`, `title`, or a combined stable key.
- Article/reference rows should show source, title, date, and optional URL.
- Source badges should use `SOURCE_CONFIG` or `SRC_COLORS` / `SRC_COLOR_MAP`, not one global color.
- Long titles should use ellipsis with `minWidth: 0` on flex/grid children.

## 12. States

Every API-driven area should distinguish `loading` / `empty` / `error` / `ready`. Do not reuse one generic fallback message for all states.

## 13. Copy Rules

- Korean UI text should be short and task-oriented.
- Use concrete dates or generated timestamps where available.
- Avoid hardcoded "최근 30일" if the API provides `days`.
- Do not put lengthy feature explanations directly inside the app UI.

## 14. Auth & Protected Routes

- 인증은 Supabase Google OAuth (`VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — 루트 `.env`).
- `AuthContext`가 Supabase 세션을 구독하고 역할(member/team/admin)을 제공. `App.jsx`의 `MemberRoute` / `TeamRoute` / `AdminRoute`가 권한 미달 시 `/login` 또는 홈으로 리디렉트.
- **공개**: `/`, `/news`, `/login` / **member**: `/archive/:slug`, `/feedback` / **team**: `/db`, `/keywords` / **admin**: `/app`, `/usage`
- 로그인 화면은 `C` 토큰 기반 흰색/크림 톤 — 큰 `<Wordmark size={42} />` + Google 로그인 버튼.
- 새 보호 라우트 추가 시 `App.jsx`에서 역할에 맞는 라우트 래퍼(`MemberRoute`/`TeamRoute`/`AdminRoute`)로 감쌀 것.

## 15. Source Color Map

기관별 고정 색상은 `theme.js`의 `SRC_COLOR_MAP`으로 관리한다. `DbPage`의 `normalizeArchive`가 `SRC_COLOR_MAP[a.name]`을 우선 참조하고, 미등록 소스는 `SRC_COLORS` 배열로 폴백.

- 스마트폰 기관 → 초록 계열 shade / 휴머노이드 기관 → 빨강 계열 shade / 자동차 기관 → 파랑 계열 shade.
- 새 소스 추가 시 `SRC_COLOR_MAP`에 항목을 추가한다. 전체 배열 순서에 의존하지 말 것.

## 16. Report Domain Theming

보고서 상세(`ReportPage`) 및 아카이브 목록(`ReportsArchivePage`)은 `domain` 필드로 색상을 자동 전환.

- `humanoid` → 빨강(`#ef4444`/`#b91c1c`), `automotive` → 파랑(`#2563eb`/`#1d4ed8`), 그 외 → 초록(`#047857`/`#065f46`).
- 로고 색도 동일 도메인 accent를 따른다(§2 Logo color policy).
- `server.py`의 `_detect_domain(process_data)`가 `archive_sources`에서 도메인을 추론. 보고서 삭제는 `DELETE /api/reports/{slug}`.

## 17. Integration Checklist

When adding a new feature:

1. 일반 표면은 `src/theme.js`의 `C`, 도메인 비주얼은 도메인 theme 토큰.
2. 로고는 `<Wordmark />`(이미지 금지). 도메인 화면이면 `color`에 도메인 accent를, 중립 화면이면 기본 초록을 유지.
3. 타이포는 §3 역할 분리를 따른다(Cabinet Grotesk 라벨 / Gowun Batang 명조 헤드라인 / Pretendard 본문).
4. Page padding `24-32px`(desktop) / `16-20px`(narrow). 카드 radius `8-18px`.
5. loading / empty / error / ready 상태 분리.
6. 모바일·데스크톱 text overflow 확인.
7. 변경 파일에 targeted `eslint`, 필요 시 `npm run build`.
