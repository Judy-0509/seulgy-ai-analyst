import { useState, useEffect, useRef } from "react";
import { PIPELINE_STEPS } from "../data/mock";

const API = "http://localhost:8000";

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
      <span style={{ fontSize:11.5, color:E.t4 }}>{label}</span>
    </div>
  );
}
function LogDivider() {
  return <div style={{ height:1, background:E.div, margin:"24px 0 20px",
    animation:"fadeSlideIn .3s ease both" }}/>;
}

/* ── Log atoms ── */
function StepHeader({ num, label }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:10, margin:"0 0 14px",
      animation:"fadeSlideIn .35s ease both" }}>
      <span style={{ fontSize:9.5, fontWeight:800, letterSpacing:".1em", color:E.em,
        background:E.emBg, border:`1px solid ${E.emBr}`, borderRadius:7, padding:"3px 9px", flexShrink:0 }}>
        Step {num}
      </span>
      <span style={{ fontSize:13.5, fontWeight:700, color:E.t1, letterSpacing:"-.015em" }}>{label}</span>
      <div style={{ flex:1, height:1, background:E.div }}/>
    </div>
  );
}
function ProseEntry({ text }) {
  return <p style={{ fontSize:13, color:E.t2, lineHeight:1.9, margin:"0 0 10px",
    animation:"fadeSlideIn .4s ease both" }}>{text}</p>;
}

