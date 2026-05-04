import { useState } from "react";
import { C } from "../theme";
import SparkLogo from "./SparkLogo";
import Tag from "./micro/Tag";

const RECOMMENDED_TOPICS = [
  {
    id: 1, active: true,
    title: "메모리 위기에 따른 OEM 가격 전략 및 시장 세분화 구조적 변화",
    tag: "HOT", org: "Counterpoint · TrendForce · Omdia",
    keyData: "DRAM/NAND 공급 과잉 → ASP 하락 → OEM 티어별 대응",
    reason: "2025 Q2 핵심 이슈",
  },
  {
    id: 2, active: false,
    title: "주요 OEM의 AI 글래스 시장 진출 및 전략적 축 전환",
    tag: "NEW", org: "Omdia · TrendForce",
    keyData: "스마트 글래스 출하 YoY +340% 전망",
    reason: "신규 폼팩터 분석",
  },
  {
    id: 3, active: false,
    title: "인도·동남아 중저가 스마트폰 시장 경쟁 구도 변화",
    tag: "NEW", org: "Counterpoint · IDC",
    keyData: "인도 <$200 세그먼트 Xiaomi vs Samsung 점유율",
    reason: "신흥시장 성장 모멘텀",
  },
  {
    id: 4, active: false,
    title: "온디바이스 AI 탑재 확산에 따른 AP 시장 세력 재편",
    tag: "분석", org: "Omdia · IDC",
    keyData: "NPU 성능 경쟁 및 파운드리 수혜 구조",
    reason: "AI 하드웨어 전환점",
  },
];

export default function HomeScreen({ onStart }) {
  const [inputVal, setInputVal] = useState("");
  const [hoveredId, setHoveredId] = useState(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: C.bg, overflow: "auto" }}>
      {/* Top nav */}
      <div style={{ padding: "18px 32px 0", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
        <SparkLogo />
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: C.t4, fontFamily: C.mono }}>by Seulgy</span>
          <div style={{ width: 1, height: 14, background: C.border }} />
          <button style={{ fontSize: 12, color: C.t3, background: "none", border: `1px solid ${C.border}`, borderRadius: 7, padding: "4px 12px", cursor: "pointer" }}>히스토리</button>
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

      {/* Topics grid */}
      <div style={{ padding: "0 32px 32px", flex: 1, overflow: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.t2 }}>AI 추천 분석 주제</span>
          <span style={{ fontSize: 10, color: C.t4, background: C.subtle, borderRadius: 99, padding: "2px 8px", border: `1px solid ${C.border}` }}>지금 분석 가능</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(270px, 1fr))", gap: 10 }}>
          {RECOMMENDED_TOPICS.map(topic => {
            const isH = hoveredId === topic.id;
            const isActive = topic.active;
            return (
              <div
                key={topic.id}
                onMouseEnter={() => setHoveredId(topic.id)}
                onMouseLeave={() => setHoveredId(null)}
                onClick={() => onStart(topic.title)}
                style={{
                  background: isActive ? C.indBg : C.card,
                  border: `1.5px solid ${isActive ? C.indBr : isH ? "#c7d2fe" : C.border}`,
                  borderRadius: 11, padding: "14px 16px", cursor: "pointer",
                  boxShadow: isH ? "0 4px 16px rgba(79,70,229,0.09)" : "0 1px 3px rgba(0,0,0,0.04)",
                  transition: "all 0.16s ease",
                  transform: isH ? "translateY(-2px)" : "none",
                  display: "flex", flexDirection: "column", gap: 9,
                  animation: "fadeUp 0.3s ease",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 6 }}>
                  <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: C.t1, lineHeight: 1.45, flex: 1 }}>{topic.title}</p>
                  <Tag label={topic.tag} />
                </div>
                <div style={{ background: isActive ? "rgba(79,70,229,0.06)" : C.subtle, borderRadius: 6, padding: "7px 9px", fontSize: 11, color: isActive ? C.ind : C.t3, fontFamily: C.mono, lineHeight: 1.4 }}>
                  {topic.keyData}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 10, color: C.t4, background: C.subtle, borderRadius: 5, padding: "2px 6px", border: `1px solid ${C.border}` }}>{topic.org}</span>
                  <span style={{ fontSize: 10, color: C.t3, maxWidth: 150, textAlign: "right", lineHeight: 1.4 }}>{topic.reason}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
