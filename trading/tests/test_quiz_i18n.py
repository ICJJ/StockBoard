"""Tests for Plan 6: bilingual backend (i18n)."""
import pytest


def test_schema_has_translations(quiz_db):
    import sqlite3
    cols = {r[1] for r in sqlite3.connect(quiz_db).execute("PRAGMA table_info(translations)")}
    assert {"en", "zh"} <= cols
