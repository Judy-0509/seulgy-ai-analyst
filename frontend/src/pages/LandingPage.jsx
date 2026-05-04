import { useState } from "react";
import { useNavigate } from "react-router-dom";

/* ── Dark forest theme tokens ── */
const E = {
  bg:      "#07110b",
  surf:    "rgba(6,20,11,.68)",
  glass:   "rgba(255,255,255,.07)",
  glassH:  "rgba(255,255,255,.12)",
  border:  "rgba(255,255,255,.14)",
  borderL: "rgba(255,255,255,.22)",
  t1: "#ffffff",
  t2: "rgba(255,255,255,.85)",
  t3: "rgba(255,255,255,.72)",
  t4: "rgba(255,255,255,.55)",
  t5: "rgba(255,255,255,.28)",
  em:   "#10b981",
  emL:  "#34d399",
  emLL: "#6ee7b7",
  emBg: "rgba(16,185,129,.12)",
  emBr: "rgba(110,231,183,.28)",
};

const FOREST_BG = "url('/forest.png')";

const WEEKLY_HOT = [
  { title: "메모리 위기에 따른 OEM 가격 전략 및 시장 세분화 구조적 변화", org: "Counterpoint · TrendForce · Omdia" },
  { title: "주요 OEM의 AI 글래스 시장 진출 및 전략적 축 전환",           org: "Omdia · TrendForce"              },
  { title: "스마트폰 위성 통신 표준화 및 시장 보급 가속화",               org: "Counterpoint · Omdia"            },
  { title: "폴더블 형태 요소 혁신 및 자체 칩 개발 경쟁 심화",            org: "Omdia · TrendForce"              },
  { title: "모바일 SoC의 데이터센터 · AI 인프라 시장 확장 전략",         org: "Counterpoint · TrendForce"       },
];

const WEEKLY_NEW = [
  { title: "애플 중국 Q1 출하 +20% · 분기 역대 최고 매출 기록",  org: "Counterpoint Research", days: "3일 전" },
  { title: "구글 픽셀 9a, 일본 시장에서 삼성 제치고 2위 등극",   org: "Counterpoint Research", days: "4일 전" },
  { title: "삼성 DS 영업이익률 65.7% — NVIDIA 추월·파업 리스크", org: "TrendForce",            days: "3일 전" },
];

const EXAMPLES = [
  "메모리 위기와 스마트폰 OEM 가격 전략 2026",
  "AI 글래스 시장 OEM 진출 전략",
  "스마트폰 위성 통신 표준화 2030",
];

/* ── Line icons ── */
function SearchIcon() {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" fill="none"
      stroke="rgba(255,255,255,.55)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>
    </svg>
  );
}
function ArrowRightIcon() {
  return (
    <svg width={17} height={17} viewBox="0 0 24 24" fill="none"
      stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14"/><path d="m13 5 7 7-7 7"/>
    </svg>
  );
}
function SparklesIcon({ color = "#fff" }) {
  return (
    <svg width={17} height={17} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 9.8 8.8 4 11l5.8 2.2L12 19l2.2-5.8L20 11l-5.8-2.2L12 3Z"/>
      <path d="M5 3v3M3 5h3M19 18v3M17 20h4"/>
    </svg>
  );
}

/* ── Topic row ── */
function TopicRow({ item, right, onStart, index }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onClick={() => onStart(item.title)}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
        borderRadius: 14, padding: "12px 16px", cursor: "pointer",
        background: hov ? "rgba(52,211,153,.08)" : "transparent", transition: "background .15s" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, overflow: "hidden", flex: 1, minWidth: 0 }}>
        {index !== undefined ? (
          <span style={{
            fontSize: 40, fontWeight: 900, lineHeight: 1, flexShrink: 0,
            letterSpacing: "-0.05em", width: 28, textAlign: "right",
            color: hov ? E.emLL : "rgba(255,255,255,.18)",
            transition: "color .15s",
          }}>
            {index + 1}
          </span>
        ) : (
          <div style={{ width: 5, height: 34, borderRadius: 99, flexShrink: 0, transition: "background .15s",
            background: hov ? E.emLL : "rgba(255,255,255,.22)" }} />
        )}
        <div style={{ minWidth: 0 }}>
          <p style={{ fontSize: 16, fontWeight: 600, margin: "0 0 4px",
            color: hov ? E.emLL : E.t1, transition: "color .15s",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {item.title}
          </p>
          <p style={{ fontSize: 12, color: E.t4, margin: 0 }}>{item.org}</p>
        </div>
      </div>

      {right && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: 12, flexShrink: 0 }}>
          <span style={{ fontSize: 9, fontWeight: 700, color: E.emLL, background: E.emBg,
            borderRadius: 99, padding: "3px 10px", border: `1px solid ${E.emBr}` }}>NEW</span>
          <span style={{ fontSize: 10, color: E.t5, whiteSpace: "nowrap" }}>{item.days}</span>
        </div>
      )}
    </div>
  );
}

