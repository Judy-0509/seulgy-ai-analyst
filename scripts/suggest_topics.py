"""
GLM-4.7 (thinking mode) 기반 스마트폰 시장 주제 자동 선정.

기준2: 14일 이내 2개 이상 Tier-1 기관이 같은 현상을 다루는 경우
기준3: 최근 N일 DB에 새롭게 등장한 주제 (기존 레포트에 없는 것)

2-pass 파이프라인:
  Pass 1 — 스마트폰 키워드 필터 → GLM → 초기 주제
  Pass 2 — 주제별 검색어 추출 → 전체 아카이브 탐색 → 추가 기사 발견 시 GLM 재작성

사용법:
  python scripts/suggest_topics.py [--days 30] [--out scripts/_topic_suggestions.json]
"""
import argparse
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

from openai import OpenAI

def _make_client():
    """LLM_BACKEND 환경변수에 따라 (client, model, thinking_body) 반환."""
    backend = os.environ.get("LLM_BACKEND", "glm")
    if backend == "qwen":
        client = OpenAI(
            api_key=os.environ["QWEN_API_KEY"],
            base_url=os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        model = os.environ.get("QWEN_MODEL", "qwen3-32b")
        thinking_body = {"enable_thinking": True}
    else:  # glm (기본값)
        client = OpenAI(
            api_key=os.environ["ZHIPU_API_KEY"],
            base_url="https://open.bigmodel.cn/api/paas/v4/",
        )
        model = "glm-4.7"
        thinking_body = {"thinking": {"type": "enabled"}}
    return client, model, thinking_body


ARCHIVES_DIR = ROOT / "data" / "archives"
REPORTS_DIR  = ROOT / "reports"
KW_PATH      = ROOT / "data" / "smartphone_keywords.json"

ARCHIVE_REGISTRY = [
    ("Counterpoint Research", "counterpoint.json"),
    ("TrendForce",            "trendforce.json"),
    ("Omdia",                 "omdia.json"),
    ("IDC",                   "idc.json"),
    ("Morgan Stanley",        "morgan_stanley.json"),
]

# ── Prompts ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior smartphone market intelligence analyst focused on OEM strategy
and brand-level competitive dynamics.
Your task is to identify research-worthy topics from a corpus of recent analyst reports.

[Core Principle]
Cluster articles by the MARKET PHENOMENON they describe, not by shared keywords.
Example: "Amazon acquires Globalstar" and "LEO satellite market inflection analysis"
are the SAME phenomenon (structural shift to always-on D2D satellite connectivity)
even though they share no keywords.

Prioritize signals at the OEM and brand level:
- A specific OEM achieving a competitive first (market share record, segment leadership, etc.)
- A brand entering a new product category or pivoting strategy
- Structural competitive advantage of one OEM over others becoming visible
- Divergence between OEM roadmaps and consumer adoption reality
- A brand's supply chain or technology self-sufficiency move (proprietary chips, vertical integration)

Also flag:
- Paradigm shifts in market structure that directly affect OEM strategy
- Technology transitions that change how OEMs differentiate their products

Do NOT flag:
- Routine periodic data tracker updates with no directional insight
- Semiconductor/memory supply chain signals with no direct OEM strategy implication
- Incremental updates to already well-documented trends"""

USER_PROMPT_TEMPLATE = """
[EXISTING REPORTS — exclude these topics from Criterion 3 ONLY]
{existing_reports}

IMPORTANT: This exclusion applies ONLY to Criterion 3 (emerging topics).
It does NOT apply to Criterion 2. Even if a topic area has an existing report,
new multi-source evidence within the last 14 days still qualifies as a Criterion 2
signal — the situation may have structurally evolved since the report was written.

[ARTICLE CORPUS — Tier-1 smartphone market articles, last {days} days]
Total: {total} articles | Sources: Counterpoint Research, TrendForce, Omdia, IDC, Morgan Stanley

{articles}

---

[SELECTION CRITERIA]

Criterion 2 — Multi-Source Signal:
2 or more independent research institutions covered the SAME market phenomenon
within a 14-day window. Institutions must be drawn from the Tier-1 list above.
"Same phenomenon" is judged semantically, not by keyword overlap.

OEM-level signals qualify: if 2+ institutions independently confirm the same brand's
strategic shift, competitive milestone, or structural advantage — even from different
angles — that counts as one multi-source signal.
Example A: Counterpoint reporting Apple's all-time record Q1 revenue + IDC confirming
Apple's resilience in China + Omdia publishing Apple's strategy outlook = one signal
(Apple achieving structural dominance during a market downturn).

CRITICAL — Opposing-direction articles can be the SAME phenomenon:
If one institution reports what OEMs are building or planning (supply-side roadmap)
while another reports how consumers are actually responding (demand-side reality),
these are TWO SIDES OF THE SAME STRUCTURAL SIGNAL — the gap between them IS the
market insight, even though one article is bullish and the other is bearish.
General form: [OEM roadmap article: "OEMs are pushing X"] + [Consumer reality article:
"consumers are not ready for X / actual usage of X is low"] = one Criterion 2 signal
(structural divergence between OEM ambition and market adoption reality).

Criterion 3 — Emerging Topic:
A topic that appears in the last {days} days and is NOT covered by any existing report above.
Single-institution articles qualify if the topic is genuinely new.

High-value Criterion 3 signals include:
- An OEM achieving a market first (e.g. first time leading global market share in Q1,
  first to launch a new product category)
- A brand's strategic pivot into a new segment or technology (e.g. proprietary SoC
  development, entry into AI wearables)
