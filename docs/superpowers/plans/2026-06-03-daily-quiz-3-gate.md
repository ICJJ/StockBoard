# Daily Quiz — Plan 3: Daily Gate, Scoring & Leaderboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate the board behind a daily question — one question/day for everyone, must answer correctly to enter; wrong reveals the answer + allows retry; first-try-correct scores; show streak/accuracy and a leaderboard.

**Architecture:** Add an `attempts` table. `trading/quiz.py` gains deterministic daily selection (sha256(ET date) % active count), the answer/scoring flow (first attempt sets `first_try_correct`; any correct sets `entered`), and streak/leaderboard math. New `/quiz/today|state|answer|leaderboard` endpoints reuse Plan 1's `current_user`. Frontend: an `/quiz` gate page (with Plan 2's keep/remove feedback), a `/leaderboard` page, and the board (`/`) redirects to `/quiz` until `entered_today` (fail-open).

**Tech Stack:** Python 3.9 (stdlib `hashlib`, `zoneinfo`), FastAPI, SQLite, pytest; Next.js client pages. Reuses `quiz.get_question/count_active`, `auth.current_user`.

**Spec:** `docs/superpowers/specs/2026-06-03-daily-quiz-design.md` §6 (flow), §7 (scoring/leaderboard). NOT in this plan: scheduled maintenance (Plan 4). **Auth guarantee preserved** — middleware is untouched, so `/quiz` and `/leaderboard` are auto-gated (already verified returning 307 without a cookie).

---

## File Structure

- `trading/quiz_db.py` — Modify: append `attempts` table to `SCHEMA`.
- `trading/quiz.py` — Modify: add `today_et`, `daily_question`, `day_state`, `record_attempt`, `_streak`, `user_stats`, `leaderboard`.
- `trading/app.py` — Modify: add `/quiz/today`, `/quiz/state`, `/quiz/answer`, `/quiz/leaderboard`.
- `lib/quizApi.js` — Modify: add `today`, `state`, `answer`, `leaderboard`.
- `app/quiz/page.js` — Create: the daily gate.
- `app/leaderboard/page.js` — Create: leaderboard view.
- `app/page.js` — Modify: redirect to `/quiz` until `entered_today` (fail-open).
- `trading/tests/test_quiz_gate.py` — Create: backend tests.

---

### Task 1: `attempts` table

**Files:** Modify `trading/quiz_db.py`; Test `trading/tests/test_quiz_gate.py`

- [ ] **Step 1: Failing test** — create `trading/tests/test_quiz_gate.py`:
```python
def test_schema_has_attempts(quiz_db):
    import sqlite3
    cols = {r[1] for r in sqlite3.connect(quiz_db).execute("PRAGMA table_info(attempts)")}
    assert {"id", "user_id", "question_id", "quiz_date", "first_try_correct",
            "entered", "attempts_count", "created_at"} <= cols
```
- [ ] **Step 2: Run → FAIL** — `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_gate.py::test_schema_has_attempts -v`
- [ ] **Step 3: Append to `SCHEMA` in `trading/quiz_db.py`** (inside the triple-quoted string):
```sql

CREATE TABLE IF NOT EXISTS attempts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    question_id    INTEGER NOT NULL,
    quiz_date      TEXT NOT NULL,
    first_try_correct INTEGER NOT NULL DEFAULT 0,
    entered        INTEGER NOT NULL DEFAULT 0,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, quiz_date)
);
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz_db.py trading/tests/test_quiz_gate.py
git commit -m "feat(quiz): attempts table

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Deterministic daily selection

**Files:** Modify `trading/quiz.py`; Test `trading/tests/test_quiz_gate.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_daily_question_deterministic(quiz_db):
    from trading import quiz
    ids = [quiz.add_question(f"q{i}", ["a", "b", "c", "d"], 0) for i in range(5)]
    a = quiz.daily_question(quiz_date="2026-06-03")
    b = quiz.daily_question(quiz_date="2026-06-03")
    assert a["id"] == b["id"]              # stable for a given date
    assert a["id"] in ids                  # from the active pool
    assert "correct_index" in a            # internal helper returns full question
    # empty pool → None (endpoint will fail-open)
    import sqlite3, os
    con = quiz.quiz_db.connect(); con.execute("UPDATE questions SET status='retired'"); con.commit(); con.close()
    assert quiz.daily_question(quiz_date="2026-06-03") is None
