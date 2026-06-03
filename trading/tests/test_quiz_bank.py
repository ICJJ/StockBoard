"""Tests for quiz question bank and feedback store (Plan 2 Tasks 1-3)."""


def test_schema_has_questions_and_feedback(quiz_db):
    import sqlite3
    con = sqlite3.connect(quiz_db)
    qcols = {r[1] for r in con.execute("PRAGMA table_info(questions)")}
    assert {"id", "prompt", "options_json", "correct_index", "explanation",
            "subject", "source", "status", "difficulty", "created_at"} <= qcols
    fcols = {r[1] for r in con.execute("PRAGMA table_info(question_feedback)")}
    assert {"id", "user_id", "question_id", "vote", "reason", "created_at"} <= fcols