- A specific OEM's competitive position shifting in a key market (e.g. surpassing a
  rival in a country for the first time)
- An OEM product launch that signals industry-wide direction change (e.g. first
  mid-range AI phone, first horizontal foldable from a Chinese OEM)

---

[OUTPUT — JSON array only, no other text]
Identify 5 to 10 topics. For each topic output:

[
  {{
    "title": "Topic title in Korean (noun phrase capturing the core phenomenon)",
    "criteria": "Criterion 2" | "Criterion 3" | "Criterion 2+3",
    "institution_count": <integer>,
    "articles": [
      {{"date": "YYYY-MM-DD", "source": "<institution>", "title": "<original article title>"}}
    ],
    "key_data": [
      "<concrete data point with %, $, year, or volume figures>",
      "..."
    ],
    "rationale": "2-3 sentences explaining why this is a structural signal, not just a trend. Cite specific article evidence."
  }}
]"""

ENRICH_PROMPT = """You previously identified the following topic from a smartphone market corpus:

TOPIC (KOREAN): {title}
CRITERIA: {criteria}

CITED ARTICLES:
{existing_articles}

KEY DATA:
{key_data}

RATIONALE: {rationale}

---

Additional articles have now been found that were not in the original corpus but are
relevant to this same market phenomenon:

ADDITIONAL ARTICLES:
{additional_articles}

---

Update this topic to incorporate the additional articles where relevant.
Output a single JSON object only (no markdown, no other text):

{{
  "title": "...",
  "criteria": "Criterion 2" | "Criterion 3" | "Criterion 2+3",
  "institution_count": <count unique institutions across ALL articles>,
  "articles": [
    {{"date": "YYYY-MM-DD", "source": "<institution>", "title": "<article title>"}}
  ],
  "key_data": ["<updated data points — add new concrete figures if found>"],
  "rationale": "2-3 sentences reflecting the fuller picture from all sources."
}}

