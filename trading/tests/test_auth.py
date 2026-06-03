def test_init_db_creates_users_table(quiz_db):
    import sqlite3
    con = sqlite3.connect(quiz_db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    assert {"id", "username", "password_hash", "is_admin", "disabled", "created_at"} <= cols


def test_password_hash_roundtrip():
    from trading import auth
    h = auth.hash_password("s3cret!")
    assert h != "s3cret!"
    assert auth.verify_password(h, "s3cret!") is True
    assert auth.verify_password(h, "wrong") is False


def test_session_cookie_sign_verify_and_tamper(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "k")
    from trading import auth
    tok = auth.make_session("icjj")
    assert auth.read_session(tok) == "icjj"
    assert auth.read_session(tok + "x") is None
    assert auth.read_session("garbage") is None


def test_user_store(quiz_db):
    from trading import auth
    auth.create_user("alice", "pw1", is_admin=False)
    assert auth.get_user("alice")["username"] == "alice"
    assert auth.check_login("alice", "pw1") is True
    assert auth.check_login("alice", "bad") is False
    assert auth.check_login("nobody", "x") is False
    auth.set_disabled("alice", True)
    assert auth.check_login("alice", "pw1") is False


def test_list_users_excludes_password_hash(quiz_db):
    from trading import auth
    auth.create_user("alice", "pw1")
    rows = auth.list_users()
    assert rows and "password_hash" not in rows[0]


def test_session_rejected_under_different_secret(monkeypatch):
    from trading import auth
    monkeypatch.setenv("SESSION_SECRET", "secretA")
    tok = auth.make_session("icjj")
    monkeypatch.setenv("SESSION_SECRET", "secretB")
    assert auth.read_session(tok) is None


def test_get_user_excludes_password_hash(quiz_db):
    from trading import auth
    auth.create_user("bob", "pw")
    u = auth.get_user("bob")
    assert u and "password_hash" not in u


def test_login_sets_cookie_and_me(client):
    from trading import auth
    auth.create_user("bob", "pw", is_admin=False)
    r = client.post("/auth/login", json={"username": "bob", "password": "pw"})
    assert r.status_code == 200
    assert "sb_session" in r.cookies
    me = client.get("/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "bob"


def test_login_bad_password_401(client):
    from trading import auth
    auth.create_user("bob", "pw")
    r = client.post("/auth/login", json={"username": "bob", "password": "nope"})
    assert r.status_code == 401


def test_first_login_bootstraps_admin(client):
    r = client.post("/auth/login", json={"username": "icjj", "password": "chosen-pw"})
    assert r.status_code == 200 and r.json()["is_admin"] in (True, 1)


def test_unknown_user_rejected_after_bootstrap(client):
    client.post("/auth/login", json={"username": "icjj", "password": "chosen-pw"})  # bootstrap
    r = client.post("/auth/login", json={"username": "stranger", "password": "x"})
    assert r.status_code == 401  # non-first users must be admin-added


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
    client.post("/auth/login", json={"username": "dave", "password": "pw"})
    assert client.post("/auth/users", json={"username": "x", "password": "y"}).status_code == 403
