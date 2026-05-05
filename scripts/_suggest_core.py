"""공통 파이프라인 엔진 — 도메인별 suggest_*.py 스크립트에서 공유.

도메인 스크립트는 ARCHIVE_REGISTRY, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE 등을
정의하고 run_pipeline()을 호출합니다.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent

_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from openai import OpenAI  # noqa: E402

ARCHIVES_DIR = ROOT / "data" / "archives"
REPORTS_DIR  = ROOT / "reports"

STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "will", "have",
    "been", "were", "are", "how", "what", "when", "where", "which", "also",
    "its", "their", "they", "than", "into", "amid", "shows", "show",
    "report", "but", "all", "more", "most", "our", "has", "had",
    "rise", "fell", "fall", "hits", "hit", "sees", "see", "gets",
    "says", "said", "over", "sets", "year", "years", "time", "data",
    "first", "second", "third", "quarter", "annual", "monthly",
    "driven", "drive", "drives", "lead", "leads", "leading", "ahead",
    "strong", "back", "high", "low", "next", "support", "supports",
    "market", "global", "growth", "sales", "share", "shipments",
}


# ── LLM client ─────────────────────────────────────────────────────────────

def make_client():
    """LLM_BACKEND 환경변수에 따라 (client, model, thinking_body) 반환."""
    backend = os.environ.get("LLM_BACKEND", "glm")
    if backend == "qwen":
        client = OpenAI(
            api_key=os.environ["QWEN_API_KEY"],
            base_url=os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        model = os.environ.get("QWEN_MODEL", "qwen3-32b")
        thinking_body = {"enable_thinking": True}
    else:
        client = OpenAI(
            api_key=os.environ["ZHIPU_API_KEY"],
            base_url="https://open.bigmodel.cn/api/paas/v4/",
        )
        model = "glm-4.7"
        thinking_body = {"thinking": {"type": "enabled"}}
    return client, model, thinking_body


# ── Article helpers ─────────────────────────────────────────────────────────

def _clean_entry(e: dict, source: str) -> dict:
    return {
        "source": source,
        "date":   e.get("lastmod", "")[:10],
        "title":  e.get("title", "").replace("‑", "-").replace("’", "'"),
        "url":    e.get("url", ""),
        "desc":   re.sub(r"<[^>]+>", "", e.get("description", ""))[:400]
                    .replace("‑", "-").replace("’", "'").strip(),
    }


def _parse_dt(lm: str):
    try:
        dt = datetime.fromisoformat(lm.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def load_articles(registry: list[tuple[str, str]], days: int,
                  keyword_filter=None) -> list[dict]:
    """레지스트리 소스에서 기사 로드. keyword_filter(entry)->bool, None이면 전체."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    articles = []
    for source, fname in registry:
        p = ARCHIVES_DIR / fname
        if not p.exists():
            continue
        for e in json.loads(p.read_text(encoding="utf-8")).get("entries", []):
            dt = _parse_dt(e.get("lastmod", ""))
            if dt is None or dt < cutoff:
                continue
            if keyword_filter and not keyword_filter(e):
                continue
            articles.append(_clean_entry(e, source))
    return articles


def extract_search_terms(topic: dict) -> tuple[list[str], list[str]]:
    terms = set()
    for a in topic.get("articles", []):
        for w in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{3,}", a.get("title", "")):
            w_lower = w.lower()
            if w_lower not in STOP_WORDS:
                terms.add(w_lower)
    specific = [t for t in terms if len(t) >= 7]
    return list(terms), specific


def find_additional_articles(topic: dict, all_articles: list[dict],
                              pass1_titles: set) -> list[dict]:
    common, specific = extract_search_terms(topic)
    if not common:
        return []
    topic_titles = {a["title"] for a in topic.get("articles", [])}
    additional = []
    for a in all_articles:
        if a["title"] in pass1_titles or a["title"] in topic_titles:
            continue
        text = (a["title"] + " " + a["desc"]).lower()
        if sum(1 for t in common if t in text) >= 2 or \
           sum(1 for t in specific if t in text) >= 1:
            additional.append(a)
    return additional


def format_article_list(articles: list[dict]) -> str:
    lines = []
    for a in sorted(articles, key=lambda x: (x["source"], x["date"])):
        lines.append(f"[{a['date']}] {a['source']} — {a['title']}")
        if a.get("desc"):
            lines.append(f"  → {a['desc']}")
    return "\n".join(lines)


def format_articles(articles: list[dict]) -> str:
    lines = []
    current_source = None
    for a in sorted(articles, key=lambda x: (x["source"], x["date"])):
        if a["source"] != current_source:
            current_source = a["source"]
            lines.append(f"\n## {current_source}")
        lines.append(f"[{a['date']}] {a['title']}")
        if a["desc"]:
            lines.append(f"  → {a['desc'][:400]}")
    return "\n".join(lines)


def parse_json_response(raw: str) -> list[dict]:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        return json.loads(m.group())
    return json.loads(raw)


def get_existing_reports() -> list[str]:
    reports = []
    for p in sorted(REPORTS_DIR.glob("*_report.md")):
        name = p.stem.replace("_report", "").replace("_", " ")
        reports.append(name)
    return reports


