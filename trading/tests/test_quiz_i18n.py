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
