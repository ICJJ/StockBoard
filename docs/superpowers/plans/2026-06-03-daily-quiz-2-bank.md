# Daily Quiz — Plan 2: Question Bank & Seed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the question-bank data model, a question/feedback store, a per-user "too professional → keep/remove" feedback endpoint, and a one-time MMLU-professional seed script — so a verified daily-question pool and its self-curation feedback exist for Plan 3 to consume.

**Architecture:** Extend `trading/quiz_db.py` SCHEMA with `questions` + `question_feedback` tables. Add `trading/quiz.py` for question/feedback logic (kept separate from auth). Add a `/quiz/feedback` endpoint reusing Plan 1's `current_user`. A standalone `trading/seed_questions.py` imports MMLU professional/finance subsets (verified answers, MIT) via the `datasets` library — imported lazily and behind an injectable loader so the test suite needs no network or heavy deps.

**Tech Stack:** Python 3.9, FastAPI, SQLite (stdlib `sqlite3`), `datasets` (seed only, lazy), pytest. Reuses Plan 1: `quiz_db.connect/init_db`, `auth.current_user`.

**Spec:** `docs/superpowers/specs/2026-06-03-daily-quiz-design.md` §4 (`questions`, `question_feedback`), §8 (bank + seed). NOT in this plan: daily gate/scoring (Plan 3), scheduled maintenance (Plan 4).

---

## File Structure

- `trading/quiz_db.py` — Modify: append `questions` + `question_feedback` to `SCHEMA`.
- `trading/quiz.py` — Create: question store (`add_question`, `get_question`, `count_active`) + feedback (`record_feedback`, `feedback_tally`). One responsibility: quiz bank/feedback data ops.
- `trading/app.py` — Modify: add `POST /quiz/feedback` (uses `current_user`).
- `trading/seed_questions.py` — Create: one-time MMLU importer (lazy `datasets`, injectable loader).
- `trading/requirements-quiz.txt` — Modify: add `datasets` (used only by the seed run).
- `trading/tests/test_quiz_bank.py` — Create: unit + endpoint + seed-logic tests (no network).

---

### Task 1: Schema — `questions` + `question_feedback`

**Files:**
- Modify: `trading/quiz_db.py` (the `SCHEMA` string)
- Test: `trading/tests/test_quiz_bank.py`

- [ ] **Step 1: Write the failing test**

Create `trading/tests/test_quiz_bank.py`:
```python
def test_schema_has_questions_and_feedback(quiz_db):
    import sqlite3
    con = sqlite3.connect(quiz_db)
    qcols = {r[1] for r in con.execute("PRAGMA table_info(questions)")}
    assert {"id", "prompt", "options_json", "correct_index", "explanation",
            "subject", "source", "status", "difficulty", "created_at"} <= qcols
    fcols = {r[1] for r in con.execute("PRAGMA table_info(question_feedback)")}
    assert {"id", "user_id", "question_id", "vote", "reason", "created_at"} <= fcols
```

- [ ] **Step 2: Run it (fails — tables don't exist)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_schema_has_questions_and_feedback -v`
Expected: FAIL (no such table).

- [ ] **Step 3: Append both tables to `SCHEMA` in `trading/quiz_db.py`**

Append inside the existing `SCHEMA = """ ... """` string (after the `users` table):
```sql

CREATE TABLE IF NOT EXISTS questions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt        TEXT NOT NULL,
    options_json  TEXT NOT NULL,
    correct_index INTEGER NOT NULL,
    explanation   TEXT NOT NULL DEFAULT '',
    subject       TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT 'mmlu',
    status        TEXT NOT NULL DEFAULT 'active',
    difficulty    TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS question_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    vote        TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, question_id)
);
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_schema_has_questions_and_feedback -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add trading/quiz_db.py trading/tests/test_quiz_bank.py
git commit -m "feat(quiz): questions + question_feedback tables

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Question store (`trading/quiz.py`)

**Files:**
- Create: `trading/quiz.py`
- Test: `trading/tests/test_quiz_bank.py`

- [ ] **Step 1: Write the failing test**

Append to `trading/tests/test_quiz_bank.py`:
```python
def test_question_store(quiz_db):
    from trading import quiz
    qid = quiz.add_question("What is 2+2?", ["3", "4", "5", "6"], 1,
                            explanation="正确答案:4", subject="math", source="mmlu")
    assert qid > 0
    assert quiz.count_active() == 1
    q = quiz.get_question(qid)
    assert q["prompt"] == "What is 2+2?"
    assert q["options"] == ["3", "4", "5", "6"]   # parsed from options_json
    assert q["correct_index"] == 1
    # retired questions don't count as active
    quiz.add_question("x", ["a", "b", "c", "d"], 0, status="retired")
    assert quiz.count_active() == 1
```

- [ ] **Step 2: Run it (fails — no module)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_question_store -v`
Expected: FAIL (ModuleNotFoundError: trading.quiz).

- [ ] **Step 3: Implement `trading/quiz.py`**

```python
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
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_question_store -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add trading/quiz.py trading/tests/test_quiz_bank.py
git commit -m "feat(quiz): question store (add/get/count_active)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Feedback store (upsert + tally)

**Files:**
- Modify: `trading/quiz.py`
- Test: `trading/tests/test_quiz_bank.py`

- [ ] **Step 1: Write the failing test**

Append to `trading/tests/test_quiz_bank.py`:
```python
def test_feedback_upsert_and_tally(quiz_db):
    from trading import quiz
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 0)
    quiz.record_feedback(user_id=1, question_id=qid, vote="remove", reason="too hard")
    quiz.record_feedback(user_id=2, question_id=qid, vote="remove")
    quiz.record_feedback(user_id=1, question_id=qid, vote="keep")  # user 1 changes mind (upsert)
    tally = quiz.feedback_tally(qid)
    assert tally == {"keep": 1, "remove": 1}   # user1=keep, user2=remove
