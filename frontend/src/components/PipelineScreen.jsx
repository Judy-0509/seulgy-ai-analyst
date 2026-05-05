import { useState, useEffect, useRef } from "react";
import { PIPELINE_STEPS } from "../data/mock";

const API = "";

function reportAppUrl(reportUrl) {
  if (!reportUrl) return "";
  const match = reportUrl.match(/\/reports\/(.+?)_report\.html$/);
  if (match) return `/archive/${match[1]}`;
  if (reportUrl.startsWith("/report/")) return reportUrl.replace("/report/", "/archive/");
  return reportUrl;
}

/* ── Design tokens ── */
const E = {
  bg:      "#f1f0ee",
  bgGrad:  "linear-gradient(160deg,#f4f3f1 0%,#ece9e6 55%,#e3e0db 100%)",
  glass:   "rgba(248,247,245,.76)",
  glassH:  "rgba(248,247,245,.90)",
  border:  "rgba(255,255,255,.62)",
  div:     "rgba(42,40,38,.07)",
  t1:"#2a2826", t2:"#4a4744", t3:"#716f6c", t4:"#9a9896",
  em:"#10b981", emD:"#059669",
  emBg:"rgba(16,185,129,.09)", emBr:"rgba(16,185,129,.28)",
  shadow:   "0 4px 24px rgba(0,0,0,.06),0 1px 3px rgba(0,0,0,.04),inset 0 1.5px 0 rgba(255,255,255,.82)",
  shadowSm: "0 2px 10px rgba(0,0,0,.05),inset 0 1px 0 rgba(255,255,255,.78)",
};

/* ── Source config ── */
const SOURCE_CONFIG = {
  "Counterpoint Research": { short:"CP",  color:"#6366f1" },
  "TrendForce":            { short:"TF",  color:"#f59e0b" },
  "Omdia":                 { short:"OM",  color:"#10b981" },
  "IDC":                   { short:"IDC", color:"#8b5cf6" },
  "Reuters":               { short:"RT",  color:"#ef4444" },
  "Yole":                  { short:"YL",  color:"#06b6d4" },
  "Gartner":               { short:"GA",  color:"#7c3aed" },
  "Morgan Stanley":        { short:"MS",  color:"#64748b" },
  "Naver Research":        { short:"NV",  color:"#059669" },
};
function srcCfg(name) {
  return SOURCE_CONFIG[name] || { short: (name||"?").slice(0,3).toUpperCase(), color:"#64748b" };
}

/* ── Glass helpers ── */
function gl(extra={}) {
  return { background:E.glass, border:`1px solid ${E.border}`, boxShadow:E.shadow,
    backdropFilter:"blur(40px) saturate(200%)", WebkitBackdropFilter:"blur(40px) saturate(200%)",
    borderRadius:20, position:"relative", overflow:"hidden", ...extra };
}
function Gloss() {
  return <div style={{ position:"absolute", inset:0, borderRadius:"inherit", pointerEvents:"none",
    background:"linear-gradient(140deg,rgba(255,255,255,.28) 0%,rgba(255,255,255,0) 52%)", zIndex:0 }}/>;
}
function BackIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="m15 18-6-6 6-6"/>
    </svg>
  );
}
function Spinner({ size=12, color=E.em }) {
  return <div style={{ width:size, height:size, borderRadius:"50%", flexShrink:0,
    border:`2px solid ${color}44`, borderTopColor:color, animation:"spin .7s linear infinite" }}/>;
}
function DotLoader({ label="처리 중..." }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:8, padding:"8px 0" }}>
      <div style={{ display:"flex", gap:4 }}>
        {[0,1,2].map(d=>(
          <div key={d} style={{ width:4, height:4, borderRadius:"50%", background:E.em,
            animation:`pulse 1.2s ease ${d*.22}s infinite` }}/>
        ))}
      </div>
      <span style={{ fontSize:12, color:E.t4 }}>{label}</span>
    </div>
  );
}
function LogDivider() {
  return <div style={{ height:1, background:E.div, margin:"24px 0 20px",
    animation:"fadeSlideIn .3s ease both" }}/>;
}

/* ── Log atoms ── */
function StepHeader({ num, label, onOpenReferences, referenceCount = 0 }) {
  const clickable = typeof onOpenReferences === "function" && referenceCount > 0;
  return (
    <div
      onClick={clickable ? onOpenReferences : undefined}
      style={{ display:"flex", alignItems:"center", gap:10, margin:"0 0 14px",
      cursor: clickable ? "pointer" : "default",
      animation:"fadeSlideIn .35s ease both" }}>
      <span style={{ fontSize:9.5, fontWeight:800, letterSpacing:".1em", color:E.em,
        background:E.emBg, border:`1px solid ${E.emBr}`, borderRadius:7, padding:"3px 9px", flexShrink:0 }}>
        Step {num}
      </span>
      <span style={{ fontSize:13.5, fontWeight:700, color:E.t1, letterSpacing:"-.015em" }}>{label}</span>
      {clickable && (
        <span style={{ fontSize:10.5, fontWeight:700, color:E.em, background:E.emBg,
          border:`1px solid ${E.emBr}`, borderRadius:99, padding:"2px 8px", flexShrink:0 }}>
          출처 {referenceCount}개
        </span>
      )}
      <div style={{ flex:1, height:1, background:E.div }}/>
    </div>
  );
}
function ProseEntry({ text }) {
  return <p style={{ fontSize:13.5, color:E.t2, lineHeight:1.9, margin:"0 0 10px",
    animation:"fadeSlideIn .4s ease both" }}>{text}</p>;
}

