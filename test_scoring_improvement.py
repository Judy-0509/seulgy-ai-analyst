"""
스코어링 개선안 시뮬레이션 (프로덕션 코드 무수정)

변경 사항 비교:
  [현재] required 최소 1개 매칭 → passes_floor (score >= 0.5)
  [개선] required 최소 2개 매칭 → passes_floor (req_match >= 2)
         + 범용 명사(production, market, supply 등)를 required → anchor로 강등

실행: python test_scoring_improvement.py
"""
import json
import re
from pathlib import Path

# ── 아카이브 로드 ──────────────────────────────────────────────
ARCHIVES_DIR = Path("data/archives")

def load_archives():
    flat = []
    for f in sorted(ARCHIVES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for e in (data.get("entries") or []):
                if not e.get("url"):
                    continue
                flat.append({
                    "url": e["url"],
                    "title": e.get("title") or "",
                    "description": e.get("description") or "",
                    "source": e.get("source") or data.get("source") or "Archive",
                    "tier": e.get("tier") if e.get("tier") is not None else data.get("tier", 1),
                })
        except Exception:
            continue
    return flat

# ── 토큰 분류 (현재 로직) ──────────────────────────────────────
ACTION_VERBS = {
    "launch","release","unveil","reveal","announce","introduce",
    "debut","rollout","ship","ships","shipping","start","begin",
}
STOP_WORDS = {
    "the","a","an","of","in","on","at","and","or","for","to",
    "is","are","be","with","by","as","from","this","that","vs","via",
    "bloomberg","counterpoint","idc","gsmarena","reuters","omdia",
    "gartner","trendforce","yole","nikkei","scmp","morgan","stanley",
}
# [개선안] 범용 명사 — required에서 anchor로 강등할 단어들
GENERIC_NOUNS = {
    "production","capacity","supply","chain","market","size","growth",
    "shipment","shipments","forecast","analysis","tracker","database",
    "report","inventory","price","cost","revenue","share","global",
    "demand","outlook","update","data","strategy","trends","trend",
    "overview","insight","latest","new","news",
}

def classify_terms_current(query: str) -> dict:
    """현재 로직: 범용 명사도 required 포함."""
    tokens = re.findall(r"[A-Za-z]+", query or "")
    required, anchor, seen = [], [], set()
    for t in tokens:
        low = t.lower()
        if low in seen or len(low) < 2:
            continue
        seen.add(low)
        if low in ACTION_VERBS or low in STOP_WORDS:
            continue
        if low == "latest" or re.fullmatch(r"\d{4}", low):
            anchor.append(low)
        else:
            required.append(low)
    # 연도 추출
    for yr in re.findall(r"\b20\d{2}\b", query):
        if yr not in anchor:
            anchor.append(yr)
    return {"required": required, "anchor": anchor}

def classify_terms_improved(query: str) -> dict:
    """개선안: 범용 명사 → anchor 강등."""
    tokens = re.findall(r"[A-Za-z]+", query or "")
    required, anchor, seen = [], [], set()
    for t in tokens:
        low = t.lower()
        if low in seen or len(low) < 2:
            continue
        seen.add(low)
        if low in ACTION_VERBS or low in STOP_WORDS:
            continue
        if low == "latest" or re.fullmatch(r"\d{4}", low):
            anchor.append(low)
        elif low in GENERIC_NOUNS:       # ← 범용 명사 anchor로 강등
            anchor.append(low)
        else:
            required.append(low)
    for yr in re.findall(r"\b20\d{2}\b", query):
        if yr not in anchor:
            anchor.append(yr)
    return {"required": required, "anchor": anchor}

# ── 스코어링 ───────────────────────────────────────────────────
TIER1_MULT = 3.0

def score_entry(entry: dict, terms: dict, min_req: int) -> tuple[float, bool]:
    text = (entry["title"] + " " + entry["description"]).lower()
    required = terms["required"]
    anchor   = terms["anchor"]
    if not required:
        return 1.0, True
    req_match = sum(1 for t in required if t in text)
    anc_match = sum(1 for t in anchor   if t in text)
    score = req_match * 3.0 + anc_match * 0.5
    if req_match == len(required):
        score *= 1.5
    passes = req_match >= min_req          # ← 핵심 차이점
    return score, passes

def rank_archive(archives: list, terms: dict, min_req: int) -> list[dict]:
    scored = []
    for e in archives:
        score, passes = score_entry(e, terms, min_req)
        if not passes:
            continue
        if e.get("tier", 1) == 1:
            score *= TIER1_MULT
        scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return scored[:15]

# ── 관련성 판단 (휴리스틱) ────────────────────────────────────
def is_relevant(title: str, topic_keywords: list[str]) -> bool:
    low = title.lower()
    return sum(1 for kw in topic_keywords if kw in low) >= 2

# ── 테스트 케이스 정의 ────────────────────────────────────────
TOPICS = [
    {
        "name": "①메모리 가격 폭등·OEM 전략",
        "queries": [
            "memory price surge OEM strategy 2026",
            "DRAM NAND supply shortage smartphone shipments 2026",
            "memory crunch smartphone market contraction 2026",
        ],
        "rel_kw": ["memory","dram","nand","smartphone","oem","supply"],
    },
    {
        "name": "②애플 역설적 성장·폴더블 진입",
        "queries": [
            "Apple foldable market share North America 2026",
            "iPhone shipments growth market decline 2026",
            "Apple AI smartphone strategy 2026",
        ],
        "rel_kw": ["apple","iphone","foldable","fold"],
    },
    {
        "name": "③화웨이 중국 1위·폼팩터 주도",
        "queries": [
            "Huawei China smartphone market leadership 2026",
            "Huawei foldable horizontal Samsung Apple competition",
            "Huawei AI glasses ecosystem 2026",
        ],
        "rel_kw": ["huawei","china","foldable","ai glasses"],
    },
    {
        "name": "④온디바이스 AI 에이전트·수용도 괴리",
        "queries": [
            "on-device AI agent smartphone adoption 2026",
            "agentic AI consumer readiness smartphone 2026",
            "AI agent app replacement smartphone user engagement",
        ],
        "rel_kw": ["ai","agent","on-device","smartphone","consumer"],
    },
    {
        "name": "⑤아마존-글로벌스타·D2D 위성 통신",
        "queries": [
            "Globalstar satellite production capacity Amazon acquisition 2026",
            "D2D satellite modem supply chain availability 2026",
            "Direct-to-Device smartphone shipment forecast 2026",
            "Satellite communication D2D market size growth 2026",
        ],
        "rel_kw": ["globalstar","satellite","d2d","amazon","direct-to-device"],
    },
    {
        "name": "⑥중고 스마트폰 시장 가속화",
        "queries": [
            "refurbished smartphone market growth LATAM 2026",
            "hardware supply constraints refurbished IT circular economy",
        ],
        "rel_kw": ["refurbished","used","circular","secondhand"],
    },
    {
        "name": "⑦구글 일본 2위·Android 생태계",
        "queries": [
            "Google Pixel Japan market share 2026",
            "Android Automotive OS open-source ecosystem expansion",
        ],
        "rel_kw": ["google","pixel","japan","android"],
    },
    {
        "name": "⑧삼성 메모리 수익·스마트폰 방어",
        "queries": [
            "Samsung memory revenue smartphone strategy 2026",
            "Samsung DS division profit margin 2026",
            "Samsung Galaxy S26 sales growth 2026",
        ],
        "rel_kw": ["samsung","memory","ds division","galaxy"],
    },
]

# ── 리포트 출력 ────────────────────────────────────────────────
def run():
    archives = load_archives()
    print(f"\n아카이브 총 {len(archives)}개 로드 완료\n")
    print("=" * 80)

    total_current_rel  = 0
    total_improved_rel = 0
    total_current_tot  = 0
    total_improved_tot = 0

    for topic in TOPICS:
        print(f"\n{'='*80}")
        print(f"  {topic['name']}")
        print(f"{'='*80}")

        for q in topic["queries"]:
            terms_cur = classify_terms_current(q)
            terms_imp = classify_terms_improved(q)

            results_cur = rank_archive(archives, terms_cur, min_req=1)
            results_imp = rank_archive(archives, terms_imp, min_req=2)

            top5_cur = results_cur[:5]
            top5_imp = results_imp[:5]

            rel_cur = sum(1 for _, e in top5_cur if is_relevant(e["title"], topic["rel_kw"]))
            rel_imp = sum(1 for _, e in top5_imp if is_relevant(e["title"], topic["rel_kw"]))

            total_current_rel  += rel_cur
            total_improved_rel += rel_imp
            total_current_tot  += len(top5_cur)
            total_improved_tot += len(top5_imp)

            print(f"\n  쿼리: \"{q}\"")
            print(f"  토큰 [현재] req={terms_cur['required']}  anc={terms_cur['anchor']}")
            print(f"  토큰 [개선] req={terms_imp['required']}  anc={terms_imp['anchor']}")

            # 현재 top5
            print(f"\n  [현재 min_req=1]  관련 {rel_cur}/5")
            for rank, (sc, e) in enumerate(top5_cur, 1):
                tag = "O" if is_relevant(e["title"], topic["rel_kw"]) else "X"
                print(f"    {rank}. [{tag}] [{e['source']:<20}] {e['title'][:70]}")

            # 개선 top5
            print(f"\n  [개선 min_req=2]  관련 {rel_imp}/5")
            for rank, (sc, e) in enumerate(top5_imp, 1):
                tag = "O" if is_relevant(e["title"], topic["rel_kw"]) else "X"
                print(f"    {rank}. [{tag}] [{e['source']:<20}] {e['title'][:70]}")

            if rel_imp > rel_cur:
                delta = rel_imp - rel_cur
                print(f"\n  [UP+{delta}] 개선안이 관련 기사를 더 상위에 노출")
            elif rel_imp < rel_cur:
                delta = rel_cur - rel_imp
                print(f"\n  [DN-{delta}] 개선안이 필터 과도")
            else:
                print(f"\n  [==] 동일")

    print(f"\n{'='*80}")
    print("  종합 결과 (top-5 기준)")
    print(f"{'='*80}")
    prec_cur = total_current_rel  / max(total_current_tot, 1) * 100
    prec_imp = total_improved_rel / max(total_improved_tot, 1) * 100
    print(f"  [현재]  관련 기사: {total_current_rel}/{total_current_tot}  precision={prec_cur:.1f}%")
    print(f"  [개선]  관련 기사: {total_improved_rel}/{total_improved_tot}  precision={prec_imp:.1f}%")
    delta_p = prec_imp - prec_cur
    sign = "+" if delta_p >= 0 else ""
    print(f"  정확도 변화: {sign}{delta_p:.1f}%p")
    print()

if __name__ == "__main__":
    run()
