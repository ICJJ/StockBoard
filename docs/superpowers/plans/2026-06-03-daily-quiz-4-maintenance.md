# Daily Quiz — Plan 4: Scheduled Bank Maintenance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Self-curating bank — retire questions the community flagged as "too professional," run weekly. Claude only selects/prunes from the already-verified pool; it never authors questions or answers.

**Architecture:** `quiz.prune_flagged()` retires active questions whose feedback is `remove >= 3 AND remove > keep` (reusing `feedback_tally`). `trading/maintain_bank.py` runs the prune and reports; top-up is a deliberate no-op/warning (the bank was fully imported from the MMLU subsets, so there is nothing more to select from the same verified source — if the pool ever falls below 60 it just advises a re-seed). A **weekly scheduled Claude task** (registered via the scheduled-tasks MCP, operationally) runs the maintenance script.

**Tech Stack:** Python 3.9, SQLite, pytest. Reuses Plan 2 `feedback_tally`/`count_active`.

**Spec:** §8.3. This is the final plan; after it the daily-quiz feature is complete.

---

## File Structure

- `trading/quiz.py` — Modify: add `prune_flagged(min_remove=3)`.
- `trading/maintain_bank.py` — Create: runnable maintenance entry point (prune + report + low-pool warning).
- `trading/tests/test_quiz_maintenance.py` — Create: prune + report tests.
- Scheduled task — registered via the scheduled-tasks MCP at execution time (not a repo file).

---

### Task 1: `prune_flagged()`

**Files:** Modify `trading/quiz.py`; Test `trading/tests/test_quiz_maintenance.py`

- [ ] **Step 1: Write the failing test** — create `trading/tests/test_quiz_maintenance.py`:
```python
def test_prune_flagged_retires_only_clear_removes(quiz_db):
    from trading import quiz
    q_remove = quiz.add_question("retire me", ["a", "b", "c", "d"], 0)   # 3 remove, 0 keep -> retire
    q_split = quiz.add_question("contested", ["a", "b", "c", "d"], 0)    # 3 remove, 3 keep -> stay
    q_few = quiz.add_question("barely", ["a", "b", "c", "d"], 0)         # 2 remove -> stay
    for u in (1, 2, 3):
        quiz.record_feedback(u, q_remove, "remove")
    for u in (1, 2, 3):
        quiz.record_feedback(u, q_split, "remove")
    for u in (4, 5, 6):
        quiz.record_feedback(u, q_split, "keep")
    for u in (1, 2):
        quiz.record_feedback(u, q_few, "remove")
    assert quiz.count_active() == 3
    retired = quiz.prune_flagged()
    assert retired == [q_remove]                 # only the clear-remove one
    assert quiz.count_active() == 2
    # a retired question is no longer eligible for the daily pick
    assert quiz.get_question(q_remove)["status"] == "retired"
```
- [ ] **Step 2: Run → FAIL** — `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_maintenance.py::test_prune_flagged_retires_only_clear_removes -v`
- [ ] **Step 3: Append to `trading/quiz.py`**:
```python
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
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz.py trading/tests/test_quiz_maintenance.py
git commit -m "feat(quiz): prune_flagged — retire questions with remove>=3 and remove>keep

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `maintain_bank.py` runner

**Files:** Create `trading/maintain_bank.py`; Test `trading/tests/test_quiz_maintenance.py`

- [ ] **Step 1: Write the failing test** — append:
```python
def test_maintain_reports(quiz_db):
    from trading import quiz, maintain_bank
    keep_q = quiz.add_question("keep", ["a", "b", "c", "d"], 0)
    drop_q = quiz.add_question("drop", ["a", "b", "c", "d"], 0)
    for u in (1, 2, 3):
        quiz.record_feedback(u, drop_q, "remove")
    report = maintain_bank.maintain()
    assert report["retired"] == 1
    assert report["active_remaining"] == 1
    assert drop_q in report["retired_ids"]
    assert keep_q not in report["retired_ids"]
```
- [ ] **Step 2: Run → FAIL** (ModuleNotFoundError: trading.maintain_bank)
- [ ] **Step 3: Create `trading/maintain_bank.py`**:
```python
"""Weekly quiz-bank maintenance.

Claude SELECTS / PRUNES from the already-verified pool only — it never authors
questions or answers. Pruning retires questions the community flagged
(remove >= 3 and remove > keep). Top-up is intentionally a no-op: the bank was
fully imported from the MMLU subsets, so there is nothing more to select from
the same verified source; if the active pool ever drops below MIN_ACTIVE we just
advise a manual re-seed.

Run:  PYTHONPATH=. ./.venv-trading/bin/python -m trading.maintain_bank
"""
from . import quiz, quiz_db

MIN_ACTIVE = 60


def maintain() -> dict:
    quiz_db.init_db()
    retired = quiz.prune_flagged()
    active = quiz.count_active()
    print(f"pruned {len(retired)} flagged question(s); active remaining = {active}")
    if active < MIN_ACTIVE:
        print(f"WARNING: active pool below {MIN_ACTIVE} — re-seed verified questions with: "
              f"PYTHONPATH=. ./.venv-trading/bin/python -m trading.seed_questions --force")
    return {"retired": len(retired), "retired_ids": retired, "active_remaining": active}


if __name__ == "__main__":
    maintain()
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Full suite** — `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` (Plan1+2+3 + these 2 = all green)
- [ ] **Step 6: Commit**
```bash
git add trading/maintain_bank.py trading/tests/test_quiz_maintenance.py
git commit -m "feat(quiz): maintain_bank runner (prune + low-pool warning; no authoring)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Register the weekly scheduled Claude task (operational — not code)

**Files:** none (created via the scheduled-tasks MCP at execution time)

- [ ] **Step 1: Register a weekly task** via the scheduled-tasks MCP with:
  - taskId: `stockboard-quiz-maintenance`
  - cron: `0 9 * * 1` (every Monday 09:00 local)
  - prompt: "StockBoard quiz-bank weekly maintenance. In /Users/maymay/StockBoard run: `PYTHONPATH=. ./.venv-trading/bin/python -m trading.maintain_bank`. It retires questions the community flagged as too professional (remove>=3 and remove>keep) and warns if the active pool drops below 60. Report how many were retired and the active remaining. Do NOT author or invent questions — only run the script."

- [ ] **Step 2: Verify it registered** — list scheduled tasks and confirm `stockboard-quiz-maintenance` appears with the Monday-09:00 schedule.

- [ ] **Step 3: Dry-run the maintenance once now** to confirm the script runs end-to-end against the live bank:
```bash
cd /Users/maymay/StockBoard && PYTHONPATH=. ./.venv-trading/bin/python -m trading.maintain_bank
```
Expected: `pruned 0 flagged question(s); active remaining = 1024` (nothing flagged yet) — no warning (1024 ≥ 60).

---

## Verification (whole plan)

- `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` → all green.
- `python -m trading.maintain_bank` prints the prune report; with no feedback yet it retires 0 and leaves 1024 active.
- The scheduled task `stockboard-quiz-maintenance` is registered (Mondays 09:00). Note: scheduled tasks run while Claude Code is open; if it was closed at fire time it runs on next launch.

## Feature complete

After this plan the daily-quiz feature is end-to-end: account login (Plan 1) → daily gate with first-try scoring, retry, leaderboard (Plan 3) over an MMLU-verified bank (Plan 2) that self-curates from user feedback on a weekly schedule (Plan 4).
