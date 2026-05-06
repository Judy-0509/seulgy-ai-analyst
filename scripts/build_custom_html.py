"""웹 ReportPage.jsx 의 CustomSlideView 를 정적 HTML 로 포팅.

기존 reports/{slug}_process.json 만 있으면 LLM 호출 없이 즉시 생성.
도메인 자동 감지(스마트폰/휴머노이드/자동차)로 액센트 컬러 일치.

사용:
    python scripts/build_custom_html.py "<slug>"
    python scripts/build_custom_html.py "reports/<slug>_process.json"

산출:
    reports/{slug}_custom.html  (단일 파일, 외부 의존성 없음)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REPORTS = ROOT / "reports"

# ── 도메인별 액센트 (ReportPage.jsx 의 makeR() 와 동일) ──────────
BASE = {
    "bg":          "#f7f6f3",
    "panel":       "rgba(255,255,255,.72)",
    "panelStrong": "rgba(255,255,255,.9)",
    "border":      "rgba(42,40,38,.09)",
    "t1":          "#2a2826",
    "t2":          "#4a4744",
    "t3":          "#716f6c",
    "t4":          "#9a9896",
    "shadow":      "0 12px 34px rgba(31,41,55,.08), inset 0 1px 0 rgba(255,255,255,.76)",
}
THEMES = {
    "smartphone": {"em": "#10b981", "emD": "#047857", "emBg": "rgba(16,185,129,.09)", "emBr": "rgba(16,185,129,.24)"},
    "humanoid":   {"em": "#ef4444", "emD": "#b91c1c", "emBg": "rgba(239,68,68,.09)",  "emBr": "rgba(239,68,68,.24)"},
    "automotive": {"em": "#2563eb", "emD": "#1d4ed8", "emBg": "rgba(37,99,235,.09)",  "emBr": "rgba(37,99,235,.24)"},
}

HUMANOID_SOURCES = {
    "The Robot Report", "IEEE Spectrum", "TechCrunch Robotics", "MIT Technology Review",
    "Robotics & Automation News", "The Verge", "arXiv (cs.RO)", "NVIDIA",
    "Boston Dynamics", "Figure AI", "Unitree Robotics",
}
AUTOMOTIVE_SOURCES = {
    "JATO Dynamics", "AlixPartners", "WardsAuto", "SAE International",
    "VW Group", "Cox Automotive", "Automotive Dive", "Automotive World",
    "Electrek", "InsideEVs", "Toyota Newsroom",
}


def detect_domain(process_data: dict) -> str:
    sources = {s.get("source_name", "") for s in process_data.get("archive_sources", [])}
    if sources & HUMANOID_SOURCES:
        return "humanoid"
    if sources & AUTOMOTIVE_SOURCES:
        return "automotive"
    return "smartphone"


def first_sentences(text: str, max_sent: int = 2) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    parts = re.findall(r"[^.!?。！？]+[.!?。！？]?", cleaned) or [cleaned]
    return " ".join(parts[:max_sent]).strip()


def parse_md_sections(md_text: str) -> dict[str, dict]:
    """Markdown 본문에서 섹션별 headline/narrative/bullets 추출."""
    out: dict[str, dict] = {}
    if not md_text:
        return out

    # 섹션 헤더 패턴: "## 1. 제목" 또는 "## 제목"
    section_pat = re.compile(r"^##\s+(?:\d+\.\s+)?(.+?)\s*$", re.MULTILINE)
    matches = list(section_pat.finditer(md_text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        # 메타 섹션 (Executive Summary, 시사점 등) 제외
        if title.lower() in {"executive summary", "시사점", "조사 배경", "참고 자료", "references"}:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        body = md_text[start:end].strip()

        # 첫 줄: 굵은 한 줄 (headline)
        headline = ""
        narrative = body
        first_line_match = re.match(r"^\*\*(.+?)\*\*\s*\n+", body)
        if first_line_match:
            headline = first_line_match.group(1).strip()
            narrative = body[first_line_match.end():].strip()

        # 불릿 추출 (• 또는 - 로 시작)
        bullets = re.findall(r"^[•\-]\s+(.+?)(?=\n[•\-]|\n\n|$)", narrative, re.MULTILINE | re.DOTALL)
        # 본문 내러티브: 불릿 빼고 첫 단락만
        narrative_paragraph = re.split(r"\n[•\-]\s", narrative, maxsplit=1)[0].strip()
        # 인용 마크다운 정리
        narrative_paragraph = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", narrative_paragraph)

        out[title] = {
            "headline": headline,
            "narrative": narrative_paragraph,
            "bullets": [b.strip() for b in bullets if b.strip()],
        }
    return out


def build_sections(process_sections: list, md_sections: dict) -> list:
    out = []
    for i, sec in enumerate(process_sections, 1):
        title = sec.get("title", "")
        md = md_sections.get(title, {})
        out.append({
            "index": i,
            "title": title,
            "headline": md.get("headline", ""),
            "narrative": md.get("narrative") or sec.get("angle", ""),
            "bullets": md.get("bullets", []),
        })
    return out


def html_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def build_html(slug: str, process_data: dict, md_text: str) -> str:
    topic = process_data["topic"]
    meta = process_data.get("meta", {})
    domain = detect_domain(process_data)
    R = {**BASE, **THEMES.get(domain, THEMES["smartphone"])}

    background = meta.get("research_background") or first_sentences(meta.get("executive_summary", ""), 2)
    insights_raw = meta.get("insights", [])
    insight_lines = [
        {"title": ins.get("title", ""), "summary": first_sentences(ins.get("body", ""), 2) or ins.get("title", "")}
        for ins in insights_raw
    ]
    md_sections = parse_md_sections(md_text)
    sections = build_sections(process_data.get("sections", []), md_sections)

    # ── HTML 빌드 ──
    insights_html = "\n          ".join(
        f'''<div style="padding:12px 14px;border-radius:8px;background:{R["emBg"]};border:1px solid {R["emBr"]}">
            <p style="margin:0 0 5px;font-size:12.5px;font-weight:800;color:{R["emD"]};letter-spacing:-.01em">{i+1}. {html_escape(ins["title"])}</p>
            <p style="margin:0;font-size:13px;color:{R["t2"]};line-height:1.6">{html_escape(ins["summary"])}</p>
          </div>'''
        for i, ins in enumerate(insight_lines)
    )

    sections_html_parts = []
    for sec in sections:
        headline_html = (
            f'<p style="margin:0 0 9px;font-size:13px;font-weight:500;color:{R["emD"]};line-height:1.5">{html_escape(sec["headline"])}</p>'
            if sec["headline"] else ""
        )
        narrative_html = (
            f'<p style="margin:0 0 10px;font-size:12.6px;color:{R["t2"]};line-height:1.65">{html_escape(sec["narrative"])}</p>'
            if sec["narrative"] else ""
        )
        sections_html_parts.append(
            f'''<div style="padding:15px 16px;border-radius:10px;background:{R["emBg"]};border:1px solid {R["emBr"]};min-width:0">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
              <span style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:7px;background:{R["emBg"]};border:1px solid {R["emBr"]};color:{R["emD"]};font-size:11px;font-weight:800;flex-shrink:0">{sec["index"]}</span>
              <h3 style="margin:0;font-size:14.5px;line-height:1.35;color:{R["t1"]}">{html_escape(sec["title"])}</h3>
            </div>
            {headline_html}
            {narrative_html}
          </div>'''
        )
    sections_html = "\n          ".join(sections_html_parts)

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_escape(topic)}</title>
<style>
  *,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:{R["bg"]}; color:{R["t1"]}; min-height:100vh; padding:28px;
    font-family:"Apple SD Gothic Neo",-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Helvetica Neue",sans-serif;
  }}
  .wrap {{ max-width:1080px; margin:0 auto; }}
  article {{
    padding:0; background:transparent; border:0; box-shadow:none;
  }}
  .grid {{ display:grid; grid-template-rows:auto auto auto 1fr; gap:12px; }}
  .section {{ padding:18px 22px; border-radius:12px; }}
  .brand {{ background:{R["panelStrong"]}; border:1px solid {R["border"]}; }}
  .bg-em {{ background:{R["emBg"]}; border:1px solid {R["emBr"]}; }}
  .badge {{
    display:inline-flex; align-items:center; height:20px; padding:0 7px;
    border-radius:6px; background:{R["emBg"]}; color:{R["emD"]};
    border:1px solid {R["emBr"]}; font-size:10.5px; font-weight:700; white-space:nowrap;
  }}
  h1.topic {{ margin:12px 0 0; font-size:26px; line-height:1.28; color:{R["t1"]}; font-weight:700; letter-spacing:0; }}
  h2.label {{ margin:0 0 10px; font-size:15px; color:{R["emD"]}; font-weight:700; }}
  h2.insights-label {{ margin:0 0 8px; font-size:14px; color:{R["emD"]}; font-weight:700; }}
  .bg-text {{ margin:0; font-size:14px; color:{R["t2"]}; line-height:1.7; }}
  .list {{ display:grid; gap:10px; }}
</style>
</head>
<body>
<div class="wrap">
  <article>
    <div class="grid">
      <section class="section brand">
        <span class="badge">Custom Brief</span>
        <h1 class="topic">{html_escape(topic)}</h1>
      </section>
      <section class="section bg-em">
        <h2 class="label">조사 배경</h2>
        <p class="bg-text">{html_escape(background)}</p>
      </section>
      <section style="padding:4px 0 0">
        <h2 class="insights-label">시사점</h2>
        <div class="list">
          {insights_html}
        </div>
      </section>
      <section class="section brand" style="min-height:0">
        <h2 class="label">핵심 분석</h2>
        <div class="list">
          {sections_html}
        </div>
      </section>
    </div>
  </article>
</div>
</body>
</html>
'''


def slugify_load(arg: str) -> tuple[str, dict, str]:
    p = Path(arg)
    if p.name.endswith("_process.json") and p.exists():
        process_path = p.resolve()
        slug = process_path.name.replace("_process.json", "")
    else:
        slug = arg
        process_path = REPORTS / f"{slug}_process.json"
    if not process_path.exists():
        raise FileNotFoundError(f"process.json not found: {process_path}")
    md_path = REPORTS / f"{slug}_report.md"
    process_data = json.loads(process_path.read_text(encoding="utf-8"))
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    return slug, process_data, md_text


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python scripts/build_custom_html.py <slug | process.json>")
        return 1
    slug, process_data, md_text = slugify_load(args[0])
    html = build_html(slug, process_data, md_text)
    out_path = REPORTS / f"{slug}_custom.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[OK] Custom HTML: {out_path}")
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    raise SystemExit(main())
