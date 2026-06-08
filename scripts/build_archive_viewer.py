"""Archive 뷰어 HTML 생성기.

data/archives/*.json 모두 읽어서 reports/archive_viewer.html 단일 파일 생성.
- 검색·정렬·source 필터 지원
- 다크 테마 (phase0_debug.html과 동일 톤)
- 정적 HTML — 서버 없이 브라우저에서 바로 열림

사용:
    python scripts/build_archive_viewer.py
"""
import io
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVES_DIR = Path("data/archives")
OUTPUT_PATH = Path("reports/archive_viewer.html")


def collect_entries() -> dict:
    """모든 archive 파일에서 entries 평탄화 + 메타데이터 수집."""
    archives_meta = []
    all_entries = []
    if not ARCHIVES_DIR.exists():
        return {"archives": [], "entries": []}

    for f in sorted(ARCHIVES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [WARN] {f.name}: {e}")
            continue
        # 메타 정규화: 빌더마다 다른 필드를 표준화
        entries = data.get("entries", [])
        # 실제 lastmod에서 oldest/newest 계산
        dates = sorted([e.get("lastmod", "") for e in entries if e.get("lastmod")])
        oldest = dates[0][:10] if dates else ""
        newest = dates[-1][:10] if dates else ""
        # 기간 표시 필드 결정 (Counterpoint=month_window / TrendForce=cutoff_date)
        if data.get("month_window"):
            range_label = f"{data['month_window'][-1]} ~ {data['month_window'][0]}"
        elif data.get("cutoff_date"):
            range_label = f"{data['cutoff_date']} ~ today"
        elif oldest and newest:
            range_label = f"{oldest} ~ {newest}"
        else:
            range_label = "?"
        archives_meta.append({
            "file": f.name,
            "source": data.get("source", f.stem),
            "built_at": data.get("built_at"),
            "range_label": range_label,
            "oldest": oldest,
            "newest": newest,
            "newly_added": data.get("newly_added"),
            "entry_count": data.get("entry_count", len(entries)),
        })
        for e in (data.get("entries") or []):
            if not e.get("url"):
                continue
            all_entries.append({
                "url": e["url"],
                "title": e.get("title", ""),
                "description": e.get("description", ""),
                "lastmod": e.get("lastmod", ""),
                "source": e.get("source") or data.get("source") or f.stem,
                "tier": e.get("tier", 1),
            })

    # lastmod 기준 최신순
    all_entries.sort(key=lambda x: x["lastmod"] or "", reverse=True)
    return {"archives": archives_meta, "entries": all_entries}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Research Archive Viewer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;min-height:100vh}