```
- [ ] **Step 2: Run → FAIL** (`AttributeError: daily_question`)
- [ ] **Step 3: Append to `trading/quiz.py`**:
```python
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo


def today_et() -> str:
    """Current quiz date (YYYY-MM-DD) in America/New_York — matches the board's market clock."""
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def daily_question(quiz_date: str | None = None):
    """Same active question for everyone on a given ET date. None if the pool is empty."""
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
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz.py trading/tests/test_quiz_gate.py
git commit -m "feat(quiz): deterministic daily question selection (ET date)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Answer flow + day state

**Files:** Modify `trading/quiz.py`; Test `trading/tests/test_quiz_gate.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_answer_flow_first_try_and_retry(quiz_db):
    from trading import quiz
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 2)  # correct = index 2
    # wrong first → not scored, not entered, reveals answer
    r1 = quiz.record_attempt(user_id=1, question_id=qid, choice_index=0, quiz_date="2026-06-03")
    assert r1["correct"] is False and r1["scored"] is False and r1["entered"] is False
    assert r1["correct_index"] == 2 and r1["explanation"] is not None
    assert quiz.day_state(1, "2026-06-03") == {"answered_today": True, "entered_today": False}
    # retry correct → entered True but scored False (first try was wrong)
    r2 = quiz.record_attempt(user_id=1, question_id=qid, choice_index=2, quiz_date="2026-06-03")
    assert r2["correct"] is True and r2["scored"] is False and r2["entered"] is True
    assert quiz.day_state(1, "2026-06-03")["entered_today"] is True

def test_answer_first_try_correct_scores(quiz_db):
    from trading import quiz
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 1)
    r = quiz.record_attempt(user_id=9, question_id=qid, choice_index=1, quiz_date="2026-06-04")
    assert r["correct"] and r["scored"] and r["entered"]
    assert r["correct_index"] is None and r["explanation"] is None  # no reveal when correct
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Append to `trading/quiz.py`**:
```python
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
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz.py trading/tests/test_quiz_gate.py
git commit -m "feat(quiz): answer flow — first-try scoring, retry, reveal-on-wrong, day state

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Streak, user stats, leaderboard

**Files:** Modify `trading/quiz.py`; Test `trading/tests/test_quiz_gate.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_streak_and_stats(quiz_db):
    from trading import quiz
    from datetime import date
    # consecutive days ending "today"
    assert quiz._streak(["2026-06-03", "2026-06-02", "2026-06-01"], today=date(2026, 6, 3)) == 3
    # gap breaks it
    assert quiz._streak(["2026-06-03", "2026-06-01"], today=date(2026, 6, 3)) == 1
    # not played today but played yesterday → streak counts from yesterday
    assert quiz._streak(["2026-06-02", "2026-06-01"], today=date(2026, 6, 3)) == 2
    # stale (last entered 2 days ago) → 0
    assert quiz._streak(["2026-06-01"], today=date(2026, 6, 3)) == 0
    assert quiz._streak([], today=date(2026, 6, 3)) == 0

def test_user_stats_and_leaderboard(quiz_db):
    from trading import quiz, auth
    auth.create_user("alice", "pw"); auth.create_user("bob", "pw")
    aid = auth.get_user("alice")["id"]; bid = auth.get_user("bob")["id"]
    qid = quiz.add_question("q", ["a", "b", "c", "d"], 0)
    quiz.record_attempt(aid, qid, 0, quiz_date="2026-06-03")  # alice first-try correct
    quiz.record_attempt(bid, qid, 1, quiz_date="2026-06-03")  # bob wrong
    quiz.record_attempt(bid, qid, 0, quiz_date="2026-06-03")  # bob retry correct (entered, not scored)
    sa = quiz.user_stats(aid); sb = quiz.user_stats(bid)
    assert sa["points"] == 1 and sb["points"] == 0
    assert sa["days_played"] == 1 and sb["days_played"] == 1
    lb = quiz.leaderboard()
    assert lb[0]["username"] == "alice" and lb[0]["points"] == 1  # alice ranks first
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Append to `trading/quiz.py`**:
```python
from datetime import date, timedelta


