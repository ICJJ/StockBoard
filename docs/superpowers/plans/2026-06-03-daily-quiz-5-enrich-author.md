# Daily Quiz — Plan 5: Bank Enrichment + Claude-Authored Questions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the question pool: one-time import of MMLU-Pro (econ/business) + FinanceIQ (Chinese securities exams), and let the weekly Claude task author original grounded MCQs that go live directly (pruned by feedback).

**Architecture:** Two new loaders in `trading/seed_questions.py` (same lazy-`datasets` + injectable-loader pattern as the MMLU seeder). A `quiz.add_authored()` + `trading/add_authored.py` CLI lets the scheduled Claude session insert original MCQs (`source='claude'`, `status='active'`). The weekly scheduled task is updated to author ~5 grounded questions per run in addition to pruning.

**Tech Stack:** Python 3.9, SQLite, `datasets` (seed only, lazy), pytest. Reuses `quiz.add_question`/`count_active`.

**Spec:** §8 / §8.3 — **REVISES the earlier "Claude never authors" stance** per the user's 2026-06-03 decision: Claude MAY author original, fact-grounded MCQs (never copying copyrighted text); they go live directly and are pruned by the keep/remove feedback loop. The gate is soft (wrong → reveal + retry, never lock out), so a bad authored question is a quality blemish, not a lockout.

---

## File Structure

- `trading/seed_questions.py` — Modify: add `seed_mmlu_pro()` and `seed_financeiq()` (each: skip-if-already-seeded, lazy default loader, injectable loader for tests).
- `trading/quiz.py` — Modify: add `add_authored(questions)`.
- `trading/add_authored.py` — Create: CLI reading a JSON array from stdin → `quiz.add_authored`.
- `trading/tests/test_quiz_enrich.py` — Create: loader + add_authored + CLI tests (no network).
- `docs/superpowers/specs/2026-06-03-daily-quiz-design.md` — Modify: §8.3 reflects authoring + the two new sources.
- Scheduled task `stockboard-quiz-maintenance` — updated via the scheduled-tasks MCP (operational).

---

### Task 1: MMLU-Pro loader (econ + business)

**Files:** Modify `trading/seed_questions.py`; Test `trading/tests/test_quiz_enrich.py`

- [ ] **Step 1: Failing test** — create `trading/tests/test_quiz_enrich.py`:
```python
def test_seed_mmlu_pro_filters_categories(quiz_db):
    from trading import seed_questions, quiz
    fake = [
        {"question": "econ q", "options": ["a", "b", "c", "d"], "answer_index": 1, "category": "economics"},
        {"question": "biz q", "options": ["a", "b", "c", "d", "e"], "answer_index": 4, "category": "business"},
        {"question": "math q", "options": ["a", "b", "c", "d"], "answer_index": 0, "category": "math"},
    ]
    n = seed_questions.seed_mmlu_pro(loader=lambda: fake)
    assert n == 2                       # math filtered out
    assert quiz.count_active() == 2
    # variable-length options preserved
    q = quiz.get_question(2)
    assert len(q["options"]) == 5 and q["correct_index"] == 4
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Append to `trading/seed_questions.py`**:
```python
MMLU_PRO_CATEGORIES = ["economics", "business"]


def _mmlu_pro_default_loader():
    from datasets import load_dataset
    return load_dataset("TIGER-Lab/MMLU-Pro", split="test")