#sidebar{width:280px;min-width:280px;background:#1e293b;border-right:1px solid #334155;position:sticky;top:0;height:100vh;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:14px}
.sidebar-title{color:#94a3b8;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px}
.archive-card{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px;cursor:pointer;transition:all .15s}
.archive-card:hover{border-color:#3b82f6;background:#162032}
.archive-card.active{border-color:#3b82f6;background:#1e3a5f;box-shadow:0 0 0 1px #3b82f6}
.archive-card.active .archive-name{color:#fbbf24}
.archive-name{font-size:13px;font-weight:700;color:#7dd3fc;margin-bottom:4px}
.archive-meta{font-size:11px;color:#64748b;line-height:1.5}
.stat-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.stat-pill{background:#162032;border:1px solid #334155;padding:2px 8px;border-radius:10px;font-size:10px;color:#94a3b8}
#main{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:14px}
.page-header{background:linear-gradient(135deg,#1e293b,#162032);border:1px solid #334155;border-radius:12px;padding:22px}
.page-header h1{font-size:22px;font-weight:700}
.page-header .sub{color:#64748b;font-size:13px;margin-top:4px}
.controls{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.controls input,.controls select{background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:7px 12px;font-size:13px;font-family:inherit}
.controls input:focus,.controls select:focus{outline:none;border-color:#3b82f6}
#search{flex:1;min-width:240px}
.controls label{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-right:4px}
.match-info{color:#7dd3fc;font-size:12px;font-weight:700}
.entry{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 18px;display:flex;flex-direction:column;gap:8px;transition:border-color .15s}
.entry:hover{border-color:#3b82f6}
.entry-hdr{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.entry-source{background:#1e3a5f;color:#7dd3fc;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700;flex-shrink:0}
.entry-tier{background:#312e81;color:#a5b4fc;padding:2px 7px;border-radius:8px;font-size:10px;font-weight:700;flex-shrink:0}
.entry-date{color:#64748b;font-size:11px;font-family:monospace;margin-left:auto}
.entry-title{font-size:15px;font-weight:700;color:#e2e8f0;line-height:1.5}
.entry-title a{color:#e2e8f0;text-decoration:none}
.entry-title a:hover{color:#7dd3fc;text-decoration:underline}
.entry-desc{color:#94a3b8;font-size:13px;line-height:1.7}
.entry-url{color:#3b82f6;font-size:11px;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.empty-state{padding:60px;text-align:center;color:#64748b;font-size:14px}
.highlight{background:#fbbf24;color:#0f172a;padding:0 2px;border-radius:2px}
</style>
</head>
<body>
<nav id="sidebar">
  <div>
    <div class="sidebar-title">Archives</div>
    <div id="archive-list"></div>
  </div>
  <div>
    <div class="sidebar-title">Quick Filters</div>
    <div id="quick-filters"></div>
  </div>
</nav>
<main id="main">
  <div class="page-header">
    <h1>Research Archive Viewer</h1>
    <div class="sub">조사기관 블로그 인덱싱 자료 조회</div>
  </div>
  <div class="controls">
    <label>Search</label>
    <input id="search" placeholder="title / description 검색 (예: foldable, memory, China)" oninput="render()">
    <label>Source</label>
    <select id="source-filter" onchange="render()">
      <option value="">All</option>
    </select>
    <label>Sort</label>
    <select id="sort" onchange="render()">
      <option value="date_desc">Date ↓ (최신)</option>
      <option value="date_asc">Date ↑ (오래된)</option>
      <option value="title_asc">Title A-Z</option>
    </select>
    <span class="match-info" id="match-info"></span>
  </div>
  <div id="entry-list"></div>
</main>
<script>
const DATA = __DATA_JS__;
const ARCHIVES = DATA.archives || [];
const ENTRIES = DATA.entries || [];

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

function highlight(text, q){
  if(!q) return esc(text);
  const safe = esc(text);
  const re = new RegExp('(' + q.replace(/[-/\\\\^$*+?.()|[\\]{}]/g,'\\\\$&') + ')', 'gi');
  return safe.replace(re, '<span class="highlight">$1</span>');
}

function fmtDate(iso){
  if(!iso) return '';
  return iso.slice(0,10);
}

function renderSidebar(){
  // archive list — "All" reset card + each archive (clickable)
  const al = document.getElementById('archive-list');
  const totalEntries = ENTRIES.length;
  let html = `<div class="archive-card" data-source="" onclick="setSourceFilter('')">
    <div class="archive-name">▦ All Sources</div>
    <div class="archive-meta">${totalEntries} entries (전체)</div>
  </div>`;
  html += ARCHIVES.map(a=>{
    const newlyAdded = (a.newly_added != null) ? `<span class="stat-pill" style="background:#14532d;color:#86efac">+${a.newly_added} new</span>` : '';
    return `<div class="archive-card" data-source="${esc(a.source)}" onclick="setSourceFilter('${esc(a.source).replace(/'/g,"\\'")}')">
      <div class="archive-name">${esc(a.source)}</div>
      <div class="archive-meta">
        ${a.entry_count || 0} entries<br>
        range: ${esc(a.range_label || '?')}<br>
        built: ${esc((a.built_at||'').slice(0,16))}
      </div>
      <div class="stat-row">${newlyAdded}</div>
    </div>`;
  }).join('');
  al.innerHTML = html || '<div style="color:#64748b;font-size:12px">(no archives)</div>';

  // source filter options
  const sf = document.getElementById('source-filter');
  const sources = [...new Set(ENTRIES.map(e=>e.source))].sort();
  for(const s of sources){
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s + ' (' + ENTRIES.filter(e=>e.source===s).length + ')';
    sf.appendChild(opt);
  }

  // quick filters
  const qf = document.getElementById('quick-filters');
  const presets = ['foldable','iPhone','Samsung','memory','AI','China','India','OLED','5G','Apple'];
  qf.innerHTML = presets.map(p=>`<span class="stat-pill" style="cursor:pointer;display:inline-block;margin:2px" onclick="setSearch('${p}')">${p}</span>`).join('');
}

function setSearch(v){
  document.getElementById('search').value = v;
  render();
}

function setSourceFilter(s){
  // 사이드바 카드 클릭 → source-filter 동기화 + active 표시 + render
  const sf = document.getElementById('source-filter');
  // 이미 같은 source가 선택된 상태에서 다시 클릭 → 해제 (toggle)
  if(sf.value === s && s !== ''){
    sf.value = '';
  } else {
    sf.value = s;
  }
  // active 카드 표시
  document.querySelectorAll('.archive-card').forEach(c=>{
    c.classList.toggle('active', c.dataset.source === sf.value);
  });
  render();
}

function render(){
  const q = document.getElementById('search').value.trim();
  const src = document.getElementById('source-filter').value;
  const sortBy = document.getElementById('sort').value;
  const ql = q.toLowerCase();

  // 드롭다운 변경 시에도 사이드바 카드 active 동기화
  document.querySelectorAll('.archive-card').forEach(c=>{
    c.classList.toggle('active', c.dataset.source === src);
  });

  let filtered = ENTRIES.filter(e=>{
    if(src && e.source !== src) return false;
    if(!q) return true;
    const blob = (e.title + ' ' + e.description + ' ' + e.url).toLowerCase();
    return blob.indexOf(ql) >= 0;
  });

  if(sortBy==='date_asc') filtered.sort((a,b)=>(a.lastmod||'').localeCompare(b.lastmod||''));
  else if(sortBy==='title_asc') filtered.sort((a,b)=>(a.title||'').localeCompare(b.title||''));
  else filtered.sort((a,b)=>(b.lastmod||'').localeCompare(a.lastmod||''));

  document.getElementById('match-info').textContent = filtered.length + ' / ' + ENTRIES.length + ' entries';

  const list = document.getElementById('entry-list');
  if(filtered.length === 0){
    list.innerHTML = '<div class="empty-state">매칭 결과 없음. 검색어를 바꿔보세요.</div>';
    return;
  }
  list.innerHTML = filtered.map(e=>`<div class="entry">
    <div class="entry-hdr">
      <span class="entry-source">${esc(e.source)}</span>
      <span class="entry-tier">tier ${e.tier}</span>
      <span class="entry-date">${esc(fmtDate(e.lastmod))}</span>
    </div>
    <div class="entry-title"><a href="${esc(e.url)}" target="_blank" rel="noopener">${highlight(e.title, q)}</a></div>
    <div class="entry-desc">${highlight(e.description, q)}</div>
    <div class="entry-url">${esc(e.url)}</div>
  </div>`).join('');
}

renderSidebar();
render();
</script>
</body>
</html>
"""


def main():
    print("=" * 60)
    print("  Archive Viewer Builder")
    print("=" * 60)

    data = collect_entries()
    print(f"  Archives: {len(data['archives'])}개")
    for a in data["archives"]:
        print(f"    - {a['source']}: {a['entry_count']}건 ({a['file']})")
    print(f"  총 entry: {len(data['entries'])}건")

    if not data["entries"]:
        print("\n  ! data/archives/ 비어있음. 먼저 archive를 빌드하세요.")
        print("    python scripts/build_counterpoint_archive.py")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # JSON 임베드 (script 태그 안전)
    data_js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__DATA_JS__", data_js)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"\n  → 저장: {OUTPUT_PATH}  ({size_kb:.1f} KB)")
    print("  → 브라우저에서 열기:")
    print(f"     file:///{OUTPUT_PATH.absolute().as_posix()}")


if __name__ == "__main__":
    main()
