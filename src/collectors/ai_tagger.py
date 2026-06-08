"""AI tagging using GLM-4-flash (sync).

One API call per article extracts:
- summary_ko        : 2-3 sentence Korean summary
- summary_en        : 2-3 sentence English summary
- vendor_tags       : smartphone brands from VENDOR_LIST
- issue_tags        : categories from ISSUE_CATEGORIES
- ai_importance     : 1-5 analyst importance score
- supply_chain_stage: build / sell_in / sell_through / null
- area_tags         : smartphone / semiconductor / memory
- tag_status        : 'success' or 'failed'
"""
from __future__ import annotations

import json
import logging
import os
import re

from src.services.token_logger import log_usage, usage_counts

logger = logging.getLogger(__name__)

VENDOR_LIST = [
    "Samsung", "Apple", "Xiaomi", "Huawei", "Honor",
    "OPPO", "OnePlus", "Realme", "vivo", "Transsion",
    "Tecno", "Infinix", "itel", "Motorola", "Lenovo",
    "Google", "Nokia", "Sony", "Others",
]

ISSUE_CATEGORIES = [
    "demand",        # consumer demand, sell-through trends
    "supply_chain",  # components, manufacturing, logistics
    "market_data",   # shipment volumes, market share
    "pricing",       # ASP, discounts, promotions
    "macro",         # tariffs, FX, interest rates, geopolitics
    "tech",          # new specs, chips, features
    "channel",       # retail, distribution
    "regulation",    # sanctions, trade policy, certification
    "competition",   # M&A, competitive dynamics
    "earnings",      # revenue, operating profit, guidance
]

_SUPPLY_CHAIN_STAGES = ["build", "sell_in", "sell_through"]
AREA_CATEGORIES = ["smartphone", "semiconductor", "memory"]

_PROMPT = """You are a smartphone market intelligence analyst. Analyze this news and respond ONLY with a JSON object.

Title: {title}
Description: {description}

JSON format:
{{
  "summary_ko": "2-3문장 핵심 요약 (한국어)",
  "summary_en": "2-3 sentence key summary (English)",
  "vendor_tags": ["BrandA", "BrandB"],
  "issue_tags": ["category1", "category2"],
  "ai_importance": 3,
  "supply_chain_stage": "build",
  "area_tags": ["smartphone"]
}}

Rules:
- vendor_tags: only from [{vendor_list}].
  * Map Korean names: 삼성→Samsung, 애플→Apple, 샤오미→Xiaomi, 화웨이→Huawei, 아너→Honor, 오포→OPPO, 비보→vivo, 구글→Google, 모토로라→Motorola, 소니→Sony, 노키아→Nokia
  * Include OEM brands mentioned directly OR as end-customer (e.g. "BOE supplies Apple" → Apple; "삼성디스플레이 패널" → Samsung).
  * Supplier/component companies (BOE, TSMC, LG Display, Qualcomm, etc.) are NOT smartphone vendors — tag the OEM customer instead.
  * Use "Others" only when a minor/unnamed brand is clearly a smartphone OEM with no match in the list.
  * If no smartphone OEM is relevant, return [].
- issue_tags: only from [{issue_list}]. Assign ALL categories that apply (can be multiple).
  * demand: consumer demand, sell-through, sales trends
  * supply_chain: components, manufacturing, logistics, suppliers
  * market_data: shipment volumes, market share data
  * pricing: ASP, discounts, promotions
  * macro: tariffs, FX, interest rates, geopolitics
  * tech: new specs, chips, features, form factors
  * channel: retail, distribution, online/offline
  * regulation: sanctions, trade policy, certification
  * competition: M&A, competitive dynamics, brand strategy
  * earnings: revenue, operating profit, guidance
- ai_importance: 1 (routine) to 5 (market-moving insight). Score 4-5 only for data releases, major strategic shifts, or supply chain disruptions.
- supply_chain_stage: classify into exactly ONE of [{stage_list}] based on smartphone supply chain context.
  * build: smartphone production planning, component orders (AP/SoC, display panel, memory, camera module), factory capacity, ODM/EMS assembly, wafer starts, panel production, parts supply-demand
  * sell_in: smartphone shipment volumes from OEM to channels/distributors/carriers, wholesale orders, channel inventory levels, B2B sell-in data, shipment-based market share (e.g. IDC/Canalys/Counterpoint shipment data)
  * sell_through: smartphone retail sales to end consumers, sell-through data, consumer demand trends, retail/online channel performance, pricing promotions, carrier subsidies, consumer purchase behavior
  * Choose the BEST fit based on where in the smartphone supply chain the article focuses.
  * If the article is NOT related to smartphone build/sell-in/sell-through at all, return null.
- area_tags: only from [{area_list}]. Assign ALL areas that apply (can be multiple).
  * smartphone: 스마트폰, 핸드셋, 모바일 기기, 폴더블폰
  * semiconductor: 반도체, 칩, AP/SoC, 파운드리, 팹, 웨이퍼
  * memory: 메모리, DRAM, NAND, HBM, 플래시
  * An article about Samsung HBM production → ["semiconductor", "memory"]
  * An article about iPhone sales → ["smartphone"]
  * If no area applies, return []
- Return ONLY the JSON. No markdown fences, no explanation."""