def seed_mmlu_pro(force: bool = False, loader=None) -> int:
    """Import MMLU-Pro (MIT) economics+business MCQs. Returns count inserted."""
    loader = loader or _mmlu_pro_default_loader
    quiz_db.init_db()
    con = quiz_db.connect()
    try:
        existing = con.execute("SELECT COUNT(*) AS c FROM questions WHERE source='mmlu_pro'").fetchone()["c"]
    finally:
        con.close()
    if existing and not force:
        print(f"mmlu_pro already seeded ({existing}); pass force=True to re-seed.")
        return 0
    if force:
        con = quiz_db.connect()
        try:
            con.execute("DELETE FROM questions WHERE source='mmlu_pro'"); con.commit()
        finally:
            con.close()
    n = 0
    for ex in loader():
        cat = ex.get("category")
        if cat not in MMLU_PRO_CATEGORIES:
            continue
        options = ex.get("options")
        ai = ex.get("answer_index")
        if not (isinstance(options, list) and len(options) >= 2
                and isinstance(ai, int) and 0 <= ai < len(options)):
            continue
        quiz.add_question(ex["question"], options, ai,
                          explanation=f"正确答案:{options[ai]}",
                          subject=f"mmlu_pro:{cat}", source="mmlu_pro")
        n += 1
    print(f"seeded {n} MMLU-Pro questions")
    return n
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/seed_questions.py trading/tests/test_quiz_enrich.py
git commit -m "feat(quiz): MMLU-Pro loader (econ+business, MIT)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: FinanceIQ loader (Chinese securities exams)

**Files:** Modify `trading/seed_questions.py`; Test `trading/tests/test_quiz_enrich.py`

