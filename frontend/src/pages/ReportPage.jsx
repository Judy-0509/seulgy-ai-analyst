import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Wordmark from "../components/Wordmark";
import { authFetch } from "../lib/authFetch";
import useMediaQuery from "../hooks/useMediaQuery";

const API = "";

// ── Editorial type system ──────────────────────────────────────────────
// 헤드라인: Noto Serif KR (명조) · 본문: Pretendard · 라벨: Cabinet Grotesk(브랜드 연결)
const SERIF = '"Gowun Batang", "Nanum Myeongjo", Georgia, "Times New Roman", serif';
const LABEL = '"Cabinet Grotesk", "Pretendard Variable", Pretendard, sans-serif';

const DOMAIN_LABEL = {
  smartphone: "Smartphone",
  humanoid: "Humanoid",
  automotive: "Automotive",
  space_datacenter: "Space Datacenter",
};

const BASE_R = {
  bg: "#f6f4ef",
  paper: "#fffefb",
  panel: "rgba(255,255,255,.72)",
  panelStrong: "rgba(255,255,255,.9)",
  border: "rgba(42,40,38,.10)",
  hair: "rgba(42,40,38,.13)",
  t1: "#211f1d",
  t2: "#46433f",
  t3: "#6f6c68",
  t4: "#9a9793",
  shadow: "0 18px 48px rgba(31,41,55,.07), inset 0 1px 0 rgba(255,255,255,.8)",
};

function makeR(domain) {
  if (domain === "humanoid") return {
    ...BASE_R,
    em:   "#ef4444",
    emD:  "#b91c1c",
    emBg: "rgba(239,68,68,.07)",
    emBr: "rgba(239,68,68,.22)",
  };
  if (domain === "automotive") return {
    ...BASE_R,
    em:   "#2563eb",
    emD:  "#1d4ed8",
    emBg: "rgba(37,99,235,.07)",
    emBr: "rgba(37,99,235,.22)",
  };
  // smartphone — 차분한 forest green
  return {
    ...BASE_R,
    em:   "#047857",
    emD:  "#065f46",
    emBg: "rgba(6,95,70,.06)",
    emBr: "rgba(6,95,70,.18)",
  };
}

const SOURCE_DOMAIN_ACCENTS = {
  smartphone: { emD: "#065f46", emBg: "rgba(6,95,70,.06)",  emBr: "rgba(6,95,70,.18)"  },
  humanoid:   { emD: "#b91c1c", emBg: "rgba(239,68,68,.08)", emBr: "rgba(239,68,68,.22)" },
  automotive: { emD: "#1d4ed8", emBg: "rgba(37,99,235,.08)", emBr: "rgba(37,99,235,.22)" },
};

const SOURCE_DOMAIN_BY_NAME = {
  "DigiTimes Asia": "smartphone",
  "Counterpoint Research": "smartphone",
  "TrendForce": "smartphone",
  "Nikkei Asia": "smartphone",
  "Omdia": "smartphone",
  "IDC": "smartphone",
  "Reuters": "smartphone",
  "CCS Insight": "smartphone",
  "Yole": "smartphone",
  "Bloomberg Technology": "smartphone",
  "Gartner": "smartphone",
  "The Robot Report": "humanoid",
  "IEEE Spectrum": "humanoid",
  "IEEE Spectrum Robotics": "humanoid",
  "TechCrunch Robotics": "humanoid",
  "MIT Technology Review": "humanoid",
  "Robotics & Automation News": "humanoid",
  "The Verge": "humanoid",
  "arXiv (cs.RO)": "humanoid",
  "NVIDIA": "humanoid",
  "NVIDIA News": "humanoid",
  "Boston Dynamics": "humanoid",
  "Figure AI": "humanoid",
  "Unitree Robotics": "humanoid",
  "Unitree": "humanoid",
  "Humanoids Daily": "humanoid",
  "RoboticsTomorrow": "humanoid",
  "IDTechEx": "humanoid",
  "ABI Research": "humanoid",
  "Yano Research": "humanoid",
  "Goldman Sachs Research": "humanoid",
  "Goldman Sachs Insights": "humanoid",
  "Morgan Stanley Research": "humanoid",
  "Barclays Research": "humanoid",
  "Bank of America Institute": "humanoid",
  "BofA Institute": "humanoid",
  "IFR": "humanoid",
  "Apptronik": "humanoid",
  "Agility Robotics": "humanoid",
  "1X Technologies": "humanoid",
  "JATO Dynamics": "automotive",
  "Cox Automotive": "automotive",
  "AlixPartners": "automotive",
  "WardsAuto": "automotive",
  "SAE International": "automotive",
  "Automotive Dive": "automotive",
  "Automotive World": "automotive",
  "InsideEVs": "automotive",
  "Electrek": "automotive",
  "Toyota Newsroom": "automotive",
  "VW Group": "automotive",
  "Mercedes-Benz Media": "automotive",
  "CnEVPost": "automotive",
  "CarNewsChina": "automotive",
  "ICCT": "automotive",
  "ACEA": "automotive",
  "BloombergNEF": "automotive",
  "RMI": "automotive",
  "Transport & Environment": "automotive",
  "IRENA": "automotive",
};

