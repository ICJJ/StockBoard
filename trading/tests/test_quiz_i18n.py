"""Tests for Plan 6: bilingual backend (i18n)."""
import pytest


def test_schema_has_translations(quiz_db):
    import sqlite3
    cols = {r[1] for r in sqlite3.connect(quiz_db).execute("PRAGMA table_info(translations)")}
    assert {"en", "zh"} <= cols


def test_translate_caches_and_passthrough_and_fallback(quiz_db):
    from trading import quiz
    calls = []
    def fake(t): calls.append(t); return "中:" + t
    assert quiz.translate_to_zh("hello world", provider=fake) == "中:hello world"
    assert quiz.translate_to_zh("hello world", provider=fake) == "中:hello world"
    assert calls == ["hello world"]
    def boom(t): raise AssertionError("must not call on CJK")
    assert quiz.translate_to_zh("你好世界", provider=boom) == "你好世界"
    def err(t): raise RuntimeError("api down")
    assert quiz.translate_to_zh("graceful fallback", provider=err) == "graceful fallback"


def test_localize_question_english_and_chinese(quiz_db):
    from trading import quiz
    fake = lambda t: "译:" + t
    en = {"id": 1, "prompt": "What is a bond?", "options": ["debt", "equity"],
          "correct_index": 0, "explanation": "A bond is debt."}
    loc = quiz.localize_question(en, provider=fake)
    assert loc["is_english"] is True
    assert loc["prompt_zh"] == "译:What is a bond?"
    assert loc["options_zh"] == ["译:debt", "译:equity"]
    assert loc["explanation_zh"] == "译:A bond is debt."
    cn = {"id": 2, "prompt": "什么是债券？", "options": ["甲", "乙"], "correct_index": 0, "explanation": "甲"}
    loc2 = quiz.localize_question(cn, provider=fake)
    assert loc2["is_english"] is False
    assert "prompt_zh" not in loc2
