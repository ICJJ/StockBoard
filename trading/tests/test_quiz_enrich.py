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


def test_seed_financeiq_inserts_normalized(quiz_db):
    from trading import seed_questions, quiz
    fake = [
        {"question": "证券 q1", "options": ["甲", "乙", "丙", "丁"], "answer_index": 2, "subject": "证券从业"},
        {"question": "bad", "options": ["甲"], "answer_index": 0, "subject": "证券从业"},
    ]
    n = seed_questions.seed_financeiq(loader=lambda: fake)
    assert n == 1
    assert quiz.count_active() == 1
    q = quiz.get_question(1)
    assert q["subject"] == "证券从业" and q["options"] == ["甲", "乙", "丙", "丁"]


def test_add_authored_validates(quiz_db):
    from trading import quiz
    items = [
        {"prompt": "good", "options": ["a", "b", "c", "d"], "correct_index": 2, "explanation": "x", "subject": "markets"},
        {"prompt": "", "options": ["a", "b"], "correct_index": 0},
        {"prompt": "bad idx", "options": ["a", "b"], "correct_index": 5},
        {"prompt": "one opt", "options": ["a"], "correct_index": 0},
    ]
    n = quiz.add_authored(items)
    assert n == 1
    assert quiz.count_active() == 1
    con = quiz.quiz_db.connect()
    src = con.execute("SELECT source FROM questions WHERE prompt='good'").fetchone()["source"]
    con.close()
    assert src == "claude"