/* ── Main ── */
export default function LandingPage() {
  const nav = useNavigate();
  const [val, setVal] = useState("");

  const handleStart = (topic) => {
    const t = topic.trim() || "아마존 글로벌스타 인수와 D2D 위성 통신";
    nav("/app", { state: { startTopic: t } });
  };

  return (
    /* Outer: clips the oversized forest-pan div */
    <div style={{ height: "100%", overflow: "hidden", background: E.bg, position: "relative" }}>

      {/* ── Background layers ── */}
      <div className="forest-pan" style={{ backgroundImage: FOREST_BG }} />
      {/* radial vignette */}
      <div style={{ position: "absolute", inset: 0, zIndex: 1, pointerEvents: "none",
        background: "radial-gradient(circle at center, rgba(12,58,36,.1) 0%, rgba(4,17,9,.42) 42%, rgba(2,8,4,.88) 100%)" }} />
      {/* top-bottom gradient */}
      <div style={{ position: "absolute", inset: 0, zIndex: 2, pointerEvents: "none",
        background: "linear-gradient(to bottom, rgba(0,0,0,.2) 0%, transparent 35%, rgba(0,0,0,.55) 100%)" }} />

      {/* ── Scrollable content ── */}
      <div style={{ position: "relative", zIndex: 3, height: "100%", overflowY: "auto", overflowX: "hidden" }}>

        {/* ── Hero section ── */}
        <section style={{ maxWidth: 1320, margin: "0 auto", display: "flex", flexDirection: "column",
          alignItems: "center", padding: "52px 32px 0", textAlign: "center" }}>

          {/* Headline */}
          <h1 style={{ fontSize: 80, fontWeight: 900, color: E.t1, letterSpacing: "-0.06em",
            lineHeight: 0.98, marginBottom: 28, textShadow: "0 4px 32px rgba(0,0,0,.5)",
            animation: "fadeUp .5s ease .06s both" }}>
            Deep research.<br/>Clear insights.
          </h1>

          {/* Search bar */}
          <div style={{ width: "100%", maxWidth: 900, borderRadius: 28,
            border: `1px solid ${E.borderL}`, background: "rgba(255,255,255,.08)",
            padding: 8, boxShadow: "0 8px 48px rgba(0,0,0,.45)",
            backdropFilter: "blur(20px)", marginBottom: 20,
            animation: "fadeUp .5s ease .14s both" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 8px" }}>
              <SearchIcon />
              <input
                value={val}
                onChange={e => setVal(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleStart(val)}
                placeholder="분석할 주제를 입력하세요 — 예: 아마존 글로벌스타 인수와 D2D 위성 통신"
                style={{ flex: 1, height: 56, background: "transparent", border: "none",
                  outline: "none", fontSize: 15, fontWeight: 500, color: E.t1,
                  caretColor: E.emL }}
              />
              <button onClick={() => handleStart(val)}
                style={{ display: "flex", alignItems: "center", gap: 8,
                  height: 50, background: E.em, border: "none", borderRadius: 20,
                  padding: "0 30px", fontSize: 14, fontWeight: 700, color: "#fff",
                  cursor: "pointer", boxShadow: "0 4px 20px rgba(16,185,129,.4)",
                  whiteSpace: "nowrap", flexShrink: 0, transition: "background .15s" }}
                onMouseEnter={e => e.currentTarget.style.background = E.emL}
                onMouseLeave={e => e.currentTarget.style.background = E.em}>
                Start Research <ArrowRightIcon />
              </button>
            </div>
          </div>

          {/* Example chips */}
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center",
            marginBottom: 44, animation: "fadeUp .5s ease .18s both" }}>
            <span style={{ fontSize: 13, color: E.t4, fontWeight: 600, alignSelf: "center" }}>Try:</span>
            {EXAMPLES.map(ex => (
              <button key={ex} onClick={() => handleStart(ex)}
                style={{ borderRadius: 99, border: `1px solid ${E.border}`,
                  background: "rgba(255,255,255,.06)", padding: "8px 20px",
                  fontSize: 13, color: E.t3, cursor: "pointer",
                  backdropFilter: "blur(8px)", transition: "background .15s" }}
                onMouseEnter={e => e.currentTarget.style.background = E.glassH}
                onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,.06)"}>
                {ex}
              </button>
            ))}
          </div>
        </section>

        {/* ── Topic sections ── */}
        <section style={{ maxWidth: 1320, margin: "0 auto", padding: "0 48px 64px" }}>
          <div style={{ borderRadius: 32, border: `1px solid ${E.border}`,
            background: E.surf, padding: "28px 32px 20px",
            boxShadow: "0 8px 48px rgba(0,0,0,.45)", backdropFilter: "blur(24px)",
            display: "grid", gridTemplateColumns: "1fr 1fr", gap: 40 }}>

            {/* Hot */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 800, color: E.t1, margin: "0 0 4px", letterSpacing: "-0.02em" }}>이번 주 핵심 주제</h2>
                  <p style={{ fontSize: 11, color: E.t4, margin: 0 }}>2026년 5월 3일 기준 · Omdia · Counterpoint · IDC</p>
                </div>
              </div>
              <div>
                {WEEKLY_HOT.map((item, i) => (
                  <TopicRow key={i} item={item} onStart={handleStart} index={i} />
                ))}
              </div>
            </div>

            {/* Divider */}
            <div style={{ position: "relative" }}>
              <div style={{ position: "absolute", left: -14, top: 0, bottom: 0,
                width: 1, background: E.border }} />
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 800, color: E.t1, margin: "0 0 4px", letterSpacing: "-0.02em" }}>이번 주 새롭게 등장한 주제</h2>
                  <p style={{ fontSize: 11, color: E.t4, margin: 0 }}>최근 7일 내 신규 등장 · 자동 감지</p>
                </div>
              </div>
              <div>
                {WEEKLY_NEW.map((item, i) => (
                  <TopicRow key={i} item={item} right onStart={handleStart} index={i} />
                ))}
              </div>
            </div>

          </div>
        </section>

      </div>{/* end scrollable */}
    </div>
  );
}
