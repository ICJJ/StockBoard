# Daily Quiz — Plan 6: Bilingual (default-Chinese) Quiz + Localized Labels — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show English quiz questions in Chinese by default with a 双语 toggle to the English original (translated on demand via a cached free API), and localize the board's English stat labels to Chinese.

**Architecture:** A `translations` cache table + `quiz.translate_to_zh()` (cache → free Google `gtx` endpoint → store; CJK text passes through; any error falls back to the original). `quiz.localize_question()` attaches `prompt_zh`/`options_zh`/`explanation_zh` + `is_english`. `/quiz/today` and the `/quiz/answer` reveal return the Chinese fields (never `correct_index`). The quiz page defaults to Chinese with a toggle. `StockCard` labels are localized. The translation provider is injectable so tests never hit the network.

**Tech Stack:** Python 3.9 (stdlib `urllib`), FastAPI, SQLite, pytest. React (Next.js). Volume is tiny (~1 daily question + its options/day, cached), so the no-key endpoint is fine; `_default_translate_provider` is swappable for DeepL+key later.

**Spec:** §6 (the gate). Keeps the auth guarantee (middleware untouched).

---

## File Structure

- `trading/quiz_db.py` — Modify: add `translations` table to `SCHEMA`.
- `trading/quiz.py` — Modify: add `_has_cjk`, `_is_english`, `_default_translate_provider`, `translate_to_zh`, `localize_question`.
- `trading/app.py` — Modify: `/quiz/today` returns localized fields; `/quiz/answer` reveal adds `explanation_zh`.
- `app/quiz/page.js` — Modify: default Chinese + 双语 toggle.
- `components/StockCard.js` — Modify: Open/Prev/L/H → 开盘/昨收/最低/最高.
- `trading/tests/test_quiz_i18n.py` — Create: translation + localize + endpoint tests (fake provider).

---

### Task 1: `translations` cache table

**Files:** Modify `trading/quiz_db.py`; Test `trading/tests/test_quiz_i18n.py`

- [ ] **Step 1: Failing test** — create `trading/tests/test_quiz_i18n.py`:
```python
def test_schema_has_translations(quiz_db):
    import sqlite3
    cols = {r[1] for r in sqlite3.connect(quiz_db).execute("PRAGMA table_info(translations)")}
    assert {"en", "zh"} <= cols
```
- [ ] **Step 2: Run → FAIL** — `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_quiz_i18n.py::test_schema_has_translations -v`
- [ ] **Step 3: Append to `SCHEMA` in `trading/quiz_db.py`**:
```sql

CREATE TABLE IF NOT EXISTS translations (
    en TEXT PRIMARY KEY,
    zh TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz_db.py trading/tests/test_quiz_i18n.py
git commit -m "feat(quiz): translations cache table

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `translate_to_zh()` (cache + provider + passthrough + fallback)

**Files:** Modify `trading/quiz.py`; Test `trading/tests/test_quiz_i18n.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_translate_caches_and_passthrough_and_fallback(quiz_db):
    from trading import quiz
    calls = []
    def fake(t): calls.append(t); return "中:" + t
    assert quiz.translate_to_zh("hello world", provider=fake) == "中:hello world"
    assert quiz.translate_to_zh("hello world", provider=fake) == "中:hello world"
    assert calls == ["hello world"]                 # cached the 2nd time
    def boom(t): raise AssertionError("must not call on CJK")
    assert quiz.translate_to_zh("你好世界", provider=boom) == "你好世界"   # CJK passthrough
    def err(t): raise RuntimeError("api down")
    assert quiz.translate_to_zh("graceful fallback", provider=err) == "graceful fallback"
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Append to `trading/quiz.py`**:
```python
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
    """Return Chinese for English `text`. Cached in the translations table.
    CJK text passes through; any provider error falls back to the original."""
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
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz.py trading/tests/test_quiz_i18n.py
git commit -m "feat(quiz): translate_to_zh (cached, CJK-passthrough, graceful fallback)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `localize_question()`

**Files:** Modify `trading/quiz.py`; Test `trading/tests/test_quiz_i18n.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_localize_question_english_and_chinese(quiz_db):
    from trading import quiz
    fake = lambda t: "译:" + t
    en = {"id": 1, "prompt": "What is a bond?", "options": ["debt", "equity"],
          "correct_index": 0, "explanation": "A bond is debt."}
    loc = quiz.localize_question(en, provider=fake)
    assert loc["is_english"] is True
    assert loc["prompt_zh"] == "译:What is a bond?"
    assert loc["options_zh"] == ["译:debt", "译:equity"]
    assert loc["explanation_zh"] == "译:A bond is debt."
    cn = {"id": 2, "prompt": "什么是债券？", "options": ["甲", "乙"], "correct_index": 0, "explanation": "甲"}
    loc2 = quiz.localize_question(cn, provider=fake)
    assert loc2["is_english"] is False
    assert "prompt_zh" not in loc2
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Append to `trading/quiz.py`**:
```python
def _is_english(text: str) -> bool:
    if not text or _has_cjk(text):
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    ascii_letters = [c for c in letters if ord(c) < 128]
    return len(ascii_letters) / len(letters) > 0.6


def localize_question(q: dict, provider=None) -> dict:
    """Attach Chinese fields when the question prompt is English."""
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
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**
```bash
git add trading/quiz.py trading/tests/test_quiz_i18n.py
git commit -m "feat(quiz): localize_question — attach zh fields for English questions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Endpoints return Chinese fields

**Files:** Modify `trading/app.py`; Test `trading/tests/test_quiz_i18n.py`

