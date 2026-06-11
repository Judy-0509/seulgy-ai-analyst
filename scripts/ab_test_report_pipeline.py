"""리포트 작성 단계(E/F/G) A/B 테스트 하네스.

배경:
  Phase 0 목적은 critique 기능을 붙이기 전에 LLM 작성 단계의 자연 변동폭을
  먼저 측정하는 것이다. A/B는 같은 evidence snapshot을 공유하므로 검색 결과
  차이 없이 stage_ef, stage_g의 출력만 비교한다.

방법:
  snapshot 명령은 run_report.py의 A→D 배선을 auto 모드로 한 번 실행하고,
  Stage D evidence guardrail을 통과한 결과를 JSON으로 저장한다.
  run 명령은 저장된 evidence를 로드해 Variant A/B의 환경변수를 각각 적용한 뒤
  E/F/G만 두 번 실행한다. 기본은 A-vs-A noise floor 측정이다.

실행:
  python scripts/ab_test_report_pipeline.py snapshot --domain humanoid "토픽 텍스트"
  python scripts/ab_test_report_pipeline.py run --evidence scripts/_ab_report_evidence/{slug}.json --skip-judge

산출:
  scripts/_ab_report_evidence/{slug}.json  (A→D evidence snapshot)
  scripts/_ab_report_quality.json          (metrics + judge audit)
  reports/_ab_{slug}.html                  (blind side-by-side HTML)
  stdout 비교 테이블
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import html
import io
import json
import os
import random
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_report import (  # noqa: E402
    ANALYST_SYSTEM_PROMPT,
    DOMAIN_ANALYST_TYPES,
    DOMAIN_SYSTEM_PROMPTS,
    LLMService,
    SearchService,
    _build_markdown,
    _extract_json_block,
    _slug,
    _warn_section_overlap,
    _year,
    load_domain,
    stage_a,
    stage_b,
    stage_c,
    stage_d,
    stage_ef,
    stage_g,
    user_gate_1,
)
from src.models import SearchResult  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

EVIDENCE_DIR = ROOT / "scripts" / "_ab_report_evidence"
QUALITY_PATH = ROOT / "scripts" / "_ab_report_quality.json"
REPORTS_DIR = ROOT / "reports"
STAGE_D_MIN_TOTAL = 10
STAGE_D_MIN_AVG_PER_SECTION = 3


def _search_result_dump(result: SearchResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


def serialize_snapshot(
    topic: str,
    domain: str,
    eng_topic: str,
    pre_queries: list[str],
    archive_results: list[SearchResult],
    sections: list[dict[str, Any]],
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "domain": domain,
        "eng_topic": eng_topic,
        "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
        "pre_queries": pre_queries,
        "archive_results": [_search_result_dump(r) for r in archive_results],
        "sections": [
            {
                **{k: v for k, v in sec.items() if k != "results"},
                "results": [_search_result_dump(r) for r in sec.get("results", [])],
            }
            for sec in sections
        ],
    }


def load_snapshot(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["archive_results"] = [SearchResult(**d) for d in data.get("archive_results", [])]
    data["sections"] = [
        {
            **{k: v for k, v in sec.items() if k != "results"},
            "results": [SearchResult(**d) for d in sec.get("results", [])],
        }
        for sec in data.get("sections", [])
    ]
    return data


def _normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'}))
    text = re.sub(r"[/\\]", " ", text)
    text = re.sub(r"['\"]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def quote_match_rate(report: dict[str, Any], evidence_texts: list[str]) -> tuple[int, int, float]:
    evidence = _normalize_text(" ".join(evidence_texts))
    matched = 0
    total = 0
    for bullet in report.get("bullets", []) or []:
        spans = re.findall(r"[“\"]([^”\"]+)[”\"]", str(bullet))
        for span in spans:
            total += 1
            if _normalize_text(span) in evidence:
                matched += 1
    return matched, total, matched / total if total else 1.0


_NUMBER_RE = re.compile(
    r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|\d{2,}(?:\.\d+)?%?)(?![\d.])"
)


def _numbers(text: str) -> set[str]:
    return {m.group(0).replace(",", "") for m in _NUMBER_RE.finditer(text or "")}


def number_support_rate(report: dict[str, Any], evidence_texts: list[str]) -> tuple[int, int, float]:
    target = f"{report.get('headline', '')} {report.get('narrative', '')}"
    nums = _numbers(target)
    evidence = " ".join(evidence_texts).replace(",", "")
    supported = sum(1 for n in nums if n in evidence)
    total = len(nums)
    return supported, total, supported / total if total else 1.0


def footnote_url_validity(report: dict[str, Any], evidence_urls: list[str]) -> tuple[int, int, float]:
    evidence = set(evidence_urls)
    urls = [fn.get("url", "") for fn in report.get("footnotes", []) or [] if fn.get("url")]
    valid = sum(1 for url in urls if url in evidence)
    total = len(urls)
    return valid, total, valid / total if total else 1.0


def compute_metrics(sections: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    quote_matched = quote_total = 0
    number_supported = number_total = 0
    footnote_valid = footnote_total = 0
    total_bullets = 0
    narrative_chars = []
    omitted = 0

    for sec in sections:
        report = sec.get("report") or {}
        if report.get("insufficient_evidence"):
            omitted += 1
            continue
        evidence_texts = [r.content for r in sec.get("results", [])]
        evidence_urls = [r.source_url for r in sec.get("results", [])]
        qm, qt, _ = quote_match_rate(report, evidence_texts)
        ns, nt, _ = number_support_rate(report, evidence_texts)
        fv, ft, _ = footnote_url_validity(report, evidence_urls)
        quote_matched += qm
        quote_total += qt
        number_supported += ns
        number_total += nt
        footnote_valid += fv
        footnote_total += ft
        bullets = report.get("bullets", []) or []
        total_bullets += len(bullets)
        narrative_chars.append(len(report.get("narrative", "") or ""))

    insights = meta.get("insights", []) or []
    insight_lengths = [len(ins.get("body", "") or "") for ins in insights if isinstance(ins, dict)]
    valid = len(sections) - omitted
    return {
        "quote_match": _ratio_dict(quote_matched, quote_total),
        "number_support": _ratio_dict(number_supported, number_total),
        "footnote_url_validity": _ratio_dict(footnote_valid, footnote_total),
        "omitted_section_count": omitted,
        "valid_section_count": valid,
        "total_bullets": total_bullets,
        "avg_narrative_chars": round(sum(narrative_chars) / len(narrative_chars), 1) if narrative_chars else 0.0,
        "executive_summary_chars": len(meta.get("executive_summary", "") or ""),
        "insight_count": len(insights),
        "avg_insight_body_chars": round(sum(insight_lengths) / len(insight_lengths), 1) if insight_lengths else 0.0,
    }


def _ratio_dict(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "matched": numerator,
        "total": denominator,
        "rate": round(numerator / denominator, 4) if denominator else 1.0,
    }


@contextmanager
def _patched_environ(overrides: dict[str, str]):
    old = {k: os.environ.get(k) for k in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# llm.py가 import 시점에 모듈 상수/백엔드 속성으로 바인딩하는 변수.
# 런타임 env 패치가 stage_ef(분석 모델 등)에 적용되지 않아 의도치 않은
# A-vs-A 비교(silent no-op)가 되므로 variant override 시 경고한다.
# (stage_g의 GLM_FINAL_MODEL 등 호출 시점에 os.getenv로 읽는 변수는 정상 적용)
_IMPORT_TIME_ENV_KEYS = {
    "LLM_BACKEND",
    "ZHIPU_API_KEY",
    "GLM_ANALYSIS_MODEL",
    "GLM_EXTRACTION_MODEL",
    "GLM_REQUEST_TIMEOUT_SECONDS",
}


def warn_import_bound_keys(env: dict[str, str], label: str) -> list[str]:
    hits = sorted(set(env) & _IMPORT_TIME_ENV_KEYS)
    if hits:
        print(
            f"  [!] variant {label}: {', '.join(hits)} 는 llm.py import 시점에 바인딩되어 "
            "E/F 단계에 적용되지 않습니다 — 이 override는 사실상 무시됩니다 (A-vs-A 위험)."
        )
    return hits


def parse_env_pairs(pairs: list[str] | None) -> dict[str, str]:
    parsed = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"환경변수 override 형식 오류: {pair} (KEY=VAL 필요)")
        key, value = pair.split("=", 1)
        if not key:
            raise ValueError(f"환경변수 key가 비어 있습니다: {pair}")
        parsed[key] = value
    return parsed


async def run_snapshot(topic: str, domain: str) -> Path:
    sys_prompt, analyst_type, player_examples, example_topic = _domain_context(domain)
    llm = LLMService()
    search = SearchService(domain=domain)
    try:
        pre_queries, eng_topic = await stage_a(
            llm,
            topic,
            system_prompt=sys_prompt,
            analyst_type=analyst_type,
            player_examples=player_examples,
            example_topic=example_topic,
        )
        search.set_core_terms(eng_topic, current_year=str(_year()))
        archive_results = await stage_b(search, pre_queries, eng_kw=eng_topic)

        external_default = os.getenv("STAGE_D_EXTERNAL_DEFAULT", "").strip().lower() in {"1", "true", "yes", "on"}
        use_external = external_default
        if len(archive_results) < 3 and use_external:
            seen = {r.source_url for r in archive_results}
            for pq in pre_queries:
                sr = await search.search(pq, pq.split())
                for r in sr.results:
                    if r.source_url not in seen:
                        archive_results.append(r)
                        seen.add(r.source_url)

        sections = await stage_c(
            llm,
            topic,
            archive_results,
            system_prompt=sys_prompt,
            analyst_type=analyst_type,
            player_examples=player_examples,
            example_topic=example_topic,
        )
        _warn_section_overlap(sections)
        sections = await user_gate_1(sections, auto=True)
        sections = await stage_d(search, sections, use_external=use_external)
        _enforce_stage_d_guardrail(sections)

        snapshot = serialize_snapshot(topic, domain, eng_topic, pre_queries, archive_results, sections)
        out_path = EVIDENCE_DIR / f"{_slug(topic)}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        _print_snapshot_summary(out_path, snapshot)
        return out_path
    finally:
        await search.close()


def _domain_context(domain: str) -> tuple[str, str, str, str]:
    sys_prompt = DOMAIN_SYSTEM_PROMPTS.get(domain, ANALYST_SYSTEM_PROMPT)
    analyst_type = DOMAIN_ANALYST_TYPES.get(domain, "senior smartphone market analyst")
    dom_cfg = load_domain(domain)
    player_examples = dom_cfg.get("player_examples", "Samsung, Apple, Xiaomi, Huawei")
    example_topic = dom_cfg.get("example_topic", "foldable smartphones")
    return sys_prompt, analyst_type, player_examples, example_topic


def _enforce_stage_d_guardrail(sections: list[dict[str, Any]]) -> None:
    total = sum(len(s.get("results", [])) for s in sections)
    avg = total / len(sections) if sections else 0
    if total < STAGE_D_MIN_TOTAL or avg < STAGE_D_MIN_AVG_PER_SECTION:
        raise RuntimeError(
            f"[Stage D 가드레일] Evidence 부족: 전체 {total}건 "
            f"(요구 >={STAGE_D_MIN_TOTAL}), 섹션당 평균 {avg:.1f}건 "
            f"(요구 >={STAGE_D_MIN_AVG_PER_SECTION})."
        )


def _print_snapshot_summary(path: Path, snapshot: dict[str, Any]) -> None:
    section_counts = [len(s.get("results", [])) for s in snapshot["sections"]]
    print("\nSnapshot")
    print("-" * 80)
    print(f"topic      : {snapshot['topic']}")
    print(f"domain     : {snapshot['domain']}")
    print(f"pre queries: {len(snapshot['pre_queries'])}")
    print(f"archive    : {len(snapshot['archive_results'])}")
    print(f"sections   : {len(section_counts)} / evidence {sum(section_counts)}")
    print(f"saved      : {path}")


async def run_variant(
    snapshot: dict[str, Any],
    env: dict[str, str],
) -> dict[str, Any]:
    sys_prompt, analyst_type, player_examples, example_topic = _domain_context(snapshot["domain"])
    llm = LLMService()
    sections = copy.deepcopy(snapshot["sections"])
    with _patched_environ(env):
        sections = await stage_ef(
            llm,
            snapshot["topic"],
            sections,
            system_prompt=sys_prompt,
            analyst_type=analyst_type,
            player_examples=player_examples,
            example_topic=example_topic,
        )
        meta = await stage_g(
            llm,
            snapshot["topic"],
            sections,
            system_prompt=sys_prompt,
            analyst_type=analyst_type,
            player_examples=player_examples,
            example_topic=example_topic,
        )
    return {"sections": sections, "meta": meta, "metrics": compute_metrics(sections, meta)}


def _full_report_text(topic: str, variant: dict[str, Any]) -> str:
    return _build_markdown(topic, variant["sections"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), variant["meta"])


def _judge_prompt(topic: str, report_1: str, report_2: str) -> str:
    criteria = ["증거 기반성", "인사이트 깊이", "논리 일관성", "문체·가독성"]
    return (
        "다음 두 한국어 시장 리서치 보고서를 블라인드로 평가하세요.\n"
        "각 기준별 winner는 반드시 \"1\", \"2\", \"tie\" 중 하나입니다.\n"
        "JSON 객체만 반환하세요.\n"
        f"기준: {', '.join(criteria)} 및 overall\n\n"
        f"주제: {topic}\n\n"
        f"보고서 1\n{report_1}\n\n"
        f"보고서 2\n{report_2}\n\n"
        "형식: {\"증거 기반성\":{\"winner\":\"1\",\"reason\":\"...\"},"
        "\"인사이트 깊이\":{\"winner\":\"1\",\"reason\":\"...\"},"
        "\"논리 일관성\":{\"winner\":\"tie\",\"reason\":\"...\"},"
        "\"문체·가독성\":{\"winner\":\"2\",\"reason\":\"...\"},"
        "\"overall\":{\"winner\":\"tie\",\"reason\":\"...\"}}"
    )


async def run_blind_judge(
    llm: Any,
    topic: str,
    variant_a: dict[str, Any],
    variant_b: dict[str, Any],
) -> dict[str, Any]:
    order = ["A", "B"]
    random.shuffle(order)
    first = await _judge_once(llm, topic, variant_a, variant_b, order)
    swapped = ["B" if x == "A" else "A" for x in order]
    second = await _judge_once(llm, topic, variant_a, variant_b, swapped)
    verdicts = _aggregate_judge(first["unmapped"], second["unmapped"])
    return {"mapping": first["mapping"], "passes": [first, second], "verdicts": verdicts}


async def _judge_once(
    llm: Any,
    topic: str,
    variant_a: dict[str, Any],
    variant_b: dict[str, Any],
    order: list[str],
) -> dict[str, Any]:
    variants = {"A": variant_a, "B": variant_b}
    reports = [_full_report_text(topic, variants[label]) for label in order]
    resp = await llm.complete(
        ANALYST_SYSTEM_PROMPT,
        _judge_prompt(topic, reports[0], reports[1]),
        model="glm-5.1",
        max_tokens=3000,
        temperature=0.1,
        response_format={"type": "json_object"},
        thinking="disabled",
    )
    parsed = _extract_json_block(resp.content.strip()) or {}
    mapping = {"1": order[0], "2": order[1]}
    return {"mapping": mapping, "raw": parsed, "unmapped": _unmap_judge(parsed, mapping)}


def _unmap_judge(parsed: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    out = {}
    for criterion, value in parsed.items():
        if not isinstance(value, dict):
            continue
        winner = value.get("winner", "tie")
        out[criterion] = {
            "winner": mapping.get(winner, "tie") if winner in {"1", "2"} else "tie",
            "reason": value.get("reason", ""),
        }
    return out


def _aggregate_judge(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    keys = set(first) | set(second)
    out = {}
    for key in sorted(keys):
        w1 = (first.get(key) or {}).get("winner", "tie")
        w2 = (second.get(key) or {}).get("winner", "tie")
        out[key] = {"winner": w1 if w1 == w2 else "noise", "pass_1": w1, "pass_2": w2}
    return out


async def run_ab(evidence_path: Path, env_a: dict[str, str], env_b: dict[str, str], skip_judge: bool) -> None:
    warn_import_bound_keys(env_a, "A")
    warn_import_bound_keys(env_b, "B")
    snapshot = load_snapshot(evidence_path)
    variant_a = await run_variant(snapshot, env_a)
    variant_b = await run_variant(snapshot, env_b)

    labels = ["A", "B"]
    random.shuffle(labels)
    html_mapping = {"보고서 1": labels[0], "보고서 2": labels[1]}
    html_path = write_ab_html(snapshot["topic"], snapshot["domain"], variant_a, variant_b, html_mapping)

    judge = None
    if not skip_judge:
        judge = await run_blind_judge(LLMService(), snapshot["topic"], variant_a, variant_b)

    quality = {
        "evidence_file": str(evidence_path),
        "topic": snapshot["topic"],
        "domain": snapshot["domain"],
        "variant_env": {"A": env_a, "B": env_b},
        "metrics": {"A": variant_a["metrics"], "B": variant_b["metrics"]},
        "judge": judge,
        "html_mapping": html_mapping,
        "html_path": str(html_path),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    QUALITY_PATH.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    print_comparison(variant_a["metrics"], variant_b["metrics"], judge, html_path)


def write_ab_html(
    topic: str,
    domain: str,
    variant_a: dict[str, Any],
    variant_b: dict[str, Any],
    mapping: dict[str, str],
) -> Path:
    variants = {"A": variant_a, "B": variant_b}
    columns = []
    for label in ("보고서 1", "보고서 2"):
        v = variants[mapping[label]]
        columns.append(_render_report_column(label, topic, v["sections"], v["meta"]))
    html_text = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A/B Report - {html.escape(topic)}</title>
<style>
body {{ font-family: 'Apple SD Gothic Neo', -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif; margin: 0; background: #f7f6f3; color: #2a2826; line-height: 1.7; }}
header {{ max-width: 1360px; margin: 0 auto; padding: 28px 24px 12px; }}
h1 {{ font-size: 1.45rem; margin: 0 0 6px; border-bottom: 2px solid #10b981; padding-bottom: 8px; }}
.meta {{ color: #6b7280; font-size: 0.86rem; }}
.grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; max-width: 1360px; margin: 0 auto; padding: 16px 24px 36px; }}
.col {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; min-width: 0; }}
h2 {{ font-size: 1.15rem; color: #047857; border-left: 4px solid #10b981; padding-left: 10px; margin-top: 2rem; }}
h3 {{ font-size: 1rem; color: #1f2933; margin-top: 1.4rem; }}
.label {{ margin-top: 0; color: #047857; }}
p {{ margin: 0.55em 0; }}
li {{ margin: 0.25em 0; }}
a {{ color: #059669; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.footnotes {{ font-size: 0.86rem; color: #4b5563; }}
@media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header><h1>{html.escape(topic)}</h1><div class="meta">domain: {html.escape(domain)} · blind A/B report</div></header>
<main class="grid">{''.join(columns)}</main>
</body>
</html>"""
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"_ab_{_slug(topic)}.html"
    path.write_text(html_text, encoding="utf-8")
    return path