Rules:
- Keep ALL original cited articles; add additional ones that genuinely support this phenomenon
- Discard additional articles that are not actually about this phenomenon
- Update institution_count to reflect unique institutions across all included articles
- If institution_count rises to 2+, upgrade single-source Criterion 3 to Criterion 2 or 2+3
- Preserve the Korean title unless a better framing emerges from the new evidence"""


# ── Helpers ────────────────────────────────────────────────────────────────

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
    "amid", "amid", "amid",
}


def load_keywords() -> list[str]:
    return json.loads(KW_PATH.read_text(encoding="utf-8"))["keywords"]


def is_smartphone(entry: dict, kw: list[str]) -> bool:
    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
    return any(k in text for k in kw)


def _clean_entry(e: dict, source: str) -> dict:
    return {
        "source": source,
        "date":   e.get("lastmod", "")[:10],
        "title":  e.get("title", "").replace("‑", "-").replace("’", "'"),
        "desc":   re.sub(r"<[^>]+>", "", e.get("description", ""))[:400]
                    .replace("‑", "-").replace("’", "'").strip(),
    }


def _parse_dt(lm: str):
    try:
        dt = datetime.fromisoformat(lm.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def load_articles(days: int) -> list[dict]:
    """Smartphone-keyword-filtered articles (Pass 1 corpus)."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    kw = load_keywords()
    articles = []
    for source, fname in ARCHIVE_REGISTRY:
        p = ARCHIVES_DIR / fname
        if not p.exists():
            continue
        for e in json.loads(p.read_text(encoding="utf-8")).get("entries", []):
            dt = _parse_dt(e.get("lastmod", ""))
            if dt is None or dt < cutoff:
                continue
            if not is_smartphone(e, kw):
                continue
            articles.append(_clean_entry(e, source))
    return articles


