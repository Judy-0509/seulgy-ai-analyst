# Canopy Frontend Design System

이 문서는 다른 기능이나 별도 웹사이트를 현재 앱에 합칠 때 따라야 할 공통 디자인 규칙이다. 목표는 새 화면이 기존 `LandingPage`, `/app`, `/db`, 파이프라인 화면과 같은 제품처럼 보이게 하는 것이다.

## 1. Product Tone

- 리서치/운영 도구이므로 조용하고 정보 밀도가 높은 UI를 우선한다.
- 장식적 카드 남발보다 명확한 섹션, 표, 리스트, 상태 배지를 쓴다.
- 메인 작업 화면은 반복 사용을 전제로 한다. 큰 마케팅 히어로보다 검색, 필터, 진행 상태, 결과 목록을 빠르게 스캔할 수 있어야 한다.
- 브랜드 신호는 `logo-mark.png`와 에메랄드 포인트 컬러로만 절제해서 사용한다.

## 2. Color Tokens

기본 화면은 [src/theme.js](./src/theme.js)의 `C` 토큰을 사용한다.

| 역할 | 토큰 | 값 | 사용처 |
| --- | --- | --- | --- |
| Page background | `C.bg` | `#f7f6f3` | 앱/DB/운영 화면 전체 배경 |
| Surface | `C.card` | `#ffffff` | 카드, 패널, 입력 바 |
| Subtle surface | `C.subtle` | `#f0eff0` | 보조 정보 박스, chips |
| Text primary | `C.t1` | `#0f172a` | 제목, 핵심 값 |
| Text secondary | `C.t2`, `C.t3` | slate 계열 | 본문, 설명 |
| Muted text | `C.t4` | `#94a3b8` | meta, timestamp |
| Border | `C.border`, `C.borderM` | warm gray | 카드/입력 경계 |
| Primary action | `C.ind` | `#4f46e5` | 일반 앱 CTA, 선택 상태 |
| Gate/human action | `C.amb` | `#f59e0b` | 사용자 확인, 경고성 단계 |

파이프라인 화면은 `PipelineScreen.jsx` 내부의 `E` 토큰을 사용한다. 이 화면을 확장할 때는 그 파일의 글래스 토큰을 유지한다.

| 역할 | 토큰 | 사용처 |
| --- | --- | --- |
| Warm background | `E.bg`, `E.bgGrad` | 파이프라인 전체 배경 |
| Glass surface | `E.glass`, `gl()` | 로그 카드, 사이드바 패널 |
| Divider | `E.div` | 헤더 구분선, 패널 내부 라인 |
| Brand accent | `E.em`, `E.emBg`, `E.emBr` | 진행 상태, step label, confirm |

## 3. Typography

- 기본 font stack은 `index.css`의 body font를 따른다.
- 화면 제목: `24px`, `700`, line-height `1.3`.
- 섹션 제목: `12-13px`, `600-700`.
- 카드 제목: `12-14px`, `600-700`, line-height `1.45-1.55`.
- 설명/본문: `12-13px`, line-height `1.6-1.9`.
- 메타/배지: `9-11px`, `600-800`.
- 숫자/쿼리/시간은 `C.mono`를 사용한다.
- letter-spacing 기준값:
  - 일반 본문/UI 텍스트: `0` (기본)
  - 카드 제목 / 섹션 헤더(h2급): `"-.015em"` ~ `"-.02em"`
  - 대형 통계 숫자: `"-.03em"`
  - 섹션 레이블(uppercase 소형): `".10em"` (아래 Section Label 패턴 참조)
  - 좁은 UI에서 과한 hero-scale type을 쓰지 않는다.

## 4. Layout

- 앱 화면 outer는 `height: "100%"`, 내부 스크롤 영역은 명확히 하나만 둔다.
- 기본 페이지 padding은 desktop `24-32px`, 좁은 화면은 `16-20px`.
- 반복 카드 grid는 다음 패턴을 기본으로 한다:

```jsx
gridTemplateColumns: "repeat(auto-fill, minmax(270px, 1fr))"
```

- 2열 정보 패널은 좁은 화면에서 자동 1열이 되도록 한다:

```jsx
gridTemplateColumns: "repeat(auto-fit, minmax(min(430px, 100%), 1fr))"
```

- flex/grid 자식에 긴 텍스트가 있으면 `minWidth: 0`을 반드시 넣는다.
- 긴 제목은 `whiteSpace: "nowrap"`, `overflow: "hidden"`, `textOverflow: "ellipsis"`를 사용한다.

