import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useDomain } from "../contexts/DomainContext";
import { useAuth } from "../contexts/AuthContext";

/* ── Dark forest theme tokens ── */
const THEMES = {
  smartphone: {
    bg: "#07110b",
    surf: "rgba(6,20,11,.68)",
    glassH: "rgba(255,255,255,.12)",
    border: "rgba(255,255,255,.14)",
    borderL: "rgba(255,255,255,.22)",
    t1: "#ffffff",
    t3: "rgba(255,255,255,.72)",
    t4: "rgba(255,255,255,.55)",
    t5: "rgba(255,255,255,.28)",
    em: "#10b981",
    emL: "#34d399",
    emLL: "#6ee7b7",
    emBg: "rgba(16,185,129,.12)",
    emBr: "rgba(110,231,183,.28)",
    navBg: "rgba(6,20,11,.52)",
    hoverBg: "rgba(16,185,129,.16)",
    rowBg: "rgba(52,211,153,.06)",
    rowBgStrong: "rgba(16,185,129,.22)",
    vignette: "radial-gradient(circle at center, rgba(12,58,36,.1) 0%, rgba(4,17,9,.42) 42%, rgba(2,8,4,.88) 100%)",
    image: "url('/smartphone-bg-v2.png')",
    bgPos: "30% 70%",
  },
  humanoid: {
    bg: "#110607",
    surf: "rgba(22,8,10,.70)",
    glassH: "rgba(255,255,255,.12)",
    border: "rgba(255,255,255,.14)",
    borderL: "rgba(255,255,255,.22)",
    t1: "#ffffff",
    t3: "rgba(255,255,255,.72)",
    t4: "rgba(255,255,255,.55)",
    t5: "rgba(255,255,255,.28)",
    em: "#b73745",
    emL: "#e75d6e",
    emLL: "#ffa0a9",
    emBg: "rgba(183,55,69,.15)",
    emBr: "rgba(255,160,169,.32)",
    navBg: "rgba(22,8,10,.52)",
    hoverBg: "rgba(183,55,69,.16)",
    rowBg: "rgba(183,55,69,.08)",
    rowBgStrong: "rgba(183,55,69,.22)",
    vignette: "radial-gradient(circle at 48% 42%, rgba(150,34,45,.13) 0%, rgba(28,8,10,.46) 44%, rgba(7,3,4,.91) 100%)",
    image: "url('/humanoid-bg.png')",
    bgPos: "center",
  },
  automotive: {
    bg: "#050c1a",
    surf: "rgba(5,14,31,.70)",
    glassH: "rgba(255,255,255,.12)",
    border: "rgba(255,255,255,.14)",
    borderL: "rgba(255,255,255,.22)",
    t1: "#ffffff",
    t3: "rgba(255,255,255,.72)",
    t4: "rgba(255,255,255,.55)",
    t5: "rgba(255,255,255,.28)",
    em: "#2563eb",
    emL: "#3b82f6",
    emLL: "#93c5fd",
    emBg: "rgba(37,99,235,.12)",
    emBr: "rgba(147,197,253,.28)",
    navBg: "rgba(5,14,31,.52)",
    hoverBg: "rgba(37,99,235,.16)",
    rowBg: "rgba(59,130,246,.06)",
    rowBgStrong: "rgba(37,99,235,.22)",
    vignette: "radial-gradient(circle at 50% 46%, rgba(5,18,55,.08) 0%, rgba(3,10,36,.46) 42%, rgba(1,4,16,.93) 100%)",
    image: "url('/automotive-bg.png')",
    bgPos: "center",
  },
  smartglass: {
    bg: "#020c10",
    surf: "rgba(2,12,16,.68)",
    glassH: "rgba(255,255,255,.12)",
    border: "rgba(255,255,255,.14)",
    borderL: "rgba(255,255,255,.22)",
    t1: "#ffffff",
    t3: "rgba(255,255,255,.72)",
    t4: "rgba(255,255,255,.55)",
    t5: "rgba(255,255,255,.28)",
    em: "#0891b2",
    emL: "#06b6d4",
    emLL: "#67e8f9",
    emBg: "rgba(8,145,178,.12)",
    emBr: "rgba(103,232,249,.28)",
    navBg: "rgba(2,12,16,.52)",
    hoverBg: "rgba(8,145,178,.16)",
    rowBg: "rgba(6,182,212,.06)",
    rowBgStrong: "rgba(8,145,178,.22)",
    vignette: "radial-gradient(circle at 50% 45%, rgba(4,60,80,.1) 0%, rgba(2,12,16,.46) 44%, rgba(1,5,8,.91) 100%)",
    image: "url('/smartglass-bg.png')",
    bgPos: "100% 40%",
  },
  tablet: {
    bg: "#0d0818",
    surf: "rgba(13,8,24,.68)",
    glassH: "rgba(255,255,255,.12)",
    border: "rgba(255,255,255,.14)",
    borderL: "rgba(255,255,255,.22)",
    t1: "#ffffff",
    t3: "rgba(255,255,255,.72)",
    t4: "rgba(255,255,255,.55)",
    t5: "rgba(255,255,255,.28)",
    em: "#7c3aed",
    emL: "#8b5cf6",
    emLL: "#c4b5fd",
    emBg: "rgba(124,58,237,.12)",
    emBr: "rgba(196,181,253,.28)",
    navBg: "rgba(13,8,24,.52)",
    hoverBg: "rgba(124,58,237,.16)",
    rowBg: "rgba(139,92,246,.06)",
    rowBgStrong: "rgba(124,58,237,.22)",
    vignette: "radial-gradient(circle at 50% 45%, rgba(60,20,120,.1) 0%, rgba(13,8,24,.46) 44%, rgba(5,3,12,.91) 100%)",
    image: "url('/tablet-bg.png')",
    bgPos: "center",
  },
  space_datacenter: {
    bg: "#050706",
    surf: "rgba(10,18,15,.72)",
    glassH: "rgba(255,255,255,.12)",
    border: "rgba(216,243,220,.18)",
    borderL: "rgba(216,243,220,.30)",
    t1: "#ffffff",
    t3: "rgba(255,255,255,.72)",
    t4: "rgba(255,255,255,.55)",
    t5: "rgba(255,255,255,.30)",
    em: "#22d3a6",
    emL: "#5eeac5",
    emLL: "#d8f3dc",
    emBg: "rgba(34,211,166,.12)",
    emBr: "rgba(216,243,220,.28)",
    navBg: "rgba(10,18,15,.52)",
    hoverBg: "rgba(34,211,166,.16)",
    rowBg: "rgba(34,211,166,.06)",
    rowBgStrong: "rgba(34,211,166,.20)",
    vignette: "linear-gradient(90deg, rgba(2,6,5,.92) 0%, rgba(2,6,5,.72) 38%, rgba(2,6,5,.20) 68%, rgba(2,6,5,.52) 100%), radial-gradient(circle at 28% 46%, rgba(34,211,166,.14) 0%, rgba(2,6,5,.32) 42%, rgba(2,6,5,.88) 100%)",
    image: "url('/space-datacenter-bg.png')",
    bgPos: "64% 48%",
  },
  macro: {
    bg: "#1a0f02",
    surf: "rgba(26,15,2,.68)",
    glassH: "rgba(255,255,255,.12)",
    border: "rgba(255,255,255,.14)",
    borderL: "rgba(255,255,255,.22)",
    t1: "#ffffff",
    t3: "rgba(255,255,255,.72)",
    t4: "rgba(255,255,255,.55)",
    t5: "rgba(255,255,255,.28)",
    em: "#d97706",
    emL: "#f59e0b",
    emLL: "#fcd34d",
    emBg: "rgba(217,119,6,.12)",
    emBr: "rgba(252,211,77,.28)",
    navBg: "rgba(26,15,2,.52)",
    hoverBg: "rgba(245,158,11,.16)",
    rowBg: "rgba(245,158,11,.06)",
    rowBgStrong: "rgba(217,119,6,.22)",
    vignette: "radial-gradient(circle at 50% 45%, rgba(100,60,5,.1) 0%, rgba(26,15,2,.46) 44%, rgba(10,5,1,.91) 100%)",
    image: "url('/macro-bg.png')",
    bgPos: "60% 40%",
  },
};