def _get_glm_client():
    from openai import OpenAI
    return OpenAI(
        api_key=os.getenv("ZHIPU_API_KEY"),
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        timeout=float(os.getenv("GLM_REQUEST_TIMEOUT_SECONDS", "600")),
    )


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


_DEFAULT = {
    "summary_ko": None,
    "summary_en": None,
    "vendor_tags": [],
    "issue_tags": [],
    "ai_importance": 3,
    "supply_chain_stage": None,
    "area_tags": [],
    "tag_status": "failed",
}


def tag_article(title: str, description: str) -> dict:
    """Tag a single article. Always returns a dict with all keys."""
    client = _get_glm_client()
    if not client:
        return dict(_DEFAULT)

    # glm-4-flash 는 2026-05 기준 deprecated (Zhipu API err 1211).
    # glm-4.5-flash 는 무료 + concurrency 2, 태깅에 충분.
    model = "glm-4.5-flash"
    prompt = _PROMPT.format(
        title=title,
        description=(description or "")[:800],
        vendor_list=", ".join(VENDOR_LIST),
        issue_list=", ".join(ISSUE_CATEGORIES),
        stage_list=", ".join(_SUPPLY_CHAIN_STAGES),
        area_list=", ".join(AREA_CATEGORIES),
    )

    # GLM-4.5-Flash 는 concurrency=2 — 대량 태깅 시 rate limit 위험. limiter 적용.
    from src.services.glm_limiter import model_slot
    try:
        try:
            with model_slot(model):
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=2048,
                )
        except Exception:
            with model_slot(model):
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=2048,
                )

        prompt_tokens, completion_tokens = usage_counts(getattr(resp, "usage", None))
        log_usage(model, prompt_tokens, completion_tokens, "ai_tagger.tag_article")

        raw = _strip_fences(resp.choices[0].message.content or "")
        data = json.loads(raw)

        vendor_tags = [v for v in data.get("vendor_tags", []) if v in VENDOR_LIST]
        issue_tags  = [i for i in data.get("issue_tags", []) if i in ISSUE_CATEGORIES]
        ai_imp      = max(1, min(5, int(data.get("ai_importance", 3))))
        stage_raw   = data.get("supply_chain_stage", "")
        stage       = stage_raw if stage_raw in _SUPPLY_CHAIN_STAGES else None
        area_tags   = [a for a in data.get("area_tags", []) if a in AREA_CATEGORIES]

        return {
            "summary_ko": data.get("summary_ko") or None,
            "summary_en": data.get("summary_en") or None,
            "vendor_tags": vendor_tags,
            "issue_tags":  issue_tags,
            "ai_importance": ai_imp,
            "supply_chain_stage": stage,
            "area_tags": area_tags,
            "tag_status": "success",
        }

    except Exception as e:
        logger.warning(f"AI tagging failed for '{title[:60]}': {e}")
        return dict(_DEFAULT)
