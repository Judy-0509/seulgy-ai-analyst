import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { C, SRC_COLORS } from "../theme";
import SparkLogo from "../components/SparkLogo";
import { useAuth } from "../contexts/AuthContext";

const MOCK_ARCHIVES = [
  { name: "Omdia", count: 847, lastUpdated: "2026-05-03", color: SRC_COLORS[0] },
  { name: "Counterpoint Research", count: 512, lastUpdated: "2026-05-02", color: SRC_COLORS[1] },
  { name: "IDC", count: 334, lastUpdated: "2026-05-01", color: SRC_COLORS[2] },
  { name: "TrendForce", count: 218, lastUpdated: "2026-04-30", color: SRC_COLORS[3] },
  { name: "Morgan Stanley", count: 156, lastUpdated: "2026-04-28", color: SRC_COLORS[4] },
  { name: "Gartner", count: 203, lastUpdated: "2026-04-29", color: "#10b981" },
  { name: "Yole Group", count: 89, lastUpdated: "2026-04-27", color: "#f43f5e" },
  { name: "Naver Research", count: 445, lastUpdated: "2026-05-03", color: "#06b6d4" },
];

const MOCK_ARTICLES = [
  { org: "Omdia", title: "Acquiring Globalstar provides Amazon Leo a fast lane to enter the D2D market", date: "2026-04-15", tags: ["위성통신", "M&A"] },
  { org: "Counterpoint", title: "Amazon Leo's Globalstar Acquisition: Amazon Heading for the Stars", date: "2026-04-14", tags: ["M&A", "위성통신"] },
  { org: "Omdia", title: "Smartphone satellite direct-to-device service revenue to be approximately $12bn by 2030", date: "2026-03-22", tags: ["위성통신", "서비스"] },
  { org: "Counterpoint", title: "Smartphones With Satellite Connectivity to Reach 46% of Global Shipments by 2030", date: "2026-03-10", tags: ["위성통신", "경쟁"] },
  { org: "Omdia", title: "Ofcom authorizes satellite D2D services in mobile spectrum bands ahead of WRC-27", date: "2026-02-25", tags: ["규제", "유럽"] },
  { org: "Omdia", title: "Apple Smartphone Technology Outlook – 2026", date: "2026-02-18", tags: ["경쟁", "부품"] },
  { org: "Omdia", title: "Samsung Smartphone Strategy Outlook 2026", date: "2026-02-12", tags: ["경쟁"] },
  { org: "IDC", title: "Worldwide Smartphone Market – Q1 2026 Forecast", date: "2026-01-30", tags: ["경쟁", "반도체"] },
  { org: "TrendForce", title: "2026 Smartphone Production Volume and Key Component Supply", date: "2026-01-20", tags: ["부품", "반도체"] },
  { org: "Morgan Stanley", title: "Satellite Direct-to-Device: The Next Trillion Dollar Market", date: "2026-01-08", tags: ["위성통신", "M&A"] },
];