function critKey(criteria = "") {
  if (criteria.includes("2") && criteria.includes("3")) return "both";
  if (criteria.includes("2")) return "hot";
  return "new";
}

function uniqueSourceCount(t) {
  return new Set((t.articles || []).map(a => a.source).filter(Boolean)).size;
}

function isCoreTopic(t) {
  // Topics from the 7-day emerging file are tagged source="emerging" by the server
  return t.source !== "emerging";
}

function toRow(t) {
  const sources = [...new Set((t.articles || []).map(a => a.source))];
  const org = sources.join(" · ");
  const dates = (t.articles || []).map(a => a.date).filter(Boolean).sort().reverse();
  const displayDate = dates[0] || "";
  let daysAgo = "";
  if (dates[0]) {
    const diff = Math.floor((Date.now() - new Date(dates[0]).getTime()) / 86400000);
    daysAgo = diff === 0 ? "오늘" : `${diff}일 전`;
  }
  return {
    title: t.title, org, days: daysAgo,
    displayDate,
    report_slug: t.report_slug || "",
    rationale: t.rationale || "",
    key_data: t.key_data || [],
    trend: t.trend || null,
    rank: t.rank ?? null,
    rank_change: t.rank_change !== undefined ? t.rank_change : undefined,
    articles: (t.articles || []).map(a => ({
      date: a.date, source: a.source, title: a.title, url: a.url || "",
    })),
    week_of: t.week_of || "",
  };
}