def _render_report_column(label: str, topic: str, sections: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    parts = [f'<section class="col"><h2 class="label">{label}</h2>']
    exec_summary = meta.get("executive_summary", "")
    if exec_summary:
        parts.append("<h2>Executive Summary</h2>")
        parts.append(f"<p>{html.escape(exec_summary)}</p>")
    for idx, sec in enumerate(sections, 1):
        rep = sec.get("report") or {}
        if rep.get("insufficient_evidence"):
            continue
        parts.append(f"<h2>{idx}. {html.escape(sec.get('title', ''))}</h2>")
        parts.append(f"<h3>{html.escape(rep.get('headline', ''))}</h3>")
        for para in (rep.get("narrative", "") or "").split("\n\n"):
            if para.strip():
                parts.append(f"<p>{html.escape(para.strip())}</p>")
        bullets = rep.get("bullets", []) or []
        if bullets:
            parts.append("<ul>")
            parts.extend(f"<li>{html.escape(str(b))}</li>" for b in bullets)
            parts.append("</ul>")
        footnotes = rep.get("footnotes", []) or []
        if footnotes:
            parts.append('<ol class="footnotes">')
            for fn in footnotes:
                url = fn.get("url", "")
                title = fn.get("title") or fn.get("source") or url
                parts.append(f'<li><a href="{html.escape(url)}">{html.escape(title)}</a></li>')
            parts.append("</ol>")
    insights = meta.get("insights", []) or []
    if insights:
        parts.append("<h2>Market Insights</h2>")
        for ins in insights:
            parts.append(f"<h3>{html.escape(ins.get('title', ''))}</h3>")
            parts.append(f"<p>{html.escape(ins.get('body', ''))}</p>")
    parts.append(f"<!-- rendered for {html.escape(topic)} -->")
    parts.append("</section>")
    return "\n".join(parts)


def print_comparison(metrics_a: dict[str, Any], metrics_b: dict[str, Any], judge: dict[str, Any] | None, html_path: Path) -> None:
    rows = [
        ("quote_match", metrics_a["quote_match"]["rate"], metrics_b["quote_match"]["rate"]),
        ("number_support", metrics_a["number_support"]["rate"], metrics_b["number_support"]["rate"]),
        ("footnote_url", metrics_a["footnote_url_validity"]["rate"], metrics_b["footnote_url_validity"]["rate"]),
        ("omitted_sections", metrics_a["omitted_section_count"], metrics_b["omitted_section_count"]),
        ("valid_sections", metrics_a["valid_section_count"], metrics_b["valid_section_count"]),
        ("total_bullets", metrics_a["total_bullets"], metrics_b["total_bullets"]),
        ("avg_narrative_chars", metrics_a["avg_narrative_chars"], metrics_b["avg_narrative_chars"]),
        ("executive_summary_chars", metrics_a["executive_summary_chars"], metrics_b["executive_summary_chars"]),
        ("insight_count", metrics_a["insight_count"], metrics_b["insight_count"]),
        ("avg_insight_body_chars", metrics_a["avg_insight_body_chars"], metrics_b["avg_insight_body_chars"]),
    ]
    print(f"{'metric':<28} {'A':>10} {'B':>10} {'Δ B-A':>10}")
    print("-" * 64)
    for name, a, b in rows:
        delta = b - a
        print(f"{name:<28} {_fmt(a):>10} {_fmt(b):>10} {_fmt(delta, signed=True):>10}")
    if judge:
        print("\nJudge")
        print("-" * 64)
        for key, verdict in judge.get("verdicts", {}).items():
            print(f"{key:<18} {verdict.get('winner', 'n/a')}")
    else:
        print("\nJudge: skipped")
    print(f"\nJSON: {QUALITY_PATH}")
    print(f"HTML: {html_path}")


def _fmt(value: float | int, signed: bool = False) -> str:
    if isinstance(value, float):
        text = f"{value:+.4f}" if signed else f"{value:.4f}"
    else:
        text = f"{value:+d}" if signed else str(value)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B test report-writing stages on identical evidence.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--domain", default="smartphone")
    snap.add_argument("topic")
    run = sub.add_parser("run")
    run.add_argument("--evidence", required=True)
    run.add_argument("--variant-a-env", nargs="*", default=[])
    run.add_argument("--variant-b-env", nargs="*", default=[])
    run.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()

    if args.cmd == "snapshot":
        asyncio.run(run_snapshot(args.topic, args.domain))
    elif args.cmd == "run":
        env_a = parse_env_pairs(args.variant_a_env)
        env_b = parse_env_pairs(args.variant_b_env)
        asyncio.run(run_ab(Path(args.evidence), env_a, env_b, args.skip_judge))


if __name__ == "__main__":
    main()