# ── Enrichment ──────────────────────────────────────────────────────────────

def enrich_topic(topic: dict, extra: list[dict], client, model: str,
                 enrich_system: str, enrich_tpl: str) -> dict:
    prompt = enrich_tpl.format(
        title               = topic.get("title", ""),
        criteria            = topic.get("criteria", ""),
        existing_articles   = format_article_list(
            [{"source": a["source"], "date": a["date"], "title": a["title"], "desc": ""}
             for a in topic.get("articles", [])]),
        key_data            = "\n".join(f"- {d}" for d in topic.get("key_data", [])),
        rationale           = topic.get("rationale", ""),
        additional_articles = format_article_list(extra),
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": enrich_system},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=4000,
        temperature=0.1,
    )
    raw = response.choices[0].message.content or ""
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return topic


# ── Pipeline ────────────────────────────────────────────────────────────────

def run_pipeline(
    *,
    registry: list[tuple[str, str]],
    keyword_filter,          # callable(entry)->bool  또는  None
    system_prompt: str,
    user_prompt_template: str,
    enrich_system: str,
    enrich_tpl: str,
    out_path: str,           # ROOT 상대 경로
    domain_label: str,
    source_label: str,       # USER_PROMPT_TEMPLATE 내 {source_label}
    days: int,
    with_existing: bool = False,
):
    """5-step 공통 파이프라인."""
    # Step 1 — 기사 로드
    print(f"[1/5] Loading articles (last {days} days, domain={domain_label})...")
    articles = load_articles(registry, days, keyword_filter)
    print(f"      → {len(articles)} articles")

    existing = get_existing_reports() if with_existing else []
    if existing:
        print(f"[2/5] Existing reports ({len(existing)}):")
        for r in existing:
            print(f"      · {r}")
    else:
        print("[2/5] Existing reports: none")

    existing_str = "\n".join(f"- {r}" for r in existing) or "- (none)"
    user_prompt = user_prompt_template.format(
        existing_reports=existing_str,
        days=days,
        total=len(articles),
        articles=format_articles(articles),
        source_label=source_label,
    )

    # Step 3 — Pass 1 LLM
    client, model, thinking_body = make_client()
    print(f"[3/5] Pass 1 — {model} thinking ({domain_label})...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=30000,
        temperature=0.1,
        extra_body=thinking_body,
    )
    msg       = response.choices[0].message
    reasoning = getattr(msg, "reasoning_content", "") or ""
    content   = msg.content or ""
    print(f"      thinking: {len(reasoning):,} chars")

    try:
        topics = parse_json_response(content)
    except Exception as e:
        print(f"[!] JSON parse failed: {e}")
        print("Raw (first 500):\n", content[:500])
        sys.exit(1)
    print(f"      → {len(topics)} topics identified")

    # Step 4 — Pass 2 enrichment
    print("[4/5] Pass 2 — full archive search & enrichment...")
    all_articles = load_articles(registry, days, keyword_filter=None)
    pass1_titles = {a["title"] for a in articles}

    enriched_topics: list[dict] = []
    enriched_count = 0
    for i, topic in enumerate(topics, 1):
        extra = find_additional_articles(topic, all_articles, pass1_titles)
        label = topic.get("title", "")[:50]
        if extra:
            print(f"      [{i}] +{len(extra)} articles — re-writing: {label}...")
            updated = enrich_topic(topic, extra, client, model, enrich_system, enrich_tpl)
            enriched_topics.append(updated)
            enriched_count += 1
        else:
            print(f"      [{i}] no additional: {label}")
            enriched_topics.append(topic)

    # URL 주입
    url_map = {a["title"]: a.get("url", "") for a in all_articles}
    for a in articles:
        if a.get("url"):
            url_map.setdefault(a["title"], a["url"])
    for topic in enriched_topics:
        for art in topic.get("articles", []):
            if not art.get("url"):
                art["url"] = url_map.get(art["title"], "")

    # Step 5 — 저장
    out = ROOT / out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({
            "generated_at":    datetime.now().isoformat(),
            "domain":          domain_label,
            "days":            days,
            "article_count":   len(articles),
            "existing_reports": existing,
            "topics":          enriched_topics,
            "thinking_length": len(reasoning),
            "enriched_count":  enriched_count,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[5/5] Done.")
    print("=" * 60)
    print(f"  {len(enriched_topics)} topics  |  {enriched_count} enriched  |  thinking {len(reasoning):,} chars")
    print(f"  Saved → {out}")
    print("=" * 60)
    for i, t in enumerate(enriched_topics, 1):
        crit  = t.get("criteria", "")
        count = t.get("institution_count", "?")
        print(f"\n[{i}] {t.get('title', '')}")
        print(f"     {crit} | {count} source(s)")
        for a in t.get("articles", []):
            print(f"     · [{a.get('date','')}] {a.get('source','')} - {a.get('title','')[:65]}")
        rationale = t.get("rationale", "")
        print(f"     → {rationale[:130]}{'...' if len(rationale) > 130 else ''}")