const TREND_LABELS = {
  Rising: "상승",
  New: "신규",
  Sustained: "유지",
  Stable: "유지",
  Cooling: "하락",
};

const DOMAIN_EXAMPLES = {
  smartphone: [
    "메모리 가격 급등과 스마트폰 OEM 가격 전략 2026",
    "AI 글래스 시장 확대와 스마트폰 OEM 진출 전략",
  ],
  humanoid: [
    "휴머노이드 AI 에이전트 로드맵과 소비자 수용도 격차",
    "휴머노이드 양산 전환과 액추에이터 공급망 재편",
  ],
  automotive: [
    "글로벌 EV 배터리 공급망 재편과 OEM 원가 전략 2026",
    "중국 OEM의 유럽 시장 진입 가속화와 관세 대응 전략",
  ],
  smartglass: [
    "AI 글래스 시장 확대와 스마트폰 OEM 진출 전략",
    "메타 레이밴 이후 스마트글래스 폼팩터 경쟁 구도",
  ],
  tablet: [
    "iPad Pro M4 출시 이후 태블릿 시장 점유율 재편",
    "안드로이드 태블릿 생태계 확장과 OEM 전략 변화",
  ],
  space_datacenter: [
    "저궤도 데이터센터 전력 냉각 경제성",
    "위성 간 광링크 기반 데이터 라우팅 전략",
  ],
  macro: [
    "미-중 관세 전쟁 장기화와 글로벌 공급망 재편",
    "연준 금리 동결과 인플레이션 구조화 리스크",
  ],
};

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
}

function topicWindowLabel(generatedAt, days) {
  const end = generatedAt ? new Date(generatedAt) : new Date();
  if (Number.isNaN(end.getTime())) return "";
  const span = Number(days) || 30;
  const start = new Date(end);
  start.setDate(start.getDate() - Math.max(span - 1, 0));
  return `${formatDate(start)} ~ ${formatDate(end)} · 최근 ${span}일`;
}

function TopicMessage({ status, fallback, theme }) {
  const E = theme;
  const text = {
    loading: "주제를 불러오는 중입니다",
    error: "주제 데이터를 불러오지 못했습니다",
    empty: "아직 생성된 추천 주제가 없습니다",
    ready: fallback,
  }[status] || fallback;

  return <p style={{ fontSize: 13, color: E.t5, padding: "12px 0" }}>{text}</p>;
}