def _streak(entered_dates, today=None) -> int:
    """Consecutive-day streak from `today` (or yesterday if not played today)."""
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
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz.py trading/tests/test_quiz_gate.py
git commit -m "feat(quiz): streak, per-user stats, leaderboard

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Endpoints — today / state / answer / leaderboard

**Files:** Modify `trading/app.py`; Test `trading/tests/test_quiz_gate.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_quiz_endpoints(client):
    from trading import quiz
    qid = quiz.add_question("2+2?", ["3", "4", "5", "6"], 1, explanation="正确答案:4")
    # gated
    assert client.get("/quiz/today").status_code == 401
    client.post("/auth/login", json={"username": "icjj", "password": "pw"})  # bootstrap admin
    t = client.get("/quiz/today").json()
    assert t["id"] == qid and t["options"] == ["3", "4", "5", "6"]
    assert "correct_index" not in t                      # never leak the answer
    assert client.get("/quiz/state").status_code == 200
    # wrong answer reveals
    w = client.post("/quiz/answer", json={"question_id": qid, "choice_index": 0}).json()
    assert w["correct"] is False and w["correct_index"] == 1 and w["explanation"]
    # correct answer enters
    c = client.post("/quiz/answer", json={"question_id": qid, "choice_index": 1}).json()
    assert c["correct"] is True and c["entered"] is True
    assert client.get("/quiz/state").json()["entered_today"] is True
    lb = client.get("/quiz/leaderboard").json()["leaderboard"]
    assert any(u["username"] == "icjj" for u in lb)

def test_quiz_today_fail_open_when_empty(client):
    client.post("/auth/login", json={"username": "icjj", "password": "pw"})
    r = client.get("/quiz/today").json()       # no questions seeded in this test DB
    assert r["available"] is False             # frontend treats this as "let in"
```
- [ ] **Step 2: Run → FAIL** (404s)
- [ ] **Step 4: Implement in `trading/app.py`** (add near the other `/quiz` endpoint; `quiz` is already imported):
```python
class AnswerReq(BaseModel):
    question_id: int
    choice_index: int


@app.get("/quiz/today")
def quiz_today(user=Depends(current_user)):
    q = quiz.daily_question()
    if not q:
        return {"available": False}              # fail-open: frontend lets the user in
    return {"available": True, "id": q["id"], "prompt": q["prompt"], "options": q["options"]}


@app.get("/quiz/state")
def quiz_state(user=Depends(current_user)):
    return quiz.day_state(user["id"])


@app.post("/quiz/answer")
def quiz_answer(req: AnswerReq, user=Depends(current_user)):
    try:
        return quiz.record_attempt(user["id"], req.question_id, req.choice_index)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/quiz/leaderboard")
def quiz_leaderboard(user=Depends(current_user)):
    return {"leaderboard": quiz.leaderboard()}
```
- [ ] **Step 5: Run → PASS**
- [ ] **Step 6: Full suite** — `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` (Plan1 14 + Plan2 5 + Plan3 = all green)
- [ ] **Step 7: Commit**
```bash
git add trading/app.py trading/tests/test_quiz_gate.py
git commit -m "feat(quiz): /quiz today/state/answer/leaderboard endpoints

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Frontend — gate page, leaderboard, board redirect

**Files:** Modify `lib/quizApi.js`; Create `app/quiz/page.js`, `app/leaderboard/page.js`; Modify `app/page.js`. Verify with `npm run build`.

- [ ] **Step 1: Add client methods to `lib/quizApi.js`** (inside the `quizApi` object):
```javascript
  today: () => j("/quiz/today"),
  state: () => j("/quiz/state"),
  answer: (question_id, choice_index) =>
    j("/quiz/answer", { method: "POST", body: JSON.stringify({ question_id, choice_index }) }),
  leaderboard: () => j("/quiz/leaderboard"),
  feedback: (question_id, vote) =>
    j("/quiz/feedback", { method: "POST", body: JSON.stringify({ question_id, vote }) }),