- [ ] **Step 1: Failing test** — append:
```python
def test_quiz_today_and_reveal_localized(client, monkeypatch):
    from trading import quiz
    monkeypatch.setattr(quiz, "_default_translate_provider", lambda t: "译:" + t)
    qid = quiz.add_question("What is a bond?", ["debt", "equity", "cash", "gold"], 0,
                            explanation="A bond is debt.", source="mmlu")
    client.post("/auth/login", json={"username": "icjj", "password": "pw"})
    t = client.get("/quiz/today").json()
    assert t["is_english"] is True
    assert t["prompt_zh"] == "译:What is a bond?" and t["options_zh"][0] == "译:debt"
    assert "correct_index" not in t                      # never leak the answer
    w = client.post("/quiz/answer", json={"question_id": qid, "choice_index": 1}).json()
    assert w["correct"] is False and w["explanation_zh"] == "译:A bond is debt."
```
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Edit `trading/app.py`** — replace the existing `quiz_today` endpoint body, and add localization to `quiz_answer`:
```python
@app.get("/quiz/today")
def quiz_today(user=Depends(current_user)):
    q = quiz.daily_question()
    if not q:
        return {"available": False}
    loc = quiz.localize_question(q)
    resp = {"available": True, "id": q["id"], "prompt": q["prompt"],
            "options": q["options"], "is_english": loc["is_english"]}
    if loc.get("is_english"):
        resp["prompt_zh"] = loc.get("prompt_zh")
        resp["options_zh"] = loc.get("options_zh")
    return resp
```
And in `quiz_answer`, after getting the result, localize the reveal:
```python
@app.post("/quiz/answer")
def quiz_answer(req: AnswerReq, user=Depends(current_user)):
    try:
        result = quiz.record_attempt(user["id"], req.question_id, req.choice_index)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not result["correct"] and result.get("explanation"):
        result["explanation_zh"] = quiz.translate_to_zh(result["explanation"])
    return result
```
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Full suite** — `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` (all green)
- [ ] **Step 6: Commit**
```bash
git add trading/app.py trading/tests/test_quiz_i18n.py
git commit -m "feat(quiz): /quiz/today + answer reveal return Chinese fields

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Quiz page — default Chinese + 双语 toggle

**Files:** Modify `app/quiz/page.js`

- [ ] **Step 1: Add a language state + use it.** READ `app/quiz/page.js`. Make these changes:
  1. Add state near the other `useState`s: `const [lang, setLang] = useState("zh");`
  2. Add helpers right before the `return (`:
```javascript
  const showZh = q.is_english && lang === "zh";
  const prompt = showZh && q.prompt_zh ? q.prompt_zh : q.prompt;
  const opts = showZh && q.options_zh ? q.options_zh : q.options;
```
  3. Replace `{q.prompt}` (the prompt `<div>`) with `{prompt}`, and change the options map from `q.options.map((opt, i) =>` to `opts.map((opt, i) =>`.
  4. In the wrong-answer reveal block, show the Chinese explanation by default — change `{result.explanation}` to `{lang === "zh" && result.explanation_zh ? result.explanation_zh : result.explanation}`.
  5. Add a toggle button, only for English questions, right after the prompt `<div>`:
```javascript
        {q.is_english && (
          <button className="refresh-btn" style={{ marginBottom: 10 }}
            onClick={() => setLang(lang === "zh" ? "en" : "zh")}>
            {lang === "zh" ? "🌐 看英文原文" : "🌐 看中文"}
          </button>
        )}
```

- [ ] **Step 2: Build** — `npm run build` → compiles; `/quiz` in the route table.

- [ ] **Step 3: Commit**
```bash
git add app/quiz/page.js
git commit -m "feat(quiz): bilingual quiz — Chinese default + 双语 toggle

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Localize board stat labels

**Files:** Modify `components/StockCard.js`

- [ ] **Step 1: Localize the four English labels.** READ `components/StockCard.js`. Replace:
  - `<span>Open</span>` → `<span>开盘</span>`
  - `<span>Prev</span>` → `<span>昨收</span>`
  - In the range labels, `L ${fmt(quote.low)}` → `最低 ${fmt(quote.low)}` and `H ${fmt(quote.high)}` → `最高 ${fmt(quote.high)}` (keep the `$`).
  Keep `quote.symbol` and `quote.name` (stock ticker + company name) exactly as-is — they're data, not UI labels.

- [ ] **Step 2: Build** — `npm run build` → compiles.

- [ ] **Step 3: Commit**
```bash
git add components/StockCard.js
git commit -m "feat(board): localize stat labels to Chinese (开盘/昨收/最低/最高)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Verification (whole plan)

- `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` → all green (translation uses a fake provider; no network in tests).
- `npm run build` clean.
- Manual (after deploy, logged in): on a day whose question is English, the gate shows it in Chinese with a "🌐 看英文原文" toggle; wrong answer shows the Chinese explanation; a Chinese (FinanceIQ) question shows no toggle. Board stat labels read 开盘/昨收/最低/最高.
- Live translation: first display of an English daily question calls the free `gtx` endpoint once and caches it (`translations` table); subsequent loads are instant.

## Notes

- Provider is swappable: replace `_default_translate_provider` with a DeepL/Google-Cloud call (+ key in `.env.trading`) if higher-quality/official translation is wanted later. Everything else (cache, localize, endpoints, UI) is unchanged.
- The weekly authoring task may author in Chinese directly (then `is_english` is false and no toggle shows) — no change needed here.
