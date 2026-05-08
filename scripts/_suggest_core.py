"""공통 파이프라인 엔진 — 도메인별 suggest_*.py 스크립트에서 공유.

도메인 스크립트는 ARCHIVE_REGISTRY, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE 등을
정의하고 run_pipeline()을 호출합니다.
"""
import json
import os
import re
import sys
import time as _time
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.services.token_logger import log_usage, usage_counts  # noqa: E402
from src.services.glm_limiter import glm47_slot, flashx_slot  # noqa: E402

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
GLM_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("GLM_REQUEST_TIMEOUT_SECONDS", "600"))

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
    """LLM_BACKEND 환경변수에 따라 (client, model, thinking_body) 반환.

    Pass 1 은 깊은 reasoning (semantic clustering, criterion 판단)이 필요하므로
    glm-4.7 thinking 모드 유지. Pass 2 enrich 는 단일 JSON 재작성 작업이라
    enrich_topic() 내부에서 별도로 ENRICH_MODEL (glm-4.7-flashx) 사용.
    """
    client = OpenAI(
        api_key=os.environ["ZHIPU_API_KEY"],
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        timeout=GLM_REQUEST_TIMEOUT_SECONDS,
    )
    model = os.getenv("GLM_PASS1_MODEL", "glm-4.7")
    thinking_body = {"thinking": {"type": "enabled"}}
    return client, model, thinking_body


