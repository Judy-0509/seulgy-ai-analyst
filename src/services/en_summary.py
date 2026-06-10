"""보고서 EN 요약 (option a) — 핵심요약·제목만 영어로.

해외 독자용 *요약 전용* 번역. 본문/섹션은 번역하지 않는다(풀 i18n 아님).
- 모델: glm-4.7 강제 (glm-5.1은 A/B에서 숫자를 변조 → 신뢰도 리스크).
- 숫자/단위/고유명사 원문 보존을 시스템 프롬프트로 강제.
- 사이드카 `reports/{slug}.en.json` 에 캐시(있으면 재생성 안 함, 멱등).
"""
from __future__ import annotations

import json
from pathlib import Path

EN_SIDECAR_SUFFIX = ".en.json"
EN_SUMMARY_MODEL = "glm-4.7"  # 절대 5.1 아님 (숫자 변조 방지)

_SYSTEM = (
    "You are a professional translator specializing in market-research reports. "
    "Translate the given Korean text into natural, concise professional English. "
    "CRITICAL RULES: (1) Preserve every number, percentage, unit, currency amount, "
    "date, and proper noun (company, product, organization names) EXACTLY as written "
    "— never add, drop, round, or alter any figure. (2) Do not summarize, expand, or "
    "add commentary. (3) Output ONLY the English translation, with no preamble, "
    "labels, or surrounding quotes."
)


def en_sidecar_path(reports_dir: Path, slug: str) -> Path:
    return Path(reports_dir) / f"{slug}{EN_SIDECAR_SUFFIX}"


def load_en_summary(reports_dir: Path, slug: str) -> dict | None:
    """사이드카가 있으면 {topic_en, executive_summary_en, ...} 반환, 없으면 None."""
    path = en_sidecar_path(reports_dir, slug)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def _translate(text: str, llm) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    resp = await llm.complete(
        _SYSTEM,
        text,
        model=EN_SUMMARY_MODEL,
        temperature=0.1,
        max_tokens=1400,
        thinking="disabled",
    )
    return (resp.content or "").strip()


async def generate_en_summary(topic_ko: str, summary_ko: str, llm) -> dict:
    """제목+핵심요약을 영어로 번역한 dict 반환 (디스크 기록 없음)."""
    topic_en = await _translate(topic_ko, llm)
    summary_en = await _translate(summary_ko, llm)
    return {
        "topic_en": topic_en,
        "executive_summary_en": summary_en,
        "model": EN_SUMMARY_MODEL,
        "source": "auto",
    }


async def ensure_en_summary(
    reports_dir: Path, slug: str, topic_ko: str, summary_ko: str, llm, *, force: bool = False
) -> dict | None:
    """사이드카가 없으면(or force) 생성·기록 후 반환. 요약이 비면 None."""
    if not force:
        existing = load_en_summary(reports_dir, slug)
        if existing:
            return existing
    if not (summary_ko or "").strip():
        return None
    data = await generate_en_summary(topic_ko, summary_ko, llm)
    path = en_sidecar_path(reports_dir, slug)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
