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


def prune_flagged(min_remove: int = 3) -> list:
    """Retire active questions the community clearly rejected:
    remove votes >= min_remove AND remove > keep. Returns the retired ids."""
    con = quiz_db.connect()
    try:
        active_ids = [r["id"] for r in con.execute(
            "SELECT id FROM questions WHERE status='active' ORDER BY id")]
    finally:
        con.close()
    retired = []
    for qid in active_ids:
        tally = feedback_tally(qid)
        removes = tally.get("remove", 0)
        keeps = tally.get("keep", 0)
        if removes >= min_remove and removes > keeps:
            con = quiz_db.connect()
            try:
                con.execute("UPDATE questions SET status='retired' WHERE id=?", (qid,))
                con.commit()
            finally:
                con.close()
            retired.append(qid)
    return retired


import hashlib
from datetime import date, datetime, timedelta
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


def day_state(user_id: int, quiz_date: str | None = None) -> dict:
    quiz_date = quiz_date or today_et()
    con = quiz_db.connect()
    try:
        row = con.execute(
            "SELECT entered FROM attempts WHERE user_id=? AND quiz_date=?",
            (user_id, quiz_date)).fetchone()
    finally:
        con.close()
    return {"answered_today": row is not None, "entered_today": bool(row and row["entered"])}


def record_attempt(user_id: int, question_id: int, choice_index: int,
                   quiz_date: str | None = None) -> dict:
    quiz_date = quiz_date or today_et()
    q = get_question(question_id)
    if q is None:
        raise ValueError("no such question")
    correct = (int(choice_index) == q["correct_index"])
    con = quiz_db.connect()
    try:
        row = con.execute(
            "SELECT * FROM attempts WHERE user_id=? AND quiz_date=?",
            (user_id, quiz_date)).fetchone()
        first_attempt = row is None
        if first_attempt:
            con.execute(
                """INSERT INTO attempts
                   (user_id, question_id, quiz_date, first_try_correct, entered, attempts_count)
                   VALUES (?,?,?,?,?,1)""",
                (user_id, question_id, quiz_date, 1 if correct else 0, 1 if correct else 0))
            entered = correct
        else:
            con.execute(
                """UPDATE attempts SET attempts_count = attempts_count + 1,
                   entered = MAX(entered, ?) WHERE user_id=? AND quiz_date=?""",
                (1 if correct else 0, user_id, quiz_date))
            entered = bool(row["entered"]) or correct
        con.commit()
    finally:
        con.close()
    scored = bool(correct and first_attempt)
    return {
        "correct": correct,
        "scored": scored,
        "entered": bool(entered),
        "correct_index": None if correct else q["correct_index"],
        "explanation": None if correct else q["explanation"],
    }


def _streak(entered_dates, today=None) -> int:
    if not entered_dates:
        return 0
    today = today or date.fromisoformat(today_et())
    have = set(entered_dates)
    cur = today if today.isoformat() in have else today - timedelta(days=1)
    n = 0
    while cur.isoformat() in have:
        n += 1
        cur -= timedelta(days=1)
    return n


def user_stats(user_id: int) -> dict:
    con = quiz_db.connect()
    try:
        points = con.execute(
            "SELECT COUNT(*) AS c FROM attempts WHERE user_id=? AND first_try_correct=1",
            (user_id,)).fetchone()["c"]
        days = con.execute(
            "SELECT COUNT(*) AS c FROM attempts WHERE user_id=? AND entered=1",
            (user_id,)).fetchone()["c"]
        dates = [r["quiz_date"] for r in con.execute(
            "SELECT quiz_date FROM attempts WHERE user_id=? AND entered=1", (user_id,))]
    finally:
        con.close()
    return {
        "points": points,
        "days_played": days,
        "accuracy": round(points / days, 3) if days else 0.0,
        "streak": _streak(dates),
    }


def add_authored(questions: list) -> int:
    """Insert original Claude-authored MCQs (source='claude', active). Validates each;
    skips malformed. Returns count inserted."""
    n = 0
    for q in questions or []:
        prompt = (q.get("prompt") or "").strip()
        options = q.get("options")
        ci = q.get("correct_index")
        if not (prompt and isinstance(options, list) and len(options) >= 2
                and isinstance(ci, int) and 0 <= ci < len(options)):
            continue
        add_question(prompt, options, ci,
                     explanation=q.get("explanation", ""),
                     subject=q.get("subject", "claude"), source="claude")
        n += 1
    return n


def leaderboard() -> list:
    con = quiz_db.connect()
    try:
        users = [(r["id"], r["username"]) for r in con.execute(
            "SELECT id, username FROM users ORDER BY username")]
    finally:
        con.close()
    rows = [{"username": name, **user_stats(uid)} for uid, name in users]
    rows.sort(key=lambda r: (r["points"], r["streak"]), reverse=True)
    return rows


def _has_cjk(s: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in (s or ""))


def _default_translate_provider(text: str) -> str:
    import json
    import urllib.parse
    import urllib.request
    url = ("https://translate.googleapis.com/translate_a/single"
           "?client=gtx&sl=en&tl=zh-CN&dt=t&q=" + urllib.parse.quote(text))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.load(r)
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def translate_to_zh(text: str, provider=None) -> str:
    if not text or _has_cjk(text):
        return text
    con = quiz_db.connect()
    try:
        row = con.execute("SELECT zh FROM translations WHERE en=?", (text,)).fetchone()
        if row:
            return row["zh"]
    finally:
        con.close()
    provider = provider or _default_translate_provider
    try:
        zh = provider(text)
    except Exception:
        return text
    if not zh:
        return text
    con = quiz_db.connect()
    try:
        con.execute("INSERT OR IGNORE INTO translations(en, zh) VALUES (?, ?)", (text, zh))
        con.commit()
    finally:
        con.close()
    return zh


def _is_english(text: str) -> bool:
    if not text or _has_cjk(text):
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    ascii_letters = [c for c in letters if ord(c) < 128]
    return len(ascii_letters) / len(letters) > 0.6


def localize_question(q: dict, provider=None) -> dict:
    out = dict(q)
    if _is_english(q.get("prompt", "")):
        out["is_english"] = True
        out["prompt_zh"] = translate_to_zh(q["prompt"], provider)
        out["options_zh"] = [translate_to_zh(o, provider) for o in q.get("options", [])]
        if q.get("explanation"):
            out["explanation_zh"] = translate_to_zh(q["explanation"], provider)
    else:
        out["is_english"] = False
    return out
