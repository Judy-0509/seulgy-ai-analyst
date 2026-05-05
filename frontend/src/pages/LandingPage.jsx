import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useDomain } from "../contexts/DomainContext";

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
    image: "url('/smartphone-bg.png')",
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
};

function critKey(criteria = "") {
  if (criteria.includes("2") && criteria.includes("3")) return "both";
  if (criteria.includes("2")) return "hot";
  return "new";
}

function toRow(t) {
  const sources = [...new Set((t.articles || []).map(a => a.source))];
  const org = sources.join(" · ");
  const dates = (t.articles || []).map(a => a.date).filter(Boolean).sort().reverse();
  let daysAgo = "";
  if (dates[0]) {
    const diff = Math.floor((Date.now() - new Date(dates[0]).getTime()) / 86400000);
    daysAgo = diff === 0 ? "오늘" : `${diff}일 전`;
  }
  return {
    title: t.title, org, days: daysAgo,
    rationale: t.rationale || "",
    key_data: t.key_data || [],
    articles: (t.articles || []).map(a => ({
      date: a.date, source: a.source, title: a.title, url: a.url || "",
    })),
  };
}

const FALLBACK_EXAMPLES = [
  "메모리 위기와 스마트폰 OEM 가격 전략 2026",
  "AI 글래스 시장 OEM 진출 전략",
];