export default function DbPage() {
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const [query, setQuery] = useState("");
  const [selectedOrg, setSelectedOrg] = useState("전체");
  const [archives, setArchives] = useState(MOCK_ARCHIVES);
  const [loading, setLoading] = useState(false);

  const orgs = ["전체", ...MOCK_ARCHIVES.map(a => a.name)];
  const totalCount = archives.reduce((a, b) => a + b.count, 0);

  const filtered = MOCK_ARTICLES.filter(a => {
    const orgMatch = selectedOrg === "전체" || a.org === selectedOrg;
    const queryMatch = !query || a.title.toLowerCase().includes(query.toLowerCase()) || a.org.toLowerCase().includes(query.toLowerCase());
    return orgMatch && queryMatch;
  });

  useEffect(() => {
    // Try to fetch real archive status
    fetch("/api/archives/status")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) setArchives(data);
      })
      .catch(() => {});
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: C.bg, overflow: "hidden" }}>
      {/* Top bar */}
      <div style={{ padding: "12px 24px", borderBottom: `1px solid ${C.border}`, background: C.card, display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
        <button onClick={() => nav("/")} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
          <SparkLogo size={24} />
        </button>
        <div style={{ width: 1, height: 16, background: C.border }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: C.t1 }}>아카이브 DB</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => nav("/app")} style={{ fontSize: 12, color: C.ind, background: C.indBg, border: `1px solid ${C.indBr}`, borderRadius: 7, padding: "5px 12px", cursor: "pointer", fontWeight: 600 }}>
          보고서 생성 →
        </button>
        {user && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: C.t4, fontFamily: C.mono }}>{user.username}</span>
            <button onClick={logout} style={{ fontSize: 11, color: C.t3, background: "none", border: `1px solid ${C.border}`, borderRadius: 6, padding: "4px 9px", cursor: "pointer" }}>로그아웃</button>
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "20px 24px" }}>
        {/* Archive cards */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: C.t2 }}>아카이브 현황</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: C.ind, background: C.indBg, borderRadius: 99, padding: "2px 10px", border: `1px solid ${C.indBr}` }}>총 {totalCount.toLocaleString()}건</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 8 }}>
            {archives.map((a, i) => (
              <div
                key={a.name}
                onClick={() => setSelectedOrg(selectedOrg === a.name ? "전체" : a.name)}
                style={{ padding: "12px 14px", background: selectedOrg === a.name ? C.indBg : C.card, border: `1.5px solid ${selectedOrg === a.name ? C.indBr : C.border}`, borderRadius: 10, cursor: "pointer", transition: "all 0.15s" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: a.color, display: "inline-block", flexShrink: 0 }} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: C.t1, lineHeight: 1.3 }}>{a.name}</span>
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: selectedOrg === a.name ? C.ind : C.t1 }}>{a.count.toLocaleString()}<span style={{ fontSize: 11, fontWeight: 400, color: C.t4, marginLeft: 2 }}>건</span></div>
                <div style={{ fontSize: 10, color: C.t4, marginTop: 3, fontFamily: C.mono }}>업데이트 {a.lastUpdated}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Search + filter */}
        <div style={{ display: "flex", gap: 10, marginBottom: 14, alignItems: "center" }}>
          <div style={{ flex: 1, display: "flex", gap: 8, background: C.card, border: `1.5px solid ${C.borderM}`, borderRadius: 10, padding: "8px 12px" }}>
            <span style={{ color: C.t4, fontSize: 15 }}>⌕</span>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="제목, 기관명으로 검색..."
              style={{ flex: 1, border: "none", outline: "none", fontSize: 13, color: C.t1, background: "transparent" }}
            />
            {query && (
              <button onClick={() => setQuery("")} style={{ background: "none", border: "none", color: C.t4, cursor: "pointer", fontSize: 13 }}>✕</button>
            )}
          </div>
          <select
            value={selectedOrg}
            onChange={e => setSelectedOrg(e.target.value)}
            style={{ border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 12px", fontSize: 12, color: C.t2, background: C.card, cursor: "pointer", outline: "none" }}
          >
            {orgs.map(o => <option key={o}>{o}</option>)}
          </select>
        </div>

        {/* Results */}
        <div style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: C.t3 }}>검색 결과</span>
          <span style={{ fontSize: 11, color: C.t4 }}>{filtered.length}건</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {filtered.map((a, i) => (
            <div key={i} style={{ display: "flex", gap: 10, padding: "11px 14px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 9, alignItems: "flex-start" }}>
              <span style={{ fontSize: 9, fontWeight: 700, color: C.ind, background: C.indBg, border: `1px solid ${C.indBr}`, borderRadius: 5, padding: "2px 7px", whiteSpace: "nowrap", marginTop: 1, flexShrink: 0 }}>{a.org}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.t1, lineHeight: 1.5, marginBottom: 5 }}>{a.title}</div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <span style={{ fontSize: 10, color: C.t4, fontFamily: C.mono }}>{a.date}</span>
                  {a.tags.map(t => (
                    <span key={t} style={{ fontSize: 9, fontWeight: 600, color: C.t3, background: C.subtle, borderRadius: 4, padding: "1px 6px", border: `1px solid ${C.border}` }}>{t}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: "40px", textAlign: "center", color: C.t4, fontSize: 13 }}>
              검색 결과가 없습니다
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