/* ── Topic row ── */
function TopicRow({ item, right, onStart, index, theme, isAuthenticated }) {
  const E = theme;
  const [hov, setHov] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const trendStatus = item.trend?.status;
  const trendLabel = trendStatus ? TREND_LABELS[trendStatus] || trendStatus : "";
  const trendColor = trendStatus === "Rising" || trendStatus === "New"
    ? E.emLL
    : trendStatus === "Cooling"
      ? "rgba(255,176,114,.92)"
      : E.t4;

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{ borderRadius: 14, marginBottom: 2, overflow: "hidden",
        background: hov || expanded ? E.rowBg : "transparent",
        transition: "background .15s", minWidth: 0 }}
    >
      {/* 클릭 → 펼침 토글 */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 16px", cursor: "pointer" }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, overflow: "hidden", flex: 1, minWidth: 0 }}>
          {index !== undefined ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0, width: 28 }}>
              <span style={{
                fontSize: 40, fontWeight: 900, lineHeight: 1,
                letterSpacing: "-0.05em", textAlign: "right", width: "100%",
                color: expanded ? E.emLL : hov ? E.emLL : "rgba(255,255,255,.18)",
                transition: "color .15s",
              }}>
                {item.rank ?? index + 1}
              </span>
              {item.trend?.status === "Rising" && (
                <span style={{ fontSize: 9, fontWeight: 800, lineHeight: 1, marginTop: 2, color: "#4ade80" }}>▲</span>
              )}
              {item.trend?.status === "Cooling" && (
                <span style={{ fontSize: 9, fontWeight: 800, lineHeight: 1, marginTop: 2, color: "#fb923c" }}>▼</span>
              )}
              {(item.trend?.status === "Stable" || item.trend?.status === "Sustained") && (
                <span style={{ fontSize: 9, fontWeight: 700, lineHeight: 1, marginTop: 2, color: "rgba(255,255,255,.3)" }}>—</span>
              )}
              {(item.trend?.status === "New" || !item.trend?.status) && (
                <span style={{ fontSize: 8, fontWeight: 800, lineHeight: 1, marginTop: 2, color: E.emLL, opacity: 0.7 }}>NEW</span>
              )}
            </div>
          ) : (
            <div style={{ width: 5, height: 34, borderRadius: 99, flexShrink: 0,
              background: expanded ? E.emLL : hov ? E.emLL : "rgba(255,255,255,.22)",
              transition: "background .15s" }} />
          )}
          <div style={{ minWidth: 0, flex: 1 }}>
            <p style={{ fontSize: 16, fontWeight: 600, margin: "0 0 4px",
              color: expanded ? E.emLL : hov ? E.emLL : E.t1, transition: "color .15s",
              whiteSpace: expanded ? "normal" : "nowrap",
              overflow: expanded ? "visible" : "hidden",
              textOverflow: expanded ? "clip" : "ellipsis",
              lineHeight: expanded ? 1.4 : 1.2,
              wordBreak: "keep-all" }}>
              {item.title}
            </p>
            <p style={{ fontSize: 12, color: E.t4, margin: 0,
              whiteSpace: expanded ? "normal" : "nowrap",
              overflow: expanded ? "visible" : "hidden",
              textOverflow: expanded ? "clip" : "ellipsis" }}>
              {right && item.displayDate ? `${item.org} · ${item.displayDate}` : item.org}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: 12, flexShrink: 0 }}>
          {trendLabel && (
            <span style={{ fontSize: 10, fontWeight: 800, color: trendColor, background: E.emBg,
              borderRadius: 99, padding: "3px 9px", border: `1px solid ${E.emBr}`, whiteSpace: "nowrap" }}>
              {trendLabel}
            </span>
          )}
          {right && (
            <span style={{ fontSize: 10, color: E.t5, whiteSpace: "nowrap" }}>{item.days}</span>
          )}
          <span style={{
            fontSize: 12, color: expanded ? E.emLL : E.t5,
            transition: "transform .25s, color .15s",
            display: "inline-block",
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
          }}>▾</span>
        </div>
      </div>

      {/* 펼침 영역 — max-height 슬라이딩 */}
      <div style={{
        maxHeight: expanded ? "220px" : "0px",
        overflow: "hidden",
        transition: "max-height 0.3s ease",
      }}>
        <div style={{
          margin: "0 16px 0 58px",
          paddingTop: 10, paddingBottom: 14,
          borderTop: `1px solid rgba(255,255,255,.1)`,
        }}>
          <p style={{ fontSize: 12, color: E.t3, lineHeight: 1.75, margin: "0 0 14px" }}>
            {item.rationale || "선정 근거 정보가 없습니다."}
          </p>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              onClick={e => { e.stopPropagation(); onStart(item.title, { rationale: item.rationale, key_data: item.key_data, articles: item.articles, report_slug: item.report_slug }); }}
              style={{
                background: E.emBg, border: `1px solid ${E.emBr}`,
                color: E.emLL, borderRadius: 10, padding: "7px 16px",
                fontSize: 12, fontWeight: 700, cursor: "pointer",
                transition: "background .15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = E.rowBgStrong}
              onMouseLeave={e => e.currentTarget.style.background = E.emBg}
            >
              {isAuthenticated ? "상세 분석으로 들어가기" : "작성된 리포트 보기"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Previous-week topic group ── */
function WeekGroup({ weekOf, topics, onStart, theme, isAuthenticated }) {
  const E = theme;
  const [open, setOpen] = useState(false);
  const d = new Date(weekOf + "T00:00:00");
  const label = `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 기준`;
  return (
    <div style={{ borderTop: "1px solid rgba(255,255,255,.07)", marginTop: 2 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "11px 8px", background: "transparent", border: "none", cursor: "pointer", textAlign: "left" }}
      >
        <span style={{ fontSize: 13, fontWeight: 700, color: E.t3 }}>{label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 11, color: E.t5 }}>{topics.length}개 주제</span>
          <span style={{ fontSize: 11, color: E.t5, display: "inline-block",
            transition: "transform .2s", transform: open ? "rotate(180deg)" : "rotate(0deg)" }}>▾</span>
        </div>
      </button>
      {open && (
        <div style={{ paddingBottom: 8 }}>
          {[...topics]
            .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999))
            .map((item, i) => (
              <TopicRow key={item.title || i} item={item} onStart={onStart} index={i} theme={E} isAuthenticated={isAuthenticated} />
            ))}
        </div>
      )}
    </div>
  );
}

