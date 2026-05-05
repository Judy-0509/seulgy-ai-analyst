import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const API = "";

const A = {
  bg: "#f7f6f3",
  panel: "rgba(255,255,255,.72)",
  panelStrong: "rgba(255,255,255,.9)",
  border: "rgba(42,40,38,.09)",
  t1: "#2a2826",
  t2: "#4a4744",
  t3: "#716f6c",
  t4: "#9a9896",
  em: "#10b981",
  emD: "#047857",
  emBg: "rgba(16,185,129,.09)",
  emBr: "rgba(16,185,129,.24)",
  shadow: "0 12px 34px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.76)",
};

function Badge({ children }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", height: 22, padding: "0 8px",
      borderRadius: 7, background: A.emBg, color: A.emD,
      border: `1px solid ${A.emBr}`, fontSize: 11, fontWeight: 700,
    }}>
      {children}
    </span>
  );
}

function ReportCard({ report, onOpen }) {
  const metricTags = report.metric_tags || [];
  return (
    <button
      onClick={onOpen}
      style={{
        display: "block", width: "100%", textAlign: "left", cursor: "pointer",
        padding: "18px 20px", borderRadius: 12, background: A.panelStrong,
        border: `1px solid ${A.border}`, boxShadow: "0 1px 4px rgba(0,0,0,.03)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <Badge>{report.section_count}개 섹션</Badge>
        <Badge>{report.reference_count}개 참고</Badge>
        <span style={{ fontSize: 11.5, color: A.t4 }}>{report.run_ts || report.modified_at}</span>
      </div>
      <h2 style={{ margin: "0 0 8px", fontSize: 17, lineHeight: 1.4, color: A.t1, letterSpacing: 0 }}>
        {report.topic}
      </h2>
      {report.summary && (
        <p style={{
          margin: "0 0 12px", fontSize: 13, color: A.t3, lineHeight: 1.65,
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
        }}>
          {report.summary}
        </p>
      )}
      {metricTags.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {metricTags.slice(0, 6).map((metric) => (
            <span key={metric} style={{
              display: "inline-flex", alignItems: "center", height: 22,
              padding: "0 8px", borderRadius: 99, background: "#eefcf6",
              color: A.emD, border: "1px solid rgba(16,185,129,.18)",
              fontSize: 11, fontWeight: 700,
            }}>
              {metric}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}

export default function ReportsArchivePage() {
  const nav = useNavigate();
  const [reports, setReports] = useState([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/reports`)
      .then((res) => {
        if (!res.ok) throw new Error("failed");
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setReports(data.reports || []);
      })
      .catch(() => {
        if (!cancelled) setError("리포트 아카이브를 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return reports;
    return reports.filter((report) =>
      `${report.topic} ${report.summary}`.toLowerCase().includes(q)
    );
  }, [reports, query]);

  return (
    <main style={{
      height: "100vh", overflow: "auto", background: A.bg, color: A.t1,
      fontFamily: "\"Apple SD Gothic Neo\", -apple-system, BlinkMacSystemFont, \"SF Pro Display\", \"SF Pro Text\", \"Helvetica Neue\", sans-serif",
    }}>
      <div style={{
        position: "sticky", top: 0, zIndex: 5, height: 58, display: "flex",
        alignItems: "center", justifyContent: "space-between", padding: "0 28px",
        background: "rgba(247,246,243,.86)", backdropFilter: "blur(28px) saturate(180%)",
        WebkitBackdropFilter: "blur(28px) saturate(180%)", borderBottom: `1px solid ${A.border}`,
      }}>
        <button onClick={() => nav("/")} style={{
          border: 0, background: "none", color: A.t3, fontSize: 13,
          fontWeight: 700, cursor: "pointer", padding: 0,
        }}>
          홈
        </button>
        <img src="/logo-mark.png" alt="Canopy" style={{ width: 50, height: 36, objectFit: "contain" }} />
      </div>

      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "38px 20px 60px" }}>
        <section style={{
          padding: "28px 30px", borderRadius: 16, background: A.panel,
          border: `1px solid ${A.border}`, boxShadow: A.shadow, marginBottom: 18,
        }}>
          <Badge>Report Archive</Badge>
          <h1 style={{ margin: "14px 0 8px", fontSize: 30, lineHeight: 1.25, letterSpacing: 0 }}>
            과거 Executive Report
          </h1>
          <p style={{ margin: "0 0 20px", fontSize: 13.5, color: A.t3, lineHeight: 1.7 }}>
            생성된 리포트를 한 곳에서 검색하고 다시 열람합니다.
          </p>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="주제 또는 요약 검색"
            style={{
              width: "100%", height: 42, boxSizing: "border-box", borderRadius: 10,
              border: `1px solid ${A.border}`, background: "rgba(255,255,255,.72)",
              padding: "0 14px", outline: "none", color: A.t1, fontSize: 13.5,
            }}
          />
        </section>

        {error && <p style={{ color: A.t3 }}>{error}</p>}

        <div style={{ display: "grid", gap: 12 }}>
          {filtered.map((report) => (
            <ReportCard
              key={report.slug}
              report={report}
              onOpen={() => nav(`/archive/${report.slug}`)}
            />
          ))}
        </div>

        {!error && filtered.length === 0 && (
          <p style={{ margin: "28px 0 0", textAlign: "center", color: A.t4, fontSize: 13 }}>
            표시할 리포트가 없습니다.
          </p>
        )}
      </div>
    </main>
  );
}