function sourceAccent(sourceName, R) {
  const domain = SOURCE_DOMAIN_BY_NAME[sourceName];
  return SOURCE_DOMAIN_ACCENTS[domain] || { emD: R.emD, emBg: R.emBg, emBr: R.emBr };
}

// ── Editorial primitives ───────────────────────────────────────────────
function Kicker({ children, color, style }) {
  return (
    <span style={{
      fontFamily: LABEL, fontSize: 11, fontWeight: 700,
      letterSpacing: ".16em", textTransform: "uppercase",
      color, lineHeight: 1, ...style,
    }}>
      {children}
    </span>
  );
}

function SourceLabel({ children, accent }) {
  return (
    <span style={{
      fontFamily: LABEL, fontSize: 10, fontWeight: 700,
      letterSpacing: ".08em", textTransform: "uppercase",
      color: accent.emD, whiteSpace: "nowrap",
    }}>
      {children}
    </span>
  );
}

function MetricPill({ value, R, accent }) {
  const A = accent || R;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", height: 21,
      padding: "0 9px", borderRadius: 99, background: A.emBg,
      color: A.emD, border: `1px solid ${A.emBr}`,
      fontSize: 11, fontWeight: 600, fontVariantNumeric: "tabular-nums",
    }}>
      {value}
    </span>
  );
}