/* ── Line icons ── */
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
};

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
function TopicRow({ item, right, onStart, index, theme }) {
  const E = theme;
  const [hov, setHov] = useState(false);
  const [expanded, setExpanded] = useState(false);

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
            <span style={{
              fontSize: 40, fontWeight: 900, lineHeight: 1, flexShrink: 0,
              letterSpacing: "-0.05em", width: 28, textAlign: "right",
              color: expanded ? E.emLL : hov ? E.emLL : "rgba(255,255,255,.18)",
              transition: "color .15s",
            }}>
              {index + 1}
            </span>
          ) : (
            <div style={{ width: 5, height: 34, borderRadius: 99, flexShrink: 0,
              background: expanded ? E.emLL : hov ? E.emLL : "rgba(255,255,255,.22)",
              transition: "background .15s" }} />
          )}
          <div style={{ minWidth: 0, flex: 1 }}>
            <p style={{ fontSize: 16, fontWeight: 600, margin: "0 0 4px",
              color: expanded ? E.emLL : hov ? E.emLL : E.t1, transition: "color .15s",
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {item.title}
            </p>
            <p style={{ fontSize: 12, color: E.t4, margin: 0,
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.org}</p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: 12, flexShrink: 0 }}>
          {right && (
            <>
              <span style={{ fontSize: 9, fontWeight: 700, color: E.emLL, background: E.emBg,
                borderRadius: 99, padding: "3px 10px", border: `1px solid ${E.emBr}` }}>NEW</span>
              <span style={{ fontSize: 10, color: E.t5, whiteSpace: "nowrap" }}>{item.days}</span>
            </>
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
              onClick={e => { e.stopPropagation(); onStart(item.title, { rationale: item.rationale, key_data: item.key_data, articles: item.articles }); }}
              style={{
                background: E.emBg, border: `1px solid ${E.emBr}`,
                color: E.emLL, borderRadius: 10, padding: "7px 16px",
                fontSize: 12, fontWeight: 700, cursor: "pointer",
                transition: "background .15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = E.rowBgStrong}
              onMouseLeave={e => e.currentTarget.style.background = E.emBg}
            >
              상세 분석으로 들어가기 →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main ── */
export default function LandingPage() {
  const nav = useNavigate();
  const { domain } = useDomain();
  const E = THEMES[domain.id] || THEMES.smartphone;
  const [val, setVal] = useState("");
  const [weeklyHot, setWeeklyHot] = useState([]);
  const [weeklyNew, setWeeklyNew] = useState([]);
  const [generatedAt, setGeneratedAt] = useState("");
  const [topicStatus, setTopicStatus] = useState("loading");
  const [topicDays, setTopicDays] = useState(30);
  const [examples, setExamples] = useState(DOMAIN_EXAMPLES[domain.id] || FALLBACK_EXAMPLES);

  useEffect(() => {
    fetch(`/api/topics/suggested?domain=${domain.id}`)
      .then(r => {
        if (!r.ok) throw new Error(`topics ${r.status}`);
        return r.json();
      })
      .then(data => {
        const topics = data.topics || [];
        const hot = topics.filter(t => critKey(t.criteria) !== "new").map(toRow);
        const newT = topics.filter(t => critKey(t.criteria) === "new").map(toRow);
        setWeeklyHot(hot);
        setWeeklyNew(newT);
        setTopicDays(data.days || 30);
        setTopicStatus(topics.length ? "ready" : "empty");
        const all = [...hot, ...newT];
        setExamples(all.length >= 2
          ? all.slice(0, 2).map(t => t.title)
          : (DOMAIN_EXAMPLES[domain.id] || DOMAIN_EXAMPLES.smartphone));
        if (data.generated_at) {
          const d = new Date(data.generated_at);
          setGeneratedAt(`${d.getFullYear()}년 ${d.getMonth()+1}월 ${d.getDate()}일 기준`);
        }
      })
      .catch(() => {
        setWeeklyHot([]);
        setWeeklyNew([]);
        setExamples(DOMAIN_EXAMPLES[domain.id] || DOMAIN_EXAMPLES.smartphone);
        setTopicStatus("error");
      });
  }, [domain.id]);

  const handleStart = (topic, topicInfo = null) => {
    const fallback = (DOMAIN_EXAMPLES[domain.id] || DOMAIN_EXAMPLES.smartphone)[0];
    const t = (typeof topic === "string" ? topic : "").trim() || "아마존 글로벌스타 인수와 D2D 위성 통신";
    nav("/app", { state: { startTopic: t.startsWith("?") ? fallback : t, topicInfo } });
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
          {[
            ["Archive", "/archive"],
            ["News", "/news"],
            ["DB", "/db"],
          ].map(([label, path]) => (
            <button
              key={path}
              onClick={() => nav(path)}
              style={{ pointerEvents: "auto", height: 34, borderRadius: 99,
                border: `1px solid ${E.border}`, background: E.navBg,
                color: label === "DB" ? E.t3 : E.emLL,
                padding: "0 14px", fontSize: 12, fontWeight: 700, cursor: "pointer",
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
          alignItems: "center", padding: "18px 32px 0", textAlign: "center" }}>

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
                placeholder="분석할 주제를 입력하세요"
                style={{ flex: 1, height: 56, background: "transparent", border: "none",
                  outline: "none", fontSize: 15, fontWeight: 500, color: E.t1,
                  caretColor: E.emL }}
              />
              <button onClick={() => handleStart(val)}
                style={{ display: "flex", alignItems: "center", gap: 8,
                  height: 50, background: E.em, border: "none", borderRadius: 20,
                  padding: "0 30px", fontSize: 14, fontWeight: 700, color: "#fff",
                  cursor: "pointer", boxShadow: `0 4px 20px ${E.emBg}`,
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
            {examples.map(ex => (
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
                    {generatedAt || "데이터 로딩 중…"}
                  </p>
                </div>
              </div>
              <div>
                {weeklyHot.length === 0
                  ? <TopicMessage status={topicStatus} fallback="이번 주 핵심 기준에 해당하는 주제가 없습니다" theme={E} />
                  : weeklyHot.map((item, i) => (
                      <TopicRow key={item.title || `${item.org}-${i}`} item={item} onStart={handleStart} index={i} theme={E} />
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
                {weeklyNew.length === 0
                  ? <TopicMessage status={topicStatus} fallback="이번 주 신규 기준에 해당하는 주제가 없습니다" theme={E} />
                  : weeklyNew.map((item, i) => (
                      <TopicRow key={item.title || `${item.org}-${i}`} item={item} right onStart={handleStart} index={i} theme={E} />
                    ))
                }
              </div>
            </div>

          </div>
        </section>

      </div>{/* end scrollable */}
    </div>
  );
}
