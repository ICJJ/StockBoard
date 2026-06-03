"""Tests for the daily-quiz gate backend (Tasks 1–4)."""


def test_schema_has_attempts(quiz_db):
    import sqlite3
    cols = {r[1] for r in sqlite3.connect(quiz_db).execute("PRAGMA table_info(attempts)")}
    assert {"id", "user_id", "question_id", "quiz_date", "first_try_correct",
            "entered", "attempts_count", "created_at"} <= cols
