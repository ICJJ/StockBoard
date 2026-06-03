# Daily Quiz — Plan 1: Accounts & Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the funnel app's shared HTTP Basic Auth with a real per-user account system (admin-provisioned allowlist, hashed passwords, persistent signed-cookie sessions), so each user logs in with their own account.

**Architecture:** FastAPI + SQLite store users; login issues an HMAC-signed persistent cookie (`sb_session`); Next.js edge middleware verifies that cookie when `QUIZ_ENABLED=1` (funnel) and otherwise keeps Basic Auth (Vercel). The `/api/trading` proxy forwards cookies both ways. Admin (`icjj`) manages accounts via `/admin`.

**Tech Stack:** Python 3.9, FastAPI, SQLite (stdlib `sqlite3`), `argon2-cffi` (password hashing), stdlib `hmac`/`hashlib` (cookie signing), pytest + httpx (tests); Next.js middleware (Web Crypto HMAC), React pages.

**Spec:** `docs/superpowers/specs/2026-06-03-daily-quiz-design.md` (§2.1, §4 `users`, §5).

---

## File Structure

- `trading/requirements-quiz.txt` — Create: pin new deps (argon2-cffi, pytest, httpx).
- `trading/quiz_db.py` — Create: SQLite connection + schema init (this plan: `users` table). One responsibility: DB access/migrations.
- `trading/auth.py` — Create: pure auth logic — password hashing, cookie sign/verify, user-store CRUD. No FastAPI here (easy to unit-test).
- `trading/app.py` — Modify: mount auth router/endpoints; seed admin on startup.
- `trading/tests/__init__.py`, `trading/tests/conftest.py` — Create: pytest fixtures (temp DB + TestClient).
- `trading/tests/test_auth.py` — Create: unit + endpoint tests.
- `app/api/trading/[...path]/route.js` — Modify: forward `Cookie` (request) and `Set-Cookie` (response).
- `middleware.js` — Modify: when `QUIZ_ENABLED`, verify `sb_session` (Web Crypto HMAC) → redirect `/login` if absent/invalid; else existing Basic Auth.
- `app/login/page.js` — Create: login form.
- `app/admin/page.js` — Create: admin user-management UI.
- `lib/quizApi.js` — Create: client fetch helpers for auth/admin.
- `.gitignore` — Modify: ignore `trading/quiz.db`.

---

### Task 1: Backend deps + test scaffolding

**Files:**
- Create: `trading/requirements-quiz.txt`
- Create: `trading/tests/__init__.py` (empty)
- Create: `trading/tests/conftest.py`
- Create: `trading/tests/test_smoke.py`

- [ ] **Step 1: Write requirements file**

`trading/requirements-quiz.txt`:
```
argon2-cffi==23.1.0
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: Install into the backend venv**

Run: `./.venv-trading/bin/pip install -r trading/requirements-quiz.txt`
Expected: "Successfully installed argon2-cffi… pytest… httpx…"

- [ ] **Step 3: Create empty package marker**

`trading/tests/__init__.py`: (empty file)

- [ ] **Step 4: Write conftest (temp DB + client fixtures)**

`trading/tests/conftest.py`:
```python
import os
import pytest