# Pass 2 enrichment 전용 모델 — flashx 가 ~10배 저렴하면서 JSON 재작성에 충분.
ENRICH_MODEL = os.getenv("GLM_ENRICH_MODEL", "glm-4.7-flashx")


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
                  keyword_filter=None,
                  per_source_cap: int | None = 35) -> list[dict]:
    """레지스트리 소스에서 기사 로드. keyword_filter(entry)->bool, None이면 전체.

    per_source_cap: 소스당 최근 N개로 제한 (default 35). LLM 컨텍스트 보호 +
    mass-publisher(예: Cox 133, Omdia 260)가 prompt를 잠식하는 것 방지.
    None이면 무제한.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    articles = []
    for source, fname in registry:
        p = ARCHIVES_DIR / fname
        if not p.exists():
            continue
        per_source: list[tuple[datetime, dict]] = []
        for e in json.loads(p.read_text(encoding="utf-8")).get("entries", []):
            dt = _parse_dt(e.get("lastmod", ""))
            if dt is None or dt < cutoff:
                continue
            if keyword_filter and not keyword_filter(e):
                continue
            per_source.append((dt, _clean_entry(e, source)))
        # 최신순 정렬 후 cap 적용
        per_source.sort(key=lambda x: x[0], reverse=True)
        if per_source_cap is not None:
            per_source = per_source[:per_source_cap]
        articles.extend(c for _, c in per_source)
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
        # Threshold raised from 2/1 → 3/2 to reduce noise & enrich call frequency.
        # See db_research / enrich 비용 분석 (2026-05-07).
        if sum(1 for t in common if t in text) >= 3 or \
           sum(1 for t in specific if t in text) >= 2:
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


def _topic_terms(topic: dict) -> set[str]:
    text_parts = [topic.get("title", "")]
    for article in topic.get("articles", []):
        text_parts.append(article.get("title", ""))
        text_parts.append(article.get("source", ""))
    text = " ".join(text_parts).lower()
    raw_terms = re.findall(r"[a-z0-9가-힣]{2,}", text)
    stop = {
        "market", "smartphone", "smartphones", "phone", "phones", "global", "research",
        "display", "dynamics", "april", "2025", "2026", "시장", "스마트폰", "기반",
        "구조", "전략", "따른", "심화", "가속화", "변화",
    }
    return {term for term in raw_terms if term not in stop}


def _topic_similarity(a: dict, b: dict) -> float:
    a_terms = _topic_terms(a)
    b_terms = _topic_terms(b)
    if not a_terms or not b_terms:
        return 0.0
    overlap = len(a_terms & b_terms)
    union = len(a_terms | b_terms)
    title_bonus = 0.0
    a_title_terms = set(re.findall(r"[a-z0-9가-힣]{2,}", a.get("title", "").lower()))
    b_title_terms = set(re.findall(r"[a-z0-9가-힣]{2,}", b.get("title", "").lower()))
    if a_title_terms and b_title_terms:
        title_bonus = len(a_title_terms & b_title_terms) / len(a_title_terms | b_title_terms)
    return (overlap / union * 0.75) + (title_bonus * 0.25)


def _topic_article_dates(topic: dict) -> list[datetime]:
    dates = []
    for article in topic.get("articles", []):
        date_str = (article.get("date") or "")[:10]
        try:
            dates.append(datetime.fromisoformat(date_str))
        except ValueError:
            continue
    return dates


def _load_topic_history(out: Path, domain_label: str, max_snapshots: int = 8) -> list[dict]:
    hist_dir = out.parent / "_history"
    snapshots = []
    if not hist_dir.exists():
        return snapshots
    for path in sorted(hist_dir.glob(f"{domain_label}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        topics = data.get("topics", [])
        if not isinstance(topics, list):
            continue
        snapshots.append({
            "path": path.name,
            "generated_at": data.get("generated_at", ""),
            "topics": topics,
        })
        if len(snapshots) >= max_snapshots:
            break
    return snapshots


_HUMANOID_SOURCE_WEIGHTS = {
    "IFR": 0.98,
    "ABI Research": 0.95,
    "IDTechEx": 0.94,
    "Yano Research": 0.90,
    "The Robot Report": 0.90,
    "IEEE Spectrum Robotics": 0.86,
    "IEEE Spectrum": 0.86,
    "Figure AI": 0.82,
    "1X Technologies": 0.82,
    "Apptronik": 0.80,
    "Agility Robotics": 0.80,
    "Unitree Robotics": 0.78,
    "Unitree": 0.78,
    "NVIDIA News": 0.78,
    "NVIDIA": 0.78,
    "TechCrunch Robotics": 0.72,
    "Robotics & Automation News": 0.64,
    "RoboticsTomorrow": 0.56,
    "The Verge": 0.55,
    "Humanoids Daily": 0.52,
    "arXiv (cs.RO)": 0.48,
}


def _humanoid_source_quality(topic: dict) -> float:
    sources = {a.get("source") for a in topic.get("articles", []) if a.get("source")}
    if not sources:
        return 0.0
    return sum(_HUMANOID_SOURCE_WEIGHTS.get(source, 0.60) for source in sources) / len(sources)


def _humanoid_impact_score(topic: dict) -> float:
    text_parts = [
        topic.get("title", ""),
        topic.get("rationale", ""),
        " ".join(topic.get("key_data", [])),
    ]
    for article in topic.get("articles", []):
        text_parts.append(article.get("title", ""))
    text = " ".join(text_parts).lower()

    patterns = [
        (1.00, [
            "production", "ramp", "high-volume", "vertically integrated",
            "botq", "neo factory", "양산", "대량 생산",
        ]),
        (1.00, [
            "deploy", "deployment", "install", "1,000", "1000", "factory network",
            "계약", "도입", "배치", "상용화",
        ]),
        (0.88, [
            "national strategy", "national robotics center", "$629", "ban", "law", "security", "sovereignty",
            "국가 전략", "법안", "규제", "안보",
        ]),
        (0.68, [
            "physical ai", "robot brain", "nvidia", "siemens", "foundation model",
            "소프트웨어", "표준화", "생태계",
        ]),
        (0.66, [
            "consumer", "home", "$42,000", "42000", "companion", "familiar",
            "소비자", "가정용", "가격", "반려",
        ]),
        (0.54, [
            "tactile", "touch", "dataset", "sim2real", "simulation", "arxiv",
            "촉각", "데이터셋", "시뮬레이션",
        ]),
    ]
    for score, keywords in patterns:
        if any(keyword in text for keyword in keywords):
            return score
    return 0.45


def _humanoid_commitment_score(topic: dict) -> float:
    text_parts = [
        topic.get("title", ""),
        topic.get("rationale", ""),
        " ".join(topic.get("key_data", [])),
    ]
    for article in topic.get("articles", []):
        text_parts.append(article.get("title", ""))
    text = " ".join(text_parts).lower()

    if any(keyword in text for keyword in [
        "production", "ramp", "high-volume", "vertically integrated", "botq",
        "deploy", "deployment", "install", "1,000", "1000", "factory network",
        "양산", "대량 생산", "도입", "배치", "계약",
    ]):
        return 1.00
    if any(keyword in text for keyword in [
        "national strategy", "national robotics center", "$629", "ban", "law",
        "국가 전략", "법안", "규제", "안보",
    ]):
        return 0.80
    if any(keyword in text for keyword in ["consumer", "home", "$42,000", "42000", "소비자", "가정용", "가격"]):
        return 0.65
    if any(keyword in text for keyword in ["partner", "partnership", "nvidia", "siemens", "physical ai", "협력", "파트너"]):
        return 0.55
    if any(keyword in text for keyword in ["funding", "raises", "investment", "투자", "펀딩"]):
        return 0.50
    return 0.45


def _humanoid_repetition_penalty(topic: dict) -> float:
    sources = [a.get("source") for a in topic.get("articles", []) if a.get("source")]
    if not sources:
        return 0.0
    low_weight_sources = {"arXiv (cs.RO)", "Humanoids Daily", "RoboticsTomorrow", "Robotics & Automation News"}
    low_count = sum(1 for source in sources if source in low_weight_sources)
    single_source_repeat = len(set(sources)) == 1 and len(sources) >= 3
    penalty = 0.0
    if low_count / len(sources) >= 0.60:
        penalty += 0.08
    if single_source_repeat:
        penalty += 0.08
    return penalty


def apply_trend_ranking(
    topics: list[dict],
    *,
    out_path: str | Path,
    domain_label: str,
    generated_at: str | None = None,
) -> list[dict]:
    """Re-rank topics by domain-specific trend and evidence quality."""
    if domain_label not in {"smartphone", "humanoid"} or not topics:
        return topics

    out = ROOT / out_path
    snapshots = _load_topic_history(out, domain_label)
    now = datetime.fromisoformat((generated_at or datetime.now().isoformat())[:19])
    ranked = []

    for topic in topics:
        articles = topic.get("articles", [])
        dates = _topic_article_dates(topic)
        current_count = len(articles)
        sources = {a.get("source") for a in articles if a.get("source")}
        latest_date = max(dates) if dates else now
        age_days = max((now - latest_date).days, 0)

        matches = []
        for snap in snapshots:
            best = None
            best_similarity = 0.0
            for old_topic in snap.get("topics", []):
                similarity = _topic_similarity(topic, old_topic)
                if similarity > best_similarity:
                    best = old_topic
                    best_similarity = similarity
            if best and best_similarity >= 0.18:
                matches.append((snap, best, best_similarity))

        previous_count = len(matches[0][1].get("articles", [])) if matches else 0
        first_seen = matches[-1][0].get("generated_at", "") if matches else (generated_at or "")
        weeks_seen = len(matches) + 1
        growth_ratio = current_count / max(previous_count, 1)

        freshness_score = max(0.0, 1.0 - (age_days / 30.0))
        volume_score = min(current_count, 10) / 10.0
        source_score = min(len(sources), 5) / 5.0
        momentum_score = max(0.0, min(growth_ratio - 1.0, 2.0) / 2.0)
        novelty_score = 1.0 if not matches else 0.0
        decline_penalty = max(0.0, min((previous_count - current_count) / max(previous_count, 1), 1.0))
        stale_penalty = 0.25 if age_days > 21 else 0.0

        extra_trend_fields = {}
        if domain_label == "humanoid":
            source_quality_score = _humanoid_source_quality(topic)
            impact_score = _humanoid_impact_score(topic)
            commitment_score = _humanoid_commitment_score(topic)
            repetition_penalty = _humanoid_repetition_penalty(topic)
            final_score = (
                0.08 * volume_score
                + 0.08 * momentum_score
                + 0.10 * source_score
                + 0.24 * source_quality_score
                + 0.25 * impact_score
                + 0.18 * commitment_score
                + 0.05 * freshness_score
                + 0.02 * novelty_score
                - 0.18 * decline_penalty
                - stale_penalty
                - repetition_penalty
            )
            extra_trend_fields = {
                "source_quality_score": round(source_quality_score, 3),
                "impact_score": round(impact_score, 3),
                "commitment_score": round(commitment_score, 3),
                "repetition_penalty": round(repetition_penalty, 3),
            }
        else:
            final_score = (
                0.35 * volume_score
                + 0.25 * momentum_score
                + 0.20 * source_score
                + 0.10 * freshness_score
                + 0.10 * novelty_score
                - 0.20 * decline_penalty
                - stale_penalty
            )

        if not matches:
            trend_status = "New"
        elif current_count >= max(previous_count * 1.5, previous_count + 2):
            trend_status = "Rising"
        elif current_count <= previous_count * 0.6:
            trend_status = "Cooling"
        elif weeks_seen >= 3:
            trend_status = "Sustained"
        else:
            trend_status = "Stable"

        topic["trend"] = {
            "status": trend_status,
            "rank_score": round(final_score, 4),
            "current_article_count": current_count,
            "previous_article_count": previous_count,
            "source_count": len(sources),
            "latest_article_date": latest_date.date().isoformat(),
            "first_seen": first_seen,
            "weeks_seen": weeks_seen,
            "growth_ratio": round(growth_ratio, 2),
            **extra_trend_fields,
        }
        ranked.append(topic)

    ranked.sort(
        key=lambda t: (
            t.get("trend", {}).get("rank_score", 0),
            t.get("trend", {}).get("current_article_count", 0),
            t.get("trend", {}).get("latest_article_date", ""),
        ),
        reverse=True,
    )
    for index, topic in enumerate(ranked, 1):
        topic.setdefault("trend", {})["rank"] = index
    return ranked


def get_existing_reports() -> list[str]:
    reports = []
    for p in sorted(REPORTS_DIR.glob("*_report.md")):
        name = p.stem.replace("_report", "").replace("_", " ")
        reports.append(name)
    return reports


# ── Enrichment ──────────────────────────────────────────────────────────────

def enrich_topic(topic: dict, extra: list[dict], client,
                 enrich_system: str, enrich_tpl: str) -> dict:
    """Pass 2 enrichment — JSON 재작성 작업이라 ENRICH_MODEL (flashx) 사용.

    flashx 는 ~10배 저렴 + concurrency 3 (4.7 의 1.5배).
    """
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
    response = None
    for _attempt in range(5):
        try:
            with flashx_slot():
                response = client.chat.completions.create(
                    model=ENRICH_MODEL,
                    messages=[
                        {"role": "system", "content": enrich_system},
                        {"role": "user",   "content": prompt},
                    ],
                    # max_tokens 4000 → 2000: 실제 JSON 800-1000 토큰, thinking off 시 충분.
                    max_tokens=2000,
                    temperature=0.1,
                    # enrich 는 단일 JSON 재작성 작업이라 reasoning 불필요.
                    # thinking 명시적 disable → 출력 토큰 ~70% 감소 (median 2781 → ~900).
                    extra_body={"thinking": {"type": "disabled"}},
                )
            break
        except Exception as _e:
            if "429" in str(_e) or "1302" in str(_e) or "rate" in str(_e).lower():
                wait = 60 * (2 ** _attempt)
                print(f"      [enrich] Rate limit, waiting {wait}s (attempt {_attempt+1}/5)...")
                _time.sleep(wait)
            else:
                raise
    if response is None:
        return topic
    prompt_tokens, completion_tokens = usage_counts(getattr(response, "usage", None))
    log_usage(ENRICH_MODEL, prompt_tokens, completion_tokens, "suggest.enrich")
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
    source_taxonomy: dict[str, str] | None = None,  # {source_name: layer_code} — 제공 시 source_layers 자동 채움
    extra_existing: list[str] | None = None,        # existing_reports에 추가로 주입할 토픽 list (예: 메이저 패스 결과)
):
    """5-step 공통 파이프라인."""
    # Step 1 — 기사 로드
    print(f"[1/5] Loading articles (last {days} days, domain={domain_label})...")
    articles = load_articles(registry, days, keyword_filter)
    print(f"      → {len(articles)} articles")

    existing = get_existing_reports() if with_existing else []
    if extra_existing:
        existing = existing + list(extra_existing)
    if existing:
        print(f"[2/5] Existing reports / topics to exclude ({len(existing)}):")
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
    for _attempt in range(5):
        try:
            with glm47_slot():
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
            break
        except Exception as _e:
            if "429" in str(_e) or "1302" in str(_e) or "rate" in str(_e).lower():
                wait = 60 * (2 ** _attempt)
                print(f"      Rate limit, waiting {wait}s (attempt {_attempt+1}/5)...")
                _time.sleep(wait)
            else:
                raise
    else:
        print("[!] Rate limit not resolved after 5 attempts")
        sys.exit(1)
    msg       = response.choices[0].message
    reasoning = getattr(msg, "reasoning_content", "") or ""
    content   = msg.content or ""
    prompt_tokens, completion_tokens = usage_counts(getattr(response, "usage", None))
    log_usage(model, prompt_tokens, completion_tokens, "suggest.pass1")
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
        existing_count = len(topic.get("articles", []))
        # Saturation skip: 토픽이 이미 4개 이상 인용 보유 시 enrich 효용 낮음.
        # 비용 절감 — see db_research/enrich 비용 분석 (2026-05-07).
        if existing_count >= 4:
            print(f"      [{i}] saturated ({existing_count} articles) — skip enrich: {label}")
            enriched_topics.append(topic)
        elif extra:
            if enriched_count > 0:
                _time.sleep(5)  # 연속 호출 간 throttle — rate limit 예방
            print(f"      [{i}] +{len(extra)} articles — re-writing: {label}...")
            updated = enrich_topic(topic, extra, client, enrich_system, enrich_tpl)
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

    # source_layers 자동 채우기 — LLM 출력 대신 코드가 인용 출처에서 직접 도출 (라벨 정확도 100%)
    if source_taxonomy:
        # LLM이 출처명을 줄여 쓰는 경우 ("arXiv" vs "arXiv (cs.RO)") 정확 매칭이 실패하므로
        # taxonomy 캐논 키로 normalize한다. 정확 매칭 → 부분 매칭 순서로 시도.
        canonical = list(source_taxonomy.keys())

        def _normalize(src: str) -> str:
            if not src:
                return src
            if src in source_taxonomy:
                return src
            sl = src.lower().strip()
            # 부분 매칭: registry 키가 src를 포함하거나 src가 registry 키를 포함
            best = None
            for c in canonical:
                cl = c.lower()
                if sl == cl or sl in cl or cl in sl:
                    # 더 긴 매칭이 더 구체적
                    if best is None or len(c) > len(best):
                        best = c
            return best or src

        for topic in enriched_topics:
            for art in topic.get("articles", []):
                art["source"] = _normalize(art.get("source", ""))
            sources = {
                a.get("source")
                for a in topic.get("articles", [])
                if a.get("source")
            }
            topic["institution_count"] = len(sources)
            layers = sorted({
                source_taxonomy[a["source"]]
                for a in topic.get("articles", [])
                if a.get("source") in source_taxonomy
            })
            topic["source_layers"] = layers
    else:
        for topic in enriched_topics:
            sources = {
                a.get("source")
                for a in topic.get("articles", [])
                if a.get("source")
            }
            topic["institution_count"] = len(sources)

    # Step 5 — 저장
    out = ROOT / out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat()
    enriched_topics = apply_trend_ranking(
        enriched_topics,
        out_path=out_path,
        domain_label=domain_label,
        generated_at=generated_at,
    )

    # 기존 파일이 있으면 히스토리 폴더에 보관
    if out.exists():
        hist_dir = out.parent / "_history"
        hist_dir.mkdir(exist_ok=True)
        existing_data = json.loads(out.read_text(encoding="utf-8"))
        ts = (existing_data.get("generated_at") or datetime.now().isoformat())[:19].replace(":", "-")
        hist_name = f"{domain_label}_{ts}.json"
        (hist_dir / hist_name).write_text(out.read_text(encoding="utf-8"), encoding="utf-8")

    out.write_text(
        json.dumps({
            "generated_at":    generated_at,
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
