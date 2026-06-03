"""Tests for the daily-quiz gate backend (Tasks 1–4)."""


def test_schema_has_attempts(quiz_db):
    import sqlite3
    cols = {r[1] for r in sqlite3.connect(quiz_db).execute("PRAGMA table_info(attempts)")}
    assert {"id", "user_id", "question_id", "quiz_date", "first_try_correct",
            "entered", "attempts_count", "created_at"} <= cols


def test_daily_question_deterministic(quiz_db):
    from trading import quiz
    ids = [quiz.add_question(f"q{i}", ["a", "b", "c", "d"], 0) for i in range(5)]
    a = quiz.daily_question(quiz_date="2026-06-03")
    b = quiz.daily_question(quiz_date="2026-06-03")
    assert a["id"] == b["id"]
    assert a["id"] in ids
    assert "correct_index" in a
    con = quiz.quiz_db.connect(); con.execute("UPDATE questions SET status='retired'"); con.commit(); con.close()
    assert quiz.daily_question(quiz_date="2026-06-03") is None