function ViewToggle({ value, onChange, R, isNarrow = false }) {
  const items = [
    { id: "report", label: "Report" },
    { id: "custom", label: "Custom" },
  ];
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 3, padding: 3,
      borderRadius: 999, background: "rgba(42,40,38,.05)",
      border: `1px solid ${R.border}`,
    }}>
      {items.map((item) => {
        const active = value === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            style={{
              border: 0, borderRadius: 999, padding: isNarrow ? "6px 10px" : "6px 14px",
              background: active ? R.em : "transparent",
              color: active ? "#fff" : R.t3,
              fontFamily: LABEL, fontSize: 11.5, fontWeight: 700,
              letterSpacing: ".04em", cursor: "pointer",
              transition: "background .15s, color .15s",
            }}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

function ReferenceCard({ refItem, R }) {
  const accent = sourceAccent(refItem.source_name || refItem.source || "", R);
  const sectionIndices = Array.isArray(refItem.section_indices) && refItem.section_indices.length > 0
    ? refItem.section_indices
    : refItem.section_index
      ? [refItem.section_index]
      : [];
  const sectionLabel = sectionIndices.map((index) => `S${index}`).join(" · ");

  return (
    <a
      href={refItem.url}
      target="_blank"
      rel="noopener noreferrer"
      className="rpt-ref"
      style={{
        display: "block", padding: "15px 4px 16px",
        borderTop: `1px solid ${R.hair}`, textDecoration: "none",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
        <SourceLabel accent={accent}>{refItem.source_name || refItem.source || "Source"}</SourceLabel>
        <span style={{ flex: 1 }} />
        {sectionLabel && (
          <span style={{ fontFamily: LABEL, fontSize: 9.5, fontWeight: 700, letterSpacing: ".06em", color: accent.emD }}>
            {sectionLabel}
          </span>
        )}
        {refItem.date && <span style={{ fontSize: 10.5, color: R.t4 }}>{refItem.date}</span>}
      </div>
      <p style={{ margin: "0 0 6px", fontFamily: SERIF, fontSize: 13.5, fontWeight: 700, color: R.t1, lineHeight: 1.5 }}>
        {refItem.title || refItem.source_name}
      </p>
      {refItem.detail && (
        <p style={{ margin: 0, fontSize: 12, color: R.t3, lineHeight: 1.6 }}>
          {refItem.detail}
        </p>
      )}
      {refItem.metrics?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 10 }}>
          {refItem.metrics.map((metric) => <MetricPill key={metric} value={metric} R={R} accent={accent} />)}
        </div>
      )}
    </a>
  );
}

function firstSentences(text = "", max = 2) {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return "";
  const parts = cleaned.match(/[^.!?。！？]+[.!?。！？]?/g) || [cleaned];
  return parts.slice(0, max).join(" ").trim();
}

function splitIntoSentences(segment) {
  return segment
    .replace(/(([가-힣]\.|[?!])["'”’)\]]*)(\s+)/g, "$1\u0000")
    .split("\u0000")
    .map((sentence) => sentence.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

function splitIntoParagraphs(text = "") {
  const segments = String(text)
    .split(/\n+/)
    .map((segment) => segment.trim())
    .filter(Boolean);

  return segments.flatMap((segment) => {
    const cleaned = segment.replace(/\s+/g, " ").trim();
    const sentences = splitIntoSentences(cleaned);

    if (sentences.length <= 2 || cleaned.length <= 200) return [cleaned];

    const paragraphs = [];
    let current = [];
    let currentLength = 0;

    sentences.forEach((sentence) => {
      current.push(sentence);
      currentLength += sentence.length + (current.length > 1 ? 1 : 0);

      if ((current.length >= 2 && currentLength >= 170) || current.length >= 3) {
        paragraphs.push(current.join(" ").replace(/\s+/g, " ").trim());
        current = [];
        currentLength = 0;
      }
    });

    if (current.length > 0) {
      const tail = current.join(" ").replace(/\s+/g, " ").trim();
      if (current.length === 1 && paragraphs.length > 0) {
        paragraphs[paragraphs.length - 1] = `${paragraphs[paragraphs.length - 1]} ${tail}`.replace(/\s+/g, " ").trim();
      } else {
        paragraphs.push(tail);
      }
    }

    return paragraphs;
  });
}

function Prose({ text, style, gap = "0.9em" }) {
  const paragraphs = splitIntoParagraphs(text);
  if (paragraphs.length === 0) return null;

  return (
    <div style={{ maxWidth: style?.maxWidth }}>
      {paragraphs.map((paragraph, index) => (
        <p
          key={index}
          style={{
            ...style,
            marginTop: index === 0 ? style?.marginTop : gap,
            marginBottom: index === 0 ? style?.marginBottom : 0,
          }}
        >
          {paragraph}
        </p>
      ))}
    </div>
  );
}

function buildResearchBackground(report) {
  if (report.research_background) return report.research_background;
  const summary = firstSentences(report.executive_summary, 2);
  if (summary) return summary;
  const sectionTitles = (report.sections || []).map((s) => s.title).filter(Boolean).slice(0, 3);
  if (sectionTitles.length > 0) {
    return `${sectionTitles.join(", ")}를 중심으로 시장 구조와 경쟁 구도 변화가 나타나고 있습니다.`;
  }
  return "시장 구조와 경쟁 구도 변화가 본격화되고 있습니다.";
}

function buildInsightSummary(insights = []) {
  return insights.map((insight) => ({
    title: insight.title,
    summary: firstSentences(insight.body, 2) || insight.title,
  }));
}

function SectionBlock({ section, R, isNarrow = false }) {
  const [open, setOpen] = useState(false);
  const bullets = section.bullets || [];
  const num = String(section.index).padStart(2, "0");
  return (
    <section style={{ padding: "40px 0 8px", borderTop: `1px solid ${R.hair}` }}>
      <Kicker color={R.emD} style={{ display: "block", marginBottom: 14 }}>
        Section&nbsp;{num}
      </Kicker>
      <h2 style={{
        margin: 0, fontFamily: SERIF, fontSize: isNarrow ? "clamp(22px, 6vw, 25px)" : 25, fontWeight: 700,
        color: R.t1, letterSpacing: "-.01em", lineHeight: 1.4,
      }}>
        {section.title}
      </h2>
      {section.headline && (
        <p style={{
          margin: "14px 0 0", fontFamily: SERIF, fontSize: 17, fontWeight: 500,
          color: R.emD, lineHeight: 1.65,
        }}>
          {section.headline}
        </p>
      )}
      {section.narrative && (
        <Prose text={section.narrative} style={{
          margin: "18px 0 0", fontSize: 14.5, color: R.t2, lineHeight: 1.95,
          maxWidth: "68ch",
        }} />
      )}
      {bullets.length > 0 && (
        <>
          <button
            onClick={() => setOpen(o => !o)}
            aria-expanded={open}
            style={{
              display: "flex", alignItems: "center", gap: 9,
              margin: "22px 0 0", padding: "8px 0", border: 0, background: "none",
              cursor: "pointer", color: R.t1,
            }}
          >
            <Kicker color={R.t3}>상세 수치</Kicker>
            <span style={{ fontSize: 11, color: R.t4, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>{bullets.length}</span>
            <span style={{
              fontSize: 13, color: R.emD, fontWeight: 700,
              transition: "transform 0.25s ease",
              transform: open ? "rotate(90deg)" : "rotate(0deg)",
              display: "inline-block", lineHeight: 1,
            }}>›</span>
          </button>
          <div style={{
            maxHeight: open ? "3000px" : "0px",
            opacity: open ? 1 : 0,
            overflow: "hidden",
            transition: "max-height 0.35s ease, opacity 0.2s ease",
          }}>
            <ul style={{
              margin: "6px 0 0", padding: 0, listStyle: "none",
              display: "grid", gap: 11,
            }}>
              {bullets.map((bullet, index) => (
                <li key={index} style={{
                  display: "flex", alignItems: "flex-start", gap: 13,
                  fontSize: 13.5, color: R.t1, lineHeight: 1.7,
                }}>
                  <span style={{
                    fontFamily: SERIF, color: R.emD, fontSize: 14, lineHeight: 1.6,
                    flexShrink: 0, fontWeight: 700,
                  }}>—</span>
                  <span style={{ minWidth: 0 }}>{bullet}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </section>
  );
}

function CustomSlideView({ report, R, isNarrow = false }) {
  const background = buildResearchBackground(report);
  const insightLines = buildInsightSummary(report.insights || []);
  const sections = report.sections || [];
  return (
    <article style={{ minWidth: 0 }}>
      <div style={{
        display: "grid", gridTemplateRows: "auto auto auto 1fr",
        minHeight: "calc(100vh - 168px)", gap: 14,
      }}>
        <section style={{
          padding: isNarrow ? "20px clamp(18px, 5vw, 26px)" : "22px 26px", borderRadius: 14, background: R.paper,
          border: `1px solid ${R.border}`, boxShadow: R.shadow,
        }}>
          <Kicker color={R.emD}>Custom Brief</Kicker>
          <h1 style={{ margin: "14px 0 0", fontFamily: SERIF, fontSize: isNarrow ? "clamp(24px, 7vw, 27px)" : 27, fontWeight: 700, lineHeight: 1.32, letterSpacing: "-.01em", color: R.t1 }}>
            {report.topic}
          </h1>
        </section>

        <section style={{ padding: "2px 4px 0", borderLeft: `2px solid ${R.emBr}`, paddingLeft: 20 }}>
          <Kicker color={R.emD} style={{ display: "block", marginBottom: 9 }}>조사 배경</Kicker>
          <p style={{ margin: 0, fontFamily: SERIF, fontSize: 15.5, color: R.t2, lineHeight: 1.8 }}>{background}</p>
        </section>

        <section style={{ padding: "6px 0 0" }}>
          <Kicker color={R.emD} style={{ display: "block", marginBottom: 12 }}>시사점</Kicker>
          <div style={{ display: "grid", gap: 12 }}>
            {(insightLines.length
              ? insightLines
              : [{ title: "시장 분석", summary: "분석 결과를 바탕으로 시장 변화와 기업 대응 방향을 요약합니다." }]
            ).map((item, index) => (
              <div key={index} style={{ display: "flex", gap: 13, alignItems: "flex-start" }}>
                <span style={{ fontFamily: SERIF, fontSize: 14, fontWeight: 700, color: R.emD, lineHeight: 1.5, fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: "0 0 4px", fontFamily: SERIF, fontSize: 14, fontWeight: 700, color: R.t1, lineHeight: 1.45 }}>
                    {item.title}
                  </p>
                  <p style={{ margin: 0, fontSize: 13, color: R.t2, lineHeight: 1.6 }}>
                    {item.summary}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section style={{
          padding: isNarrow ? "20px clamp(18px, 5vw, 26px)" : "22px 26px", borderRadius: 14, background: R.paper,
          border: `1px solid ${R.border}`, boxShadow: R.shadow, minHeight: 0,
        }}>
          <Kicker color={R.emD} style={{ display: "block", marginBottom: 16 }}>핵심 분석</Kicker>
          <div style={{ display: "grid", gap: 0 }}>
            {sections.map((section, i) => (
              <div key={section.index} style={{
                padding: i === 0 ? "0 0 16px" : "16px 0",
                borderTop: i === 0 ? "none" : `1px solid ${R.hair}`,
                minWidth: 0,
              }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 11, marginBottom: 7 }}>
                  <span style={{ fontFamily: SERIF, fontSize: 13, fontWeight: 700, color: R.emD, fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
                    {String(section.index).padStart(2, "0")}
                  </span>
                  <h3 style={{ margin: 0, fontFamily: SERIF, fontSize: 15.5, fontWeight: 700, lineHeight: 1.4, color: R.t1 }}>
                    {section.title}
                  </h3>
                </div>
                {section.headline && (
                  <p style={{ margin: "0 0 8px 24px", fontFamily: SERIF, fontSize: 13, fontWeight: 500, color: R.emD, lineHeight: 1.55 }}>
                    {section.headline}
                  </p>
                )}
                {section.narrative && (
                  <p style={{ margin: "0 0 0 24px", fontSize: 12.6, color: R.t2, lineHeight: 1.7 }}>
                    {section.narrative}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </article>
  );
}

export default function ReportPage() {
  const { slug = "" } = useParams();
  const nav = useNavigate();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [viewMode, setViewMode] = useState("report");
  const isNarrowReport = useMediaQuery("(max-width: 768px)");
  // 모바일에서는 참고 수치 아코디언을 기본 접힘으로 시작 (본문이 먼저 보이도록)
  const [refsOpen, setRefsOpen] = useState(() => !isNarrowReport);

  useEffect(() => {
    let cancelled = false;
    authFetch(`${API}/api/reports/${encodeURIComponent(slug)}`)
      .then((res) => {
        if (!res.ok) throw new Error("report not found");
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch(() => {
        if (!cancelled) setError("리포트를 불러오지 못했습니다.");
      });
    return () => { cancelled = true; };
  }, [slug]);

  const R = useMemo(() => makeR(report?.domain), [report?.domain]);
  const references = useMemo(() => report?.references || [], [report]);

  if (error) {
    return (
      <main style={{ minHeight: "100vh", background: BASE_R.bg, display: "grid", placeItems: "center", color: BASE_R.t2, fontFamily: SERIF }}>
        {error}
      </main>
    );
  }

  if (!report) {
    return (
      <main style={{ minHeight: "100vh", background: BASE_R.bg, display: "grid", placeItems: "center", color: BASE_R.t3, fontFamily: SERIF }}>
        리포트 로딩 중…
      </main>
    );
  }

  const domainLabel = DOMAIN_LABEL[report.domain] || "Research";
  const sectionCount = (report.sections || []).length;

  return (
    <main style={{
      height: "100vh", overflow: "auto", background: R.bg, color: R.t1,
      fontFamily: '"Pretendard Variable", Pretendard, Inter, -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif',
    }}>
      <style>{`
        .rpt-ref { transition: background .15s ease; }
        .rpt-ref:hover { background: rgba(42,40,38,.025); }
        .rpt-navlink { transition: color .15s ease, opacity .15s ease; }
        .rpt-navlink:hover { opacity: .62; }
      `}</style>

      <div style={{
        position: "sticky", top: 0, zIndex: 5, height: isNarrowReport ? "auto" : 60, minHeight: 60, display: "flex",
        alignItems: isNarrowReport ? "flex-start" : "center", justifyContent: "space-between", padding: isNarrowReport ? "10px 14px" : "0 30px",
        flexWrap: isNarrowReport ? "wrap" : "nowrap", gap: isNarrowReport ? 10 : 0,
        background: "rgba(246,244,239,.82)", backdropFilter: "blur(28px) saturate(180%)",
        WebkitBackdropFilter: "blur(28px) saturate(180%)", borderBottom: `1px solid ${R.border}`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: isNarrowReport ? 14 : 20, minHeight: 36 }}>
          <button onClick={() => nav("/")} className="rpt-navlink" style={{
            border: 0, background: "none", color: R.t3, fontFamily: LABEL, fontSize: 11.5,
            fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", cursor: "pointer", padding: 0,
          }}>
            홈
          </button>
          <button onClick={() => nav("/archive")} className="rpt-navlink" style={{
            border: 0, background: "none", color: R.emD, fontFamily: LABEL, fontSize: 11.5,
            fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", cursor: "pointer", padding: 0,
          }}>
            Archive
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: isNarrowReport ? 10 : 16, flexWrap: isNarrowReport ? "wrap" : "nowrap", justifyContent: "flex-end", minWidth: 0 }}>
          <ViewToggle value={viewMode} onChange={setViewMode} R={R} isNarrow={isNarrowReport} />
          <button onClick={() => nav("/")} style={{ border: 0, background: "none", padding: 0, cursor: "pointer", display: "inline-flex", alignItems: "center" }} aria-label="Seulgy 홈">
            <Wordmark size={22} color={R.emD} />
          </button>
        </div>
      </div>

      <div style={{
        maxWidth: 1240, margin: "0 auto", padding: isNarrowReport ? "24px clamp(12px, 4vw, 22px) 44px" : "44px 22px 64px",
        display: "grid", gridTemplateColumns: isNarrowReport ? "minmax(0, 1fr)" : "minmax(0, 1fr) 332px", gap: isNarrowReport ? 24 : 46,
      }}>
        {viewMode === "custom" ? (
          <CustomSlideView report={report} R={R} isNarrow={isNarrowReport} />
        ) : (
          <article style={{
            minWidth: 0, padding: isNarrowReport ? "clamp(24px, 6vw, 52px) clamp(20px, 5vw, 60px) clamp(26px, 6vw, 48px)" : "52px 60px 48px", borderRadius: 18, background: R.paper,
            border: `1px solid ${R.border}`, boxShadow: R.shadow,
          }}>
            {/* ── Masthead ── */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 22 }}>
              <span style={{ width: 26, height: 2, background: R.em, borderRadius: 2 }} />
              <Kicker color={R.emD}>Executive Report · {domainLabel}</Kicker>
            </div>
            <h1 style={{
              margin: "0 0 18px", fontFamily: SERIF, fontSize: isNarrowReport ? "clamp(28px, 8vw, 38px)" : 38, fontWeight: 700,
              lineHeight: 1.34, letterSpacing: "-.015em", color: R.t1, maxWidth: "20ch",
            }}>
              {report.topic}
            </h1>
            <div style={{
              display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
              paddingBottom: 30, borderBottom: `1px solid ${R.hair}`,
              fontSize: 12, color: R.t4,
            }}>
              {report.run_ts && <span style={{ fontVariantNumeric: "tabular-nums" }}>{report.run_ts}</span>}
              {report.run_ts && sectionCount > 0 && <span style={{ color: R.hair }}>·</span>}
              {sectionCount > 0 && <span>{sectionCount}개 섹션</span>}
              {references.length > 0 && <span style={{ color: R.hair }}>·</span>}
              {references.length > 0 && <span>참고 {references.length}건</span>}
            </div>

            {/* ── Executive summary (standfirst) ── */}
            {report.executive_summary && (
              <section style={{ padding: "30px 0 6px", borderLeft: `2px solid ${R.em}`, paddingLeft: 24, marginLeft: -2 }}>
                <Kicker color={R.emD} style={{ display: "block", marginBottom: 12 }}>핵심 요약</Kicker>
                <Prose text={report.executive_summary} style={{ margin: 0, fontSize: 14.5, fontWeight: 500, color: R.t2, lineHeight: 1.95 }} />
              </section>
            )}

            {/* ── Sections ── */}
            <div style={{ marginTop: 18 }}>
              {(report.sections || []).map((section) => (
                <SectionBlock key={section.index} section={section} R={R} isNarrow={isNarrowReport} />
              ))}
            </div>

            {/* ── Market insights ── */}
            {report.insights?.length > 0 && (
              <section style={{ marginTop: 44, paddingTop: 40, borderTop: `2px solid ${R.hair}` }}>
                <Kicker color={R.emD} style={{ display: "block", marginBottom: 6 }}>Market Insights</Kicker>
                <h2 style={{ margin: "0 0 8px", fontFamily: SERIF, fontSize: isNarrowReport ? "clamp(22px, 6vw, 24px)" : 24, fontWeight: 700, color: R.t1, letterSpacing: "-.01em" }}>
                  시사점
                </h2>
                <div style={{ display: "grid", gap: 0 }}>
                  {report.insights.map((insight, index) => (
                    <div key={index} style={{
                      display: "flex", gap: 18, alignItems: "flex-start",
                      padding: "22px 0", borderTop: `1px solid ${R.hair}`,
                    }}>
                      <span style={{
                        fontFamily: SERIF, fontSize: 22, fontWeight: 700, color: R.emD,
                        lineHeight: 1.1, fontVariantNumeric: "tabular-nums", flexShrink: 0, opacity: .85,
                      }}>
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <h3 style={{ margin: "2px 0 9px", fontFamily: SERIF, fontSize: 17, fontWeight: 700, color: R.t1, lineHeight: 1.45 }}>
                          {insight.title}
                        </h3>
                        <Prose text={insight.body} style={{ margin: 0, fontSize: 14, color: R.t2, lineHeight: 1.85, maxWidth: "66ch" }} />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </article>
        )}

        {/* ── Sidebar: references ── */}
        <aside style={{ position: isNarrowReport ? "static" : "sticky", top: 82, alignSelf: "start", maxHeight: isNarrowReport ? "none" : "calc(100vh - 104px)", overflow: "auto", width: "100%" }}>
          <div style={{
            padding: "20px 22px 8px", borderRadius: 16, background: R.panel,
            border: `1px solid ${R.border}`, boxShadow: R.shadow,
          }}>
            <button
              onClick={() => setRefsOpen(o => !o)}
              aria-expanded={refsOpen}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                width: "100%", margin: 0, padding: "0 0 4px", border: 0, background: "none",
                textAlign: "left", cursor: "pointer", color: R.t1,
              }}
            >
              <span style={{ display: "flex", alignItems: "baseline", gap: 9, minWidth: 0 }}>
                <Kicker color={R.t1}>참고 수치</Kicker>
                <span style={{ fontSize: 11, color: R.t4, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>
                  {references.length}
                </span>
              </span>
              <span style={{
                fontSize: 13, color: R.emD, fontWeight: 700,
                transition: "transform 0.25s ease",
                transform: refsOpen ? "rotate(90deg)" : "rotate(0deg)",
                display: "inline-block", lineHeight: 1, marginLeft: 8,
              }}>
                ›
              </span>
            </button>
            <div style={{
              maxHeight: refsOpen ? "5000px" : "0px",
              opacity: refsOpen ? 1 : 0,
              overflow: "hidden",
              transition: "max-height 0.35s ease, opacity 0.2s ease",
            }}>
              <p style={{ margin: "10px 0 6px", fontSize: 11.5, color: R.t4, lineHeight: 1.5 }}>
                본문에 사용된 링크와 근거
              </p>
              <div>
                {references.map((refItem, index) => (
                  <ReferenceCard key={`${refItem.url}-${index}`} refItem={refItem} R={R} />
                ))}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}
