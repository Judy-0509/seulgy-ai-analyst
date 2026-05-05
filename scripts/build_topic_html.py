"""
scripts/build_topic_html.py

_topic_suggestions.json + _manual_topics.json → reports/glm_topic_suggestions.html
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT          = Path(__file__).parent.parent
GLM_PATH      = ROOT / "scripts" / "_topic_suggestions.json"
MANUAL_PATH   = ROOT / "scripts" / "_manual_topics.json"
OUT_PATH      = ROOT / "reports" / "glm_topic_suggestions.html"

SOURCE_COLORS = {
    "Counterpoint Research": ("cp",  "#6c8ef5"),
    "TrendForce":            ("tf",  "#e5c07b"),
    "Omdia":                 ("om",  "#e06c75"),
    "IDC":                   ("idc", "#98c379"),
    "Morgan Stanley":        ("ms",  "#c678dd"),
}

def source_cls(src: str) -> str:
    return SOURCE_COLORS.get(src, ("xx", "#8b90a8"))[0]

def source_color(src: str) -> str:
    return SOURCE_COLORS.get(src, ("xx", "#8b90a8"))[1]

def badge_html(src: str) -> str:
    cls = source_cls(src)
    return f'<span class="badge badge-{cls}">{src}</span>'

def articles_html(articles: list[dict]) -> str:
    groups: dict[str, list] = {}
    for a in articles:
        groups.setdefault(a["source"], []).append(a)
    html = ""
    for src, items in groups.items():
        cls = source_cls(src)
        html += f'<div class="src-group">'
        html += f'<div class="src-name src-{cls}">{src}</div>'
        for a in items:
            title = a.get("title", "")
            date  = a.get("date", "")
            html += f'''<div class="ev">
  <span class="ev-title">{title}</span>
  <div class="ev-date">{date}</div>
</div>'''
        html += '</div>'
    return html

def key_data_html(data: list[str]) -> str:
    html = ""
    for i, d in enumerate(data):
        accent = "accent" if i % 2 == 1 else ""
        html += f'<div class="kd {accent}">{d}</div>'
    return html

def criteria_badge(criteria: str) -> str:
    if "2+3" in criteria or ("2" in criteria and "3" in criteria):
        return '<span class="crit-badge crit-both">기준2+3</span>'
    elif "2" in criteria:
        return '<span class="crit-badge crit-2">기준2 멀티소스</span>'
    else:
        return '<span class="crit-badge crit-3">기준3 신규</span>'

def card_class(criteria: str) -> str:
    if "2" in criteria and "3" in criteria:
        return "card card-both"
    if "3" in criteria:
        return "card card-new"
    return "card card-multi"

def topic_card(idx: int, t: dict) -> str:
    title      = t.get("title", "")
    criteria   = t.get("criteria", "")
    inst_count = t.get("institution_count", 0)
    articles   = t.get("articles", [])
    key_data   = t.get("key_data", [])
    rationale  = t.get("rationale", "")

    sources = list(dict.fromkeys(a["source"] for a in articles))
    badges  = " ".join(badge_html(s) for s in sources)

    return f'''
<div class="{card_class(criteria)}">
  <div class="card-header">
    <div class="topic-num">{idx}</div>
    <div class="topic-info">
      <div class="topic-title">{title}</div>
      <div class="badges">
        {criteria_badge(criteria)}
        {badges}
        <span class="coverage">{inst_count}개 기관</span>
      </div>
    </div>
  </div>
  <div class="flow">
    <div class="flow-col">
      <div class="col-label">참조 원문</div>
      {articles_html(articles)}
    </div>
    <div class="flow-col">
      <div class="col-label">핵심 데이터</div>
      {key_data_html(key_data)}
    </div>
    <div class="flow-col">
      <div class="col-label">선정 근거</div>
      <div class="reasoning">{rationale}</div>
    </div>
  </div>
</div>'''


def sections_html_for(data: dict) -> str:
    topics = data.get("topics", [])

    t2 = [t for t in topics if "2" in t.get("criteria","") and "3" not in t.get("criteria","")]
    t3 = [t for t in topics if t.get("criteria","") == "Criterion 3"]
    tb = [t for t in topics if "2" in t.get("criteria","") and "3" in t.get("criteria","")]

    def section(label, color, items, start_idx):
        if not items:
            return ""
        cards = ""
        for i, t in enumerate(items, start_idx):
            cards += topic_card(i, t)
        return f'''
<div class="section-title">
  <span class="section-dot" style="background:{color}"></span>
  <span class="label">{label}</span>
  <span style="color:var(--muted);font-size:12px;font-weight:400">— {len(items)}개 주제</span>
</div>
{cards}'''

    idx = 1
    html = ""
    if tb:
        html += section("기준2+3 — 멀티소스 & 신규 동시", "#c678dd", tb, idx)
        idx += len(tb)
    if t2:
        html += section("기준2 — 멀티소스 신호", "#e5c07b", t2, idx)
        idx += len(t2)
    if t3:
        html += section("기준3 — 신규 등장 주제", "#56b6c2", t3, idx)
        idx += len(t3)
    return html


def meta_line(data: dict, label: str) -> str:
    generated  = data.get("generated_at", "")[:16].replace("T", " ")
    days       = data.get("days", 30)
    art_count  = data.get("article_count", 0)
    thinking   = data.get("thinking_length", 0)
    topics     = data.get("topics", [])
    thinking_part = f"Thinking: <span>{thinking:,} chars</span> &nbsp;|&nbsp;" if thinking else ""
    return f'''
<p class="meta">
  출처: <span>{label}</span> &nbsp;|&nbsp;
  생성: <span>{generated}</span> &nbsp;|&nbsp;
  분석 기사: <span>{art_count}개</span> (최근 {days}일) &nbsp;|&nbsp;
  {thinking_part}선정 주제: <span>{len(topics)}개</span>
</p>'''


def excl_html(data: dict) -> str:
    existing = data.get("existing_reports", [])
    tags = "".join(f'<span class="excl-tag">{r}</span>' for r in existing)
    return f'''<div class="excl-row">
  <span class="excl-label">기준3 제외 (기존 레포트)</span>
  {tags}
</div>'''


def build_html(glm_data: dict, manual_data: dict) -> str:
    css_source_vars = "\n".join(
        f"  .badge-{cls} {{ background: rgba(0,0,0,.25); color: {color}; border: 1px solid {color}44; }}\n"
        f"  .src-{cls} {{ color: {color}; }}"
        for cls, color in SOURCE_COLORS.values()
    )

    glm_meta    = meta_line(glm_data, "GLM-4.7 (Thinking Mode)")
    manual_meta = meta_line(manual_data, "Claude (수동 분석)")

    criteria_boxes = '''
<div class="criteria-row">
  <div class="criteria-box criteria-box-multi">
    <div class="crit-lbl crit-lbl-multi">기준2 — 멀티소스 신호</div>
    <div class="crit-desc">서로 독립적인 Tier-1 기관 2곳 이상이 같은 현상을 30일 이내에 다룰 때 구조적 전환 신호로 인식. OEM 경쟁 우위·전략 변화도 포함.</div>
  </div>
  <div class="criteria-box criteria-box-new">
    <div class="crit-lbl crit-lbl-new">기준3 — 신규 등장 주제</div>
    <div class="crit-desc">최근 30일 DB에 처음 등장한 주제. 기존 레포트에 없는 OEM 전략 신호, 브랜드 최초 달성, 기술 자립 등 단일 기관도 포함.</div>
  </div>
  <div class="criteria-box criteria-box-both">
    <div class="crit-lbl crit-lbl-both">기준2+3 — 동시 충족</div>
    <div class="crit-desc">멀티소스 신호이면서 기존 레포트에도 없는 완전히 새로운 구조적 전환 신호.</div>
  </div>
</div>'''

    glm_sections    = sections_html_for(glm_data)
    manual_sections = sections_html_for(manual_data)

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>주제 선정 비교 — GLM vs Claude</title>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --surface2: #22263a;
    --border: #2e3248; --text: #e2e4f0; --muted: #8b90a8;
    --multi: #e5c07b; --new: #56b6c2; --both: #c678dd;
    --tab-active-glm: #6c8ef5; --tab-active-claude: #56b6c2;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg); color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px; line-height: 1.6;
    padding: 32px 24px; max-width: 1400px; margin: 0 auto;
  }}
  h1 {{ font-size: 20px; font-weight: 600; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 6px; }}
  .meta {{ color: var(--muted); font-size: 12px; margin-bottom: 16px; }}
  .meta span {{ color: var(--text); font-weight: 600; }}

  /* 탭 네비게이션 */
  .tab-nav {{
    display: flex; gap: 0; margin-bottom: 28px;
    border-bottom: 2px solid var(--border);
  }}
  .tab-btn {{
    padding: 10px 28px; font-size: 14px; font-weight: 600;
    color: var(--muted); background: transparent; border: none;
    cursor: pointer; position: relative; transition: color .15s;
    letter-spacing: .01em;
  }}
  .tab-btn::after {{
    content: ''; position: absolute; bottom: -2px; left: 0; right: 0;
    height: 2px; background: transparent; transition: background .15s;
  }}
  .tab-btn.active-glm {{ color: var(--tab-active-glm); }}
  .tab-btn.active-glm::after {{ background: var(--tab-active-glm); }}
  .tab-btn.active-claude {{ color: var(--tab-active-claude); }}
  .tab-btn.active-claude::after {{ background: var(--tab-active-claude); }}
  .tab-btn .tab-count {{
    display: inline-block; margin-left: 7px; font-size: 11px;
    font-weight: 700; padding: 1px 7px; border-radius: 10px;
    background: var(--surface2);
  }}

  /* 탭 패널 */
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}

  /* 기존 레포트 제외 목록 */
  .excl-row {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:28px; align-items:center; }}
  .excl-label {{ font-size:11px; color:var(--muted); font-weight:700;
                 text-transform:uppercase; letter-spacing:.08em; white-space:nowrap; }}
  .excl-tag {{
    font-size:11px; padding:2px 8px; border-radius:4px;
    background:rgba(255,255,255,.05); border:1px solid var(--border); color:var(--muted);
    text-decoration: line-through;
  }}

  /* 기준 설명 */
  .criteria-row {{ display:flex; gap:12px; margin-bottom:36px; flex-wrap:wrap; }}
  .criteria-box {{
    flex:1; min-width:220px;
    background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:14px 16px;
  }}
  .criteria-box-multi {{ border-top:3px solid var(--multi); }}
  .criteria-box-new   {{ border-top:3px solid var(--new); }}
  .criteria-box-both  {{ border-top:3px solid var(--both); }}
  .crit-lbl {{ font-size:11px; font-weight:700; letter-spacing:.08em;
               text-transform:uppercase; margin-bottom:5px; }}
  .crit-lbl-multi {{ color:var(--multi); }}
  .crit-lbl-new   {{ color:var(--new); }}
  .crit-lbl-both  {{ color:var(--both); }}
  .crit-desc {{ font-size:12px; color:var(--muted); line-height:1.5; }}

  /* 섹션 */
  .section-title {{
    display:flex; align-items:center; gap:10px;
    font-size:11px; font-weight:700; letter-spacing:.1em;
    text-transform:uppercase; color:var(--muted);
    margin:36px 0 16px; padding-bottom:8px; border-bottom:1px solid var(--border);
  }}
  .section-title .label {{ color:var(--text); font-size:14px;
                           text-transform:none; letter-spacing:0; font-weight:600; }}
  .section-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}

  /* 카드 */
  .card {{ background:var(--surface); border:1px solid var(--border);
           border-radius:10px; margin-bottom:20px; overflow:hidden; }}
  .card-multi {{ border-top:3px solid var(--multi); }}
  .card-new   {{ border-top:3px solid var(--new); }}
  .card-both  {{ border-top:3px solid var(--both); }}

  .card-header {{
    display:flex; align-items:flex-start; gap:14px;
    padding:16px 20px 14px; border-bottom:1px solid var(--border);
  }}
  .topic-num {{
    width:28px; height:28px; background:var(--surface2); border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:13px; font-weight:700; color:var(--muted);
    flex-shrink:0; margin-top:2px;
  }}
  .topic-info {{ flex:1; }}
  .topic-title {{ font-size:15px; font-weight:600; margin-bottom:8px; }}
  .badges {{ display:flex; gap:6px; flex-wrap:wrap; align-items:center; }}
  .badge {{ font-size:11px; font-weight:600; padding:2px 8px;
            border-radius:4px; letter-spacing:.02em; }}
  .crit-badge {{ font-size:11px; font-weight:700; padding:2px 9px; border-radius:4px; }}
  .crit-2    {{ background:rgba(229,192,123,.12); color:var(--multi); border:1px solid rgba(229,192,123,.3); }}
  .crit-3    {{ background:rgba(86,182,194,.12);  color:var(--new);   border:1px solid rgba(86,182,194,.3); }}
  .crit-both {{ background:rgba(198,120,221,.12); color:var(--both);  border:1px solid rgba(198,120,221,.3); }}
  .coverage {{ font-size:11px; color:var(--muted); margin-left:2px; }}

{css_source_vars}

  /* 3컬럼 */
  .flow {{ display:grid; grid-template-columns:1.1fr 1fr 1fr; }}
  .flow-col {{ padding:16px 18px; border-right:1px solid var(--border); }}
  .flow-col:last-child {{ border-right:none; }}
  .col-label {{ font-size:10px; font-weight:700; letter-spacing:.1em;
                text-transform:uppercase; color:var(--muted); margin-bottom:12px; }}

  /* 소스 */
  .src-group {{ margin-bottom:14px; }}
  .src-name {{ font-size:11px; font-weight:700; margin-bottom:6px; letter-spacing:.03em; }}
  .ev {{ margin-bottom:8px; padding-left:10px; border-left:2px solid var(--border); }}
  .ev-title {{ font-size:12px; line-height:1.4; color:var(--text); }}
  .ev-date {{ font-size:11px; color:var(--muted); margin-top:2px; }}

  /* 핵심 데이터 */
  .kd {{ margin-bottom:8px; padding:8px 10px; background:var(--surface2);
         border-radius:6px; font-size:12px; line-height:1.5; color:var(--text); }}
  .kd.accent {{ border-left:2px solid var(--new); }}

  /* 선정 근거 */
  .reasoning {{ font-size:12px; line-height:1.75; color:var(--text); }}
</style>
</head>
<body>

<h1>스마트폰 시장 주제 선정 비교</h1>
<p class="subtitle">GLM-4.7 Thinking Mode vs Claude 수동 분석</p>

<nav class="tab-nav">
  <button class="tab-btn active-glm" onclick="switchTab('glm', this)">
    GLM 제안
    <span class="tab-count">{len(glm_data.get("topics", []))}</span>
  </button>
  <button class="tab-btn" onclick="switchTab('claude', this)">
    Claude 제안
    <span class="tab-count">{len(manual_data.get("topics", []))}</span>
  </button>
</nav>

<!-- GLM 탭 -->
<div id="panel-glm" class="tab-panel active">
  {glm_meta}
  {excl_html(glm_data)}
  {criteria_boxes}
  {glm_sections}
</div>

<!-- Claude 탭 -->
<div id="panel-claude" class="tab-panel">
  {manual_meta}
  {excl_html(manual_data)}
  {criteria_boxes}
  {manual_sections}
</div>

<script>
function switchTab(name, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.className = 'tab-btn');
  document.getElementById('panel-' + name).classList.add('active');
  btn.classList.add('active-' + name);
}}
</script>

</body>
</html>'''


def main():
    if not GLM_PATH.exists():
        print(f"[!] {GLM_PATH} not found. Run suggest_topics.py first.")
        return
    if not MANUAL_PATH.exists():
        print(f"[!] {MANUAL_PATH} not found.")
        return

    glm_data    = json.loads(GLM_PATH.read_text(encoding="utf-8"))
    manual_data = json.loads(MANUAL_PATH.read_text(encoding="utf-8"))

    html = build_html(glm_data, manual_data)
    OUT_PATH.write_text(html, encoding="utf-8")

    glm_count    = len(glm_data.get("topics", []))
    manual_count = len(manual_data.get("topics", []))
    print(f"Done: {OUT_PATH}  (GLM: {glm_count} topics, Claude: {manual_count} topics)")


if __name__ == "__main__":
    main()