The TEST feeds an already-normalized fake loader, so it has no network/schema dependency. The REAL schema mapping lives in `_financeiq_default_loader` and is verified at the Task 6 real-seed step (FinanceIQ's exact field names must be inspected against a live row there).

- [ ] **Step 1: Failing test** — append:
```python
def test_seed_financeiq_inserts_normalized(quiz_db):
    from trading import seed_questions, quiz
    fake = [
        {"question": "证券 q1", "options": ["甲", "乙", "丙", "丁"], "answer_index": 2, "subject": "证券从业"},
        {"question": "bad", "options": ["甲"], "answer_index": 0, "subject": "证券从业"},  # <2 options → skipped
    ]
    n = seed_questions.seed_financeiq(loader=lambda: fake)
    assert n == 1
    assert quiz.count_active() == 1
    q = quiz.get_question(1)
    assert q["subject"] == "证券从业" and q["options"] == ["甲", "乙", "丙", "丁"]
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Append to `trading/seed_questions.py`**:
```python
def _financeiq_default_loader():
    """Load Duxiaoman-DI/FinanceIQ across its subject configs, yielding NORMALIZED
    rows: {question, options(list), answer_index, subject}.

    NOTE TO IMPLEMENTER: FinanceIQ's raw field names must be confirmed against a
    live row at seed time. Inspect with:
        from datasets import get_dataset_config_names, load_dataset
        cfgs = get_dataset_config_names("Duxiaoman-DI/FinanceIQ")
        ex = load_dataset("Duxiaoman-DI/FinanceIQ", cfgs[0], split="test")[0]; print(ex)
    Then map its question / option columns / answer (letter or index) into the
    normalized dict below. The common shape is a `question` field, options under
    keys like A/B/C/D (or an `options` list), and an `answer` letter.
    """
    from datasets import get_dataset_config_names, load_dataset
    cfgs = get_dataset_config_names("Duxiaoman-DI/FinanceIQ")
    for cfg in cfgs:
        try:
            ds = load_dataset("Duxiaoman-DI/FinanceIQ", cfg, split="test")
        except Exception:
            continue
        for ex in ds:
            norm = _normalize_financeiq(ex, cfg)
            if norm:
                yield norm


def _normalize_financeiq(ex: dict, subject: str):
    """Best-effort map a FinanceIQ row to {question, options, answer_index, subject}.
    Handles both an `options` list and discrete A/B/C/D columns; answer as a
    letter (A-?) or an int index. Returns None if it can't be parsed."""
    q = ex.get("question") or ex.get("question_text") or ex.get("query")
    if not q:
        return None
    options = ex.get("options")
    if not isinstance(options, list):
        options = []
        for key in ("A", "B", "C", "D", "E", "F"):
            v = ex.get(key)
            if v not in (None, ""):
                options.append(v)
    ans = ex.get("answer")
    if isinstance(ans, str) and len(ans) >= 1 and ans[0].upper() in "ABCDEF":
        idx = "ABCDEF".index(ans[0].upper())
    elif isinstance(ans, int):
        idx = ans
    else:
        return None
    if not (len(options) >= 2 and 0 <= idx < len(options)):
        return None
    return {"question": q, "options": options, "answer_index": idx, "subject": subject}


def seed_financeiq(force: bool = False, loader=None) -> int:
    """Import FinanceIQ (Chinese securities/finance exam MCQs, cc-by-NC-sa; personal
    use only — stays in the gitignored quiz.db, never committed). Returns count."""
    loader = loader or _financeiq_default_loader
    quiz_db.init_db()
    con = quiz_db.connect()
    try:
        existing = con.execute("SELECT COUNT(*) AS c FROM questions WHERE source='financeiq'").fetchone()["c"]
    finally:
        con.close()
    if existing and not force:
        print(f"financeiq already seeded ({existing}); pass force=True to re-seed.")
        return 0
    if force:
        con = quiz_db.connect()
        try:
            con.execute("DELETE FROM questions WHERE source='financeiq'"); con.commit()
        finally:
            con.close()
    n = 0
    for ex in loader():
        options = ex.get("options")
        ai = ex.get("answer_index")
        if not (isinstance(options, list) and len(options) >= 2
                and isinstance(ai, int) and 0 <= ai < len(options)):
            continue
        quiz.add_question(ex["question"], options, ai,
                          explanation=f"正确答案:{options[ai]}",
                          subject=ex.get("subject", "financeiq"), source="financeiq")
        n += 1
    print(f"seeded {n} FinanceIQ questions")
    return n
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/seed_questions.py trading/tests/test_quiz_enrich.py
git commit -m "feat(quiz): FinanceIQ loader (Chinese securities MCQ; personal/local-only)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `quiz.add_authored()`

**Files:** Modify `trading/quiz.py`; Test `trading/tests/test_quiz_enrich.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_add_authored_validates(quiz_db):
    from trading import quiz
    items = [
        {"prompt": "good", "options": ["a", "b", "c", "d"], "correct_index": 2, "explanation": "x", "subject": "markets"},
        {"prompt": "", "options": ["a", "b"], "correct_index": 0},                 # empty prompt → skip
        {"prompt": "bad idx", "options": ["a", "b"], "correct_index": 5},          # idx out of range → skip
        {"prompt": "one opt", "options": ["a"], "correct_index": 0},               # <2 options → skip
    ]
    n = quiz.add_authored(items)
    assert n == 1
    assert quiz.count_active() == 1
    con = quiz.quiz_db.connect()
    src = con.execute("SELECT source FROM questions WHERE prompt='good'").fetchone()["source"]
    con.close()
    assert src == "claude"
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Append to `trading/quiz.py`**:
```python
def add_authored(questions: list) -> int:
    """Insert original Claude-authored MCQs (source='claude', active). Validates each;
    skips malformed. Returns the count inserted."""
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
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz.py trading/tests/test_quiz_enrich.py
git commit -m "feat(quiz): add_authored — insert validated Claude-authored questions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `trading/add_authored.py` CLI

**Files:** Create `trading/add_authored.py`; Test `trading/tests/test_quiz_enrich.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_add_authored_cli(quiz_db):
    import os, json, subprocess
    payload = json.dumps([
        {"prompt": "cli q", "options": ["a", "b", "c", "d"], "correct_index": 1, "subject": "markets"}
    ])
    env = {**os.environ, "PYTHONPATH": "."}   # QUIZ_DB is already in os.environ via the fixture
    r = subprocess.run(["./.venv-trading/bin/python", "-m", "trading.add_authored"],
                       input=payload, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "inserted 1" in r.stdout
    from trading import quiz
    assert quiz.count_active() == 1
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Create `trading/add_authored.py`**:
```python
"""Insert Claude-authored MCQs (source='claude', active). Reads a JSON array from stdin.

Each item: {"prompt": str, "options": [str, ...], "correct_index": int,
            "explanation"?: str, "subject"?: str}

Usage:  echo '[{...}]' | PYTHONPATH=. ./.venv-trading/bin/python -m trading.add_authored
"""
import json
import sys

from . import quiz


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, list):
        print("error: expected a JSON array of question objects", file=sys.stderr)
        sys.exit(1)
    n = quiz.add_authored(data)
    print(f"inserted {n} authored question(s)")