```

- [ ] **Step 2: Run it (fails)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_feedback_upsert_and_tally -v`
Expected: FAIL (AttributeError: record_feedback).

- [ ] **Step 3: Implement feedback in `trading/quiz.py`**

Append:
```python
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
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_feedback_upsert_and_tally -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add trading/quiz.py trading/tests/test_quiz_bank.py
git commit -m "feat(quiz): feedback upsert + tally (one vote per user/question)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `POST /quiz/feedback` endpoint

**Files:**
- Modify: `trading/app.py`
- Test: `trading/tests/test_quiz_bank.py`

- [ ] **Step 1: Write the failing test**

Append to `trading/tests/test_quiz_bank.py`:
```python
def test_feedback_endpoint_requires_login_and_records(client):
    from trading import quiz
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 0)
    # not logged in -> 401
    assert client.post("/quiz/feedback", json={"question_id": qid, "vote": "remove"}).status_code == 401
    # log in (empty DB -> bootstrap admin), then feedback works
    client.post("/auth/login", json={"username": "icjj", "password": "pw"})
    r = client.post("/quiz/feedback", json={"question_id": qid, "vote": "remove", "reason": "太专业"})
    assert r.status_code == 200
    assert quiz.feedback_tally(qid) == {"remove": 1}
    # bad vote -> 400
    assert client.post("/quiz/feedback", json={"question_id": qid, "vote": "maybe"}).status_code == 400
```

- [ ] **Step 2: Run it (fails — 404)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_feedback_endpoint_requires_login_and_records -v`
Expected: FAIL (404 on /quiz/feedback).

- [ ] **Step 3: Implement in `trading/app.py`**

Add `quiz` to the local import line — change `from . import auth, ib_client, quiz_db` to `from . import auth, ib_client, quiz, quiz_db`. Then add (near the other endpoints):
```python
class FeedbackReq(BaseModel):
    question_id: int
    vote: str           # keep | remove
    reason: str = ""


@app.post("/quiz/feedback")
def quiz_feedback(req: FeedbackReq, user=Depends(current_user)):
    if req.vote not in ("keep", "remove"):
        raise HTTPException(400, "vote must be 'keep' or 'remove'")
    quiz.record_feedback(user["id"], req.question_id, req.vote, req.reason)
    return {"ok": True}
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_feedback_endpoint_requires_login_and_records -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add trading/app.py trading/tests/test_quiz_bank.py
git commit -m "feat(quiz): POST /quiz/feedback (keep/remove, login-required)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: MMLU seed script (lazy `datasets`, injectable loader)

**Files:**
- Create: `trading/seed_questions.py`
- Modify: `trading/requirements-quiz.txt` (add `datasets`)
- Test: `trading/tests/test_quiz_bank.py`

- [ ] **Step 1: Write the failing test (fake loader — no network, no datasets import)**

Append to `trading/tests/test_quiz_bank.py`:
```python
def test_seed_maps_mmlu_examples(quiz_db):
    from trading import seed_questions, quiz
    fake = [
        {"question": "Q1", "choices": ["a", "b", "c", "d"], "answer": 2},
        {"question": "Q2", "choices": ["w", "x", "y", "z"], "answer": 0},
        {"question": "bad", "choices": ["only", "three", "opts"], "answer": 0},  # skipped
    ]
    n = seed_questions.seed(loader=lambda subject: fake)
    # 2 valid per subject x len(SUBJECTS); bad one (3 choices) skipped
    assert n == 2 * len(seed_questions.SUBJECTS)
    assert quiz.count_active() == n
    q = quiz.get_question(1)
    assert len(q["options"]) == 4 and 0 <= q["correct_index"] < 4
    assert q["explanation"].startswith("正确答案")
