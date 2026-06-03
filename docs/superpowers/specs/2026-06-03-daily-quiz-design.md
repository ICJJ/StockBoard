# StockBoard Daily Quiz — Design Spec

> Date: 2026-06-03 · Status: approved (design), pending implementation plan
> Authored via Superpowers brainstorming. Source of truth for the implementation plan.

## 1. Overview

Gate the StockBoard board behind a **daily capital-markets multiple-choice question** tied to a **per-user account system** with its **own scoring/leaderboard**. After login, a user must answer the day's question correctly to enter; a wrong answer reveals the correct answer + explanation and allows retry until correct. The question bank is professional-grade, seeded from a public verified dataset, periodically maintained by a scheduled Claude task, and self-curating via per-question user feedback.

## 2. Locked decisions

1. **Identity**: per-user accounts; `icjj` is admin; **allowlist only** (admin provisions accounts, no public signup); hashed passwords; persistent "remember me" sessions (no practical expiry).
2. **Storage/deployment**: FastAPI + **SQLite**, runs on the **funnel app** only. Vercel stays the Basic-Auth board mirror with quiz disabled.
3. **Question bank**: professional-grade; **seed = MMLU professional subsets** (MIT, verified answers); a **scheduled Claude task** updates/prunes; **per-question user feedback** ("too professional → keep/remove") drives pruning.
4. **Scoring**: **first-attempt** correctness scores; **streak** (consecutive days) + **cumulative** correct; **leaderboard** across accounts.
5. **Gate**: hard — must answer correctly to enter; wrong → reveal answer + retry; **one question/day, same for all users**.

## 3. Architecture

- **Frontend (Next.js, funnel + Vercel shared code)**: `/login`, daily quiz gate (`/quiz`), board (`/`), `/leaderboard`, `/admin` (admin only). New `lib/quizApi.js`. `middleware.js` updated to switch auth mode by env.
- **Backend (FastAPI, funnel only)**: new `trading/quiz.py` (models + logic), endpoints under `/auth/*` and `/quiz/*`, SQLite `trading/quiz.db`. One-time `trading/seed_questions.py`. Reached from Next via the existing `/api/trading/[...path]` proxy.
- **Scheduled maintenance**: a scheduled-tasks entry running Claude (weekly) to prune + top-up.
- **Env**: `QUIZ_ENABLED=1` (funnel only), `SESSION_SECRET` (HMAC key), `QUIZ_DB` path. On Vercel `QUIZ_ENABLED` is unset → Basic Auth path unchanged.

## 4. Data model (SQLite)

- `users(id, username UNIQUE, password_hash, is_admin BOOL, disabled BOOL, created_at)` — argon2 hash. `icjj` seeded admin.
- `questions(id, prompt, options_json, correct_index, explanation, subject, source ENUM(mmlu|admin|review), status ENUM(active|retired|pending_review), difficulty, created_at)`.
- `attempts(id, user_id, question_id, quiz_date, first_try_correct BOOL, entered BOOL, attempts_count, created_at)` — unique `(user_id, quiz_date)`.
- `question_feedback(id, user_id, question_id, vote ENUM(keep|remove), reason, created_at)` — unique `(user_id, question_id)`.

## 5. Auth & sessions

