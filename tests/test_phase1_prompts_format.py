"""Format-string smoke tests for Phase 1 prompts."""
from src.prompts.step_prompts import (
    PHASE1_QUESTION_FINALIZE_PROMPT,
    PHASE1_ANSWER_PROMPT,
    PHASE1_REFINE_QUERY_PROMPT,
)


def test_phase1_finalize_format():
    out = PHASE1_QUESTION_FINALIZE_PROMPT.format(
        topic="x",
        key_questions_text="...",
        prev_excluded_topics_ko="[]",
        prev_excluded_topics_en="[]",
        feedback="ok",
        current_year=2026,
    )
    assert "kept_question_ids" in out
    assert "merge_groups" in out
    assert "excluded_topics_ko" in out


def test_phase1_answer_format():
    out = PHASE1_ANSWER_PROMPT.format(
        topic="x",
        question="?",
        question_perspective="sell_in",
        source_perspective_breakdown="null",
        related_dimensions_text="...",
        active_excluded_topics_ko="[]",
        time_horizon="단기 6~12개월",
        previous_attempts_block="",
    )
    assert "paragraph" in out
    assert "sentence_count" in out
    assert "source_urls" in out


def test_phase1_refine_format():
    out = PHASE1_REFINE_QUERY_PROMPT.format(
        topic="x",
        eng_topic="iPhone foldable",
        question="?",
        gap="ASP missing",
        active_excluded_topics_en="[]",
        current_year=2026,
    )
    assert "queries" in out
    assert "iPhone foldable" in out
