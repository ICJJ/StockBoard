"""Quiz question bank + feedback data operations (separate from auth)."""
from __future__ import annotations

import json

from . import quiz_db


def add_question(prompt: str, options: list, correct_index: int,
                 explanation: str = "", subject: str = "",
                 source: str = "mmlu", status: str = "active",
                 difficulty: str = "") -> int:
    con = quiz_db.connect()
    try:
        cur = con.execute(
            """INSERT INTO questions
               (prompt, options_json, correct_index, explanation, subject, source, status, difficulty)
               VALUES (?,?,?,?,?,?,?,?)""",
            (prompt, json.dumps(options, ensure_ascii=False), int(correct_index),
             explanation, subject, source, status, difficulty),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def get_question(qid: int):
    con = quiz_db.connect()
    try:
        row = con.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        if not row:
            return None
        q = dict(row)
        q["options"] = json.loads(q["options_json"])
        return q
    finally:
        con.close()


def count_active() -> int:
    con = quiz_db.connect()
    try:
        return con.execute("SELECT COUNT(*) AS c FROM questions WHERE status='active'").fetchone()["c"]
    finally:
        con.close()


def record_feedback(user_id: int, question_id: int, vote: str, reason: str = "") -> None:
    con = quiz_db.connect()
    try:
        con.execute(
            """INSERT INTO question_feedback (user_id, question_id, vote, reason)
               VALUES (?,?,?,?)
               ON CONFLICT(user_id, question_id)
               DO UPDATE SET vote=excluded.vote, reason=excluded.reason""",
            (user_id, question_id, vote, reason),
        )
        con.commit()
    finally:
        con.close()


def feedback_tally(question_id: int) -> dict:
    con = quiz_db.connect()
    try:
        rows = con.execute(
            "SELECT vote, COUNT(*) AS c FROM question_feedback WHERE question_id=? GROUP BY vote",
            (question_id,)).fetchall()
        return {r["vote"]: r["c"] for r in rows}
    finally:
        con.close()


import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo


def today_et() -> str:
    """Current quiz date (YYYY-MM-DD) in America/New_York."""
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def daily_question(quiz_date: str | None = None):
    """Same active question for everyone on a given ET date. None if pool empty."""
    quiz_date = quiz_date or today_et()
    con = quiz_db.connect()
    try:
        ids = [r["id"] for r in con.execute(
            "SELECT id FROM questions WHERE status='active' ORDER BY id")]
    finally:
        con.close()
    if not ids:
        return None
    idx = int(hashlib.sha256(quiz_date.encode()).hexdigest(), 16) % len(ids)
    return get_question(ids[idx])
