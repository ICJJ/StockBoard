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


def test_streak_and_stats(quiz_db):
    from trading import quiz
    from datetime import date
    assert quiz._streak(["2026-06-03", "2026-06-02", "2026-06-01"], today=date(2026, 6, 3)) == 3
    assert quiz._streak(["2026-06-03", "2026-06-01"], today=date(2026, 6, 3)) == 1
    assert quiz._streak(["2026-06-02", "2026-06-01"], today=date(2026, 6, 3)) == 2
    assert quiz._streak(["2026-06-01"], today=date(2026, 6, 3)) == 0
    assert quiz._streak([], today=date(2026, 6, 3)) == 0

def test_user_stats_and_leaderboard(quiz_db):
    from trading import quiz, auth
    auth.create_user("alice", "pw"); auth.create_user("bob", "pw")
    aid = auth.get_user("alice")["id"]; bid = auth.get_user("bob")["id"]
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 0)
    quiz.record_attempt(aid, qid, 0, quiz_date="2026-06-03")
    quiz.record_attempt(bid, qid, 1, quiz_date="2026-06-03")
    quiz.record_attempt(bid, qid, 0, quiz_date="2026-06-03")
    sa = quiz.user_stats(aid); sb = quiz.user_stats(bid)
    assert sa["points"] == 1 and sb["points"] == 0
    assert sa["days_played"] == 1 and sb["days_played"] == 1
    lb = quiz.leaderboard()
    assert lb[0]["username"] == "alice" and lb[0]["points"] == 1
