"""Tests for quiz question bank and feedback store (Plan 2 Tasks 1-3)."""


def test_schema_has_questions_and_feedback(quiz_db):
    import sqlite3
    con = sqlite3.connect(quiz_db)
    qcols = {r[1] for r in con.execute("PRAGMA table_info(questions)")}
    assert {"id", "prompt", "options_json", "correct_index", "explanation",
            "subject", "source", "status", "difficulty", "created_at"} <= qcols
    fcols = {r[1] for r in con.execute("PRAGMA table_info(question_feedback)")}
    assert {"id", "user_id", "question_id", "vote", "reason", "created_at"} <= fcols


def test_question_store(quiz_db):
    from trading import quiz
    qid = quiz.add_question("What is 2+2?", ["3", "4", "5", "6"], 1,
                            explanation="正确答案:4", subject="math", source="mmlu")
    assert qid > 0
    assert quiz.count_active() == 1
    q = quiz.get_question(qid)
    assert q["prompt"] == "What is 2+2?"
    assert q["options"] == ["3", "4", "5", "6"]
    assert q["correct_index"] == 1
    quiz.add_question("x", ["a", "b", "c", "d"], 0, status="retired")
    assert quiz.count_active() == 1


def test_feedback_upsert_and_tally(quiz_db):
    from trading import quiz
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 0)
    quiz.record_feedback(user_id=1, question_id=qid, vote="remove", reason="too hard")
    quiz.record_feedback(user_id=2, question_id=qid, vote="remove")
    quiz.record_feedback(user_id=1, question_id=qid, vote="keep")
    tally = quiz.feedback_tally(qid)
    assert tally == {"keep": 1, "remove": 1}


def test_feedback_endpoint_requires_login_and_records(client):
    from trading import quiz
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 0)
    assert client.post("/quiz/feedback", json={"question_id": qid, "vote": "remove"}).status_code == 401
    client.post("/auth/login", json={"username": "icjj", "password": "pw"})  # empty DB -> bootstrap admin
    r = client.post("/quiz/feedback", json={"question_id": qid, "vote": "remove", "reason": "太专业"})
    assert r.status_code == 200
    assert quiz.feedback_tally(qid) == {"remove": 1}
    assert client.post("/quiz/feedback", json={"question_id": qid, "vote": "maybe"}).status_code == 400
