from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any


QUOTE_SPAN_RE = re.compile(r"[\u201c\"]([^\u201d\"]+)[\u201d\"]")
NUMBER_RE = re.compile(
    r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|\d{2,}(?:\.\d+)?%?)(?![\d.])"
)


@dataclass
class BulletVerdict:
    index: int
    bullet: str
    status: str
    method: str
    reason: str


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'}))
    text = re.sub(r"[/\\]", " ", text)
    text = re.sub(r"['\"]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_quote_spans(text: str) -> list[str]:
    return [m.group(1).strip() for m in QUOTE_SPAN_RE.finditer(text or "") if m.group(1).strip()]


def extract_numbers(text: str) -> set[str]:
    return {m.group(0).replace(",", "") for m in NUMBER_RE.finditer(text or "")}


def deterministic_check(
    bullets: list[str],
    evidence_text: str,
) -> tuple[list[BulletVerdict], list[int]]:
    evidence = normalize_text(evidence_text)
    verdicts: list[BulletVerdict] = []
    unresolved: list[int] = []

    for index, bullet in enumerate(bullets or []):
        bullet_text = str(bullet)
        spans = extract_quote_spans(bullet_text)
        if not spans:
            verdicts.append(
                BulletVerdict(index, bullet_text, "unverified", "no_quote", "no quoted span found")
            )
            unresolved.append(index)
            continue

        missing = [span for span in spans if normalize_text(span) not in evidence]
        if missing:
            verdicts.append(
                BulletVerdict(
                    index,
                    bullet_text,
                    "unverified",
                    "deterministic",
                    "quoted span not found in evidence",
                )
            )
            unresolved.append(index)
            continue

        verdicts.append(
            BulletVerdict(
                index,
                bullet_text,
                "verified",
                "deterministic",
                "all quoted spans found in evidence",
            )
        )

    return verdicts, unresolved


def clip_evidence(bullet: str, evidence_text: str, window: int = 1200, cap: int = 2500) -> str:
    evidence = evidence_text or ""
    if not evidence:
        return ""

    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9,.\-%]{2,}", bullet or "")
    distinctive = sorted(
        {t.strip(".,;:!?()[]{}\"'").lower() for t in tokens if len(t.strip(".,;:!?()[]{}\"'")) >= 4},
        key=lambda t: (-len(t), t),
    )
    lower_evidence = evidence.lower()
    hit = -1
    for token in distinctive[:12]:
        hit = lower_evidence.find(token)
        if hit >= 0:
            break

    if hit < 0:
        return evidence[:cap]

    start = max(0, hit - window)
    end = min(len(evidence), hit + len(token) + window)
    clip = evidence[start:end]
    if len(clip) <= cap:
        return clip

    center = min(hit - start, len(clip))
    half = cap // 2
    clip_start = max(0, center - half)
    clip_end = min(len(clip), clip_start + cap)
    return clip[clip_start:clip_end]


async def llm_check_bullets(llm: Any, items: list[dict]) -> list[BulletVerdict]:
    fallback = [
        BulletVerdict(
            int(item.get("index", i)),
            str(item.get("bullet", "")),
            "unverified",
            "llm",
            "checker unavailable",
        )
        for i, item in enumerate(items or [])
    ]
    if not items:
        return []

    item_by_index = {int(item.get("index", i)): item for i, item in enumerate(items)}
    prompt_items = []
    for item in items:
        prompt_items.append(
            f"ID {item['index']}\n"
            f"Bullet: {item['bullet']}\n"
            f"Evidence clip:\n{item.get('evidence_clip', '')}"
        )
    prompt = (
        "Judge whether each bullet is supported ONLY by its own evidence clip.\n"
        "Return JSON only in this shape:\n"
        '{"verdicts":[{"id":0,"verdict":"verified|unsupported","reason":"one line"}]}\n\n'
        + "\n\n---\n\n".join(prompt_items)
    )

    try:
        resp = await llm.complete(
            "You are a strict citation fact checker.",
            prompt,
            model=os.getenv("GLM_FACTCHECK_MODEL", "glm-4.7-flashx"),
            max_tokens=2000,
            temperature=0.0,
            response_format={"type": "json_object"},
            thinking="disabled",
        )
        parsed = json.loads((getattr(resp, "content", "") or "").strip())
        raw_verdicts = parsed.get("verdicts", [])
        if not isinstance(raw_verdicts, list):
            return fallback
    except Exception:
        return fallback

    out_by_index: dict[int, BulletVerdict] = {}
    for raw in raw_verdicts:
        if not isinstance(raw, dict) or "id" not in raw:
            continue
        try:
            idx = int(raw["id"])
        except (TypeError, ValueError):
            continue
        item = item_by_index.get(idx)
        if item is None:
            continue
        status = raw.get("verdict")
        reason = str(raw.get("reason") or "")[:300]
        if status not in {"verified", "unsupported"}:
            status = "unverified"
            reason = reason or "checker returned invalid verdict"
        out_by_index[idx] = BulletVerdict(idx, str(item.get("bullet", "")), status, "llm", reason)

    return [
        out_by_index.get(
            int(item.get("index", i)),
            BulletVerdict(
                int(item.get("index", i)),
                str(item.get("bullet", "")),
                "unverified",
                "llm",
                "checker response missing id",
            ),
        )
        for i, item in enumerate(items)
    ]


def apply_verdicts(report: dict, verdicts: list[BulletVerdict]) -> dict:
    bullets = list(report.get("bullets", []) or [])
    unsupported = {v.index for v in verdicts if v.status == "unsupported"}
    report["bullets"] = [bullet for i, bullet in enumerate(bullets) if i not in unsupported]

    verified = sum(1 for v in verdicts if v.status == "verified")
    unsupported_dropped = sum(1 for v in verdicts if v.status == "unsupported")
    unverified_kept = sum(1 for v in verdicts if v.status == "unverified")
    return {
        "enabled": True,
        "total": len(bullets),
        "verified": verified,
        "unsupported_dropped": unsupported_dropped,
        "unverified_kept": unverified_kept,
        "verdicts": [asdict(v) for v in verdicts],
    }
