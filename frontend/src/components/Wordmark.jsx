// Seulgy 브랜드 워드마크 — Cabinet Grotesk Extrabold.
// 로고는 도메인과 무관하게 항상 forest green 브랜드 컬러를 유지한다.
// 헤더/로그인 등에서 기존 <img src="/logo-mark.png" /> 자리를 대체.
// favicon·앱 아이콘은 계속 tree 심볼(logo-mark.png)을 사용.

const BRAND_GREEN = "#065f46";

export default function Wordmark({
  size = 22,
  color = BRAND_GREEN,
  text = "Seulgy",
  weight = 800,
  style = {},
  ...rest
}) {
  return (
    <span
      role="img"
      aria-label={text}
      style={{
        fontFamily: '"Cabinet Grotesk", "Pretendard Variable", Pretendard, sans-serif',
        fontWeight: weight,
        fontSize: size,
        letterSpacing: "-0.02em",
        lineHeight: 1,
        color,
        userSelect: "none",
        whiteSpace: "nowrap",
        ...style,
      }}
      {...rest}
    >
      {text}
    </span>
  );
}