def load_all_articles(days: int) -> list[dict]:
    """ALL Tier-1 articles, no keyword filter — used in Pass 2."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    articles = []
    for source, fname in ARCHIVE_REGISTRY:
        p = ARCHIVES_DIR / fname
        if not p.exists():
            continue
        for e in json.loads(p.read_text(encoding="utf-8")).get("entries", []):
            dt = _parse_dt(e.get("lastmod", ""))
            if dt is None or dt < cutoff:
                continue
            articles.append(_clean_entry(e, source))
    return articles


def extract_search_terms(topic: dict) -> tuple[list[str], list[str]]:
    """
    Returns (common_terms, specific_terms) extracted from topic's article titles.
    specific_terms: words >= 7 chars (proper nouns / domain terms).
    Requires >= 2 common OR >= 1 specific to match.
    """
    terms = set()
    for a in topic.get("articles", []):
        for w in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{3,}", a.get("title", "")):
            w_lower = w.lower()
            if w_lower not in STOP_WORDS:
                terms.add(w_lower)
    specific = [t for t in terms if len(t) >= 7]
    common   = list(terms)
    return common, specific


def find_additional_articles(topic: dict, all_articles: list[dict],
                              pass1_titles: set) -> list[dict]:
    """Articles from full corpus relevant to topic but outside Pass 1."""
    common, specific = extract_search_terms(topic)
    if not common:
        return []

    topic_titles = {a["title"] for a in topic.get("articles", [])}
    additional = []
    for a in all_articles:
        if a["title"] in pass1_titles or a["title"] in topic_titles:
            continue
        text = (a["title"] + " " + a["desc"]).lower()
        common_hits   = sum(1 for t in common   if t in text)
        specific_hits = sum(1 for t in specific if t in text)
        if common_hits >= 2 or specific_hits >= 1:
            additional.append(a)
    return additional


def format_article_list(articles: list[dict]) -> str:
    lines = []
    for a in sorted(articles, key=lambda x: (x["source"], x["date"])):
        lines.append(f"[{a['date']}] {a['source']} — {a['title']}")
        if a.get("desc"):
            lines.append(f"  → {a['desc']}")
    return "\n".join(lines)


def enrich_topic(topic: dict, extra: list[dict], client, model: str = "glm-4.7") -> dict:
    """GLM re-writes the topic incorporating additional articles."""
    prompt = ENRICH_PROMPT.format(
        title             = topic.get("title", ""),
        criteria          = topic.get("criteria", ""),
        existing_articles = format_article_list(
            [{"source": a["source"], "date": a["date"],
              "title": a["title"], "desc": ""}
             for a in topic.get("articles", [])]),
        key_data          = "\n".join(f"- {d}" for d in topic.get("key_data", [])),
        rationale         = topic.get("rationale", ""),
        additional_articles = format_article_list(extra),
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a smartphone market intelligence analyst. Output only valid JSON."},
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
    return topic  # fallback: keep original


def get_existing_reports() -> list[str]:
    reports = []
    for p in sorted(REPORTS_DIR.glob("*_report.md")):
        name = p.stem.replace("_report", "").replace("_", " ")
        reports.append(name)
    return reports


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


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",        type=int, default=30)
    parser.add_argument("--out",         default="scripts/_topic_suggestions.json")
    parser.add_argument("--no-existing", action="store_true",
                        help="Treat existing reports list as empty (no Criterion 3 exclusions)")
    args = parser.parse_args()

    # ── Pass 1 ──────────────────────────────────────────────────────────────
    print(f"[1/5] Loading articles (last {args.days} days)...")
    articles = load_articles(args.days)
    print(f"      → {len(articles)} Tier-1 smartphone articles (keyword-filtered)")

    existing = [] if args.no_existing else get_existing_reports()
    if existing:
        print(f"[2/5] Existing reports ({len(existing)}):")
        for r in existing:
            print(f"      · {r}")
    else:
        print("[2/5] Existing reports: none")

    articles_text    = format_articles(articles)
    existing_reports = "\n".join(f"- {r}" for r in existing) or "- (none)"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        existing_reports=existing_reports,
        days=args.days,
        total=len(articles),
        articles=articles_text,
    )

    client, model, thinking_body = _make_client()
    print(f"[3/5] Pass 1 — {model} thinking mode (initial topic selection)...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=30000,
        temperature=0.3,
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
        print("Raw output (first 500 chars):\n", content[:500])
        sys.exit(1)
    print(f"      → {len(topics)} topics identified")

    # ── Pass 2 ──────────────────────────────────────────────────────────────
    print(f"[4/5] Pass 2 — full archive search & topic enrichment...")
    all_articles  = load_all_articles(args.days)
    pass1_titles  = {a["title"] for a in articles}

    enriched_topics = []
    enriched_count  = 0
    for i, topic in enumerate(topics, 1):
        extra = find_additional_articles(topic, all_articles, pass1_titles)
        label = topic.get("title", "")[:50]
        if extra:
            print(f"      [{i}] +{len(extra)} articles — re-writing: {label}...")
            updated = enrich_topic(topic, extra, client, model)
            enriched_topics.append(updated)
            enriched_count += 1
        else:
            print(f"      [{i}] no additional articles: {label}")
            enriched_topics.append(topic)

    # ── Save ────────────────────────────────────────────────────────────────
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({
            "generated_at":    datetime.now().isoformat(),
            "days":            args.days,
            "article_count":   len(articles),
            "existing_reports": existing,
            "topics":          enriched_topics,
            "thinking_length": len(reasoning),
            "enriched_count":  enriched_count,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[5/5] Done.")
    print(f"{'='*60}")
    print(f"  {len(enriched_topics)} topics  |  {enriched_count} enriched  |  thinking {len(reasoning):,} chars")
    print(f"  Saved → {out_path}")
    print(f"{'='*60}")
    for i, t in enumerate(enriched_topics, 1):
        crit  = t.get("criteria", "")
        count = t.get("institution_count", "?")
        print(f"\n[{i}] {t.get('title', '')}")
        print(f"     {crit} | {count} institution(s)")
        for a in t.get("articles", []):
            print(f"     · [{a.get('date','')}] {a.get('source','')} - {a.get('title','')[:65]}")
        rationale = t.get("rationale", "")
        print(f"     → {rationale[:130]}{'...' if len(rationale) > 130 else ''}")


if __name__ == "__main__":
    main()