function QueryList({ queries }) {
  return (
    <div style={{ margin:"16px 0 0", animation:"fadeSlideIn .4s ease both" }}>
      <p style={{ fontSize:9.5, fontWeight:700, letterSpacing:".12em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>생성된 검색 쿼리</p>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {queries.map((q,i)=>(
          <div key={i} style={{ display:"flex", alignItems:"baseline", gap:10,
            padding:"9px 12px", borderRadius:10,
            background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}`,
            animation:`fadeSlideIn .35s ease ${i*60}ms both` }}>
            <span style={{ fontSize:9.5, fontWeight:800, color:E.em,
              background:E.emBg, borderRadius:5, padding:"2px 7px", flexShrink:0 }}>Q{i+1}</span>
            <span style={{ fontSize:12.5, color:E.t1, flex:1, letterSpacing:".005em" }}>"{q}"</span>
          </div>
        ))}
      </div>
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

/* ── Stage D section progress list ── */
function DSectionList({ sections }) {
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:9.5, fontWeight:700, letterSpacing:".12em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>섹션별 검색 진행</p>
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
            <span style={{ fontSize:13, color:E.t2, flex:1 }}>{sec.title}</span>
            {sec.status==="done"      && <span style={{ fontSize:12, color:E.em, fontWeight:700, flexShrink:0 }}>✓</span>}
            {sec.status==="searching" && <Spinner size={10}/>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── TOC section list (Gate 1) ── */
function TocSections({ sections }) {
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:9.5, fontWeight:700, letterSpacing:".12em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>생성된 목차</p>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {sections.map((sec, i) => (
          <div key={i} style={{ padding:"10px 14px", borderRadius:10,
            background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}`,
            animation:`fadeSlideIn .35s ease ${i*60}ms both` }}>
            <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom: sec.angle ? 4 : 0 }}>
              <span style={{ fontSize:9.5, fontWeight:800, color:E.em, background:E.emBg,
                borderRadius:5, padding:"2px 7px", flexShrink:0 }}>{i+1}</span>
              <span style={{ fontSize:13, fontWeight:600, color:E.t1 }}>{sec.title}</span>
            </div>
            {sec.angle && (
              <p style={{ fontSize:11.5, color:E.t3, margin:"0 0 0 27px", lineHeight:1.5 }}>{sec.angle}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Archive log rows ── */
function ArchiveLog({ visibleSources, doneSources, selectedSource, onSelect, bySource }) {
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:9.5, fontWeight:700, letterSpacing:".12em", color:E.t4,
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
              <span style={{ flex:1, fontSize:13, fontWeight:600, color:E.t1 }}>{name}</span>
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
                  <span style={{ fontSize:11.5, color:E.t4 }}>검색 중...</span>
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
        <p style={{ fontSize:9.5, fontWeight:700, letterSpacing:".12em", color:E.t4,
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
                <p style={{ fontSize:12.5, fontWeight:600, color:E.t1, margin:0, lineHeight:1.45, flex:1 }}>
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
                <p style={{ fontSize:10.5, color:E.t4, margin:"5px 0 0",
                  overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{a.url}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Gate 2 results summary ── */
function Gate2Summary({ sections }) {
  const total = sections.reduce((a,s) => a + (s.results?.length || 0), 0);
  return (
    <div style={{ margin:"14px 0 0" }}>
      <p style={{ fontSize:9.5, fontWeight:700, letterSpacing:".12em", color:E.t4,
        textTransform:"uppercase", margin:"0 0 8px" }}>섹션별 검색 결과 ({total}건)</p>
      <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
        {sections.map((sec, i) => (
          <div key={i} style={{ padding:"10px 14px", borderRadius:10,
            background:"rgba(42,40,38,.04)", border:`1px solid ${E.div}`,
            animation:`fadeSlideIn .35s ease ${i*60}ms both` }}>
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              <span style={{ fontSize:9.5, fontWeight:800, color:E.em, background:E.emBg,
                borderRadius:5, padding:"2px 7px", flexShrink:0 }}>{i+1}</span>
              <span style={{ fontSize:13, fontWeight:600, color:E.t1, flex:1 }}>{sec.title}</span>
              <span style={{ fontSize:11, color:E.t3, flexShrink:0 }}>{sec.results?.length || 0}건</span>
            </div>
            {sec.results?.slice(0,2).map((r,j) => (
              <p key={j} style={{ fontSize:11.5, color:E.t3, margin:"4px 0 0 27px",
                overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                · {r.title || r.url}
              </p>
            ))}
            {(sec.results?.length||0) > 2 && (
              <p style={{ fontSize:11, color:E.t4, margin:"2px 0 0 27px" }}>
                외 {sec.results.length-2}건 더
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Report done ── */
function ReportDone({ reportUrl }) {
  return (
    <div style={{ margin:"20px 0 0", padding:"20px 24px",
      border:`1px solid ${E.emBr}`, background:"rgba(16,185,129,.07)",
      borderRadius:14, animation:"fadeSlideIn .4s ease both" }}>
      <p style={{ fontSize:13, fontWeight:700, color:E.em, margin:"0 0 6px" }}>✓ 보고서 생성 완료</p>
      <p style={{ fontSize:12.5, color:E.t2, margin:"0 0 14px", lineHeight:1.6 }}>
        분석이 완료되었습니다. 보고서를 확인하세요.
      </p>
      <a href={`${API}${reportUrl}`} target="_blank" rel="noopener noreferrer"
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
      <p style={{ fontSize:12, color:E.t3, margin:0, whiteSpace:"pre-wrap", lineHeight:1.6 }}>{message}</p>
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
        <div style={{ width:34, height:34, borderRadius:11, background:E.emBg, border:`1px solid ${E.emBr}`,
          display:"flex", alignItems:"center", justifyContent:"center",
          fontSize:14, fontWeight:900, color:E.em, boxShadow:E.shadowSm }}>R</div>
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
                    <p style={{ fontSize:11.5, fontWeight:600, margin:0,
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
                    <span style={{ fontSize:10.5, color:E.t4 }}>
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

/* ══════════════════════════════════════════════════════════
   Main
══════════════════════════════════════════════════════════ */
export default function PipelineScreen({ topic, onBack }) {
  const [steps, setSteps] = useState(() =>
    PIPELINE_STEPS.map((s,i) => ({...s, status: i===0 ? "running" : "pending"}))
  );
  const [phase,          setPhase]          = useState("loading");
  const [queries,        setQueries]        = useState([]);
  const [bySource,       setBySource]       = useState({});
  const [totalArchive,   setTotalArchive]   = useState(0);
  const [visibleSources, setVisibleSources] = useState([]);
  const [doneSources,    setDoneSources]    = useState([]);
  const [selectedSource, setSelectedSource] = useState(null);
  const [gate1Sections,  setGate1Sections]  = useState(null);
  const [gate1Done,      setGate1Done]      = useState(false);
  const [gate2Sections,  setGate2Sections]  = useState(null);
  const [gate2Done,      setGate2Done]      = useState(false);
  const [dSections,      setDSections]      = useState([]);
  const [reportUrl,      setReportUrl]      = useState(null);
  const [error,          setError]          = useState(null);

  /* refs for stable access inside async handlers */
  const sessionRef       = useRef(null);
  const gate1SectionsRef = useRef(null);
  const gate2SectionsRef = useRef(null);
  const logEndRef        = useRef(null);

  const completedSteps = steps.filter(s => s.status==="done").length;
  const currentStepIdx = steps.findIndex(s => s.status==="running");
  const isDone         = phase === "done";
  const isError        = phase === "error";
  const isRunning      = !isDone && !isError;
  const srcNames       = Object.keys(bySource);

  /* auto-scroll */
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior:"smooth", block:"nearest" });
  }, [queries, visibleSources, gate1Sections, gate1Done, gate2Sections, gate2Done, reportUrl, error]);

  /* SSE connection */
  useEffect(() => {
    let es = null;
    const timers = [];
    const T = (ms, fn) => { const id = setTimeout(fn, ms); timers.push(id); };

    const mark = (idx, status) =>
      setSteps(prev => prev.map((s,i) => i===idx ? {...s, status} : s));

    const handleEvent = (ev) => {
      switch (ev.type) {

        case "report_log": {
          if      (ev.text.startsWith("[E/F]")) { mark(6, "running"); setPhase("step_ef"); }
          else if (ev.text.startsWith("[G]"))   { mark(7, "running"); setPhase("step_g"); }
          break;
        }

        case "report_step_a": {
          setQueries(ev.queries || []);
          setPhase("step_a_done");
          mark(0, "done");
          T(200, () => mark(1, "running"));
          break;
        }

        case "report_step_b": {
          const srcMap = ev.by_source || {};
          setBySource(srcMap);
          setTotalArchive(ev.total || 0);
          setPhase("step_b");
          const names = Object.keys(srcMap);
          names.forEach((name, i) => {
            T(i*350,     () => setVisibleSources(prev => [...prev, name]));
            T(i*350+700, () => setDoneSources(prev => [...prev, name]));
          });
          T(names.length*350 + 900, () => mark(1, "done"));
          break;
        }

        case "report_step_c": {
          setPhase("step_c");
          mark(1, "done");
          mark(2, "running");
          break;
        }

        case "report_step_d": {
          const secs = (ev.sections || []).map(s => ({ title: s.title, status: "pending" }));
          setDSections(secs);
          setPhase("step_d");
          mark(4, "running");
          break;
        }

        case "report_step_d_progress": {
          setDSections(prev => prev.map((s, i) => {
            if (i < ev.idx)  return { ...s, status: "done" };
            if (i === ev.idx) return { ...s, status: "searching" };
            return s;
          }));
          break;
        }

        case "report_gate1": {
          const secs = ev.sections || [];
          setGate1Sections(secs);
          gate1SectionsRef.current = secs;
          setPhase("gate1_pending");
          mark(2, "done");
          mark(3, "running");
          break;
        }

        case "report_gate2": {
          const secs = ev.sections || [];
          setGate2Sections(secs);
          gate2SectionsRef.current = secs;
          setPhase("gate2_pending");
          setDSections(prev => prev.map(s => ({ ...s, status: "done" })));
          mark(4, "done");
          mark(5, "running");
          break;
        }

        case "report_done": {
          setReportUrl(ev.report_url);
          setPhase("done");
          setSteps(prev => prev.map(s => ({...s, status:"done"})));
          es?.close();
          break;
        }

        case "report_error": {
          setError(ev.text || "알 수 없는 오류");
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

        es = new EventSource(`${API}/api/report/stream/${session_id}`);
        es.onmessage = (e) => {
          try { handleEvent(JSON.parse(e.data)); }
          catch(err) { console.error("SSE parse:", err); }
        };
        es.onerror = () => {
          setError("서버 연결이 끊겼습니다. 백엔드가 실행 중인지 확인해주세요.");
          setPhase("error");
          es?.close();
        };
      } catch(err) {
        setError(err.message);
        setPhase("error");
      }
    })();

    return () => { es?.close(); timers.forEach(clearTimeout); };
  }, [topic]);

  /* Gate handlers (defined outside useEffect, use refs for fresh values) */
  const handleGate1 = async () => {
    setGate1Done(true);
    setSteps(prev => prev.map((s,i) =>
      i===3 ? {...s,status:"done"} : i===4 ? {...s,status:"running"} : s
    ));
    try {
      await fetch(`${API}/api/report/gate1`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ session_id: sessionRef.current, sections: gate1SectionsRef.current }),
      });
    } catch(err) { console.error("gate1 confirm:", err); }
  };

  const handleGate2 = async () => {
    setGate2Done(true);
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

  const detailOpen = selectedSource !== null;
  const showStep2  = visibleSources.length > 0 || ["step_b","step_b_done","gate1_pending","gate1_confirmed","step_d","gate2_pending","step_ef","step_g","done"].includes(phase);
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
                  {queries.length === 0
                    ? <DotLoader label={phase==="loading" ? "서버 연결 중..." : "쿼리 생성 중..."}/>
                    : <QueryList queries={queries}/>
                  }

                  {/* ── Step 02 ── */}
                  {showStep2 && (
                    <>
                      <LogDivider/>
                      <StepHeader num="02" label="아카이브 사전 검색"/>
                      <ProseEntry text="Tier-1 아카이브에 생성된 쿼리를 병렬로 투입합니다. 각 기관의 리포트 인덱스를 스캔해 제목·URL 메타데이터를 수집하고, 유사도 기준으로 상위 리포트를 선별합니다. 이 단계는 목차 설계를 위한 사전 스캔이며, 실제 본문은 읽지 않습니다."/>
                      {visibleSources.length > 0 && (
                        <ArchiveLog
                          visibleSources={visibleSources}
                          doneSources={doneSources}
                          selectedSource={selectedSource}
                          onSelect={setSelectedSource}
                          bySource={bySource}
                        />
                      )}
                      {doneSources.length === srcNames.length && srcNames.length > 0 && (
                        <p style={{ fontSize:13, fontWeight:600, color:E.em, margin:"14px 0 0",
                          animation:"fadeSlideIn .4s ease both" }}>
                          ✓ 전체 아카이브 검색 완료 — {totalArchive}건 수집 ({srcNames.length}개 기관)
                        </p>
                      )}
                    </>
                  )}

                  {/* ── Step 03 ── */}
                  {showStep3 && (
                    <>
                      <LogDivider/>
                      <StepHeader num="03" label="목차 + 섹션별 검색어 생성"/>
                      <ProseEntry text="수집된 아카이브 메타데이터를 기반으로 GLM이 보고서 목차를 설계합니다. 각 섹션의 분석 각도와 심층 검색어를 함께 생성합니다."/>
                      {!gate1Sections
                        ? <DotLoader label="GLM이 목차를 생성하고 있습니다..."/>
                        : <TocSections sections={gate1Sections}/>
                      }
                    </>
                  )}

                  {/* ── Step 04: GATE 1 ── */}
                  {showStep4 && (
                    <>
                      <LogDivider/>
                      <StepHeader num="04" label="GATE 1 — 목차 검토"/>
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
                      <StepHeader num="05" label="섹션별 본격 검색 실행"/>
                      {dSections.length > 0
                        ? <DSectionList sections={dSections}/>
                        : <DotLoader label="섹션별 검색 중..."/>
                      }
                    </>
                  )}

                  {/* ── Step 06: Gate 2 ── */}
                  {showStep6 && (
                    <>
                      {!showStep5 && <LogDivider/>}
                      <StepHeader num="06" label="GATE 2 — 검색결과 검토"/>
                      <Gate2Summary sections={gate2Sections}/>
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
                      <StepHeader num="07" label="본문 fetch + 목차별 분석"/>
                      {!showStep8 && <DotLoader label="섹션별 분석 중..."/>}
                    </>
                  )}

                  {/* ── Step 08: 시사점 ── */}
                  {showStep8 && (
                    <>
                      <LogDivider/>
                      <StepHeader num="08" label="Executive Summary + 시사점 도출"/>
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
              {selectedSource !== null && (
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