@pytest.fixture()
def quiz_db(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite file for each test."""
    db = tmp_path / "quiz.db"
    monkeypatch.setenv("QUIZ_DB", str(db))
    monkeypatch.setenv("SESSION_SECRET", "test-secret-please-change")
    # import lazily so env is set before module import
    import importlib
    from trading import quiz_db as qdb
    importlib.reload(qdb)
    qdb.init_db()
    return db


@pytest.fixture()
def client(quiz_db):
    from fastapi.testclient import TestClient
    from trading import app as appmod
    import importlib
    importlib.reload(appmod)
    return TestClient(appmod.app)
```

- [ ] **Step 5: Write a smoke test for the existing /health**

`trading/tests/test_smoke.py`:
```python
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
```

- [ ] **Step 6: Run smoke test (will fail until quiz_db exists)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_smoke.py -v`
Expected: FAIL (ImportError: no module named `trading.quiz_db`) — proves the fixture wiring runs. (Fixed in Task 2.)

- [ ] **Step 7: Commit**

```bash
git add trading/requirements-quiz.txt trading/tests/
git commit -m "test: scaffold pytest for trading backend (temp-DB + TestClient fixtures)"
```

---

### Task 2: SQLite schema (`users`)

**Files:**
- Create: `trading/quiz_db.py`
- Modify: `.gitignore`
- Test: `trading/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

`trading/tests/test_auth.py`:
```python
def test_init_db_creates_users_table(quiz_db):
    import sqlite3
    con = sqlite3.connect(quiz_db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    assert {"id", "username", "password_hash", "is_admin", "disabled", "created_at"} <= cols
```

- [ ] **Step 2: Run it (fails: no module)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py::test_init_db_creates_users_table -v`
Expected: FAIL — `ModuleNotFoundError: trading.quiz_db`.

- [ ] **Step 3: Implement quiz_db.py**

`trading/quiz_db.py`:
```python
"""SQLite store for the quiz feature. Path from QUIZ_DB env (default trading/quiz.db)."""
import os
import sqlite3
import pathlib

_DEFAULT = pathlib.Path(__file__).with_name("quiz.db")


def db_path() -> str:
    return os.environ.get("QUIZ_DB", str(_DEFAULT))


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    disabled      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    con = connect()
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py::test_init_db_creates_users_table -v`
Expected: PASS.

- [ ] **Step 5: Gitignore the live DB**

Append to `.gitignore`:
```
# Quiz SQLite DB (local data, never commit)
trading/quiz.db
```

- [ ] **Step 6: Commit**

```bash
git add trading/quiz_db.py trading/tests/test_auth.py .gitignore
git commit -m "feat(quiz): SQLite users schema + connection helper"
```

---

### Task 3: Password hashing (argon2)

**Files:**
- Create: `trading/auth.py`
- Test: `trading/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Append to `trading/tests/test_auth.py`:
```python
def test_password_hash_roundtrip():
    from trading import auth
    h = auth.hash_password("s3cret!")
    assert h != "s3cret!"
    assert auth.verify_password(h, "s3cret!") is True
    assert auth.verify_password(h, "wrong") is False
```

- [ ] **Step 2: Run it (fails: no module/attr)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py::test_password_hash_roundtrip -v`
Expected: FAIL — `ModuleNotFoundError: trading.auth`.

- [ ] **Step 3: Implement hashing in auth.py**

`trading/auth.py`:
```python
"""Auth primitives: password hashing, signed-cookie sessions, user store."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py::test_password_hash_roundtrip -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add trading/auth.py trading/tests/test_auth.py
git commit -m "feat(quiz): argon2 password hashing"
```

---

### Task 4: Signed session cookies (stdlib HMAC)

**Files:**
- Modify: `trading/auth.py`
- Test: `trading/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Append to `trading/tests/test_auth.py`:
```python
def test_session_cookie_sign_verify_and_tamper(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "k")
    from trading import auth
    tok = auth.make_session("icjj")
    assert auth.read_session(tok) == "icjj"
    assert auth.read_session(tok + "x") is None          # tampered sig
    assert auth.read_session("garbage") is None           # malformed
```

- [ ] **Step 2: Run it (fails)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py::test_session_cookie_sign_verify_and_tamper -v`
Expected: FAIL — `AttributeError: make_session`.

- [ ] **Step 3: Implement session sign/verify (must match the JS middleware in Task 8)**

Append to `trading/auth.py`:
```python
import base64
import hashlib
import hmac
import os


def _secret() -> bytes:
    return os.environ.get("SESSION_SECRET", "").encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_session(username: str) -> str:
    payload = _b64(username.encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_session(token: str) -> str | None:
    try:
        payload, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return _unb64(payload).decode()
    except Exception:
        return None
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py::test_session_cookie_sign_verify_and_tamper -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add trading/auth.py trading/tests/test_auth.py
git commit -m "feat(quiz): HMAC-signed session tokens (stdlib)"
```

---

### Task 5: User store (create / get / verify-login / set-disabled)

**Files:**
- Modify: `trading/auth.py`
- Test: `trading/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Append to `trading/tests/test_auth.py`:
```python
def test_user_store(quiz_db):
    from trading import auth, quiz_db as qdb
    auth.create_user("alice", "pw1", is_admin=False)
    assert auth.get_user("alice")["username"] == "alice"
    assert auth.check_login("alice", "pw1") is True
    assert auth.check_login("alice", "bad") is False
    assert auth.check_login("nobody", "x") is False
    auth.set_disabled("alice", True)
    assert auth.check_login("alice", "pw1") is False   # disabled rejected
```

- [ ] **Step 2: Run it (fails)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py::test_user_store -v`
Expected: FAIL — `AttributeError: create_user`.

- [ ] **Step 3: Implement user store**

Append to `trading/auth.py`:
```python
from . import quiz_db


def create_user(username: str, password: str, is_admin: bool = False) -> None:
    con = quiz_db.connect()
    try:
        con.execute(
            "INSERT INTO users(username, password_hash, is_admin) VALUES (?,?,?)",
            (username, hash_password(password), 1 if is_admin else 0),
        )
        con.commit()
    finally:
        con.close()


def get_user(username: str):
    con = quiz_db.connect()
    try:
        row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def check_login(username: str, password: str) -> bool:
    u = get_user(username)
    if not u or u["disabled"]:
        return False
    return verify_password(u["password_hash"], password)


def set_disabled(username: str, disabled: bool) -> None:
    con = quiz_db.connect()
    try:
        con.execute("UPDATE users SET disabled=? WHERE username=?", (1 if disabled else 0, username))
        con.commit()
    finally:
        con.close()


def list_users() -> list[dict]:
    con = quiz_db.connect()
    try:
        return [dict(r) for r in con.execute(
            "SELECT username, is_admin, disabled, created_at FROM users ORDER BY username")]
    finally:
        con.close()
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py::test_user_store -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add trading/auth.py trading/tests/test_auth.py
git commit -m "feat(quiz): user store (create/get/check-login/disable/list)"
```

---

### Task 6: Auth endpoints (login/logout/me) + admin seed

**Files:**
- Modify: `trading/app.py`
- Test: `trading/tests/test_auth.py`

- [ ] **Step 1: Add ADMIN_INIT_PASSWORD to the conftest fixture**

In `trading/tests/conftest.py`, inside the `quiz_db` fixture, right after the `SESSION_SECRET` line, add:
```python
    monkeypatch.setenv("ADMIN_INIT_PASSWORD", "adminpw")
```

- [ ] **Step 2: Write the failing tests**

Append to `trading/tests/test_auth.py`:
```python
def test_login_sets_cookie_and_me(client):
    from trading import auth
    auth.create_user("bob", "pw", is_admin=False)
    r = client.post("/auth/login", json={"username": "bob", "password": "pw"})
    assert r.status_code == 200
    assert "sb_session" in r.cookies
    me = client.get("/auth/me")           # client persists cookie
    assert me.status_code == 200 and me.json()["username"] == "bob"


def test_login_bad_password_401(client):
    from trading import auth
    auth.create_user("bob", "pw")
    r = client.post("/auth/login", json={"username": "bob", "password": "nope"})
    assert r.status_code == 401


def test_admin_icjj_seeded(client):
    r = client.post("/auth/login", json={"username": "icjj", "password": "adminpw"})
    assert r.status_code == 200 and r.json().get("is_admin") in (True, 1)
```

- [ ] **Step 3: Run it (fails)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py -k "login or seeded" -v`
Expected: FAIL — 404 (no /auth routes).

- [ ] **Step 4: Implement endpoints + startup seed in app.py**

Add near the imports in `trading/app.py`:
```python
from fastapi import Response, Request, Cookie
from . import auth, quiz_db

quiz_db.init_db()

# Seed admin icjj once, if ADMIN_INIT_PASSWORD is set and icjj is absent.
_admin_pw = os.environ.get("ADMIN_INIT_PASSWORD")
if _admin_pw and not auth.get_user("icjj"):
    auth.create_user("icjj", _admin_pw, is_admin=True)

_COOKIE = "sb_session"
_COOKIE_KW = dict(httponly=True, samesite="lax", secure=True, max_age=315360000, path="/")


class LoginReq(BaseModel):
    username: str
    password: str


def current_user(sb_session: str = Cookie(default="")):
    username = auth.read_session(sb_session)
    if not username:
        raise HTTPException(401, "not logged in")
    u = auth.get_user(username)
    if not u or u["disabled"]:
        raise HTTPException(401, "account unavailable")
    return u


def require_admin(user=Depends(current_user)):
    if not user["is_admin"]:
        raise HTTPException(403, "admin only")
    return user


@app.post("/auth/login")
def login(req: LoginReq, response: Response):
    if not auth.check_login(req.username, req.password):
        raise HTTPException(401, "invalid credentials")
    response.set_cookie(_COOKIE, auth.make_session(req.username), **_COOKIE_KW)
    u = auth.get_user(req.username)
    return {"username": u["username"], "is_admin": bool(u["is_admin"])}


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(_COOKIE, path="/")
    return {"ok": True}


@app.get("/auth/me")
def me(user=Depends(current_user)):
    return {"username": user["username"], "is_admin": bool(user["is_admin"])}
```

- [ ] **Step 5: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py -k "login or seeded" -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add trading/app.py trading/tests/test_auth.py trading/tests/conftest.py
git commit -m "feat(quiz): /auth login/logout/me endpoints + icjj admin seed"
```

---

### Task 7: Admin user-management endpoints

**Files:**
- Modify: `trading/app.py`
- Test: `trading/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Append to `trading/tests/test_auth.py`:
```python
def test_admin_can_add_and_disable_users(client):
    client.post("/auth/login", json={"username": "icjj", "password": "adminpw"})
    r = client.post("/auth/users", json={"username": "carol", "password": "pw"})
    assert r.status_code == 200
    assert any(u["username"] == "carol" for u in client.get("/auth/users").json()["users"])
    assert client.patch("/auth/users/carol", json={"disabled": True}).status_code == 200


def test_non_admin_cannot_add_users(client):
    from trading import auth
    auth.create_user("dave", "pw")
    client.post("/auth/login", json={"username": "dave", "password": "pw"})
    assert client.post("/auth/users", json={"username": "x", "password": "y"}).status_code == 403
```

- [ ] **Step 2: Run it (fails)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py -k admin -v`
Expected: FAIL — 404 on `/auth/users`.

- [ ] **Step 3: Implement admin endpoints in app.py**

Append to `trading/app.py`:
```python
class NewUserReq(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class PatchUserReq(BaseModel):
    disabled: Optional[bool] = None
    new_password: Optional[str] = None


@app.get("/auth/users")
def admin_list_users(_=Depends(require_admin)):
    return {"users": auth.list_users()}


@app.post("/auth/users")
def admin_add_user(req: NewUserReq, _=Depends(require_admin)):
    if auth.get_user(req.username):
        raise HTTPException(409, "user exists")
    auth.create_user(req.username, req.password, req.is_admin)
    return {"ok": True}


@app.patch("/auth/users/{username}")
def admin_patch_user(username: str, req: PatchUserReq, _=Depends(require_admin)):
    if not auth.get_user(username):
        raise HTTPException(404, "no such user")
    if req.disabled is not None:
        auth.set_disabled(username, req.disabled)
    if req.new_password:
        auth.set_password(username, req.new_password)
    return {"ok": True}
```

And add `set_password` to `trading/auth.py`:
```python
def set_password(username: str, password: str) -> None:
    con = quiz_db.connect()
    try:
        con.execute("UPDATE users SET password_hash=? WHERE username=?",
                    (hash_password(password), username))
        con.commit()
    finally:
        con.close()
```

- [ ] **Step 4: Run it (passes)**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/test_auth.py -k admin -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full backend suite**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add trading/app.py trading/auth.py trading/tests/test_auth.py
git commit -m "feat(quiz): admin user-management endpoints (add/list/disable/reset)"
```

---

### Task 8: Proxy forwards cookies

**Files:**
- Modify: `app/api/trading/[...path]/route.js`

**Why:** the browser talks to the backend only through this same-origin proxy. For `Set-Cookie` (login) and `Cookie` (auth) to work, the proxy must forward both headers.

- [ ] **Step 1: Read the current proxy**

Run: `cat "app/api/trading/[...path]/route.js"`
Note how it builds the upstream request/response (method, headers, body).

- [ ] **Step 2: Forward Cookie up and Set-Cookie back**

Ensure the handler (a) copies the incoming `cookie` header onto the upstream fetch, and (b) copies upstream `set-cookie` onto the response. Concretely, when constructing upstream headers include:
```js
const headers = { "content-type": req.headers.get("content-type") || "application/json" };
const cookie = req.headers.get("cookie");
if (cookie) headers["cookie"] = cookie;
```
and when returning, propagate Set-Cookie:
```js
const res = new NextResponse(bodyText, { status: upstream.status });
const setCookie = upstream.headers.get("set-cookie");
if (setCookie) res.headers.set("set-cookie", setCookie);
res.headers.set("content-type", upstream.headers.get("content-type") || "application/json");
return res;
```
(Match the file's existing style; keep the existing token/header logic.)

- [ ] **Step 3: Manual verify (after backend running with SESSION_SECRET + ADMIN_INIT_PASSWORD)**

Run:
```bash
export SESSION_SECRET=devsecret ADMIN_INIT_PASSWORD=adminpw QUIZ_ENABLED=1
# start backend + next (or use start-stockboard.sh), then:
curl -s -i -X POST http://localhost:3000/api/trading/auth/login \
  -H 'content-type: application/json' -d '{"username":"icjj","password":"adminpw"}' | grep -i set-cookie
```
Expected: a `set-cookie: sb_session=…` line is present.

- [ ] **Step 4: Commit**

```bash
git add "app/api/trading/[...path]/route.js"
git commit -m "feat(quiz): proxy forwards Cookie/Set-Cookie for session auth"
```

---

### Task 9: Middleware — session auth when QUIZ_ENABLED (edge HMAC verify)

**Files:**
- Modify: `middleware.js`

- [ ] **Step 1: Replace middleware with env-switched auth**

`middleware.js`:
```javascript
import { NextResponse } from "next/server";

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };

const enc = new TextEncoder();

async function validSession(token, secret) {
  if (!token || !token.includes(".")) return false;
  const [payload, sig] = token.split(".", 2);
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
  const b64 = btoa(String.fromCharCode(...new Uint8Array(mac)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return b64 === sig;
}

export async function middleware(req) {
  const { pathname } = req.nextUrl;

  // Session-auth mode (funnel)
  if (process.env.QUIZ_ENABLED === "1") {
    if (pathname.startsWith("/login") ||
        pathname.startsWith("/api/trading/auth/login")) {
      return NextResponse.next();
    }
    const token = req.cookies.get("sb_session")?.value;
    if (await validSession(token, process.env.SESSION_SECRET || "")) {
      return NextResponse.next();
    }
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // Basic Auth mode (Vercel) — unchanged
  const user = process.env.BASIC_AUTH_USER;
  const pass = process.env.BASIC_AUTH_PASSWORD;
  if (!user || !pass) return NextResponse.next();
  const header = req.headers.get("authorization");
  if (header) {
    const [scheme, encoded] = header.split(" ");
    if (scheme === "Basic" && encoded) {
      const decoded = atob(encoded);
      const i = decoded.indexOf(":");
      if (decoded.slice(0, i) === user && decoded.slice(i + 1) === pass) {
        return NextResponse.next();
      }
    }
  }
  return new NextResponse("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="StockBoard", charset="UTF-8"' },
  });
}
```

- [ ] **Step 2: Manual verify**

With backend+next running (`QUIZ_ENABLED=1`, `SESSION_SECRET=devsecret`):
```bash
curl -s -o /dev/null -w "no-cookie: %{http_code}\n" -L http://localhost:3000/   # expect 200 at /login (redirected)
# capture a real cookie then re-request with it:
C=$(curl -s -i -X POST http://localhost:3000/api/trading/auth/login -H 'content-type: application/json' -d '{"username":"icjj","password":"adminpw"}' | sed -n 's/.*sb_session=\([^;]*\).*/\1/p')
curl -s -o /dev/null -w "with-cookie /: %{http_code}\n" --cookie "sb_session=$C" http://localhost:3000/
```
Expected: without cookie you land on `/login`; with a valid cookie `/` returns 200.

- [ ] **Step 3: Commit**

```bash
git add middleware.js
git commit -m "feat(quiz): middleware session auth (QUIZ_ENABLED) replacing Basic Auth on funnel"
```

---

### Task 10: `/login` page

**Files:**
- Create: `lib/quizApi.js`
- Create: `app/login/page.js`

- [ ] **Step 1: Client helpers**

`lib/quizApi.js`:
```javascript
const base = "/api/trading";
async function j(path, opts = {}) {
  const r = await fetch(base + path, {
    headers: { "content-type": "application/json" }, ...opts,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}
export const quizApi = {
  login: (username, password) =>
    j("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => j("/auth/logout", { method: "POST" }),
  me: () => j("/auth/me"),
  listUsers: () => j("/auth/users"),
  addUser: (b) => j("/auth/users", { method: "POST", body: JSON.stringify(b) }),
  patchUser: (u, b) => j(`/auth/users/${u}`, { method: "PATCH", body: JSON.stringify(b) }),
};
```

- [ ] **Step 2: Login page**

`app/login/page.js`:
```javascript
"use client";
import { useState } from "react";
import { quizApi } from "../../lib/quizApi";

export default function Login() {
  const [u, setU] = useState(""); const [p, setP] = useState("");
  const [err, setErr] = useState(null); const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await quizApi.login(u, p); window.location.href = "/"; }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div className="container" style={{ maxWidth: 360 }}>
      <h1 style={{ margin: "40px 0 20px" }}>StockBoard 登录</h1>
      <form onSubmit={submit} className="bt-panel">
        <label className="bt-field"><span>账号</span>
          <input className="search-input" value={u} onChange={(e) => setU(e.target.value)} /></label>
        <label className="bt-field"><span>密码</span>
          <input className="search-input" type="password" value={p} onChange={(e) => setP(e.target.value)} /></label>
        <button className="bt-run" disabled={busy}>{busy ? "…" : "登录"}</button>
        {err && <div className="notice error">{err}</div>}
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Manual verify**

Visit `http://localhost:3000/` without a cookie → redirected to `/login`; submit `icjj`/`adminpw` → lands on the board.

- [ ] **Step 4: Commit**

```bash
git add lib/quizApi.js app/login/page.js
git commit -m "feat(quiz): /login page + auth client helpers"
```

---

### Task 11: `/admin` user management UI

**Files:**
- Create: `app/admin/page.js`

- [ ] **Step 1: Admin page**

`app/admin/page.js`:
```javascript
"use client";
import { useEffect, useState } from "react";
import { quizApi } from "../../lib/quizApi";

export default function Admin() {
  const [users, setUsers] = useState([]); const [err, setErr] = useState(null);
  const [nu, setNu] = useState(""); const [np, setNp] = useState("");
  async function load() {
    try { setUsers((await quizApi.listUsers()).users); }
    catch (e) { setErr(e.message); }
  }
  useEffect(() => { load(); }, []);
  async function add(e) {
    e.preventDefault();
    try { await quizApi.addUser({ username: nu, password: np }); setNu(""); setNp(""); load(); }
    catch (e) { setErr(e.message); }
  }
  async function toggle(u, disabled) { await quizApi.patchUser(u, { disabled }); load(); }
  return (
    <div className="container" style={{ maxWidth: 560 }}>
      <h1 style={{ margin: "30px 0 16px" }}>账号管理（管理员）</h1>
      {err && <div className="notice error">{err}</div>}
      <form onSubmit={add} className="order-form">
        <input className="search-input" placeholder="新账号" value={nu} onChange={(e) => setNu(e.target.value)} />
        <input className="search-input" placeholder="密码" type="password" value={np} onChange={(e) => setNp(e.target.value)} />
        <button className="bt-run" style={{ maxWidth: 120 }}>添加</button>
      </form>
      <table className="ptable" style={{ marginTop: 16 }}>
        <thead><tr><th>账号</th><th>管理员</th><th>状态</th><th></th></tr></thead>
        <tbody>{users.map((u) => (
          <tr key={u.username}>
            <td className="psym">{u.username}</td>
            <td>{u.is_admin ? "✓" : ""}</td>
            <td>{u.disabled ? "已停用" : "正常"}</td>
            <td><button className="refresh-btn" onClick={() => toggle(u.username, !u.disabled)}>
              {u.disabled ? "启用" : "停用"}</button></td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Manual verify**

Logged in as `icjj`, visit `/admin` → add a user `test`/`pw` → appears in the table → toggle disable → re-login as `test` fails when disabled, works when enabled.

- [ ] **Step 3: Commit**

```bash
git add app/admin/page.js
git commit -m "feat(quiz): /admin user-management UI"
```

---

### Task 12: Wire env + full local verification

**Files:**
- Modify: `.env.trading.example`, `start-stockboard.sh` (env), `com.stockboard.trading.plist` (env)

- [ ] **Step 1: Document new env in `.env.trading.example`**

Append:
```
# Quiz feature (funnel only)
QUIZ_ENABLED=1
SESSION_SECRET=change-me-to-a-long-random-string
ADMIN_INIT_PASSWORD=set-once-then-remove
```

- [ ] **Step 2: Ensure the backend gets SESSION_SECRET + ADMIN_INIT_PASSWORD + QUIZ_DB**

The start script already `set -a; . .env.trading; set +a` — so vars flow to both `npm start` (needs `QUIZ_ENABLED`, `SESSION_SECRET`) and uvicorn (needs `SESSION_SECRET`, `ADMIN_INIT_PASSWORD`, `QUIZ_DB`). No code change if `.env.trading` holds them. Verify by printing inside the script run (`echo "QUIZ_ENABLED=$QUIZ_ENABLED"`), then remove the echo.

- [ ] **Step 3: Full manual end-to-end**

```bash
# .env.trading has QUIZ_ENABLED=1, SESSION_SECRET, ADMIN_INIT_PASSWORD, BASIC_AUTH_* (still used by Vercel)
./start-stockboard.sh
# 1) visit / → redirected to /login
# 2) login icjj/<ADMIN_INIT_PASSWORD> → board
# 3) /admin → add a user → that user can log in
# 4) restart browser → still logged in (persistent cookie)
```
Expected: all four behaviors hold.

- [ ] **Step 4: Run full backend test suite once more**

Run: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit + push**

```bash
git add .env.trading.example
git commit -m "feat(quiz): document quiz env (QUIZ_ENABLED/SESSION_SECRET/ADMIN_INIT_PASSWORD)"
git push origin main
```

---

## Verification (whole plan)

- Backend: `PYTHONPATH=. ./.venv-trading/bin/pytest trading/tests/ -v` → all green.
- Funnel: no cookie → `/login`; valid login → board; persistent across browser restart; disabled account rejected; non-admin blocked from `/auth/users`.
- Vercel (QUIZ_ENABLED unset): Basic Auth still works (unchanged).

## Notes for later plans

- Plan 2 (bank/seed) adds `questions` + `question_feedback` tables to `trading/quiz_db.py` `SCHEMA` and a `seed_questions.py`.
- Plan 3 (gate/scoring) adds `attempts` + `/quiz/*` endpoints and reuses `current_user` from Task 6.
- Plan 4 (scheduled task) reuses the feedback table + a scheduled-tasks SKILL.md.
