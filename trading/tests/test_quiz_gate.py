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


def test_answer_flow_first_try_and_retry(quiz_db):
    from trading import quiz
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 2)
    r1 = quiz.record_attempt(user_id=1, question_id=qid, choice_index=0, quiz_date="2026-06-03")
    assert r1["correct"] is False and r1["scored"] is False and r1["entered"] is False
    assert r1["correct_index"] == 2 and r1["explanation"] is not None
    assert quiz.day_state(1, "2026-06-03") == {"answered_today": True, "entered_today": False}
    r2 = quiz.record_attempt(user_id=1, question_id=qid, choice_index=2, quiz_date="2026-06-03")
    assert r2["correct"] is True and r2["scored"] is False and r2["entered"] is True
    assert quiz.day_state(1, "2026-06-03")["entered_today"] is True

def test_answer_first_try_correct_scores(quiz_db):
    from trading import quiz
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 1)
    r = quiz.record_attempt(user_id=9, question_id=qid, choice_index=1, quiz_date="2026-06-04")
    assert r["correct"] and r["scored"] and r["entered"]
    assert r["correct_index"] is None and r["explanation"] is None
