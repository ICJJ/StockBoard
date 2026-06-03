"""Tests for Plan 5 enrichment: MMLU-Pro, FinanceIQ, add_authored, and CLI."""
import pytest


def test_seed_mmlu_pro_filters_categories(quiz_db):
    from trading import seed_questions, quiz
    fake = [
        {"question": "econ q", "options": ["a", "b", "c", "d"], "answer_index": 1, "category": "economics"},
        {"question": "biz q", "options": ["a", "b", "c", "d", "e"], "answer_index": 4, "category": "business"},
        {"question": "math q", "options": ["a", "b", "c", "d"], "answer_index": 0, "category": "math"},
    ]
    n = seed_questions.seed_mmlu_pro(loader=lambda: fake)
    assert n == 2
    assert quiz.count_active() == 2
    q = quiz.get_question(2)
    assert len(q["options"]) == 5 and q["correct_index"] == 4
