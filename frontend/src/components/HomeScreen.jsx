import { useState, useEffect } from "react";
import { C } from "../theme";
import SparkLogo from "./SparkLogo";

const CRIT_STYLE = {
  "2":    { label: "HOT",     bg: "#fefce8", color: "#b45309", dot: "#f59e0b" },
  "3":    { label: "NEW",     bg: "#f0fdf4", color: "#15803d", dot: "#22c55e" },
  "2+3":  { label: "HOT·NEW", bg: "#faf5ff", color: "#7e22ce", dot: "#a855f7" },
};

function critKey(criteria = "") {
  if (criteria.includes("2") && criteria.includes("3")) return "2+3";
  if (criteria.includes("2")) return "2";
  return "3";
}

function CritBadge({ criteria }) {
  const key = critKey(criteria);
  const s = CRIT_STYLE[key];
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 5,
      background: s.bg, color: s.color, whiteSpace: "nowrap",
    }}>
      {s.label}
    </span>
  );
}

function SectionHeader({ label, color, count }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      marginBottom: 12, marginTop: 28,
      paddingBottom: 8, borderBottom: `1.5px solid ${C.border}`,
    }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block", flexShrink: 0 }} />
      <span style={{ fontSize: 13, fontWeight: 600, color: C.t2 }}>{label}</span>
      <span style={{
        fontSize: 10, color: C.t4, background: C.subtle,
        borderRadius: 99, padding: "1px 8px", border: `1px solid ${C.border}`,
      }}>{count}개 주제</span>
    </div>
  );
}