```

- [ ] **Step 2: Create `app/quiz/page.js`** (the gate):
```javascript
"use client";
import { useEffect, useState } from "react";
import { quizApi } from "../../lib/quizApi";

export default function Quiz() {
  const [q, setQ] = useState(null);
  const [picked, setPicked] = useState(null);
  const [result, setResult] = useState(null);   // {correct, correct_index, explanation}
  const [msg, setMsg] = useState("加载中…");

  useEffect(() => {
    quizApi.state()
      .then((s) => { if (s.entered_today) { window.location.href = "/"; return null; } return quizApi.today(); })
      .then((t) => {
        if (!t) return;
        if (!t.available) { window.location.href = "/"; return; }   // fail-open
        setQ(t); setMsg(null);
      })
      .catch(() => { window.location.href = "/"; });                // fail-open
  }, []);

  async function submit() {
    if (picked == null) return;
    const r = await quizApi.answer(q.id, picked);
    setResult(r);
    if (r.correct) setTimeout(() => (window.location.href = "/"), 800);
  }

  async function feedback(vote) {
    try {
      await quizApi.feedback(q.id, vote);
      setMsg(vote === "remove" ? "已反馈:太专业(将参与剔除)" : "已反馈:保留");
    } catch {}
  }

  if (msg && !q) return <div className="container"><p style={{ padding: 40 }}>{msg}</p></div>;
  if (!q) return null;

  return (
    <div className="container" style={{ maxWidth: 640 }}>
      <h1 style={{ margin: "30px 0 6px" }}>每日一题</h1>
      <p style={{ color: "var(--text-dim)", marginBottom: 18 }}>答对才能进入看板;答错会显示答案,可重试。</p>
      <div className="bt-panel">
        <div style={{ fontSize: 16, marginBottom: 16 }}>{q.prompt}</div>
        {q.options.map((opt, i) => {
          const isAnswer = result && !result.correct && result.correct_index === i;
          const isPicked = picked === i;
          return (
            <button key={i}
              onClick={() => !result?.correct && setPicked(i)}
              className="quiz-opt"
              style={{
                borderColor: isAnswer ? "var(--green)" : isPicked ? "var(--accent)" : "var(--border)",
                color: isAnswer ? "var(--green)" : "var(--text)",
              }}>
              {String.fromCharCode(65 + i)}. {opt}
            </button>
          );
        })}
        {!result?.correct && (
          <button className="bt-run" style={{ marginTop: 12 }} onClick={submit} disabled={picked == null}>
            提交
          </button>
        )}
        {result && !result.correct && (
          <div className="notice error" style={{ marginTop: 12 }}>
            答错了。正确答案:{String.fromCharCode(65 + result.correct_index)}。{result.explanation}
            <div style={{ marginTop: 8 }}>再选一次并提交即可进入。</div>
          </div>
        )}
        {result?.correct && (
          <div className="order-msg ok" style={{ marginTop: 12 }}>
            {result.scored ? "答对!首答得分 ✅ 正在进入…" : "答对!正在进入…"}
          </div>
        )}
        <div className="refresh-row" style={{ marginTop: 14 }}>
          <span style={{ color: "var(--text-faint)", fontSize: 12 }}>这题:</span>
          <button className="refresh-btn" onClick={() => feedback("keep")}>保留</button>
          <button className="refresh-btn" onClick={() => feedback("remove")}>太专业，剔除</button>
          {msg && q && <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{msg}</span>}
        </div>
      </div>
      <p className="footer"><a href="/leaderboard">查看排行榜 →</a></p>
    </div>
  );
}
```

- [ ] **Step 3: Add styles to `app/globals.css`** (append):
```css
.quiz-opt {
  display: block; width: 100%; text-align: left; margin-top: 8px;
  padding: 11px 14px; border-radius: 10px; border: 1px solid var(--border);
  background: var(--bg); color: var(--text); font-size: 14px; cursor: pointer;
}
.quiz-opt:hover { border-color: var(--accent); }
```

- [ ] **Step 4: Create `app/leaderboard/page.js`**:
```javascript
"use client";
import { useEffect, useState } from "react";
import { quizApi } from "../../lib/quizApi";