if __name__ == "__main__":
    main()
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Full suite** — `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` (all prior + these 4 green)
- [ ] **Step 6: Commit**
```bash
git add trading/add_authored.py trading/tests/test_quiz_enrich.py
git commit -m "feat(quiz): add_authored CLI (JSON stdin → inserted authored questions)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Update the spec (§8.3)

**Files:** Modify `docs/superpowers/specs/2026-06-03-daily-quiz-design.md`

- [ ] **Step 1:** In §8.3, replace the "Claude only selects/prunes; does NOT author" wording with the revised policy:
> **Scheduled Claude task (weekly):** ① prune feedback-flagged questions (`remove>=3 and remove>keep`); ② **author ~5 ORIGINAL, fact-grounded capital-markets MCQs** — based on verifiable public/factual finance knowledge (SEC/FINRA/Fed investor-education concepts), **never copying any copyrighted question bank or passage**, each self-checked for a single unambiguous correct answer — inserted via `trading/add_authored.py` as `source='claude'`, `status='active'` (go live directly; the keep/remove feedback + weekly prune remove any that are wrong; the gate is soft so a bad question never locks anyone out). Seed sources expanded: MMLU + MMLU-Pro (econ/business, MIT) + FinanceIQ (Chinese securities, cc-by-NC-sa, personal/local-only).

Also update §4 `source` enum note to include `mmlu_pro`, `financeiq`, `claude`.

- [ ] **Step 2: Commit**
```bash
git add docs/superpowers/specs/2026-06-03-daily-quiz-design.md
git commit -m "spec: Claude may author grounded MCQs (direct-active); add MMLU-Pro + FinanceIQ sources

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Operational — run seeds + update the weekly task (not code)

**Files:** none (run against the live bank + scheduled-tasks MCP)

- [ ] **Step 1: Real MMLU-Pro seed** — `PYTHONPATH=. ./.venv-trading/bin/python -c "from trading import seed_questions as s; s.seed_mmlu_pro()"` → prints a few hundred imported.
- [ ] **Step 2: Inspect + real FinanceIQ seed** — first confirm the schema:
  `PYTHONPATH=. ./.venv-trading/bin/python -c "from datasets import get_dataset_config_names,load_dataset as L; c=get_dataset_config_names('Duxiaoman-DI/FinanceIQ'); print(c[:3]); print(L('Duxiaoman-DI/FinanceIQ',c[0],split='test')[0])"`
  If the field names differ from `_normalize_financeiq`'s assumptions, fix that function, re-run its unit test, then seed: `PYTHONPATH=. ./.venv-trading/bin/python -c "from trading import seed_questions as s; print(s.seed_financeiq())"`. If FinanceIQ proves un-mappable, report it (don't insert garbage) — the bank still has MMLU + MMLU-Pro.
- [ ] **Step 3: Confirm bank grew** — `./.venv-trading/bin/python -c "from trading import quiz; print('active =', quiz.count_active())"` (should be > 1024).
- [ ] **Step 4: Update the weekly scheduled task** (via scheduled-tasks MCP `update_scheduled_task`, taskId `stockboard-quiz-maintenance`) so the prompt becomes: run the prune (`python -m trading.maintain_bank`), THEN author ~5 original capital-markets MCQs grounded in verifiable public finance facts (no copying copyrighted text), format them as a JSON array `[{"prompt","options","correct_index","explanation","subject"}]`, self-check each answer, and insert via `PYTHONPATH=. ./.venv-trading/bin/python -m trading.add_authored`. Report pruned count + authored count + active total.

---

## Verification (whole plan)

- `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` → all green (no network).
- After seeds: `quiz.count_active()` > 1024 (MMLU + MMLU-Pro [+ FinanceIQ if mappable]).
- `echo '[{"prompt":"t","options":["a","b","c","d"],"correct_index":0}]' | python -m trading.add_authored` → "inserted 1".
- The weekly task now prunes AND authors; authored questions are `source='claude'`, active, and subject to feedback pruning.

## Feature note

Copyright: Claude authors ORIGINAL questions testing facts (facts aren't copyrightable); it must never copy a copyrighted question/passage. This is distinct from ingesting a copyrighted bank (which we refused).