function TopicCard({ topic, onStart, isHovered, onEnter, onLeave }) {
  const sources = [...new Set((topic.articles || []).map(a => a.source))];
  const orgStr  = sources.join(" · ");
  const keyDatum = (topic.key_data || [])[0] || "";
  const rationale = topic.rationale || "";
  const key = critKey(topic.criteria);
  const dot = CRIT_STYLE[key].dot;

  return (
    <div
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onClick={() => onStart(topic.title)}
      style={{
        background: C.card,
        border: `1.5px solid ${isHovered ? dot : C.border}`,
        borderRadius: 11, padding: "14px 16px", cursor: "pointer",
        boxShadow: isHovered ? `0 4px 16px ${dot}22` : "0 1px 3px rgba(0,0,0,0.04)",
        transition: "all 0.16s ease",
        transform: isHovered ? "translateY(-2px)" : "none",
        display: "flex", flexDirection: "column", gap: 9,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 6 }}>
        <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: C.t1, lineHeight: 1.45, flex: 1 }}>
          {topic.title}
        </p>
        <CritBadge criteria={topic.criteria} />
      </div>

      {keyDatum && (
        <div style={{
          background: C.subtle, borderRadius: 6, padding: "7px 9px",
          fontSize: 11, color: C.t3, fontFamily: C.mono, lineHeight: 1.4,
        }}>
          {keyDatum}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
        <span style={{
          fontSize: 10, color: C.t4, background: C.subtle,
          borderRadius: 5, padding: "2px 6px", border: `1px solid ${C.border}`,
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 220,
        }}>
          {orgStr}
        </span>
        <span style={{ fontSize: 10, color: C.t4, flexShrink: 0 }}>
          {topic.institution_count}개 기관
        </span>
      </div>

      {rationale && (
        <p style={{ margin: 0, fontSize: 11, color: C.t3, lineHeight: 1.55,
                    display: "-webkit-box", WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {rationale}
        </p>
      )}
    </div>
  );
}

function TopicSection({ label, color, topics, onStart, hoveredId, setHoveredId }) {
  if (!topics.length) return null;
  return (
    <div>
      <SectionHeader label={label} color={color} count={topics.length} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(270px, 1fr))", gap: 10 }}>
        {topics.map((t, i) => (
          <TopicCard
            key={i}
            topic={t}
            onStart={onStart}
            isHovered={hoveredId === `${label}-${i}`}
            onEnter={() => setHoveredId(`${label}-${i}`)}
            onLeave={() => setHoveredId(null)}
          />
        ))}
      </div>
    </div>
  );
}

export default function HomeScreen({ onStart, onArchive }) {
  const [inputVal, setInputVal]   = useState("");
  const [hoveredId, setHoveredId] = useState(null);
  const [topics, setTopics]       = useState(null); // null = loading
  const [generatedAt, setGeneratedAt] = useState(null);

  useEffect(() => {
    fetch("/api/topics/suggested")
      .then(r => r.json())
      .then(data => {
        setTopics(data.topics || []);
        setGeneratedAt(data.generated_at || null);
      })
      .catch(() => setTopics([]));
  }, []);

  const t2  = (topics || []).filter(t => critKey(t.criteria) === "2");
  const t3  = (topics || []).filter(t => critKey(t.criteria) === "3");
  const tb  = (topics || []).filter(t => critKey(t.criteria) === "2+3");
  const hasTopics = (topics || []).length > 0;

  const genLabel = generatedAt
    ? generatedAt.slice(0, 16).replace("T", " ")
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: C.bg, overflow: "auto" }}>
      {/* Top nav */}
      <div style={{ padding: "18px 32px 0", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
        <SparkLogo />
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: C.t4, fontFamily: C.mono }}>by Seulgy</span>
          <div style={{ width: 1, height: 14, background: C.border }} />
          <button
            onClick={onArchive}
            style={{ fontSize: 12, color: C.t3, background: "none", border: `1px solid ${C.border}`, borderRadius: 7, padding: "4px 12px", cursor: "pointer" }}
          >
            아카이브
          </button>
        </div>
      </div>

      {/* Hero */}
      <div style={{ padding: "32px 32px 24px", flexShrink: 0 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: C.t1, margin: 0, letterSpacing: "-0.03em", lineHeight: 1.3, marginBottom: 6 }}>
          어떤 주제를 분석할까요?
        </h1>
        <p style={{ fontSize: 13, color: C.t3, margin: 0 }}>
          Omdia · Counterpoint Research · IDC Tier-1 아카이브 기반으로 AI가 단계적으로 리서치합니다
        </p>

        {/* Search bar */}
        <div style={{ display: "flex", gap: 8, marginTop: 20, background: C.card, border: `1.5px solid ${C.borderM}`, borderRadius: 12, padding: "10px 12px", boxShadow: "0 1px 4px rgba(0,0,0,0.05)" }}>
          <span style={{ color: C.t4, fontSize: 16, flexShrink: 0, paddingTop: 1 }}>⌕</span>
          <input
            value={inputVal}
            onChange={e => setInputVal(e.target.value)}
            onKeyDown={e => e.key === "Enter" && inputVal.trim() && onStart(inputVal.trim())}
            placeholder="분석할 주제를 직접 입력하세요 (예: 애플 위성 D2D 전략 2026)"
            style={{ flex: 1, border: "none", outline: "none", fontSize: 13, color: C.t1, background: "transparent" }}
          />
          <button
            onClick={() => inputVal.trim() && onStart(inputVal.trim())}
            style={{ background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)", color: "#fff", border: "none", borderRadius: 8, padding: "7px 18px", fontSize: 13, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0 }}
          >
            보고서 생성 →
          </button>
        </div>
      </div>

      {/* Topics */}
      <div style={{ padding: "0 32px 40px", flex: 1, overflow: "auto" }}>
        {/* 섹션 헤더 */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.t2 }}>AI 추천 분석 주제</span>
          {genLabel && (
            <span style={{ fontSize: 10, color: C.t4, background: C.subtle, borderRadius: 99, padding: "2px 8px", border: `1px solid ${C.border}` }}>
              {genLabel} 기준
            </span>
          )}
        </div>

        {/* 로딩 */}
        {topics === null && (
          <p style={{ fontSize: 13, color: C.t4, marginTop: 24 }}>주제 불러오는 중...</p>
        )}

        {/* 데이터 없음 */}
        {topics !== null && !hasTopics && (
          <div style={{ marginTop: 24, padding: "20px 24px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 10 }}>
            <p style={{ margin: 0, fontSize: 13, color: C.t3 }}>
              아직 분석된 주제가 없습니다.
            </p>
            <p style={{ margin: "6px 0 0", fontSize: 12, color: C.t4, fontFamily: C.mono }}>
              python scripts/suggest_topics.py 를 실행해 주제를 생성하세요.
            </p>
          </div>
        )}

        {/* 주제 섹션 */}
        {hasTopics && (
          <>
            <TopicSection
              label="이번달 핵심 & 신규 주제"
              color="#a855f7"
              topics={tb}
              onStart={onStart}
              hoveredId={hoveredId}
              setHoveredId={setHoveredId}
            />
            <TopicSection
              label="이번달 핵심 주제"
              color="#f59e0b"
              topics={t2}
              onStart={onStart}
              hoveredId={hoveredId}
              setHoveredId={setHoveredId}
            />
            <TopicSection
              label="이번달 새롭게 등장한 주제"
              color="#22c55e"
              topics={t3}
              onStart={onStart}
              hoveredId={hoveredId}
              setHoveredId={setHoveredId}
            />
          </>
        )}
      </div>
    </div>
  );
}