function QueryList({ queries }) {
  return (
    <div style={{ margin:"16px 0 0", animation:"fadeSlideIn .4s ease both" }}>
      <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>생성된 검색 쿼리</p>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {queries.map((q,i)=>(
          <div key={i} style={{ display:"flex", alignItems:"baseline", gap:10,
            padding:"9px 12px", borderRadius:10,
            background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}`,
            animation:`fadeSlideIn .35s ease ${i*60}ms both` }}>
            <span style={{ fontSize:9.5, fontWeight:800, color:E.em,
              background:E.emBg, borderRadius:5, padding:"2px 7px", flexShrink:0 }}>Q{i+1}</span>
            <span style={{ fontSize:13, fontWeight:500, color:E.t1, flex:1, letterSpacing:".005em" }}>"{q}"</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StepLogLine({ current, fallback="", logs, open, onToggle }) {
  const hasLogs = (logs || []).length > 0;
  const canToggle = hasLogs;
  const line = current || fallback;
  if (!line && !hasLogs) return null;
  return (
    <div style={{ margin:"10px 0 0" }}>
      <div
        onClick={canToggle ? onToggle : undefined}
        style={{
          display:"flex", alignItems:"center", gap:8,
          cursor: canToggle ? "pointer" : "default",
          userSelect:"none",
        }}
      >
        <span style={{
          width:14, height:14, flexShrink:0,
          display:"inline-flex", alignItems:"center", justifyContent:"center",
          color:E.em, fontSize:16, lineHeight:1,
          transform: open ? "rotate(90deg)" : "rotate(0deg)",
          transition:"transform .18s ease",
        }}>
          ›
        </span>
        <span style={{ fontSize:12.5, color: current ? E.t2 : E.t4, lineHeight:1.45, flex:1 }}>
          {line}
        </span>
        {hasLogs && (
          <span style={{ fontSize:10.5, color:E.t4, flexShrink:0 }}>
            {open ? "접기" : `로그 ${logs.length}`}
          </span>
        )}
      </div>
      {open && hasLogs && (
        <div style={{ margin:"8px 0 0 20px", paddingLeft:10, borderLeft:`1px solid ${E.div}`, display:"grid", gap:4 }}>
          {logs.map((item, i) => (
            <div key={`${item.step || "log"}-${i}`} style={{ display:"flex", alignItems:"baseline", gap:8 }}>
              <span style={{ width:5, height:5, borderRadius:"50%", background:E.em, flexShrink:0, marginTop:6 }} />
              <span style={{ fontSize:11.8, color:E.t3, lineHeight:1.45, flex:1 }}>
                {item.text}
                {item.preview && (
                  <span style={{ display:"block", marginTop:3, whiteSpace:"pre-wrap", wordBreak:"break-word", color:E.t4 }}>
                    GLM 응답: {item.preview}
                  </span>
                )}
              </span>
              {typeof item.elapsed === "number" && (
                <span style={{ fontSize:10, color:E.t4, flexShrink:0 }}>
                  {item.elapsed}s
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GatePrompt({ message, onConfirm, confirmed, confirmLabel="확정", cancelLabel=null }) {
  return (
    <div style={{ margin:"20px 0 0", padding:"16px 20px",
      border:`1px solid ${E.emBr}`,
      background: confirmed ? "rgba(16,185,129,.06)" : "rgba(16,185,129,.07)",
      borderRadius:14, animation:"fadeSlideIn .4s ease both", transition:"background .3s" }}>
      {confirmed ? (
        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          <span style={{ color:E.em, fontWeight:800 }}>✓</span>
          <p style={{ fontSize:13, fontWeight:600, color:E.em, margin:0 }}>진행합니다...</p>
        </div>
      ) : (
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", gap:16 }}>
          <p style={{ fontSize:13, color:E.t2, margin:0, lineHeight:1.6 }}>{message}</p>
          <div style={{ display:"flex", gap:7, flexShrink:0 }}>
            <button onClick={onConfirm} style={{
              background:E.em, color:"#fff", border:"none", borderRadius:9,
              padding:"8px 22px", fontSize:13, fontWeight:700, cursor:"pointer",
              boxShadow:"0 4px 14px rgba(16,185,129,.28)", transition:"background .15s" }}
              onMouseEnter={e=>e.currentTarget.style.background=E.emD}
              onMouseLeave={e=>e.currentTarget.style.background=E.em}>
              {confirmLabel}
            </button>
            {cancelLabel && (
              <button style={{ background:"rgba(42,40,38,.07)", color:E.t2,
                border:`1px solid ${E.div}`, borderRadius:9, padding:"8px 16px",
                fontSize:13, fontWeight:500, cursor:"pointer" }}>
                {cancelLabel}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Stage D/EF section progress list ── */
function DSectionList({ sections, label="섹션별 검색 진행" }) {
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>{label}</p>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {sections.map((sec, i) => (
          <div key={i} style={{
            display:"flex", alignItems:"center", gap:12,
            padding:"10px 14px", borderRadius:10,
            background: sec.status==="done" ? "rgba(16,185,129,.05)" : "rgba(42,40,38,.04)",
            border:`1px solid ${sec.status==="done" ? E.emBr : E.div}`,
            animation:`fadeSlideIn .35s ease ${i*60}ms both`,
            transition:"background .3s, border-color .3s",
          }}>
            <span style={{ fontSize:9.5, fontWeight:800, color:E.em, background:E.emBg,
              borderRadius:5, padding:"2px 7px", flexShrink:0 }}>{i+1}</span>
            <span style={{ fontSize:14, fontWeight:600, color:E.t2, flex:1 }}>{sec.title}</span>
            {sec.status==="done"                                           && <span style={{ fontSize:12, color:E.em, fontWeight:700, flexShrink:0 }}>✓</span>}
            {(sec.status==="searching"||sec.status==="analyzing")          && <Spinner size={10}/>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── TOC section list (Gate 1) ── */
function TocSections({ sections, onToggle, disabled }) {
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>생성된 목차 및 섹션별 검색어</p>
      <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
        {sections.map((sec, i) => {
          const queries  = sec.queries || [];
          const included = sec.included?.length ? sec.included : queries.map(() => true);
          const activeCount = included.filter(Boolean).length;
          return (
            <div key={i} style={{ padding:"12px 14px", borderRadius:10,
              background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}`,
              animation:`fadeSlideIn .35s ease ${i*60}ms both` }}>
              <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom: sec.angle ? 4 : 0 }}>
                <span style={{ fontSize:9.5, fontWeight:800, color:E.em, background:E.emBg,
                  borderRadius:5, padding:"2px 7px", flexShrink:0 }}>{i+1}</span>
                <span style={{ fontSize:14, fontWeight:700, color:E.t1, flex:1 }}>{sec.title}</span>
                {queries.length > 0 && (
                  <span style={{ fontSize:10, color:E.t4, flexShrink:0 }}>
                    검색어 <strong style={{ color:E.em }}>{activeCount}</strong>/{queries.length}개 활성
                  </span>
                )}
              </div>
              {sec.angle && (
                <p style={{ fontSize:12, color:E.t3, margin:"0 0 8px 27px", lineHeight:1.5 }}>{sec.angle}</p>
              )}
              {queries.length > 0 && (
                <div style={{ display:"flex", flexDirection:"column", gap:4, marginTop:6, paddingLeft:27 }}>
                  {queries.map((q, qi) => {
                    const on = included[qi] !== false;
                    return (
                      <div key={qi}
                        onClick={() => !disabled && onToggle(i, qi)}
                        style={{ display:"flex", alignItems:"center", gap:8,
                          padding:"6px 10px", borderRadius:7,
                          background: on ? "rgba(16,185,129,.06)" : "rgba(42,40,38,.04)",
                          border:`1px solid ${on ? E.emBr : E.div}`,
                          cursor: disabled ? "default" : "pointer",
                          opacity: on ? 1 : 0.5,
                          transition:"background .2s, border-color .2s, opacity .2s" }}>
                        <div style={{ width:14, height:14, borderRadius:4, flexShrink:0,
                          border:`1.5px solid ${on ? E.em : E.t4}`,
                          background: on ? E.em : "transparent",
                          display:"flex", alignItems:"center", justifyContent:"center",
                          transition:"background .15s, border-color .15s" }}>
                          {on && <span style={{ fontSize:9, color:"#fff", fontWeight:800, lineHeight:1 }}>✓</span>}
                        </div>
                        <span style={{ fontSize:13, fontWeight:500, color: on ? E.t1 : E.t3, flex:1, lineHeight:1.4 }}>"{q}"</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Archive log rows ── */
function ArchiveLog({ visibleSources, doneSources, selectedSource, onSelect, bySource }) {
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>아카이브 검색 결과</p>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {visibleSources.map((name) => {
          const isDone = doneSources.includes(name);
          const isSel  = selectedSource === name;
          const cfg    = srcCfg(name);
          const count  = (bySource[name] || []).length;
          return (
            <div key={name}
              onClick={() => isDone && onSelect(isSel ? null : name)}
              style={{
                display:"flex", alignItems:"center", gap:12,
                padding:"10px 14px", borderRadius:10,
                background: isSel ? `${cfg.color}14` : isDone ? "rgba(16,185,129,.05)" : "rgba(42,40,38,.04)",
                border:`1px solid ${isSel ? cfg.color+"66" : isDone ? E.emBr : E.div}`,
                cursor: isDone ? "pointer" : "default",
                transition:"background .25s, border-color .25s",
                animation:"fadeSlideIn .35s ease both",
              }}
              onMouseEnter={e=>{ if(isDone&&!isSel) e.currentTarget.style.background=`${cfg.color}0e`; }}
              onMouseLeave={e=>{ if(isDone&&!isSel) e.currentTarget.style.background="rgba(16,185,129,.05)"; }}>
              <div style={{ width:34, height:34, borderRadius:10, flexShrink:0,
                display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:10, fontWeight:800, color:"#fff", background:cfg.color,
                boxShadow:`0 3px 10px ${cfg.color}44` }}>{cfg.short}</div>
              <span style={{ flex:1, fontSize:14, fontWeight:700, color:E.t1 }}>{name}</span>
              {isDone ? (
                <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                  <div style={{ display:"flex", alignItems:"baseline", gap:4 }}>
                    <span style={{ fontSize:16, fontWeight:800, color:cfg.color, letterSpacing:"-.03em" }}>{count}</span>
                    <span style={{ fontSize:11, color:E.t3 }}>건</span>
                  </div>
                  <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
                    stroke={isSel ? cfg.color : E.t4} strokeWidth="2.5"
                    strokeLinecap="round" strokeLinejoin="round"
                    style={{ transform: isSel?"rotate(90deg)":"rotate(0deg)", transition:"transform .25s" }}>
                    <path d="m9 18 6-6-6-6"/>
                  </svg>
                </div>
              ) : (
                <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                  <Spinner size={11} color={cfg.color}/>
                  <span style={{ fontSize:12, color:E.t4 }}>검색 중...</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Archive detail panel ── */
function ArchiveDetail({ name, articles, totalCount, onClose }) {
  const cfg = srcCfg(name);
  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%" }}>
      <div style={{ display:"flex", alignItems:"center", gap:12, padding:"20px 20px 16px",
        borderBottom:`1px solid ${E.div}`, flexShrink:0 }}>
        <div style={{ width:40, height:40, borderRadius:12, flexShrink:0,
          display:"flex", alignItems:"center", justifyContent:"center",
          fontSize:11, fontWeight:800, color:"#fff", background:cfg.color,
          boxShadow:`0 4px 14px ${cfg.color}44` }}>{cfg.short}</div>
        <div style={{ flex:1, minWidth:0 }}>
          <h3 style={{ fontSize:15, fontWeight:700, color:E.t1, margin:0, letterSpacing:"-.015em" }}>{name}</h3>
          <p style={{ fontSize:11, color:E.t3, margin:0 }}>
            총 <strong style={{ color:E.t2 }}>{totalCount}건</strong> 발견
            &nbsp;·&nbsp;유사도 상위 <strong style={{ color:E.em }}>{articles.length}건</strong> 표시
          </p>
        </div>
        <button onClick={onClose} style={{ width:28, height:28, borderRadius:"50%", border:"none",
          background:"rgba(42,40,38,.08)", color:E.t3, cursor:"pointer",
          display:"flex", alignItems:"center", justifyContent:"center",
          fontSize:14, fontWeight:600, flexShrink:0, transition:"background .15s" }}
          onMouseEnter={e=>e.currentTarget.style.background="rgba(42,40,38,.14)"}
          onMouseLeave={e=>e.currentTarget.style.background="rgba(42,40,38,.08)"}>×</button>
      </div>

      <div style={{ margin:"12px 16px 0", padding:"9px 12px", borderRadius:10,
        background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}`,
        display:"flex", alignItems:"flex-start", gap:8 }}>
        <span style={{ fontSize:13, flexShrink:0, marginTop:1 }}>ℹ️</span>
        <p style={{ fontSize:11, color:E.t3, margin:0, lineHeight:1.6 }}>
          이 단계는 <strong style={{ color:E.t2 }}>메타데이터(제목·URL) 전용 스캔</strong>입니다.
          본문은 읽지 않으며, 목차 설계 인풋으로만 활용됩니다.
          실제 인용 출처는 <strong style={{ color:E.t2 }}>Step 5 섹션별 검색</strong>에서 확정됩니다.
        </p>
      </div>

      <div style={{ flex:1, overflowY:"auto", padding:"16px 20px 24px" }}>
        <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
          textTransform:"uppercase", margin:"0 0 10px" }}>수집된 리포트</p>
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {articles.map((a,i)=>(
            <div key={i}
              onClick={()=> a.url && window.open(a.url,"_blank","noopener,noreferrer")}
              style={{ padding:"12px 14px", borderRadius:12,
                background:E.glass, border:`1px solid ${E.border}`,
                boxShadow:E.shadowSm, cursor: a.url ? "pointer" : "default",
                transition:"background .18s, box-shadow .18s",
                animation:`fadeSlideIn .35s ease ${i*60}ms both` }}
              onMouseEnter={e=>{ if(a.url){ e.currentTarget.style.background=E.glassH; e.currentTarget.style.boxShadow=E.shadow; }}}
              onMouseLeave={e=>{ e.currentTarget.style.background=E.glass; e.currentTarget.style.boxShadow=E.shadowSm; }}>
              <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", gap:8 }}>
                <p style={{ fontSize:13, fontWeight:600, color:E.t1, margin:0, lineHeight:1.45, flex:1 }}>
                  {a.title || a.url}
                </p>
                {a.url && (
                  <svg width={11} height={11} viewBox="0 0 24 24" fill="none"
                    stroke={E.t4} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
                    style={{ flexShrink:0, marginTop:2 }}>
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                  </svg>
                )}
              </div>
              {a.url && (
                <p style={{ fontSize:11, color:E.t4, margin:"5px 0 0",
                  overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{a.url}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ReferenceDetail({ name, articles, totalCount, onClose, note, subtitle }) {
  const cfg = srcCfg(name);
  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%" }}>
      <div style={{ display:"flex", alignItems:"center", gap:12, padding:"20px 20px 16px",
        borderBottom:`1px solid ${E.div}`, flexShrink:0 }}>
        <div style={{ width:40, height:40, borderRadius:12, flexShrink:0,
          display:"flex", alignItems:"center", justifyContent:"center",
          fontSize:11, fontWeight:800, color:"#fff", background:cfg.color,
          boxShadow:`0 4px 14px ${cfg.color}44` }}>{cfg.short}</div>
        <div style={{ flex:1, minWidth:0 }}>
          <h3 style={{ fontSize:15, fontWeight:700, color:E.t1, margin:0, letterSpacing:"-.015em" }}>{name}</h3>
          <p style={{ fontSize:11, color:E.t3, margin:0 }}>
            {subtitle || <>총 <strong style={{ color:E.t2 }}>{totalCount}건</strong> 중 <strong style={{ color:E.em }}>{articles.length}건</strong> 표시</>}
          </p>
        </div>
        <button onClick={onClose} style={{ width:28, height:28, borderRadius:"50%", border:"none",
          background:"rgba(42,40,38,.08)", color:E.t3, cursor:"pointer",
          display:"flex", alignItems:"center", justifyContent:"center",
          fontSize:14, fontWeight:600, flexShrink:0, transition:"background .15s" }}
          onMouseEnter={e=>e.currentTarget.style.background="rgba(42,40,38,.14)"}
          onMouseLeave={e=>e.currentTarget.style.background="rgba(42,40,38,.08)"}>×</button>
      </div>

      <div style={{ margin:"12px 16px 0", padding:"9px 12px", borderRadius:10,
        background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}`,
        display:"flex", alignItems:"flex-start", gap:8 }}>
        <span style={{ width:16, height:16, borderRadius:4, background:"#dbeafe", color:"#2563eb",
          display:"inline-flex", alignItems:"center", justifyContent:"center",
          fontSize:11, fontWeight:800, flexShrink:0, marginTop:1 }}>i</span>
        <p style={{ fontSize:11, color:E.t3, margin:0, lineHeight:1.6 }}>
          {note || <>이 단계는 <strong style={{ color:E.t2 }}>메타데이터(제목·URL) 중심 참고 목록</strong>입니다. 본문에 실제 인용되는 출처는 이후 섹션별 분석에서 확정됩니다.</>}
        </p>
      </div>

      <div style={{ flex:1, overflowY:"auto", padding:"16px 20px 24px" }}>
        <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
          textTransform:"uppercase", margin:"0 0 10px" }}>수집된 리포트</p>
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {articles.map((a,i)=>(
            <div key={`${a.url || a.title || "ref"}-${i}`}
              onClick={()=> a.url && window.open(a.url,"_blank","noopener,noreferrer")}
              style={{ padding:"12px 14px", borderRadius:12,
                background:E.glass, border:`1px solid ${E.border}`,
                boxShadow:E.shadowSm, cursor: a.url ? "pointer" : "default",
                transition:"background .18s, box-shadow .18s",
                animation:`fadeSlideIn .35s ease ${Math.min(i, 12)*35}ms both` }}
              onMouseEnter={e=>{ if(a.url){ e.currentTarget.style.background=E.glassH; e.currentTarget.style.boxShadow=E.shadow; }}}
              onMouseLeave={e=>{ e.currentTarget.style.background=E.glass; e.currentTarget.style.boxShadow=E.shadowSm; }}>
              <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", gap:8 }}>
                {a.section && (
                  <span style={{ fontSize:9, fontWeight:800, color:E.em, background:E.emBg,
                    borderRadius:4, padding:"2px 6px", flexShrink:0, marginTop:1 }}>
                    {a.section}
                  </span>
                )}
                <p style={{ fontSize:13, fontWeight:600, color:E.t1, margin:0, lineHeight:1.45, flex:1 }}>
                  {a.title || a.url}
                </p>
                {a.url && (
                  <svg width={11} height={11} viewBox="0 0 24 24" fill="none"
                    stroke={E.t4} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
                    style={{ flexShrink:0, marginTop:2 }}>
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                  </svg>
                )}
              </div>
              {a.source && <p style={{ fontSize:11, color:E.t3, margin:"5px 0 0" }}>{a.source}</p>}
              {a.url && (
                <p style={{ fontSize:11, color:E.t4, margin:"5px 0 0",
                  overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{a.url}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Gate 2 results accordion ── */
function Gate2Sections({ sections, onSectionSelect }) {
  const total = sections.reduce((a,s) => a + (s.results?.length || 0), 0);
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>섹션별 검색 결과 ({total}건) — 섹션 클릭 시 상세 확인</p>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {sections.map((sec, i) => {
          const isOpen = false;
          const count  = sec.results?.length || 0;
          return (
            <div key={i} style={{ borderRadius:10, overflow:"hidden",
              background:"rgba(42,40,38,.04)",
              border:`1px solid ${E.div}`,
              transition:"background .2s, border-color .2s",
              animation:`fadeSlideIn .35s ease ${i*60}ms both` }}>

              {/* 헤더 (클릭 → 펼침/접힘) */}
              <div onClick={() => onSectionSelect?.(sec, i)}
                style={{ display:"flex", alignItems:"center", gap:8,
                  padding:"10px 14px", cursor:"pointer" }}>
                <span style={{ fontSize:9.5, fontWeight:800, color:E.em, background:E.emBg,
                  borderRadius:5, padding:"2px 7px", flexShrink:0 }}>{i+1}</span>
                <span style={{ fontSize:14, fontWeight:700, color:E.t1, flex:1 }}>{sec.title}</span>
                <span style={{ fontSize:11, fontWeight:700,
                  color: count > 0 ? E.em : E.t4, flexShrink:0 }}>{count}건</span>
                <svg width={12} height={12} viewBox="0 0 24 24" fill="none"
                  stroke={E.t4} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                  style={{ flexShrink:0 }}>
                  <path d="m9 18 6-6-6-6"/>
                </svg>
              </div>

              {/* 펼쳐진 결과 목록 */}
              {isOpen && (
                <div style={{ padding:"0 14px 12px", display:"flex", flexDirection:"column", gap:4 }}>
                  {count === 0
                    ? <p style={{ fontSize:13, color:E.t4, margin:0, paddingLeft:27 }}>검색 결과 없음</p>
                    : sec.results.map((r, j) => {
                        const cfg = srcCfg(r.source);
                        return (
                          <div key={j} style={{ display:"flex", alignItems:"baseline", gap:8,
                            padding:"7px 10px", borderRadius:7,
                            background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}`,
                            animation:`fadeSlideIn .25s ease ${j*40}ms both` }}>
                            <span style={{ fontSize:9, fontWeight:800, color:"#fff",
                              background:cfg.color, borderRadius:4, padding:"2px 6px",
                              flexShrink:0, letterSpacing:".02em" }}>{cfg.short}</span>
                            <span style={{ fontSize:13, color:E.t2, lineHeight:1.4, flex:1 }}>
                              {r.title || "(제목 없음)"}
                            </span>
                          </div>
                        );
                      })
                  }
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Report done ── */
function ReportDone({ reportUrl }) {
  const appUrl = reportAppUrl(reportUrl);
  return (
    <div style={{ margin:"20px 0 0", padding:"20px 24px",
      border:`1px solid ${E.emBr}`, background:"rgba(16,185,129,.07)",
      borderRadius:14, animation:"fadeSlideIn .4s ease both" }}>
      <p style={{ fontSize:13, fontWeight:700, color:E.em, margin:"0 0 6px" }}>✓ 보고서 생성 완료</p>
      <p style={{ fontSize:13, color:E.t2, margin:"0 0 14px", lineHeight:1.6 }}>
        분석이 완료되었습니다. 보고서를 확인하세요.
      </p>
      <a href={appUrl} target="_blank" rel="noopener noreferrer"
        style={{ display:"inline-flex", alignItems:"center", gap:6,
          background:E.em, color:"#fff", borderRadius:9,
          padding:"9px 22px", fontSize:13, fontWeight:700,
          boxShadow:"0 4px 14px rgba(16,185,129,.28)", textDecoration:"none" }}>
        보고서 열기 →
      </a>
    </div>
  );
}

/* ── Error panel ── */
function ErrorPanel({ message }) {
  return (
    <div style={{ margin:"20px 0 0", padding:"16px 20px",
      border:"1px solid rgba(239,68,68,.4)", background:"rgba(239,68,68,.07)",
      borderRadius:14, animation:"fadeSlideIn .4s ease both" }}>
      <p style={{ fontSize:13, fontWeight:700, color:"#ef4444", margin:"0 0 4px" }}>오류 발생</p>
      <p style={{ fontSize:13, color:E.t3, margin:0, whiteSpace:"pre-wrap", lineHeight:1.6 }}>{message}</p>
    </div>
  );
}

/* ── Header ── */
function Header({ topic, onBack, completedSteps, totalSteps, isRunning }) {
  const pct = Math.round((completedSteps/totalSteps)*100);
  const ts = new Date().toLocaleString("ko-KR",{ month:"long",day:"numeric",hour:"2-digit",minute:"2-digit" });
  return (
    <header style={{ position:"relative", zIndex:20, flexShrink:0, height:64,
      display:"flex", alignItems:"center", justifyContent:"space-between", padding:"0 28px",
      background:"rgba(241,240,238,.90)", backdropFilter:"blur(40px) saturate(180%)",
      WebkitBackdropFilter:"blur(40px) saturate(180%)", borderBottom:`1px solid ${E.div}`,
      boxShadow:"0 1px 0 rgba(255,255,255,.8),0 2px 8px rgba(0,0,0,.04)" }}>
      <div style={{ display:"flex", alignItems:"center", gap:16 }}>
        <button onClick={onBack}
          style={{ display:"flex", alignItems:"center", gap:5, fontSize:13, fontWeight:600,
            color:E.t3, background:"none", border:"none", cursor:"pointer", padding:0, transition:"color .15s" }}
          onMouseEnter={e=>e.currentTarget.style.color=E.t1}
          onMouseLeave={e=>e.currentTarget.style.color=E.t3}>
          <BackIcon/> 홈
        </button>
        <div style={{ width:1, height:22, background:E.div }}/>
        <img src="/logo-mark.png" alt="Canopy" style={{ width:52, height:38, display:"block", objectFit:"contain", flexShrink:0 }} />
        <div>
          <h1 style={{ fontSize:14, fontWeight:700, color:E.t1, margin:0, letterSpacing:"-.02em",
            maxWidth:480, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{topic}</h1>
          <p style={{ fontSize:11, color:E.t4, margin:0 }}>{ts} · Research Helper</p>
        </div>
      </div>
      <div style={{ display:"flex", alignItems:"center", gap:12 }}>
        {isRunning && (
          <span style={{ display:"flex", alignItems:"center", gap:6, fontSize:11, fontWeight:700,
            color:E.em, background:E.emBg, border:`1px solid ${E.emBr}`, borderRadius:99, padding:"5px 12px" }}>
            <Spinner/> 분석 진행 중
          </span>
        )}
        <span style={{ fontSize:12, fontWeight:600, color:E.t3 }}>{completedSteps}/{totalSteps} 완료</span>
        <div style={{ width:88, height:4, borderRadius:99, background:E.div, overflow:"hidden" }}>
          <div style={{ height:"100%", width:`${pct}%`, borderRadius:99, background:E.em, transition:"width .4s ease" }}/>
        </div>
      </div>
    </header>
  );
}

/* ── Sidebar ── */
function Sidebar({ steps, currentStepIdx, completedSteps, totalSteps }) {
  return (
    <aside style={{ width:288, flexShrink:0, overflowY:"auto",
      borderRight:`1px solid ${E.div}`, background:"rgba(244,243,241,.72)",
      backdropFilter:"blur(40px) saturate(180%)", WebkitBackdropFilter:"blur(40px) saturate(180%)",
      padding:"18px 14px", position:"relative", zIndex:10 }}>
      <div style={{ ...gl({ padding:"16px 18px", marginBottom:14,
        border:`1px solid ${E.emBr}`, background:"rgba(16,185,129,.07)", boxShadow:E.shadowSm }) }}>
        <Gloss/>
        <div style={{ position:"relative", zIndex:1 }}>
          <p style={{ fontSize:9, fontWeight:800, letterSpacing:".16em", color:E.em,
            margin:"0 0 10px", textTransform:"uppercase" }}>Research Timeline</p>
          <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", gap:8 }}>
            <div>
              <h2 style={{ fontSize:15, fontWeight:700, color:E.t1, margin:"0 0 3px" }}>전체 진행 단계</h2>
              <p style={{ fontSize:11, color:E.t3, margin:0 }}>검색부터 요약까지의 에이전트 흐름</p>
            </div>
            <div style={{ textAlign:"center", flexShrink:0, border:`1px solid ${E.emBr}`,
              background:E.emBg, borderRadius:12, padding:"6px 10px", boxShadow:E.shadowSm }}>
              <p style={{ fontSize:16, fontWeight:800, color:E.em, margin:0 }}>{completedSteps}/{totalSteps}</p>
              <p style={{ fontSize:9, color:E.t3, margin:0 }}>완료</p>
            </div>
          </div>
          <div style={{ marginTop:12, height:3, borderRadius:99, background:E.div, overflow:"hidden" }}>
            <div style={{ height:"100%", borderRadius:99, background:E.em,
              width:`${Math.round((completedSteps/totalSteps)*100)}%`, transition:"width .4s ease" }}/>
          </div>
        </div>
      </div>
      <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
        {steps.map((step,i)=>{
          const isActive = currentStepIdx===i || step.status==="running";
          const isDone   = step.status==="done";
          const isGate   = step.type==="gate";
          return (
            <div key={step.id} style={{ ...gl({ padding:"9px 11px", borderRadius:14,
              border:`1px solid ${isActive?E.emBr:E.border}`,
              background:isActive?"rgba(16,185,129,.08)":isDone?"rgba(16,185,129,.04)":E.glass,
              boxShadow:isActive?`0 2px 12px rgba(16,185,129,.14),inset 0 1px 0 rgba(255,255,255,.8)`:E.shadowSm,
              transition:"background .3s, border-color .3s" }) }}>
              <Gloss/>
              <div style={{ position:"relative", zIndex:1, display:"flex", alignItems:"center", gap:9 }}>
                <div style={{ width:28, height:28, borderRadius:9, flexShrink:0,
                  display:"flex", alignItems:"center", justifyContent:"center",
                  fontSize:isDone?13:10, fontWeight:800,
                  background:isDone||isActive?E.em:"rgba(42,40,38,.07)",
                  color:isDone||isActive?"#fff":E.t3,
                  boxShadow:isActive||isDone?"0 2px 8px rgba(16,185,129,.3)":"none",
                  transition:"background .3s" }}>
                  {isDone?"✓":String(i+1).padStart(2,"0")}
                </div>
                <div style={{ minWidth:0, flex:1 }}>
                  <div style={{ display:"flex", alignItems:"center", gap:5, marginBottom:2 }}>
                    <p style={{ fontSize:12, fontWeight:600, margin:0,
                      color:isActive?E.em:isDone?E.em:E.t1, letterSpacing:"-.01em",
                      overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{step.label}</p>
                    {isGate&&<span style={{ fontSize:8, fontWeight:800, flexShrink:0,
                      color:E.em, background:E.emBg, border:`1px solid ${E.emBr}`,
                      borderRadius:99, padding:"1px 6px" }}>USER</span>}
                  </div>
                  <div style={{ display:"flex", alignItems:"center", gap:5 }}>
                    {step.status==="running"
                      ?<Spinner size={10}/>
                      :<div style={{ width:5, height:5, borderRadius:"50%", flexShrink:0,
                          background:isDone?E.em:E.t4, transition:"background .3s" }}/>}
                    <span style={{ fontSize:11, color:E.t4 }}>
                      {step.status==="running"?"진행 중":isDone?"완료":"대기 중"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}

/* ── External search toggle card ── */
function ExtSearchToggle({ totalArchive, queries, useExternal, onToggle, onConfirm, confirmed }) {
  const suggest = totalArchive < 15;
  return (
    <div style={{ margin:"16px 0 0", padding:"18px 22px", borderRadius:14,
      border:`1px solid ${suggest && !confirmed ? "rgba(245,158,11,.4)" : confirmed ? E.div : useExternal ? E.emBr : E.div}`,
      background: confirmed ? "rgba(42,40,38,.04)" : suggest ? "rgba(245,158,11,.04)" : "rgba(42,40,38,.04)",
      animation:"fadeSlideIn .4s ease both", transition:"background .3s, border-color .3s" }}>
      {confirmed ? (
        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          <span style={{ color:E.em, fontWeight:800 }}>✓</span>
          <p style={{ fontSize:13, fontWeight:600, color:E.em, margin:0 }}>
            {useExternal ? "외부 검색 포함하여 진행합니다..." : "아카이브 결과만으로 진행합니다."}
          </p>
        </div>
      ) : (
        <>
          {suggest && (
            <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:12,
              padding:"8px 12px", borderRadius:8, background:"rgba(245,158,11,.08)",
              border:"1px solid rgba(245,158,11,.28)" }}>
              <span style={{ fontSize:13, flexShrink:0 }}>⚠</span>
              <p style={{ fontSize:12, color:"#92400e", margin:0 }}>
                아카이브 결과가 <strong>{totalArchive}건</strong>으로 적습니다. 외부 검색 포함을 권장합니다.
              </p>
            </div>
          )}
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", gap:16 }}>
            <div>
              <p style={{ fontSize:13, fontWeight:700, color:E.t1, margin:"0 0 3px" }}>
                외부 검색 포함 (RSS + DuckDuckGo)
              </p>
              <p style={{ fontSize:12, color:E.t3, margin:0 }}>
                아카이브에 없는 최신 기사를 보완합니다 · 추가 소요 약 10~20초
              </p>
            </div>
            <div onClick={onToggle} style={{ cursor:"pointer", flexShrink:0 }}>
              <div style={{ width:44, height:24, borderRadius:12, position:"relative",
                background: useExternal ? E.em : "rgba(42,40,38,.15)", transition:"background .2s" }}>
                <div style={{ position:"absolute", top:2, left: useExternal ? 22 : 2,
                  width:20, height:20, borderRadius:"50%", background:"#fff",
                  boxShadow:"0 1px 4px rgba(0,0,0,.2)", transition:"left .2s" }}/>
              </div>
            </div>
          </div>
          <div style={{ marginTop:12, padding:"10px 14px", borderRadius:10,
            background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}` }}>
            <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
              textTransform:"uppercase", margin:"0 0 6px" }}>사용할 검색어 ({queries.length}개)</p>
            <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
              {queries.map((q, i) => (
                <div key={i} style={{ display:"flex", gap:8, alignItems:"baseline" }}>
                  <span style={{ fontSize:9, fontWeight:800, color:E.em, background:E.emBg,
                    borderRadius:4, padding:"1px 5px", flexShrink:0 }}>Q{i+1}</span>
                  <span style={{ fontSize:13, color:E.t2 }}>"{q}"</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display:"flex", justifyContent:"flex-end", marginTop:14 }}>
            <button onClick={onConfirm} style={{
              background: useExternal ? E.em : "rgba(42,40,38,.09)",
              color: useExternal ? "#fff" : E.t2,
              border:`1px solid ${useExternal ? "transparent" : E.div}`,
              borderRadius:9, padding:"8px 22px", fontSize:13, fontWeight:700,
              cursor:"pointer", transition:"background .15s, color .15s",
              boxShadow: useExternal ? "0 4px 14px rgba(16,185,129,.28)" : "none" }}>
              {useExternal ? "외부 검색 포함하여 진행 →" : "아카이브만으로 진행 →"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/* ── External search results view (panel style) ── */
function ExtSourceLog({ queries, bySource, total, onOpenAll, onOpenSource }) {
  const names = Object.keys(bySource);
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>외부 검색 결과</p>
      <div style={{ marginBottom:10, padding:"9px 14px", borderRadius:10,
        background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}` }}>
        <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
          textTransform:"uppercase", margin:"0 0 6px" }}>사용된 검색어</p>
        <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
          {queries.map((q, i) => (
            <div key={i} style={{ display:"flex", gap:8, alignItems:"baseline" }}>
              <span style={{ fontSize:9, fontWeight:800, color:E.em, background:E.emBg,
                borderRadius:4, padding:"1px 5px", flexShrink:0 }}>Q{i+1}</span>
              <span style={{ fontSize:13, color:E.t2 }}>"{q}"</span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {names.map((name) => {
          const cfg = srcCfg(name);
          const count = (bySource[name] || []).length;
          return (
            <div key={name}
              onClick={() => onOpenSource(name)}
              style={{
                display:"flex", alignItems:"center", gap:12,
                padding:"10px 14px", borderRadius:10,
                background:"rgba(16,185,129,.05)",
                border:`1px solid ${E.emBr}`,
                cursor:"pointer",
                transition:"background .25s, border-color .25s",
                animation:"fadeSlideIn .35s ease both",
              }}
              onMouseEnter={e=>{ e.currentTarget.style.background=`${cfg.color}0e`; e.currentTarget.style.borderColor=`${cfg.color}66`; }}
              onMouseLeave={e=>{ e.currentTarget.style.background="rgba(16,185,129,.05)"; e.currentTarget.style.borderColor=E.emBr; }}>
              <div style={{ width:34, height:34, borderRadius:10, flexShrink:0,
                display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:10, fontWeight:800, color:"#fff", background:cfg.color,
                boxShadow:`0 3px 10px ${cfg.color}44` }}>{cfg.short}</div>
              <span style={{ flex:1, fontSize:14, fontWeight:700, color:E.t1 }}>{name}</span>
              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                <div style={{ display:"flex", alignItems:"baseline", gap:4 }}>
                  <span style={{ fontSize:16, fontWeight:800, color:cfg.color, letterSpacing:"-.03em" }}>{count}</span>
                  <span style={{ fontSize:11, color:E.t3 }}>건</span>
                </div>
                <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
                  stroke={E.t4} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m9 18 6-6-6-6"/>
                </svg>
              </div>
            </div>
          );
        })}
      </div>
      {total > 0 && (
        <button
          type="button"
          onClick={onOpenAll}
          style={{ marginTop:10, border:`1px solid ${E.emBr}`, background:E.emBg, color:E.em,
            borderRadius:99, padding:"4px 9px", fontSize:11, fontWeight:700,
            cursor:"pointer", display:"block" }}
        >
          전체 결과 보기 ({total}건)
        </button>
      )}
      <p style={{ fontSize:13, fontWeight:600, color:E.em, margin:"12px 0 0",
        animation:"fadeSlideIn .4s ease both" }}>
        외부 검색 완료 — {total}건 추가 ({names.length}개 소스)
      </p>
    </div>
  );
}

/* ── MetricCards ── */
function MetricCards({ queryCount, totalArchive, sectionCount, sourceCount }) {
  const items = [
    { value: queryCount  > 0 ? `${queryCount}개`  : "—", label:"생성된 쿼리" },
    { value: totalArchive> 0 ? `${totalArchive}건`: "—", label:"수집 자료" },
    { value: sectionCount> 0 ? `${sectionCount}개`: "—", label:"분석 목차" },
    { value: sourceCount > 0 ? `${sourceCount}곳` : "—", label:"출처 기관" },
  ];
  return (
    <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10, marginBottom:12 }}>
      {items.map(m=>(
        <div key={m.label} style={{ ...gl({ padding:"16px 20px", textAlign:"center", boxShadow:E.shadowSm }) }}>
          <Gloss/>
          <div style={{ position:"relative", zIndex:1 }}>
            <p style={{ fontSize:26, fontWeight:800, color:m.value!=="—"?E.em:E.t4,
              margin:"0 0 4px", letterSpacing:"-.04em", transition:"color .4s" }}>{m.value}</p>
            <p style={{ fontSize:11, color:E.t3, margin:0, fontWeight:500 }}>{m.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const STEP_LOG_KEYS = ["step01", "step02", "step02b", "step03", "step04", "step05", "step06", "step07", "step08"];

function initStepMap(value) {
  return Object.fromEntries(STEP_LOG_KEYS.map((key) => [key, value]));
}

/* ══════════════════════════════════════════════════════════
   Main
══════════════════════════════════════════════════════════ */
export default function PipelineScreen({ topic, onBack, topicInfo = null }) {
  const [started, setStarted] = useState(!topicInfo?.rationale);
  const [steps, setSteps] = useState(() =>
    PIPELINE_STEPS.map((s,i) => ({...s, status: (!topicInfo?.rationale && i===0) ? "running" : "pending"}))
  );
  const [phase,          setPhase]          = useState(topicInfo?.rationale ? "idle" : "loading");
  const [queries,        setQueries]        = useState([]);
  const [bySource,       setBySource]       = useState({});
  const [totalArchive,   setTotalArchive]   = useState(0);
  const [visibleSources, setVisibleSources] = useState([]);
  const [doneSources,    setDoneSources]    = useState([]);
  const [selectedSource, setSelectedSource] = useState(null);
  const [referenceDetail, setReferenceDetail] = useState(null);
  const [gate1Sections,  setGate1Sections]  = useState(null);
  const [gate1Done,      setGate1Done]      = useState(false);
  const [gate2Sections,  setGate2Sections]  = useState(null);
  const [gate2Done,      setGate2Done]      = useState(false);
  const [dSections,      setDSections]      = useState([]);
  const [efSections,     setEfSections]     = useState([]);
  const [useExternal,     setUseExternal]     = useState(false);
  const [extDecisionDone, setExtDecisionDone] = useState(false);
  const [extBySource,     setExtBySource]     = useState({});
  const [extQueries,      setExtQueries]      = useState([]);
  const [extTotal,        setExtTotal]        = useState(0);
  const [reportUrl,      setReportUrl]      = useState(null);
  const [error,          setError]          = useState(null);
  const [statusText,     setStatusText]     = useState(topicInfo?.rationale ? "분석 시작 대기 중" : "서버 연결 중...");
  const [elapsedSec,     setElapsedSec]     = useState(0);
  const [stepLogs,       setStepLogs]       = useState(() => initStepMap([]));
  const [stepCurrents,   setStepCurrents]   = useState(() => initStepMap(""));
  const [stepOpen,       setStepOpen]       = useState(() => initStepMap(false));

  /* refs for stable access inside async handlers */
  const sessionRef       = useRef(null);
  const gate1SectionsRef = useRef(null);
  const gate2SectionsRef = useRef(null);
  const logEndRef        = useRef(null);

  /* 탭 닫기 / 새로고침 시 서버 파이프라인 취소 */
  useEffect(() => {
    const onPageHide = () => {
      const sid = sessionRef.current;
      if (sid) navigator.sendBeacon(`${API}/api/report/cancel/${sid}`);
    };
    window.addEventListener("pagehide", onPageHide);
    return () => window.removeEventListener("pagehide", onPageHide);
  }, []);

  /* keep ref in sync when user toggles queries */
  useEffect(() => { gate1SectionsRef.current = gate1Sections; }, [gate1Sections]);

  const appendStepLog = (stepKey, text, extra = {}) => {
    setStepCurrents(prev => ({ ...prev, [stepKey]: text }));
    setStepLogs(prev => ({
      ...prev,
      [stepKey]: [...(prev[stepKey] || []), { step: stepKey, text, ...extra }].slice(-40),
    }));
  };

  const showReferenceDetail = (detail) => {
    setSelectedSource(null);
    setReferenceDetail(detail);
  };

  const selectSource = (sourceName) => {
    setReferenceDetail(null);
    setSelectedSource(sourceName);
  };

  const completedSteps = steps.filter(s => s.status==="done").length;
  const currentStepIdx = steps.findIndex(s => s.status==="running");
  const isDone         = phase === "done";
  const isError        = phase === "error";
  const isRunning      = started && !isDone && !isError;
  const srcNames       = Object.keys(bySource);

  /* auto-scroll */
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior:"smooth", block:"nearest" });
  }, [queries, visibleSources, gate1Sections, gate1Done, gate2Sections, gate2Done, reportUrl, error]);

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setElapsedSec((v) => v + 1), 1000);
    return () => clearInterval(id);
  }, [isRunning]);

  /* SSE connection */
  useEffect(() => {
    if (!started) return;
    let es = null;
    const timers = [];
    const T = (ms, fn) => { const id = setTimeout(fn, ms); timers.push(id); };

    const mark = (idx, status) =>
      setSteps(prev => prev.map((s,i) => i===idx ? {...s, status} : s));
    const updateStatus = (text) => {
      setStatusText(text);
    };
    const logStep = (stepKey, text, extra = {}) => {
      appendStepLog(stepKey, text, extra);
      updateStatus(text);
    };
    const stepKeyForLog = (text = "") => {
      if (text.startsWith("[A]") || text.includes("영문 쿼리") || text.includes("GLM 응답")) return "step01";
      if (text.startsWith("[B-EXT]") || text.includes("외부 검색")) return "step02b";
      if (text.startsWith("[B]") || text.includes("Archive")) return "step02";
      if (text.startsWith("[C]") || text.includes("목차") || text.includes("쿼리")) return "step03";
      if (text.includes("Gate 1")) return "step04";
      if (text.startsWith("[D]") || text.includes("섹션별") || text.includes("검색 완료")) return "step05";
      if (text.includes("Gate 2")) return "step06";
      if (text.startsWith("[E/F]") || text.includes("본문") || text.includes("분석")) return "step07";
      if (text.startsWith("[G]") || text.includes("시사점") || text.includes("저장")) return "step08";
      return "step01";
    };

    const handleEvent = (ev) => {
      switch (ev.type) {

        case "report_log": {
          const key = stepKeyForLog(ev.text || "");
          logStep(key, ev.text || "처리 중...");
          if      (ev.text.startsWith("[E/F]")) { mark(6, "running"); setPhase("step_ef"); }
          else if (ev.text.startsWith("[G]"))   { mark(7, "running"); setPhase("step_g"); }
          break;
        }

        case "report_step_a": {
          setQueries(ev.queries || []);
          logStep("step01", "영문 검색 쿼리 생성 완료");
          setPhase("step_a_done");
          mark(0, "done");
          T(200, () => mark(1, "running"));
          break;
        }

        case "report_step_a_trace": {
          logStep("step01", ev.text || "영문 검색 쿼리 생성 중...", ev);
          break;
        }

        case "report_step_b": {
          logStep("step02", `아카이브 검색 결과 ${ev.total || 0}건 수집`);
          const srcMap = ev.by_source || {};
          setBySource(srcMap);
          setTotalArchive(ev.total || 0);
          setUseExternal((ev.total || 0) < 15);
          setPhase("step_b");
          const names = Object.keys(srcMap);
          names.forEach((name, i) => {
            T(i*350,     () => setVisibleSources(prev => [...prev, name]));
            T(i*350+700, () => setDoneSources(prev => [...prev, name]));
          });
          T(names.length*350 + 900, () => mark(1, "done"));
          break;
        }

        case "report_step_b_ext": {
          setExtQueries(ev.queries || []);
          setExtBySource(ev.by_source || {});
          setExtTotal(ev.total || 0);
          logStep("step02b", `외부 검색 결과 ${ev.total || 0}건 수집`);
          setPhase("step_b_ext");
          break;
        }

        case "report_step_c": {
          logStep("step03", "목차와 섹션별 검색어 생성 중...");
          setPhase("step_c");
          mark(1, "done");
          mark(2, "running");
          break;
        }

        case "report_step_d": {
          logStep("step05", "섹션별 본격 검색 실행 중...");
          const secs = (ev.sections || []).map(s => ({ title: s.title, status: "pending" }));
          setDSections(secs);
          setPhase("step_d");
          mark(4, "running");
          break;
        }

        case "report_step_d_progress": {
          logStep("step05", `섹션 검색 중: ${(ev.idx ?? 0) + 1}/${ev.total || "?"} ${ev.title || ""}`);
          setDSections(prev => prev.map((s, i) => {
            if (i < ev.idx)  return { ...s, status: "done" };
            if (i === ev.idx) return { ...s, status: "searching" };
            return s;
          }));
          break;
        }

        case "report_gate1": {
          logStep("step04", "Gate 1 대기 중: 목차를 검토해주세요");
          const secs = ev.sections || [];
          setGate1Sections(secs);
          gate1SectionsRef.current = secs;
          setPhase("gate1_pending");
          mark(2, "done");
          mark(3, "running");
          break;
        }

        case "report_gate2": {
          logStep("step06", "Gate 2 대기 중: 검색 결과를 검토해주세요");
          const secs = ev.sections || [];
          setGate2Sections(secs);
          gate2SectionsRef.current = secs;
          setPhase("gate2_pending");
          setDSections(prev => prev.map(s => ({ ...s, status: "done" })));
          mark(4, "done");
          mark(5, "running");
          break;
        }

        case "report_step_ef_progress": {
          logStep("step07", `본문 분석 중: ${ev.si}/${ev.total} ${ev.title || ""}`);
          setEfSections(prev => prev.map((s, i) => {
            if (i < ev.si - 1)  return { ...s, status: "done" };
            if (i === ev.si - 1) return { ...s, status: "analyzing" };
            return s;
          }));
          break;
        }

        case "report_done": {
          setReportUrl(ev.report_url);
          logStep("step08", "보고서 생성 완료");
          setPhase("done");
          setDSections(prev => prev.map(s => ({ ...s, status: "done" })));
          setEfSections(prev => prev.map(s => ({ ...s, status: "done" })));
          setSteps(prev => prev.map(s => ({...s, status:"done"})));
          es?.close();
          break;
        }

        case "report_error": {
          setError(ev.text || "알 수 없는 오류");
          logStep("step08", "오류 발생");
          setPhase("error");
          break;
        }

        case "done": {
          es?.close();
          break;
        }
      }
    };

    (async () => {
      try {
        const res = await fetch(`${API}/api/report/start`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ topic }),
        });
        if (!res.ok) throw new Error(`서버 오류 ${res.status}`);
        const { session_id } = await res.json();
        sessionRef.current = session_id;
        setStatusText(`연결됨: ${session_id.slice(0, 8)}`);
        appendStepLog("step01", `연결됨: ${session_id.slice(0, 8)}`);

        es = new EventSource(`${API}/api/report/stream/${session_id}`);
        es.onmessage = (e) => {
          try { handleEvent(JSON.parse(e.data)); }
          catch(err) { console.error("SSE parse:", err); }
        };
        es.onerror = () => {
          setError("서버 연결이 끊겼습니다. 백엔드가 실행 중인지 확인해주세요.");
          setStatusText("서버 연결 끊김");
          appendStepLog("step01", "서버 연결 끊김");
          setPhase("error");
          es?.close();
        };
      } catch(err) {
        setError(err.message);
        setPhase("error");
      }
    })();

    return () => {
      es?.close();
      timers.forEach(clearTimeout);
      const sid = sessionRef.current;
      if (sid) {
        navigator.sendBeacon(`${API}/api/report/cancel/${sid}`);
        sessionRef.current = null;
      }
    };
  }, [topic, started]);

  const handleStartAnalysis = () => {
    setStarted(true);
    setPhase("loading");
    setElapsedSec(0);
    setStepLogs(initStepMap([]));
    setStepCurrents(initStepMap(""));
    setStepOpen(initStepMap(false));
    setStatusText("서버 연결 중...");
    setSteps(prev => prev.map((s, i) => i === 0 ? {...s, status: "running"} : s));
  };

  const handleExtDecision = async () => {
    setExtDecisionDone(true);
    try {
      const res = await fetch(`${API}/api/report/ext_decision`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ session_id: sessionRef.current, use_external: useExternal }),
      });
      if (!res.ok) throw new Error(`ext_decision ${res.status}`);
    } catch(err) {
      console.error("ext decision:", err);
      setExtDecisionDone(false);
      setError("외부 검색 설정 중 오류가 발생했습니다.");
      setPhase("error");
    }
  };

  const handleToggleQuery = (secIdx, qIdx) => {
    setGate1Sections(prev => prev.map((sec, i) => {
      if (i !== secIdx) return sec;
      const base = sec.included?.length ? [...sec.included] : sec.queries.map(() => true);
      base[qIdx] = !base[qIdx];
      return { ...sec, included: base };
    }));
  };

  /* Gate handlers (defined outside useEffect, use refs for fresh values) */
  const handleGate1 = async () => {
    setGate1Done(true);
    setSteps(prev => prev.map((s,i) =>
      i===3 ? {...s,status:"done"} : i===4 ? {...s,status:"running"} : s
    ));
    try {
      const res = await fetch(`${API}/api/report/gate1`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ session_id: sessionRef.current, sections: gate1SectionsRef.current }),
      });
      if (!res.ok) throw new Error(`gate1 ${res.status}`);
    } catch(err) {
      console.error("gate1 confirm:", err);
      setGate1Done(false);
      setSteps(prev => prev.map((s,i) =>
        i===3 ? {...s,status:"running"} : i===4 ? {...s,status:"pending"} : s
      ));
      setError("목차 확정 중 오류가 발생했습니다. 다시 시도해주세요.");
      setPhase("error");
    }
  };

  const handleGate2 = async () => {
    setGate2Done(true);
    setEfSections((gate2SectionsRef.current || []).map(s => ({ title: s.title, status: "pending" })));
    setSteps(prev => prev.map((s,i) =>
      i===5 ? {...s,status:"done"} : i===6 ? {...s,status:"running"} : s
    ));
    try {
      await fetch(`${API}/api/report/gate2`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ session_id: sessionRef.current, proceed: true, sections: gate2SectionsRef.current }),
      });
    } catch(err) { console.error("gate2 confirm:", err); }
  };

  const archiveArticles = Object.entries(bySource).flatMap(([source, items]) =>
    (items || []).map((item) => ({ ...item, source }))
  );
  const externalArticles = Object.entries(extBySource).flatMap(([source, items]) =>
    (items || []).map((item) => ({ ...item, source }))
  );
  const gate2Articles = (gate2Sections || []).flatMap((section, sectionIndex) =>
    (section.results || []).map((item) => ({
      ...item,
      source: item.source || item.source_name,
      section: `S${sectionIndex + 1}`,
    }))
  );

  const openArchiveReferences = () => showReferenceDetail({
    name: "전체 아카이브 출처",
    articles: archiveArticles,
    totalCount: archiveArticles.length,
    subtitle: `${srcNames.length}개 기관 · ${archiveArticles.length}건 표시`,
    note: <>이 목록은 Step 02에서 수집한 <strong style={{ color:E.t2 }}>아카이브 메타데이터</strong>입니다. 목차 설계에 쓰이며, 본문 인용 출처는 이후 섹션별 검색에서 다시 확정됩니다.</>,
  });
  const openExternalReferences = () => showReferenceDetail({
    name: "외부 검색 출처",
    articles: externalArticles,
    totalCount: externalArticles.length,
    subtitle: `${Object.keys(extBySource).length}개 출처 · ${externalArticles.length}건 표시`,
    note: <>이 목록은 아카이브 결과가 부족할 때 보강한 <strong style={{ color:E.t2 }}>외부 검색 후보</strong>입니다. 실제 사용 여부는 이후 목차와 섹션별 검색 단계에서 좁혀집니다.</>,
  });
  const openGate2References = () => showReferenceDetail({
    name: "섹션별 검색 출처",
    articles: gate2Articles,
    totalCount: gate2Articles.length,
    subtitle: `${gate2Sections?.length || 0}개 섹션 · ${gate2Articles.length}건 표시`,
    note: <>이 목록은 Step 05 섹션별 검색에서 확보한 결과입니다. Step 07 본문 분석에서 이 후보들 중 실제로 읽고 인용할 출처가 결정됩니다.</>,
  });
  const openGate2SectionReferences = (section, sectionIndex) => {
    const articles = (section?.results || []).map((item) => ({
      ...item,
      source: item.source || item.source_name,
      section: `S${sectionIndex + 1}`,
    }));
    showReferenceDetail({
      name: section?.title || `섹션 ${sectionIndex + 1}`,
      articles,
      totalCount: articles.length,
      subtitle: `섹션 ${sectionIndex + 1} · ${articles.length}건 표시`,
      note: <>이 목록은 해당 섹션의 검색 후보 전체입니다. 각 항목을 눌러 원문 링크를 확인할 수 있고, 이후 본문 분석 단계에서 실제 인용 출처가 선별됩니다.</>,
    });
  };

  const detailOpen    = selectedSource !== null || referenceDetail !== null;
  const step2Done     = doneSources.length === srcNames.length && srcNames.length > 0;
  const showExtToggle = step2Done;
  const showExtResults = extTotal > 0;
  const showStep2  = visibleSources.length > 0 || ["step_b","step_b_done","step_b_ext","gate1_pending","gate1_confirmed","step_d","gate2_pending","step_ef","step_g","done"].includes(phase);
  const showStep3  = ["step_c","step_d","gate2_pending","step_ef","step_g","done"].includes(phase) || gate1Sections !== null;
  const showStep4  = gate1Sections !== null;
  const showStep5  = gate1Done && ["step_d","gate2_pending","step_ef","step_g","done"].includes(phase);
  const showStep6  = gate2Sections !== null;
  const showStep7  = gate2Done && ["step_ef","step_g","done"].includes(phase);
  const showStep8  = gate2Done && ["step_g","done"].includes(phase);

  return (
    <div style={{ height:"100%", display:"flex", flexDirection:"column",
      background:E.bgGrad, color:E.t1, position:"relative", overflow:"hidden" }}>

      {/* Background blobs */}
      <div style={{ position:"absolute", width:520, height:520, borderRadius:"50%", pointerEvents:"none",
        background:"radial-gradient(circle,rgba(110,231,183,.28) 0%,transparent 70%)",
        right:-100, top:-100, filter:"blur(20px)" }}/>
      <div style={{ position:"absolute", width:380, height:380, borderRadius:"50%", pointerEvents:"none",
        background:"radial-gradient(circle,rgba(167,243,208,.20) 0%,transparent 70%)",
        left:"30%", bottom:-60, filter:"blur(20px)" }}/>
      <div style={{ position:"absolute", width:260, height:260, borderRadius:"50%", pointerEvents:"none",
        background:"radial-gradient(circle,rgba(209,213,219,.55) 0%,transparent 70%)",
        left:-40, top:"35%", filter:"blur(16px)" }}/>

      <Header topic={topic} onBack={onBack}
        completedSteps={completedSteps} totalSteps={steps.length} isRunning={isRunning}/>

      <div style={{ position:"relative", zIndex:10, flex:1, display:"flex", overflow:"hidden" }}>
        <Sidebar steps={steps} currentStepIdx={currentStepIdx>=0?currentStepIdx:0}
          completedSteps={completedSteps} totalSteps={steps.length}/>

        <div style={{ flex:1, display:"flex", overflow:"hidden" }}>

          {/* Main log panel */}
          <div style={{ flex:1, minWidth:0, overflowY:"auto", overflowX:"hidden", padding:"24px 28px" }}>
            <div style={{ maxWidth:860, margin:"0 auto" }}>

              <MetricCards
                queryCount={queries.length}
                totalArchive={totalArchive}
                sectionCount={gate1Sections?.length || 0}
                sourceCount={srcNames.length}
              />

              {!started && topicInfo?.rationale && (
                <div style={{ ...gl({ padding:"24px 28px", marginBottom:20 }), animation:"fadeUp .35s ease both" }}>
                  <Gloss/>
                  <div style={{ position:"relative", zIndex:1 }}>

                    {/* 선정 근거 */}
                    <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.em,
                      textTransform:"uppercase", margin:"0 0 8px" }}>선정 근거</p>
                    <p style={{ fontSize:15.5, color:E.t2, lineHeight:1.85, margin:"0 0 20px" }}>
                      {topicInfo.rationale}
                    </p>

                    {/* 핵심 데이터 */}
                    {topicInfo.key_data?.length > 0 && (
                      <div style={{ margin:"0 0 20px" }}>
                        <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
                          textTransform:"uppercase", margin:"0 0 8px" }}>핵심 데이터</p>
                        <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
                          {topicInfo.key_data.map((d, i) => (
                            <div key={i} style={{ display:"flex", alignItems:"baseline", gap:8,
                              padding:"8px 12px", borderRadius:8,
                              background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}` }}>
                              <span style={{ fontSize:9, fontWeight:800, color:E.em, flexShrink:0,
                                background:E.emBg, borderRadius:4, padding:"2px 6px" }}>•</span>
                              <span style={{ fontSize:13.5, color:E.t2, lineHeight:1.6 }}>{d}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 참고 기사 */}
                    {topicInfo.articles?.length > 0 && (
                      <div style={{ margin:"0 0 20px" }}>
                        <p style={{ fontSize:11, fontWeight:700, letterSpacing:".10em", color:E.t4,
                          textTransform:"uppercase", margin:"0 0 8px" }}>참고 기사 ({topicInfo.articles.length}건)</p>
                        <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
                          {topicInfo.articles.map((a, i) => (
                            <div key={i} style={{ display:"flex", alignItems:"center", gap:10,
                              padding:"9px 12px", borderRadius:8,
                              background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}` }}>
                              <span style={{ fontSize:9, fontWeight:800, color:E.em, flexShrink:0,
                                background:E.emBg, borderRadius:4, padding:"2px 6px", whiteSpace:"nowrap" }}>
                                {a.source?.split(" ")[0]}
                              </span>
                              <div style={{ flex:1, minWidth:0 }}>
                                {a.url
                                  ? <a href={a.url} target="_blank" rel="noreferrer"
                                      style={{ fontSize:13.5, color:E.t1, textDecoration:"none",
                                        display:"block", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                                      onMouseEnter={e => e.currentTarget.style.color = E.em}
                                      onMouseLeave={e => e.currentTarget.style.color = E.t1}>
                                      {a.title}
                                    </a>
                                  : <span style={{ fontSize:13.5, color:E.t2, display:"block",
                                      overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                                      {a.title}
                                    </span>
                                }
                                <span style={{ fontSize:11, color:E.t4 }}>{a.date}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 분석 시작 버튼 */}
                    <div style={{ display:"flex", justifyContent:"flex-end" }}>
                      <button
                        onClick={handleStartAnalysis}
                        style={{ background:E.em, color:"#fff", border:"none", borderRadius:10,
                          padding:"10px 28px", fontSize:14, fontWeight:700, cursor:"pointer",
                          boxShadow:"0 4px 14px rgba(16,185,129,.28)", transition:"background .15s" }}
                        onMouseEnter={e => e.currentTarget.style.background = E.emD}
                        onMouseLeave={e => e.currentTarget.style.background = E.em}
                      >
                        분석 시작하기 →
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div style={{ ...gl({ padding:28 }) }}>
                <Gloss/>
                <div style={{ position:"relative", zIndex:1 }}>

                  {/* Panel header */}
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:24 }}>
                    <div>
                      <p style={{ fontSize:9, fontWeight:800, letterSpacing:".14em", color:E.em,
                        margin:"0 0 3px", textTransform:"uppercase" }}>Agent Thinking</p>
                      <h3 style={{ fontSize:17, fontWeight:700, color:E.t1, margin:0, letterSpacing:"-.02em" }}>
                        에이전트 사고 흐름
                      </h3>
                      <p style={{ fontSize:13, color:E.t4, margin:"6px 0 0", lineHeight:1.45 }}>
                        {statusText}
                        {isRunning && <span style={{ marginLeft:8 }}>{formatElapsed(elapsedSec)}</span>}
                      </p>
                    </div>
                    {isRunning
                      ? <span style={{ display:"flex", alignItems:"center", gap:6, fontSize:11,
                            fontWeight:700, color:E.em, background:E.emBg, border:`1px solid ${E.emBr}`,
                            borderRadius:99, padding:"5px 12px" }}><Spinner/>Thinking</span>
                      : <span style={{ fontSize:11, fontWeight:600,
                            color:isError?"#ef4444":E.t3,
                            background:"rgba(42,40,38,.06)", border:`1px solid ${E.div}`,
                            borderRadius:99, padding:"5px 12px" }}>
                          {isError ? "Error" : "Completed"}
                        </span>
                    }
                  </div>

                  {/* ── Step 01 ── */}
                  <StepHeader num="01" label="영문 검색 쿼리 생성"/>
                  <StepLogLine
                    current={stepCurrents.step01}
                    fallback={phase==="idle" ? "위의 주제 정보를 확인 후 분석을 시작해주세요" : "영어 검색 쿼리 생성 중..."}
                    logs={stepLogs.step01 || []}
                    open={stepOpen.step01}
                    onToggle={() => setStepOpen(prev => ({ ...prev, step01: !prev.step01 }))}
                  />
                  {queries.length === 0
                    ? <DotLoader label={phase==="idle" ? "위의 주제 정보를 확인 후 분석을 시작해주세요" : stepCurrents.step01 || "쿼리 생성 중..."}/>
                    : <QueryList queries={queries}/>
                  }

                  {/* ── Step 02 ── */}
                  {showStep2 && (
                    <>
                      <LogDivider/>
                      <StepHeader
                        num="02"
                        label="아카이브 사전 검색"
                        onOpenReferences={openArchiveReferences}
                        referenceCount={archiveArticles.length}
                      />
                      <StepLogLine
                        current={stepCurrents.step02}
                        fallback="아카이브 검색 중..."
                        logs={stepLogs.step02 || []}
                        open={stepOpen.step02}
                        onToggle={() => setStepOpen(prev => ({ ...prev, step02: !prev.step02 }))}
                      />
                      <ProseEntry text="Tier-1 아카이브에 생성된 쿼리를 병렬로 투입합니다. 각 기관의 리포트 인덱스를 스캔해 제목·URL 메타데이터를 수집하고, 유사도 기준으로 상위 리포트를 선별합니다. 이 단계는 목차 설계를 위한 사전 스캔이며, 실제 본문은 읽지 않습니다."/>
                      {visibleSources.length > 0 && (
                        <ArchiveLog
                          visibleSources={visibleSources}
                          doneSources={doneSources}
                          selectedSource={selectedSource}
                          onSelect={selectSource}
                          bySource={bySource}
                        />
                      )}
                      {step2Done && (
                        <p style={{ fontSize:13, fontWeight:600, color:E.em, margin:"14px 0 0",
                          animation:"fadeSlideIn .4s ease both" }}>
                          ✓ 아카이브 검색 완료 — {totalArchive}건 수집 (결과 발견된 {srcNames.length}개 기관)
                        </p>
                      )}
                      {showExtToggle && (
                        <ExtSearchToggle
                          totalArchive={totalArchive}
                          queries={queries}
                          useExternal={useExternal}
                          onToggle={() => !extDecisionDone && setUseExternal(v => !v)}
                          onConfirm={handleExtDecision}
                          confirmed={extDecisionDone}
                        />
                      )}
                      {showExtResults && (
                        <>
                          <LogDivider/>
                          <StepHeader
                            num="02B"
                            label="외부 검색 보완 (RSS + DuckDuckGo)"
                            onOpenReferences={openExternalReferences}
                            referenceCount={externalArticles.length}
                          />
                          <StepLogLine
                            current={stepCurrents.step02b}
                            fallback="외부 검색 보완 중..."
                            logs={stepLogs.step02b || []}
                            open={stepOpen.step02b}
                            onToggle={() => setStepOpen(prev => ({ ...prev, step02b: !prev.step02b }))}
                          />
                          <ExtSourceLog
                            queries={extQueries}
                            bySource={extBySource}
                            total={extTotal}
                            onOpenAll={openExternalReferences}
                            onOpenSource={(name) => showReferenceDetail({
                              name,
                              articles: extBySource[name] || [],
                              totalCount: (extBySource[name] || []).length,
                              subtitle: `외부 검색 · ${(extBySource[name] || []).length}건`,
                              note: <>이 목록은 아카이브 결과가 부족할 때 보강한 <strong style={{ color:E.t2 }}>외부 검색 후보</strong>입니다. 실제 사용 여부는 이후 섹션별 검색 단계에서 좁혀집니다.</>,
                            })}
                          />
                        </>
                      )}
                    </>
                  )}

                  {/* ── Step 03 ── */}
                  {showStep3 && (
                    <>
                      <LogDivider/>
                      <StepHeader num="03" label="목차 + 섹션별 검색어 생성"/>
                      <StepLogLine
                        current={stepCurrents.step03}
                        fallback="목차와 섹션별 검색어 생성 중..."
                        logs={stepLogs.step03 || []}
                        open={stepOpen.step03}
                        onToggle={() => setStepOpen(prev => ({ ...prev, step03: !prev.step03 }))}
                      />
                      <ProseEntry text="수집된 아카이브 메타데이터를 기반으로 GLM이 보고서 목차를 설계합니다. 각 섹션의 분석 각도와 심층 검색어를 함께 생성합니다."/>
                      {!gate1Sections
                        ? <DotLoader label="GLM이 목차를 생성하고 있습니다..."/>
                        : <TocSections sections={gate1Sections} onToggle={handleToggleQuery} disabled={gate1Done}/>
                      }
                    </>
                  )}

                  {/* ── Step 04: GATE 1 ── */}
                  {showStep4 && (
                    <>
                      <LogDivider/>
                      <StepHeader num="04" label="GATE 1 — 목차 검토"/>
                      <StepLogLine
                        current={stepCurrents.step04}
                        fallback="목차 검토 대기 중..."
                        logs={stepLogs.step04 || []}
                        open={stepOpen.step04}
                        onToggle={() => setStepOpen(prev => ({ ...prev, step04: !prev.step04 }))}
                      />
                      <GatePrompt
                        message={`목차 ${gate1Sections.length}개가 생성되었습니다. 섹션별 본격 검색을 시작할까요?`}
                        onConfirm={handleGate1}
                        confirmed={gate1Done}
                        confirmLabel="확정 · 검색 시작"
                        cancelLabel="목차 수정"
                      />
                    </>
                  )}

                  {/* ── Step 05: 섹션별 검색 ── */}
                  {showStep5 && (
                    <>
                      <LogDivider/>
                      <StepHeader
                        num="05"
                        label="섹션별 본격 검색 실행"
                        onOpenReferences={openGate2References}
                        referenceCount={gate2Articles.length}
                      />
                      <StepLogLine
                        current={stepCurrents.step05}
                        fallback="섹션별 검색 중..."
                        logs={stepLogs.step05 || []}
                        open={stepOpen.step05}
                        onToggle={() => setStepOpen(prev => ({ ...prev, step05: !prev.step05 }))}
                      />
                      {dSections.length > 0
                        ? <DSectionList sections={dSections}/>
                        : <DotLoader label="섹션별 검색 중..."/>
                      }
                    </>
                  )}

                  {/* ── Step 06: Gate 2 ── */}
                  {showStep6 && (
                    <>
                      <LogDivider/>
                      <StepHeader
                        num="06"
                        label="GATE 2 — 검색결과 검토"
                        onOpenReferences={openGate2References}
                        referenceCount={gate2Articles.length}
                      />
                      <StepLogLine
                        current={stepCurrents.step06}
                        fallback="검색 결과 검토 대기 중..."
                        logs={stepLogs.step06 || []}
                        open={stepOpen.step06}
                        onToggle={() => setStepOpen(prev => ({ ...prev, step06: !prev.step06 }))}
                      />
                      <Gate2Sections
                        sections={gate2Sections}
                        onSectionSelect={openGate2SectionReferences}
                      />
                      <GatePrompt
                        message="섹션별 검색이 완료되었습니다. 본문 분석을 시작할까요?"
                        onConfirm={handleGate2}
                        confirmed={gate2Done}
                        confirmLabel="분석 시작"
                      />
                    </>
                  )}

                  {/* ── Step 07: 분석 ── */}
                  {showStep7 && (
                    <>
                      <LogDivider/>
                      <StepHeader
                        num="07"
                        label="본문 fetch + 목차별 분석"
                        onOpenReferences={openGate2References}
                        referenceCount={gate2Articles.length}
                      />
                      <StepLogLine
                        current={stepCurrents.step07}
                        fallback="본문 분석 중..."
                        logs={stepLogs.step07 || []}
                        open={stepOpen.step07}
                        onToggle={() => setStepOpen(prev => ({ ...prev, step07: !prev.step07 }))}
                      />
                      {efSections.length > 0
                        ? <DSectionList sections={efSections} label="섹션별 분석 진행"/>
                        : <DotLoader label="본문 수집 중..."/>
                      }
                    </>
                  )}

                  {/* ── Step 08: 시사점 ── */}
                  {showStep8 && (
                    <>
                      <LogDivider/>
                      <StepHeader num="08" label="Executive Summary + 시사점 도출"/>
                      <StepLogLine
                        current={stepCurrents.step08}
                        fallback="시사점 생성 중..."
                        logs={stepLogs.step08 || []}
                        open={stepOpen.step08}
                        onToggle={() => setStepOpen(prev => ({ ...prev, step08: !prev.step08 }))}
                      />
                      {!reportUrl && <DotLoader label="시사점 생성 중..."/>}
                    </>
                  )}

                  {reportUrl && <ReportDone reportUrl={reportUrl}/>}
                  {error && <ErrorPanel message={error}/>}

                  <div ref={logEndRef}/>
                </div>
              </div>
              <div style={{ height:40 }}/>
            </div>
          </div>

          {/* ── Sliding detail panel ── */}
          <div style={{
            flex:"none",
            width: detailOpen ? 440 : 0,
            transition:"width .4s cubic-bezier(.4,0,.2,1)",
            overflow:"hidden",
            borderLeft: detailOpen ? `1px solid ${E.div}` : "none",
            background:"rgba(246,245,243,.94)",
            backdropFilter:"blur(40px) saturate(180%)",
            WebkitBackdropFilter:"blur(40px) saturate(180%)",
          }}>
            <div style={{ width:440, height:"100%", overflowY:"auto" }}>
              {referenceDetail !== null && (
                <ReferenceDetail
                  name={referenceDetail.name}
                  articles={referenceDetail.articles || []}
                  totalCount={referenceDetail.totalCount || 0}
                  subtitle={referenceDetail.subtitle}
                  note={referenceDetail.note}
                  onClose={() => setReferenceDetail(null)}
                />
              )}
              {referenceDetail === null && selectedSource !== null && (
                <ArchiveDetail
                  name={selectedSource}
                  articles={bySource[selectedSource] || []}
                  totalCount={(bySource[selectedSource] || []).length}
                  onClose={() => setSelectedSource(null)}
                />
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