- **Login** `POST /auth/login {username,password}` → verify argon2 → set cookie `sb_session` = `base64(username|issued_at) + "." + HMAC_SHA256(secret, payload)`; flags: `HttpOnly; Secure; SameSite=Lax; Max-Age=315360000` (~10y = persistent). No plaintext password ever stored or returned.
- **Logout** `POST /auth/logout` clears cookie.
- **Admin** (requires admin session): `POST /auth/users {username,password,is_admin?}`, `PATCH /auth/users/{username} {disabled?,new_password?}`, `GET /auth/users`.
- **Edge middleware** (`middleware.js`): if `QUIZ_ENABLED` → read `sb_session`, verify HMAC (no DB) → if invalid/missing redirect `/login` (allow `/login`, `/_next`, static, and `/api/trading/auth/login`). Else (Vercel) → existing Basic Auth unchanged. **This replaces Basic Auth on the funnel.**
- Disabled accounts are rejected at login; the backend re-checks `disabled` on each `/auth`/`/quiz` call (cookie alone isn't trusted for disable).

## 6. Daily quiz flow

- **Selection** `GET /quiz/today` → deterministic pick from `status=active`: `index = sha256(quiz_date) % count`, ordered by `id`. `quiz_date` = current date in America/New_York (matches the board's market clock). Same question for everyone that day. Returns prompt+options+id (NOT correct_index).
- **State** `GET /quiz/state` → `{answered_today, entered_today}`. If `entered_today`, frontend skips the gate.
- **Submit** `POST /quiz/answer {question_id, choice_index}`:
  - Record/increment the day's `attempts` row. If this is the **first** attempt, set `first_try_correct = (choice==correct)`.
  - If correct (any attempt): set `entered=true`; respond `{correct:true, scored: first_try_correct}`.
  - If wrong: respond `{correct:false, correct_index, explanation}` and allow retry. `entered` stays false until a correct pick.
- **Feedback** `POST /quiz/feedback {question_id, vote, reason?}` — upsert one vote per user/question.
- **Fail-open**: if active pool is empty or backend errors, frontend treats the gate as passed (never lock out). Admin is never gated out (admin bypass flag).

## 7. Scoring & leaderboard

- **Points** = `count(attempts where first_try_correct)`.
- **Streak** = consecutive calendar days (ET) with an `entered` row, counting back from today (or yesterday if not yet played today).
- **Accuracy** = points / `count(distinct quiz_date entered)`.
- `GET /quiz/leaderboard` → list of `{username, points, streak, accuracy}` sorted by points desc, streak desc. Shown on board header + `/leaderboard`.

## 8. Question bank & self-curation

- **Seed** (`seed_questions.py`, one-time): import MMLU professional/finance subsets — `professional_accounting`, `high_school_macroeconomics`, `high_school_microeconomics`, `econometrics` (via HF `datasets`/parquet). Map to schema, `source=mmlu`, `status=active`. De-dupe.
- **User feedback**: "too professional" → `keep`/`remove` vote (one per user/question).
- **Scheduled Claude task** (scheduled-tasks SKILL.md, weekly):
  1. **Prune**: retire (`status=retired`) questions where `remove_votes ≥ 3 AND remove_votes > keep_votes`.
  2. **Top-up**: if active pool `< 60`, import more verified questions from the professional source to refill.
  3. Any LLM-*drafted* novel capital-markets questions are inserted as `status=pending_review` — **never auto-active**; `icjj` approves them in `/admin`. This honors the "LLM 可能出错" constraint: only verified-source questions go live automatically.

## 9. Error handling & security

- Empty pool / backend down → fail-open (board accessible); never self-lock.
- Wrong password / disabled account → 401 with clear message; admin un-lockoutable.
- Passwords: argon2 hashing; never logged/returned. Session cookie: HMAC-signed, HttpOnly, Secure, SameSite=Lax.
- Admin-only mutations enforced server-side (not just UI).
- Quiz DB (`quiz.db`) is gitignored.

## 10. Testing (TDD)

Backend pytest: argon2 hash/verify; allowlist + disabled rejection; HMAC cookie sign/verify (tamper rejected); deterministic daily selection (same date → same id; stable across calls); first-try scoring (retry-after-reveal earns 0); streak math (gap breaks streak); pruning threshold; fail-open on empty pool. Frontend: unauthenticated redirect to `/login`; gate retry reveals answer; `entered_today` skips gate.

## 11. Out of scope (YAGNI)

Public signup; email/password reset flows; OAuth; per-user question randomization; multi-question/day; categories/difficulty selection by user; quiz on the Vercel deployment.

## 12. Defaulted sub-choices (changeable)

Same-question-for-all (not per-user); streak = days-entered (not days-first-try-correct); prune threshold ≥3 votes & remove>keep; active-pool floor = 60; weekly schedule.