/* ── Main ── */
export default function LandingPage() {
  const nav = useNavigate();
  const { domain } = useDomain();
  const { isAuthenticated } = useAuth();
  const E = THEMES[domain.id] || THEMES.smartphone;
  const [monthlyHot, setMonthlyHot] = useState([]);
  const [monthlyNew, setMonthlyNew] = useState([]);
  const [generatedAt, setGeneratedAt] = useState("");
  const [topicStatus, setTopicStatus] = useState("loading");
  const [topicDays, setTopicDays] = useState(30);
  const [historyByWeek, setHistoryByWeek] = useState([]);
  const topicWindow = topicWindowLabel(generatedAt, topicDays);

  useEffect(() => {
    fetch(`/api/topics/suggested?domain=${domain.id}`)
      .then(r => {
        if (!r.ok) throw new Error(`topics ${r.status}`);
        return r.json();
      })
      .then(data => {
        const topics = data.topics || [];
        const hot = topics.filter(isCoreTopic).map(toRow).sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
        const newT = topics.filter(t => !isCoreTopic(t)).map(toRow);
        setMonthlyHot(hot);
        setMonthlyNew(newT);
        setTopicDays(data.days || 30);
        setTopicStatus(topics.length ? "ready" : "empty");
        setHistoryByWeek(
          (data.history_by_week || []).map(week => ({
            week_of: week.week_of,
            topics: (week.topics || []).filter(isCoreTopic).map(toRow),
          }))
        );
        if (data.generated_at) {
          setGeneratedAt(data.generated_at);
        }
      })
      .catch(() => {
        setMonthlyHot([]);
        setMonthlyNew([]);
        setTopicStatus("error");
      });
  }, [domain.id]);

  const handleStart = (topic, topicInfo = null) => {
    const fallback = (DOMAIN_EXAMPLES[domain.id] || DOMAIN_EXAMPLES.smartphone)[0];
    const t = (typeof topic === "string" ? topic : "").trim() || "아마존 글로벌스타 인수와 D2D 위성 통신";
    const startTopic = t.startsWith("?") ? fallback : t;
    // 이미 생성된 보고서가 있으면 인증 여부와 무관하게 archive로 점프
    if (topicInfo?.report_slug) {
      nav(`/archive/${encodeURIComponent(topicInfo.report_slug)}`);
      return;
    }
    if (isAuthenticated) {
      nav("/app", { state: { startTopic, topicInfo } });
      return;
    }
    alert("이 주제로 생성된 리포트가 아직 없습니다.");
  };

  return (
    /* Outer: clips the oversized forest-pan div */
    <div style={{ height: "100%", overflow: "hidden", background: E.bg, position: "relative" }}>

      {/* ── Background layers ── */}
      <div className="forest-pan" style={{ backgroundImage: E.image, backgroundPosition: E.bgPos }} />
      {/* radial vignette */}
      <div style={{ position: "absolute", inset: 0, zIndex: 1, pointerEvents: "none",
        background: E.vignette }} />
      {/* top-bottom gradient */}
      <div style={{ position: "absolute", inset: 0, zIndex: 2, pointerEvents: "none",
        background: "linear-gradient(to bottom, rgba(0,0,0,.2) 0%, transparent 35%, rgba(0,0,0,.55) 100%)" }} />

      {/* ── Scrollable content ── */}
      <div style={{ position: "relative", zIndex: 3, height: "100%", overflowY: "auto", overflowX: "hidden" }}>
        <nav style={{ position: "sticky", top: 0, zIndex: 10, display: "flex", justifyContent: "flex-end",
          gap: 8, padding: "18px clamp(16px, 4vw, 48px) 0", pointerEvents: "none" }}>
          {(isAuthenticated ? [
            ["Onboarding", "/onboarding"],
            ["Archive", "/archive"],
            ["News", "/news"],
            ["DB", "/db"],
            ["Keywords", "/keywords"],
            ["Usage", "/usage"],
          ] : [
            ["Onboarding", "/onboarding"],
            ["Login", "/login"],
          ]).map(([label, path]) => (
            <button
              key={path}
              onClick={() => {
                if (path === "/onboarding") { window.location.href = path; return; }
                nav(path);
              }}
              style={{ pointerEvents: "auto", height: 34, borderRadius: 99,
                border: `1px solid ${E.border}`, background: E.navBg,
                color: label === "DB" ? E.t3 : E.emLL,
                padding: "0 14px", fontFamily: '"Cabinet Grotesk", "Pretendard Variable", Pretendard, sans-serif',
                fontSize: 12, fontWeight: 700, letterSpacing: "0.02em", cursor: "pointer",
                backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
                boxShadow: "0 4px 18px rgba(0,0,0,.18)", transition: "background .15s, color .15s" }}
              onMouseEnter={e => {
                e.currentTarget.style.background = E.hoverBg;
                e.currentTarget.style.color = E.emLL;
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = E.navBg;
                e.currentTarget.style.color = label === "DB" ? E.t3 : E.emLL;
              }}
            >
              {label}
            </button>
          ))}
        </nav>

        {/* ── Hero section ── */}
        <section style={{ maxWidth: 1320, margin: "0 auto", display: "flex", flexDirection: "column",
          alignItems: "center", padding: "18px 32px 18px", textAlign: "center" }}>

          {/* Headline */}
          <h1 style={{ fontFamily: '"Cabinet Grotesk", "Pretendard Variable", Pretendard, sans-serif',
            fontSize: 80, fontWeight: 800, color: E.t1, letterSpacing: "-0.045em",
            lineHeight: 0.98, margin: "16px 0 0", textShadow: "0 4px 32px rgba(0,0,0,.5)",
            animation: "fadeUp .5s ease .06s both" }}>
            Deep research.<br/>
            <span style={{ color: E.em }}>{domain.label}</span>
            <span style={{ color: E.t1 }}> insights.</span>
          </h1>
        </section>

        {/* ── Topic sections ── */}
        <section style={{ width: "100%", maxWidth: 1320, margin: "0 auto", padding: "0 clamp(16px, 4vw, 48px) 64px", boxSizing: "border-box" }}>
          <div style={{ borderRadius: 32, border: `1px solid ${E.border}`,
            background: E.surf, padding: "28px clamp(20px, 4vw, 48px) 20px",
            boxShadow: "0 8px 48px rgba(0,0,0,.45)", backdropFilter: "blur(24px)",
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(430px, 100%), 1fr))", gap: 40,
            overflow: "hidden", width: "100%", boxSizing: "border-box" }}>

            {/* Hot */}
            <div style={{ minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 800, color: E.t1, margin: "0 0 4px", letterSpacing: "-0.02em" }}>이번 주 핵심 주제</h2>
                  <p style={{ fontSize: 11, color: E.t4, margin: 0 }}>
                    {topicWindow || "데이터 로딩 중…"}
                  </p>
                </div>
              </div>
              <div>
                {monthlyHot.length === 0
                  ? <TopicMessage status={topicStatus} fallback="이번 주 핵심 기준에 해당하는 주제가 없습니다" theme={E} />
                  : monthlyHot.map((item, i) => (
                      <TopicRow key={item.title || `${item.org}-${i}`} item={item} onStart={handleStart} index={i} theme={E} isAuthenticated={isAuthenticated} />
                    ))
                }
              </div>
            </div>

            {/* New topics */}
            <div style={{ position: "relative", minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 800, color: E.t1, margin: "0 0 4px", letterSpacing: "-0.02em" }}>이번 주 새롭게 등장한 주제</h2>
                  <p style={{ fontSize: 11, color: E.t4, margin: 0 }}>최근 {topicDays}일 내 신규 등장 · 자동 감지</p>
                </div>
              </div>
              <div>
                {monthlyNew.length === 0
                  ? <TopicMessage status={topicStatus} fallback="이번 주 신규 기준에 해당하는 주제가 없습니다" theme={E} />
                  : monthlyNew.map((item, i) => (
                      <TopicRow key={item.title || `${item.org}-${i}`} item={item} right onStart={handleStart} index={i} theme={E} isAuthenticated={isAuthenticated} />
                    ))
                }
              </div>
            </div>

          </div>
        </section>

        {/* ── 이전 주 주제 ── */}
        {historyByWeek.length > 0 && (
          <section style={{ width: "100%", maxWidth: 1320, margin: "0 auto",
            padding: "0 clamp(16px, 4vw, 48px) 56px", boxSizing: "border-box" }}>
            <div style={{ borderRadius: 24, border: `1px solid ${E.border}`, background: E.surf,
              padding: "20px clamp(16px, 4vw, 40px)", boxShadow: "0 4px 24px rgba(0,0,0,.3)",
              backdropFilter: "blur(20px)" }}>
              <h2 style={{ fontSize: 15, fontWeight: 800, color: E.t2, margin: "0 0 2px",
                letterSpacing: "-0.02em" }}>이전 주 주제</h2>
              <p style={{ fontSize: 11, color: E.t4, margin: "0 0 8px" }}>주 1회 선정 기록 — 최근 8주</p>
              {historyByWeek.map(({ week_of, topics }) => (
                <WeekGroup key={week_of} weekOf={week_of} topics={topics}
                  onStart={handleStart} theme={E} isAuthenticated={isAuthenticated} />
              ))}
            </div>
          </section>
        )}

      </div>{/* end scrollable */}
    </div>
  );
}