export default function Leaderboard() {
  const [rows, setRows] = useState([]); const [err, setErr] = useState(null);
  useEffect(() => { quizApi.leaderboard().then((d) => setRows(d.leaderboard)).catch((e) => setErr(e.message)); }, []);
  return (
    <div className="container" style={{ maxWidth: 560 }}>
      <h1 style={{ margin: "30px 0 16px" }}>排行榜</h1>
      {err && <div className="notice error">{err}</div>}
      <table className="ptable">
        <thead><tr><th>#</th><th>账号</th><th>积分</th><th>连续</th><th>正确率</th></tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={r.username}>
            <td>{i + 1}</td><td className="psym">{r.username}</td>
            <td><b>{r.points}</b></td><td>{r.streak}</td>
            <td>{Math.round((r.accuracy || 0) * 100)}%</td>
          </tr>))}</tbody>
      </table>
      <p className="footer"><a href="/">← 返回看板</a></p>
    </div>
  );
}
```

- [ ] **Step 5: Gate the board in `app/page.js`** — READ the file first. It's a client component `export default function Page()` (the watchlist). Add a gate that redirects to `/quiz` until the user has entered today, failing open on error:
  1. Add import at top (with other imports): `import { quizApi } from "../lib/quizApi";`
  2. Inside the component, alongside the other `useState` hooks, add: `const [gate, setGate] = useState("checking");`
  3. Alongside the other `useEffect` hooks, add:
```javascript
  useEffect(() => {
    quizApi.state()
      .then((s) => { if (s.entered_today) setGate("ok"); else { setGate("redirect"); window.location.href = "/quiz"; } })
      .catch(() => setGate("ok"));   // fail-open: if backend/quiz unavailable, show the board
  }, []);
```
  4. Immediately before the component's main `return (` (after all hooks — React requires hooks run unconditionally), add an early return:
```javascript
  if (gate !== "ok") {
    return <div className="container"><p style={{ padding: 48, textAlign: "center", color: "var(--text-dim)" }}>每日一题校验中…</p></div>;
  }
```

- [ ] **Step 6: Build** — `npm run build`. MUST compile; route list should include `/quiz` and `/leaderboard`. Paste the route table. (Build runs in the live checkout; the new pages are auto-gated by the existing middleware. No middleware change.)

- [ ] **Step 7: Commit**
```bash
git add lib/quizApi.js app/quiz/page.js app/leaderboard/page.js app/page.js app/globals.css
git commit -m "feat(quiz): daily gate page, leaderboard, board redirect-until-entered

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Verification (whole plan)

- `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` → all green (Plan1+2+3).
- `npm run build` clean; `/quiz` + `/leaderboard` in the route table.
- Manual (after merge + restart, logged in): visiting `/` redirects to `/quiz`; wrong answer reveals the correct option + explanation and lets you retry; first-try-correct shows "首答得分" and lands on the board; revisiting `/` goes straight to the board (entered today); `/leaderboard` lists accounts by points. Auth guarantee intact (every route still 307→/login without a cookie).

## Notes for Plan 4 (scheduled maintenance)

- `quiz.feedback_tally(question_id)` (Plan 2) + a new retire helper drive pruning (`remove >= 3 and remove > keep` → `status='retired'`).
- Top-up re-runs `seed_questions.seed(force=False)` logic / selects more active questions.
- Scheduled via the scheduled-tasks MCP (SKILL.md), weekly.