```

- [ ] **Step 2: Run it (fails — no module)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_seed_maps_mmlu_examples -v`
Expected: FAIL (ModuleNotFoundError: trading.seed_questions).

- [ ] **Step 3: Implement `trading/seed_questions.py`**

```python
"""One-time seed: import MMLU professional/finance subsets (verified answers, MIT)
into the questions table.

Run for real:  PYTHONPATH=. ./.venv-trading/bin/python -m trading.seed_questions [--force]
(`datasets` is imported lazily so the test suite needs neither the dep nor network.)
"""
from __future__ import annotations

import sys

from . import quiz, quiz_db

SUBJECTS = [
    "professional_accounting",
    "high_school_macroeconomics",
    "high_school_microeconomics",
    "econometrics",
]


def _default_loader(subject: str):
    from datasets import load_dataset
    return load_dataset("cais/mmlu", subject, split="test")


def seed(force: bool = False, loader=None) -> int:
    """Import questions. Returns the number inserted. Idempotent unless force."""
    loader = loader or _default_loader
    quiz_db.init_db()
    if quiz.count_active() > 0 and not force:
        print(f"already seeded ({quiz.count_active()} active questions); use --force to re-seed.")
        return 0
    if force:
        con = quiz_db.connect()
        try:
            con.execute("DELETE FROM questions WHERE source='mmlu'")
            con.commit()
        finally:
            con.close()
    n = 0
    for subject in SUBJECTS:
        for ex in loader(subject):
            choices = ex.get("choices")
            answer = ex.get("answer")
            if not (isinstance(choices, list) and len(choices) == 4
                    and isinstance(answer, int) and 0 <= answer < 4):
                continue
            quiz.add_question(
                ex["question"], choices, answer,
                explanation=f"正确答案:{choices[answer]}",
                subject=subject, source="mmlu", status="active",
            )
            n += 1
    print(f"seeded {n} questions; active total = {quiz.count_active()}")
    return n


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
```

- [ ] **Step 4: Run the unit test (passes — uses fake loader)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_bank.py::test_seed_maps_mmlu_examples -v`
Expected: PASS.

- [ ] **Step 5: Add the `datasets` dep**

Append to `trading/requirements-quiz.txt`:
```
datasets
```
(Unpinned — let pip resolve a compatible version; this dep is only used by the real seed run, never by tests.)

- [ ] **Step 6: Commit (code + tests + dep)**

```bash
git add trading/seed_questions.py trading/requirements-quiz.txt trading/tests/test_quiz_bank.py
git commit -m "feat(quiz): MMLU seed script (lazy datasets, injectable loader)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 7: Run the FULL suite (all green, no network)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v`
Expected: ALL pass (Plan 1's 14 + this plan's 5 = 19).

---

### Task 6: Real seed run (integration — populates the live bank)

**Files:** none (operational step)

- [ ] **Step 1: Install `datasets` into the venv**

Run: `./.venv-trading/bin/pip install -r trading/requirements-quiz.txt`
Expected: `datasets` installed (pulls pyarrow/huggingface-hub/etc.). Retry once if the network blips.

- [ ] **Step 2: Run the real seed against the live DB**

Run: `PYTHONPATH=. ./.venv-trading/bin/python -m trading.seed_questions`
Expected: prints `seeded N questions; active total = N` where N is several hundred to ~1000. (This writes to `trading/quiz.db` — the live bank. It touches only `questions`, not `users`, so the admin-bootstrap state is unaffected.)

- [ ] **Step 3: Sanity-check the bank**

Run:
```bash
./.venv-trading/bin/python -c "from trading import quiz; print('active =', quiz.count_active()); q=quiz.get_question(1); print(q['subject'], '|', q['prompt'][:60], '|', len(q['options']), 'opts | ans', q['correct_index'])"
```
Expected: active > 0; a sample question with 4 options and a valid `correct_index`.

---

## Verification (whole plan)

- `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` → 19 green, no network.
- After the real seed: `quiz.count_active()` is in the hundreds; `/quiz/feedback` records keep/remove for a logged-in user (one vote per user/question, upsert).
- The `datasets` dep is only needed for the real seed run, not for tests.

## Notes for Plan 3

- Daily selection will read `status='active'` questions and pick deterministically by date; `get_question` already parses `options`.
- `feedback_tally(question_id)` is ready for Plan 4's pruning (`remove >= 3 and remove > keep`).
- `attempts` table + `/quiz/today`, `/quiz/state`, `/quiz/answer`, scoring, leaderboard are Plan 3.
