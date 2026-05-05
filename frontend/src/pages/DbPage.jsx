import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { C, SRC_COLORS, SRC_COLOR_MAP } from "../theme";
import { useAuth } from "../contexts/AuthContext";
import { useDomain } from "../contexts/DomainContext";

const TOPIC_DAYS = 30;

function normalizeArchive(a, i) {
  return {
    name: a.name,
    count: a.entry_count ?? a.count ?? 0,
    lastUpdated: (a.latest_entry || a.built_at || "").slice(0, 10) || "-",
    color: SRC_COLOR_MAP[a.name] ?? SRC_COLORS[i % SRC_COLORS.length],
    exists: !!a.exists,
  };
}

function flattenTopicGroups(groups = {}) {
  return Object.entries(groups).flatMap(([org, items]) =>
    (items || []).map(item => ({
      org,
      title: item.title || "",
      date: item.date || "",
      url: item.url || "",
    }))
  );
}

export default function DbPage() {
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const { domain } = useDomain();
  const [query, setQuery] = useState("");
  const [selectedOrg, setSelectedOrg] = useState("전체");
  const [archives, setArchives] = useState([]);

  // 전체 탭 — 스마트폰 관련 기사 (최근 30일)
  const [smArticles, setSmArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  // 소스 선택 탭 — 전체 기사 (org: 로드 완료된 소스명)
  const [orgData, setOrgData] = useState({ org: null, items: [], total: 0 });

  const orgs = ["전체", ...archives.map(a => a.name)];
  const totalCount = archives.reduce((a, b) => a + b.count, 0);
  const orgColorMap = Object.fromEntries(archives.map(a => [a.name, a.color]));

  // 초기 로드
  useEffect(() => {
    let alive = true;
    Promise.all([
      fetch("/api/archives/status").then(r => { if (!r.ok) throw new Error(); return r.json(); }),
      fetch(`/api/topics/mine?days=${TOPIC_DAYS}&domain=${domain.id}`).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
    ])
      .then(([archiveData, topicData]) => {
        if (!alive) return;
        setArchives((archiveData.archives || []).map(normalizeArchive));
        setSmArticles(flattenTopicGroups(topicData.groups));
      })
      .catch(() => {
        if (!alive) return;
        setLoadError("아카이브 데이터를 불러오지 못했습니다");
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [domain.id]);

  // 소스 선택 시 전체 기사 fetch — setState는 콜백 안에서만 호출
  useEffect(() => {
    if (selectedOrg === "전체") return;
    const controller = new AbortController();
    fetch(`/api/archives/entries?source=${encodeURIComponent(selectedOrg)}&limit=500`, { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => setOrgData({ org: selectedOrg, items: data.items || [], total: data.total || 0 }))
      .catch(() => setOrgData(prev => prev.org === selectedOrg ? prev : { org: selectedOrg, items: [], total: 0 }));
    return () => controller.abort();
  }, [selectedOrg]);

  const isOrgView = selectedOrg !== "전체";
  const orgLoading = isOrgView && orgData.org !== selectedOrg;
  const orgArticles = orgData.org === selectedOrg ? orgData.items : [];
  const orgTotal = orgData.org === selectedOrg ? orgData.total : 0;

  const displayList = isOrgView
    ? orgArticles
        .filter(a => !query || a.title.toLowerCase().includes(query.toLowerCase()))
        .map(a => ({ ...a, org: selectedOrg }))
    : smArticles
        .filter(a =>
          !query ||
          a.title.toLowerCase().includes(query.toLowerCase()) ||
          a.org.toLowerCase().includes(query.toLowerCase())
        );

  const handleCardClick = (name) => {
    setSelectedOrg(prev => prev === name ? "전체" : name);
    setQuery("");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: C.bg, overflow: "hidden" }}>
      {/* Top bar */}
      <div style={{ height: 64, padding: "0 24px", borderBottom: `1px solid ${C.border}`, background: C.card, display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
        <button onClick={() => nav("/")} style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center" }}>
          <img src="/logo-mark.png" alt="Canopy" style={{ height: 36, objectFit: "contain" }} />
        </button>
        <div style={{ width: 1, height: 20, background: C.border }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: C.t1, letterSpacing: "-.01em" }}>아카이브 DB</span>
        <div style={{ flex: 1 }} />
        {user && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: C.t4 }}>{user.username}</span>
            <button onClick={logout} style={{ fontSize: 11, color: C.t3, background: "none", border: `1px solid ${C.border}`, borderRadius: 6, padding: "4px 9px", cursor: "pointer" }}>로그아웃</button>
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "20px 24px" }}>

        {/* Archive cards */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".10em", color: C.t3, textTransform: "uppercase" }}>아카이브 현황</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: C.ind, background: C.indBg, borderRadius: 99, padding: "2px 10px", border: `1px solid ${C.indBr}` }}>총 {totalCount.toLocaleString()}건</span>
            {loading && <span style={{ fontSize: 11, color: C.t4 }}>불러오는 중...</span>}
            {loadError && <span style={{ fontSize: 11, color: "#dc2626" }}>{loadError}</span>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 8 }}>
            {archives.map((a) => (
              <div
                key={a.name}
                onClick={() => handleCardClick(a.name)}
                style={{
                  padding: "12px 14px",
                  background: selectedOrg === a.name ? C.indBg : C.card,
                  border: `1.5px solid ${selectedOrg === a.name ? C.indBr : C.border}`,
                  borderRadius: 10,
                  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: a.color, display: "inline-block", flexShrink: 0 }} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: C.t1, lineHeight: 1.3 }}>{a.name}</span>
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, color: selectedOrg === a.name ? C.ind : C.t1, letterSpacing: "-.02em" }}>
                  {a.count.toLocaleString()}
                  <span style={{ fontSize: 11, fontWeight: 400, color: C.t4, marginLeft: 2 }}>건</span>
                </div>
                <div style={{ fontSize: 10, color: C.t4, marginTop: 3 }}>업데이트 {a.lastUpdated}</div>
              </div>
            ))}
            {!loading && archives.length === 0 && (
              <div style={{ padding: "24px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, color: C.t4, fontSize: 12 }}>
                표시할 아카이브가 없습니다.
              </div>
            )}
          </div>
        </div>

        {/* Search + filter */}
        <div style={{ display: "flex", gap: 10, marginBottom: 14, alignItems: "center" }}>
          <div style={{ flex: 1, display: "flex", gap: 8, background: C.card, border: `1.5px solid ${C.borderM}`, borderRadius: 10, padding: "8px 12px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
            <span style={{ color: C.t4, fontSize: 15 }}>⌕</span>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="제목으로 검색..."
              style={{ flex: 1, border: "none", outline: "none", fontSize: 13, color: C.t1, background: "transparent" }}
            />
            {query && (
              <button onClick={() => setQuery("")} style={{ background: "none", border: "none", color: C.t4, cursor: "pointer", fontSize: 13 }}>✕</button>
            )}
          </div>
          <select
            value={selectedOrg}
            onChange={e => { setSelectedOrg(e.target.value); setQuery(""); }}
            style={{ border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 12px", fontSize: 12, color: C.t2, background: C.card, cursor: "pointer", outline: "none", fontFamily: "inherit" }}
          >
            {orgs.map(o => <option key={o}>{o}</option>)}
          </select>
        </div>

        {/* Results header */}
        <div style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}>
          {isOrgView ? (
            <>
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".10em", color: C.t3, textTransform: "uppercase" }}>{selectedOrg}</span>
              {orgLoading
                ? <span style={{ fontSize: 11, color: C.t4 }}>불러오는 중...</span>
                : <span style={{ fontSize: 11, color: C.t4 }}>전체 {orgTotal.toLocaleString()}건 중 최신 {orgArticles.length}건</span>
              }
              {query && <span style={{ fontSize: 11, color: C.t4 }}>— 검색 {displayList.length}건</span>}
            </>
          ) : (
            <>
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".10em", color: C.t3, textTransform: "uppercase" }}>최근 {TOPIC_DAYS}일 {domain.label} 관련</span>
              <span style={{ fontSize: 11, color: C.t4 }}>{displayList.length}건</span>
            </>
          )}
        </div>

        {/* Results list */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, overflow: "hidden" }}>
          {orgLoading ? (
            <div style={{ padding: "40px", textAlign: "center", color: C.t4, fontSize: 13 }}>불러오는 중...</div>
          ) : displayList.length === 0 ? (
            <div style={{ padding: "40px", textAlign: "center", color: C.t4, fontSize: 13 }}>검색 결과가 없습니다</div>
          ) : (
            displayList.map((a, idx) => {
              const badgeColor = orgColorMap[a.org] || C.ind;
              return (
                <div
                  key={a.url || `${a.org}-${a.title}`}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "9px 14px",
                    borderBottom: idx < displayList.length - 1 ? `1px solid ${C.border}` : "none",
                  }}
                >
                  {!isOrgView && (
                    <span style={{
                      fontSize: 9, fontWeight: 800, color: "#fff",
                      background: badgeColor,
                      borderRadius: 4, padding: "2px 7px",
                      whiteSpace: "nowrap", flexShrink: 0, letterSpacing: ".02em",
                    }}>{a.org}</span>
                  )}
                  <a
                    href={a.url || undefined}
                    target="_blank"
                    rel="noreferrer"
                    style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 500, color: C.t1, lineHeight: 1.4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textDecoration: "none", cursor: a.url ? "pointer" : "default" }}
                  >
                    {a.title}
                  </a>
                  <span style={{ fontSize: 10, color: C.t4, flexShrink: 0 }}>{a.date}</span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
