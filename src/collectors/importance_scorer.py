"""Importance scoring for news articles.

Final score = source_tier(30%) + cluster_size(30%) + keyword_hits(20%) + ai_score(20%)
Range: 0.0 – 10.0
"""

IMPORTANCE_KEYWORDS = [
    # Market data
    "shipment", "market share", "출하", "시장점유율", "market size", "marketshare",
    "quarterly", "annual", "forecast", "guidance", "outlook", "예측", "전망",
    # Demand signals
    "demand", "sales", "sell-through", "sellthrough", "판매량", "판매",
    "upgrade cycle", "replacement", "수요", "소비", "pre-order", "사전예약",
    # Supply chain
    "supply chain", "shortage", "component", "TSMC", "foundry", "공급망",
    "부품", "부족", "생산", "칩", "반도체", "semiconductor",
    # Financial
    "revenue", "profit", "earnings", "EPS", "매출", "영업이익", "실적",
    # Macro
    "tariff", "관세", "sanction", "제재", "trade war", "무역",
    "inflation", "인플레이션", "interest rate", "금리", "exchange rate", "환율",
    # Analyst / data sources
    "IDC", "Counterpoint", "Canalys", "TrendForce", "GfK", "Omdia",
]


def count_keyword_hits(title: str, description: str) -> int:
    """Count importance keywords present in title + description."""
    text = f"{title} {description}".lower()
    return sum(1 for kw in IMPORTANCE_KEYWORDS if kw.lower() in text)


def compute_importance(
    source_tier: int,
    cluster_size: int,
    keyword_hits: int,
    ai_score: int,
) -> float:
    """Compute final importance score 0.0–10.0.

    Weights:
      source_tier  30%  (tier 1→1pt, tier 2→2pt, tier 3→3pt)
      cluster_size 30%  (1 article→0, 5+→3pt)
      keyword_hits 20%  (0→0, 5+→2pt)
      ai_score     20%  (1→0, 5→2pt)
    """
    tier_score    = min(max(source_tier, 1), 3) / 3.0 * 3.0
    cluster_score = min(cluster_size, 5) / 5.0 * 3.0
    kw_score      = min(keyword_hits, 5) / 5.0 * 2.0
    ai_normalized = max(0, (int(ai_score) - 1)) / 4.0 * 2.0
    return round(tier_score + cluster_score + kw_score + ai_normalized, 2)