## 5. Surfaces

일반 카드:

```jsx
{
  background: C.card,
  border: `1px solid ${C.border}`,
  borderRadius: 10,
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
}
```

선택/hover 카드:

```jsx
{
  border: `1.5px solid ${active ? C.indBr : C.border}`,
  background: active ? C.indBg : C.card,
  transition: "all 0.15s",
}
```

파이프라인 글래스 패널은 `gl()` helper를 재사용한다. 새 패널을 만들 때 직접 다른 blur/shadow 조합을 만들지 않는다.

## 6. Buttons

Primary CTA:

```jsx
{
  background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "7px 18px",
  fontSize: 13,
  fontWeight: 600,
}
```

Secondary button:

```jsx
{
  background: C.card,
  border: `1px solid ${C.border}`,
  borderRadius: 7,
  color: C.t3,
  padding: "5px 12px",
}
```

Pipeline confirm button uses `E.em` and `E.emD`, not indigo.

## 7. Section Labels

데이터 목록 위의 섹션 구분자는 아래 패턴을 공통으로 사용한다. `/app`과 `/db` 모두 이 스타일을 따른다:

```jsx
{
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: ".10em",
  color: C.t3,
  textTransform: "uppercase",
}
```

파이프라인(`E` 토큰 사용) 안에서는 `E.t4`를 쓰고 나머지는 동일하다.

## 8. Badges And Tags

- Status badges should reuse [src/components/micro/Badge.jsx](./src/components/micro/Badge.jsx).
- Topic/source tags should reuse [src/components/micro/Tag.jsx](./src/components/micro/Tag.jsx) or copy its compact style.
- Badge radius is usually `99` for pill status and `5-6` for compact labels.
- Badge text is `9-10px`, `600-800`, `whiteSpace: "nowrap"`.

**소스 배지 (Source Badge):** 기사 목록에서 출처를 표시할 때는 `C.ind + C.indBg` 조합이 아니라 `SRC_COLORS` 기반의 컬러 배지를 사용한다. 소스별로 고유한 색이 부여되어 빠른 시각 분류가 가능하다:

```jsx
const orgColorMap = Object.fromEntries(archives.map(a => [a.name, a.color]));
// ...
{
  fontSize: 9,
  fontWeight: 800,
  color: "#fff",
  background: orgColorMap[a.org],   // SRC_COLORS 기반
  borderRadius: 4,
  padding: "2px 7px",
  whiteSpace: "nowrap",
  letterSpacing: ".02em",
}
```

## 9. Header And Brand

- Use `frontend/public/logo-mark.png` for the Canopy mark.
- In the `/app` pipeline header, the logo sits directly on the warm white header background. Do not wrap it in a colored square, border, or glow.
- Header height is `64px` in pipeline views.
- Header brand/logo area should stay compact so the topic title remains visible.

## 10. States

Every API-driven surface should distinguish these states:

- `loading`: show "불러오는 중..." or a compact loader.
- `empty`: show a neutral empty message with next action.
- `error`: show a visible but restrained red message.
- `ready`: render data.

Do not use one generic fallback message for all three cases.

## 11. Data Lists

- Do not use array index as React key when rows can reorder or contain local state.
- Prefer stable keys: `id`, `url`, `title`, or a combination like `${source}-${title}`.
- Source lists should use `SOURCE_CONFIG` in `PipelineScreen.jsx` or `SRC_COLORS` from `theme.js`.
- Article rows should show source, title, date, and optional original URL.

## 12. Icons

- Use simple line icons or existing SVG helpers.
- Functional controls should use familiar symbols: back arrow, search, close, check, loader.
- Avoid decorative icons inside dense operational panels.

## 13. Copy Rules

- Korean UI text should be short and task-oriented.
- Avoid explanatory paragraphs inside the app unless it is an empty/error state.
- Use exact dates or generated timestamps where available.
- Avoid hardcoded “최근 30일” when an API supplies `days`.

## 14. Integration Checklist

When adding another website or feature:

1. Import `C` from `src/theme.js` for base UI.
2. Use `logo-mark.png` for brand marks and favicon.
3. Match page padding: `24-32px`, cards `10-12px` radius.
4. Use `C.card`, `C.border`, `C.subtle`, not new random grays.
5. Use `C.ind` for general primary actions, `E.em` only inside pipeline-style flows.
6. Add loading, empty, error, ready states.
7. Use stable React keys.
8. Check narrow widths for text overflow.
9. Run targeted eslint on changed files.
