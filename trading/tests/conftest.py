import os
import pytest


@pytest.fixture()
def quiz_db(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite file for each test."""
    db = tmp_path / "quiz.db"
    monkeypatch.setenv("QUIZ_DB", str(db))
    monkeypatch.setenv("SESSION_SECRET", "test-secret-please-change")
    monkeypatch.setenv("COOKIE_SECURE", "0")
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
