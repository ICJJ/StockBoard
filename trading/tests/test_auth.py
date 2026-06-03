def test_init_db_creates_users_table(quiz_db):
    import sqlite3
    con = sqlite3.connect(quiz_db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    assert {"id", "username", "password_hash", "is_admin", "disabled", "created_at"} <= cols
